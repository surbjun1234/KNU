import requests
from bs4 import BeautifulSoup
import os
import openai
import urllib3

# SSL 경고 무시 설정 (경북대 서버 특성상 필요할 수 있음)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------
# 환경변수 세팅
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# URL 설정
MAIN_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/btin/stdList.action?menu_idx=42"
LAST_ID_FILE = "last_id.txt"

# --------------------------------------
def fetch_latest_notice():
    # 1. 세션 생성 (쿠키 유지를 위해 필수)
    session = requests.Session()
    
    # 2. 진짜 사람처럼 보이는 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.knu.ac.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        print("Bot: 경북대 메인 페이지 접속 시도 (쿠키 획득)...")
        # [핵심] 메인 페이지를 먼저 찔러서 세션 쿠키를 받아냄
        session.get(MAIN_URL, headers=headers, verify=False, timeout=10)
        
        print("Bot: 학사공지 게시판 접속 시도...")
        # [핵심] 그 쿠키를 들고 게시판으로 이동
        res = session.get(NOTICE_URL, headers=headers, verify=False, timeout=10)
        res.raise_for_status()
        res.encoding = 'utf-8' # 한글 깨짐 방지
        
    except Exception as e:
        print(f"❌ 접속 오류 발생: {e}")
        return None

    # HTML 파싱
    soup = BeautifulSoup(res.text, "html.parser")

    # 게시글 행 찾기 (여러 패턴 시도)
    rows = soup.select("tbody tr")
    if not rows:
        rows = soup.select(".board_list tbody tr")
    
    if not rows:
        print("❌ 게시판 구조를 찾지 못했습니다.")
        # 디버깅: 혹시 차단당했으면 페이지 제목이라도 출력
        print(f"현재 페이지 제목: {soup.title.string if soup.title else '제목없음'}")
        return None

    # 최신글 찾기
    latest_notice = None
    for row in rows:
        subject_td = row.select_one("td.subject a") or row.select_one("td.title a")
        
        # 번호 확인 (공지 배지 걸러내기)
        num_td = row.select_one("td.num")
        # 번호가 없거나 숫자가 아니면(예: '공지') 건너뜀
        if num_td and not num_td.get_text(strip=True).isdigit():
            continue

        if not subject_td:
            continue
            
        title = subject_td.get_text(strip=True)
        href = subject_td.get("href")
        
        # 링크/ID 추출
        post_id = None
        full_url = NOTICE_URL
        
        if href:
            if "btin_idx=" in href:
                post_id = href.split("btin_idx=")[1].split("&")[0]
                full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?btin_idx={post_id}&menu_idx=42"
            elif "nttId=" in href:
                post_id = href.split("nttId=")[1].split("&")[0]
                full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?nttId={post_id}&menu_idx=42"
        
        if not post_id:
            post_id = title

        latest_notice = {"id": post_id, "title": title, "url": full_url}
        break # 가장 최신글 1개만 잡고 종료

    return latest_notice

# --------------------------------------
def summarize_text(title):
    if not OPENAI_API_KEY:
        return title
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "너는 대학교 학사공지 요약 봇이야."},
                {"role": "user", "content": f"이 제목을 보고 핵심 내용을 한 문장으로 요약해줘: {title}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ 요약 API 에러: {e}")
        return title

# --------------------------------------
def send_discord(notice, summary):
    if not DISCORD_WEBHOOK:
        print("❌ Discord Webhook 없음")
        return

    message = f"📢 **[경북대 학사공지]**\n{notice['title']}\n\n📝 **요약**: {summary}\n🔗 [바로가기]({notice['url']})"
    
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
        print("✅ Discord 전송 성공")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

# --------------------------------------
def main():
    print("✅ 봇 실행 시작 (v3.0)")
    
    latest = fetch_latest_notice()
    if not latest:
        print("❌ 공지사항을 가져오는데 실패했습니다.")
        return

    last_id = ""
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r", encoding='utf-8') as f:
            last_id = f.read().strip()

    print(f"🔍 가져온 최신글: {latest['title']}")
    
    if latest["id"] == last_id:
        print("👌 새로운 공지가 없습니다. (ID 일치)")
        return

    print("🚀 새 공지 발견! 디스코드로 전송합니다...")
    summary = summarize_text(latest['title'])
    send_discord(latest, summary)

    with open(LAST_ID_FILE, "w", encoding='utf-8') as f:
        f.write(latest["id"])

if __name__ == "__main__":
    main()
