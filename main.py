import requests
from bs4 import BeautifulSoup
import os
from openai import OpenAI
from urllib.parse import urljoin

# ========================
# 환경변수
# ========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

client = OpenAI(api_key=OPENAI_API_KEY)

# ========================
# 설정
# ========================
BASE_URL = "https://www.knu.ac.kr"
NOTICE_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42"


# ========================
# 디스코드 전송
# ========================
def send_to_discord(message: str):
    if not DISCORD_WEBHOOK:
        print("❌ DISCORD_WEBHOOK is missing")
        return
    payload = {"content": message}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    print("Discord status:", r.status_code)


# ========================
# 학사공지 크롤링 (User-Agent 포함, 제목 + URL)
# ========================
def fetch_notices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/117.0.0.0 Safari/537.36"
    }
    res = requests.get(NOTICE_URL, headers=headers)
    res.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, "html.parser")
    rows = soup.select("table.board-table tbody tr")

    notices = []
    for row in rows:
        link_tag = row.select_one("td:nth-child(2) a")
        if not link_tag:
            continue

        title = link_tag.get_text(strip=True)
        relative_url = link_tag.get("href")
        full_url = urljoin(BASE_URL, relative_url)

        notices.append({
            "title": title,
            "url": full_url
        })
    return notices


# ========================
# GPT 요약 (공지 1개 기준)
# ========================
def summarize_with_gpt(notice):
    prompt = (
        "다음은 경북대학교 학사공지 제목이다.\n"
        "학생이 이해하기 쉽게 핵심만 2~3줄로 요약해줘.\n\n"
        f"- {notice['title']}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 한국 대학생을 돕는 비서다."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


# ========================
# 메인 실행
# ========================
def main():
    print("✅ 학사공지 자동 확인 시작")

    notices = fetch_notices()
    if not notices:
        print("❌ 공지를 가져오지 못했습니다")
        return

    # 항상 최신 공지 1개 선택
    latest_notice = notices[0]
    print(f"📢 최신 공지: {latest_notice['title']}")

    summary = summarize_with_gpt(latest_notice)

    send_to_discord(
        "📢 **경북대 학사공지 (최근 공지)**\n\n"
        f"📝 **요약**\n{summary}\n\n"
        f"🔗 **공지 바로가기**\n{latest_notice['url']}"
    )


if __name__ == "__main__":
    main()
