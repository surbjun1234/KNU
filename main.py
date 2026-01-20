import time
import os
import openai
import requests
from bs4 import BeautifulSoup

# Selenium 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --------------------------------------
# 환경변수 세팅
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# URL 설정
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/btin/stdList.action?menu_idx=42"
LAST_ID_FILE = "last_id.txt"

# --------------------------------------
def fetch_latest_notice_selenium():
    print("Bot: 가상 브라우저(Chrome) 세팅 중...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # 화면 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # [핵심] 봇 탐지 방지 옵션
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        # 크롬 드라이버 자동 설치 및 실행
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"Bot: 페이지 접속 시도 -> {NOTICE_URL}")
        driver.get(NOTICE_URL)
        
        # 페이지 로딩 대기 (3초)
        time.sleep(3)
        
        # 현재 페이지 제목 확인 (디버깅용)
        print(f"Bot: 현재 페이지 제목 -> {driver.title}")
        
        if "KNU STUD" in driver.title:
            print("❌ 여전히 리다이렉트 되었습니다. (IP 차단 가능성 높음)")
            driver.quit()
            return None

        # HTML 가져오기
        html = driver.page_source
        driver.quit() # 브라우저 종료
        
        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(html, "html.parser")
        
        # 게시글 행 찾기
        rows = soup.select("tbody tr")
        if not rows:
             rows = soup.select(".board_list tbody tr")
             
        if not rows:
            print("❌ 게시판 테이블을 못 찾았습니다.")
            return None

        # 최신글 추출 로직
        latest_notice = None
        for row in rows:
            subject_td = row.select_one("td.subject a") or row.select_one("td.title a")
            num_td = row.select_one("td.num")
            
            # '공지' 배지 제외
            if num_td and not num_td.get_text(strip=True).isdigit():
                continue
                
            if not subject_td:
                continue

            title = subject_td.get_text(strip=True)
            href = subject_td.get("href")
            
            # 링크 파싱
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
            break

        return latest_notice

    except Exception as e:
        print(f"❌ Selenium 에러: {e}")
        return None

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
        return

    message = f"📢 **[경북대 학사공지]**\n{notice['title']}\n\n📝 **요약**: {summary}\n🔗 [바로가기]({notice['url']})"
    
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
        print("✅ Discord 전송 성공")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

# --------------------------------------
def main():
    print("✅ Selenium 봇 실행 시작 (v4.0)")
    
    latest = fetch_latest_notice_selenium()
    
    if not latest:
        print("❌ 공지를 가져오지 못하고 종료합니다.")
        return

    last_id = ""
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r", encoding='utf-8') as f:
            last_id = f.read().strip()

    print(f"🔍 가져온 최신글: {latest['title']}")
    
    if latest["id"] == last_id:
        print("👌 이미 보낸 공지입니다.")
        return

    print("🚀 새 공지 발견! 디스코드로 전송합니다...")
    summary = summarize_text(latest['title'])
    send_discord(latest, summary)

    with open(LAST_ID_FILE, "w", encoding='utf-8') as f:
        f.write(latest["id"])

if __name__ == "__main__":
    main()
