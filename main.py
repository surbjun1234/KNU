import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

# 🔹 환경 변수
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# 🔹 요약용 라이브러리
from transformers import pipeline

summarizer = pipeline("summarization", model="t5-small")  # 가벼운 요약 모델

# 🔹 사이트 정보
BASE_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/btin/stdList.action"

# 🔹 디스코드 전송 함수
def send_to_discord(message: str):
    if not DISCORD_WEBHOOK:
        print("❌ DISCORD_WEBHOOK is missing")
        return
    payload = {"content": message}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    print("Discord status:", r.status_code, r.text[:200])  # 앞 200자만 확인

# 🔹 학사공지 크롤링
def fetch_notices():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "menu_idx": "42",
        "pageIndex": "1"
    }

    res = requests.post(NOTICE_URL, headers=headers, data=data)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("table tbody tr")
    if not rows:
        print("❌ 게시판 테이블을 찾을 수 없습니다. HTML 구조 확인 필요")
        return []

    notices = []
    for row in rows:
        link = row.select_one("td:nth-child(2) a")
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link.get("href")
        notices.append({
            "title": title,
            "url": urljoin(BASE_URL, href)
        })

    return notices

# 🔹 로컬 모델 요약
def summarize_text(text):
    try:
        result = summarizer(text, max_length=60, min_length=20, do_sample=False)
        return result[0]['summary_text']
    except Exception as e:
        print("❌ 요약 실패:", e)
        return text  # 실패하면 원본 제목 사용

# 🔹 메인 실행
def main():
    print("✅ 학사공지 자동 확인 시작")

    notices = fetch_notices()
    if not notices:
        print("❌ 공지를 가져오지 못했습니다")
        return

    latest_notice = notices[0]  # 항상 최신 공지 1개
    print(f"📢 최신 공지: {latest_notice['title']}")

    summary = summarize_text(latest_notice['title'])

    send_to_discord(
        "📢 **경북대 학사공지 (최근 공지)**\n\n"
        f"📝 **요약**\n{summary}\n\n"
        f"🔗 **공지 바로가기**\n{latest_notice['url']}"
    )

if __name__ == "__main__":
    main()
