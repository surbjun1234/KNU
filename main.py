import requests
import json
import os
from bs4 import BeautifulSoup
from openai import OpenAI

# ===== 환경변수 =====
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42"
STATE_FILE = "sent.json"


def load_sent():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent(sent):
    with open(STATE_FILE, "w") as f:
        json.dump(list(sent), f)


def get_notices():
    html = requests.get(LIST_URL).text
    soup = BeautifulSoup(html, "html.parser")

    notices = []
    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if title and href and "stdViewBtin.action" in href:
            notices.append((title, "https://www.knu.ac.kr" + href))

    return notices[:5]


def summarize(text):
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "너는 대학교 학사공지를 요약하는 도우미야."},
            {"role": "user", "content": f"아래 공지를 학생 기준으로 3~5줄로 요약해줘:\n{text}"}
        ]
    )
    return res.choices[0].message.content


def send_discord(title, summary, link):
    data = {
        "embeds": [{
            "title": f"📢 {title}",
            "description": summary,
            "url": link,
            "color": 3447003
        }]
    }
    requests.post(DISCORD_WEBHOOK, json=data)


def main():
    sent = load_sent()
    notices = get_notices()

    for title, link in notices:
        if link in sent:
            continue

        detail_html = requests.get(link).text
        soup = BeautifulSoup(detail_html, "html.parser")
        text = soup.get_text()

        summary = summarize(text)
        send_discord(title, summary, link)

        sent.add(link)

    save_sent(sent)


if __name__ == "__main__":
    main()
