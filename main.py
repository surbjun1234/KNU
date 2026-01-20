import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import re

# --------------------------------------
# 환경변수 세팅
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 모델
GEMINI_MODEL = "gemini-2.5-flash-lite"

# 게시판 URL
BASE_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42"

# --------------------------------------
# 공지 가져오기
def fetch_notices():
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(NOTICE_URL, headers=headers)
    if res.status_code != 200:
        print(f"❌ 게시판 페이지 요청 실패: {res.status_code}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")

    # tbody 제거, table 안 tr 모두 선택
    rows = soup.select("div.board_list table tr")
    if not rows:
        print("❌ 게시판 테이블을 찾을 수 없습니다.")
        return []

    notices = []
    for row in rows:
        subject_td = row.select_one("td.subject a")
        if not subject_td:
            continue

        title = subject_td.get_text(strip=True)
        href = subject_td.get("href")

        # Javascript 링크 처리
        match = re.search(r"doRead\('(\d+)'", href)
        if match:
            ntt_id = match.group(1)
            full_url = f"https://www.knu.ac.kr/wbbs/bbs/btin/view.action?nttId={ntt_id}&menu_idx=42"
        else:
            full_url = "#"

        notices.append({"title": title, "url": full_url})

    # 최신 공지 1개만
    return notices[:1]

# --------------------------------------
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
            {"role": "user", "content": f"Summarize this text briefly: {text}"}
        ]
    }

    res = requests.post("https://api.gemini.google/v1/chat/completions", headers=headers, json=data)
    if res.status_code != 200:
        print(f"❌ Gemini API 오류: {res.status_code}")
        return text

    response_json = res.json()
    summary = response_json['choices'][0]['message']['content']
    return summary

# --------------------------------------
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

# --------------------------------------
# 메인
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

# --------------------------------------
if __name__ == "__main__":
    main()
