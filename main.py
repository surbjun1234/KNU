import requests
from bs4 import BeautifulSoup
import os
import openai

# --------------------------------------
# 환경변수 세팅
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 게시판 URL
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/btin/stdList.action?menu_idx=42"
LAST_ID_FILE = "last_id.txt"

# --------------------------------------
# 공지 가져오기 (수정된 부분)
def fetch_latest_notice():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        res = requests.get(NOTICE_URL, headers=headers, timeout=15)
        res.raise_for_status() # 404, 500 에러 체크
    except Exception as e:
        print(f"❌ 접속 오류: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # [수정 포인트] 선택자 범위를 넓혀서 확실하게 잡도록 변경
    # 전략 1: 표준적인 tbody 안의 tr 태그 검색
    rows = soup.select("tbody tr")
    
    # 전략 2: 만약 못 찾았으면 board_list 클래스 검색
    if not rows:
        rows = soup.select(".board_list tr")

    if not rows:
        print("❌ 게시물 행(tr)을 찾을 수 없습니다.")
        # 디버깅을 위해 HTML 앞부분만 출력해봄 (로그에서 확인 가능)
        print("HTML 일부:", soup.text[:200].strip()) 
        return None

    # 최신 공지 찾기 (공지사항 배지 제외)
    latest_notice = None
    
    for row in rows:
        # 제목 칸 찾기
        subject_td = row.select_one("td.subject a") or row.select_one("td.title a")
        if not subject_td:
            continue
            
        title = subject_td.get_text(strip=True)
        href = subject_td.get("href")
        
        # 번호 확인 (공지사항 배지인 '공지' 텍스트가 있는 행은 건너뛰고 진짜 최신글 찾기 위함)
        # 필요하다면 이 로직은 제거하고 무조건 맨 위 글을 가져와도 됨
        
        # 링크 파싱
        post_id = None
        full_url = NOTICE_URL

        if href and "btin_idx=" in href:
            post_id = href.split("btin_idx=")[1].split("&")[0]
            full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?btin_idx={post_id}&menu_idx=42"
        elif href and "nttId=" in href:
            post_id = href.split("nttId=")[1].split("&")[0]
            full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?nttId={post_id}&menu_idx=42"
        
        # ID를 못 찾았으면 제목을 ID로 대체
        if not post_id:
            post_id = title

        latest_notice = {"id": post_id, "title": title, "url": full_url}
        break # 맨 위 하나만 찾고 종료

    return latest_notice

# --------------------------------------
# 요약 (GPT)
def summarize_text(title):
    if not OPENAI_API_KEY:
        return title # 키 없으면 제목 그대로 리턴

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
        print(f"⚠️ 요약 실패 (그냥 제목 보냄): {e}")
        return title

# --------------------------------------
# 디스코드 전송
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
# 메인 실행
def main():
    print("✅ 크롤링 시작...")
    
    latest = fetch_latest_notice()
    if not latest:
        print("❌ 최신 글을 못 찾음")
        return

    # 저장된 ID 확인
    last_id = ""
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r", encoding='utf-8') as f:
            last_id = f.read().strip()

    print(f"🔍 확인된 최신글: {latest['title']} (ID: {latest['id']})")

    if latest["id"] == last_id:
        print("👌 이미 보낸 공지입니다.")
        return

    # 새 글이면 전송
    print("🚀 새 공지 전송 중...")
    summary = summarize_text(latest['title'])
    send_discord(latest, summary)

    # ID 업데이트
    with open(LAST_ID_FILE, "w", encoding='utf-8') as f:
        f.write(latest["id"])

if __name__ == "__main__":
    main()
