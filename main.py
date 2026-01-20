import requests
from bs4 import BeautifulSoup
import re
import os
from transformers import pipeline

# --------------------------------------
# 환경변수 세팅
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# 게시판 URL
BASE_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/btin/stdList.action?menu_idx=42"

# HuggingFace 요약 모델 로딩 (GitHub Actions에서 가능)
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# --------------------------------------
# 공지 가져오기
def fetch_notices():
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(NOTICE_URL, headers=headers)
    if res.status_code != 200:
        print(f"❌ 게시판 페이지 요청 실패: {res.status_code}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    rows = soup.select("div.board_list table tr")  # tbody 제거

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

        match = re.search(r"doRead\('(\d+)'", href)
        if match:
            ntt_id = match.group(1)
            full_url = f"https://www.knu.ac.kr/wbbs/bbs/btin/view.action?nttId={ntt_id}&menu_idx=42"
        else:
            full_url = "#"

        notices.append({"title": title, "url": full_url})

    return notices[:1]  # 최신 공지 1개

# --------------------------------------
# HuggingFace로 요약
def summarize_with_hf(text):
    try:
        summary = summarizer(text, max_length=60, min_length=20, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"❌ 요약 실패: {e}")
        return text

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

    summary = summarize_with_hf(latest_notice['title'])
    message = f"📢 {latest_notice['title']}\n📝 요약: {summary}\n🔗 {latest_notice['url']}"
    send_discord(message)

# --------------------------------------
if __name__ == "__main__":
    main()
