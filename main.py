import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

# Discord Webhook
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://api.gemini.google/v1/chat/completions"
GEMINI_MODEL = "gemini-2.5-flash-lite"  # 제일 저렴한 모델

# 공지 URL
BASE_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42"

# 크롤링 함수
def fetch_notices():
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"menu_idx": "42", "pageIndex": "1"}

    res = requests.get(NOTICE_URL, headers=headers, params=params)
    if res.status_code != 200:
        print(f"❌ 게시판 페이지 요청 실패: {res.status_code}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    
    # 게시판 구조에 맞춰 선택자 수정 필요
    rows = soup.select("div.board_list ul li")  # 구조 확인 후 바꾸기
    if not rows:
        print("❌ 게시판 테이블을 찾을 수 없습니다.")
        return []

    notices = []
    for row in rows:
        link = row.select_one("a")
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link.get("href")
        notices.append({
            "title": title,
            "url": urljoin(BASE_URL, href)
        })

    # 최신 공지 1개만
    return notices[:1]

# Gemini로 요약
def summarize_with_gemini(text):
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that summarizes text."},
            {"role": "user", "content": f"Summarize this: {text}"}
        ]
    }

    res = requests.post(GEMINI_URL, headers=headers, json=data)
    if res.status_code != 200:
        print(f"❌ Gemini API 오류: {res.status_code}")
        return text

    response_json = res.json()
    summary = response_json['choices'][0]['message']['content']
    return summary

# Discord 전송
def send_discord(message):
    if not DISCORD_WEBHOOK:
        print("❌ Discord Webhook 미설정")
        return
    data = {"content": message}
    res = requests.post(DISCORD_WEBHOOK, json=data)
    if res.status_code == 204:
        print("✅ Discord 전송 완료")
    else:
        print(f"❌ Discord 전송 실패: {res.status_code}")

# 메인 실행
def main():
    print("✅ 학사공지 자동 확인 시작")
    notices = fetch_notices()
    if not notices:
        print("❌ 공지를 가져오지 못했습니다")
        return

    latest_notice = notices[0]
    print(f"📢 최신 공지: {latest_notice['title']}")

    summary = summarize_with_gemini(latest_notice['title'])
    message = f"📢 {latest_notice['title']}\n📝 요약: {summary}\n🔗 {latest_notice['url']}"
    send_discord(message)

if __name__ == "__main__":
    main()
