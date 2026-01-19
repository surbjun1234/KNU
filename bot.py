import requests
from bs4 import BeautifulSoup
import openai
import os

# 환경 변수 로드
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
openai.api_key = OPENAI_API_KEY

BASE_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42"
LAST_ID_FILE = "last_id.txt"

def get_latest_notice():
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 공지사항 목록에서 첫 번째 게시물 찾기 (KNU 사이트 구조에 맞게 조정 필요)
    # 보통 tr 태그 내의 td.subject 등을 찾습니다.
    notice_list = soup.select("table.board_list tbody tr")
    
    for notice in notice_list:
        # '공지' 배지가 달린 것 제외하고 일반 최신글 번호 확인
        num_tag = notice.select_one("td.num")
        if num_tag and num_tag.text.strip().isdigit():
            title_tag = notice.select_one("td.subject a")
            href = title_tag['href']
            # 게시글 고유 ID 추출 (URL 파라미터 등)
            post_id = href.split('btin_idx=')[-1].split('&')[0]
            title = title_tag.text.strip()
            link = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?btin_idx={post_id}&menu_idx=42"
            return post_id, title, link
    return None, None, None

def summarize_text(title):
    # 본문까지 크롤링하려면 상세 페이지 접속이 필요하지만, 
    # 토큰 절약을 위해 우선 제목을 바탕으로 핵심 요약을 요청합니다.
    prompt = f"다음 대학교 학사공지 제목을 짧고 명확하게 요약해줘: {title}"
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_discord_message(content):
    data = {"content": content}
    requests.post(DISCORD_WEBHOOK_URL, json=data)

def main():
    post_id, title, link = get_latest_notice()
    
    if not post_id:
        return

    # 이전 ID와 비교
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            last_id = f.read().strip()
    else:
        last_id = ""

    if post_id != last_id:
        summary = summarize_text(title)
        message = f"📢 **새로운 학사공지**\n\n**제목:** {title}\n**요약:** {summary}\n**링크:** {link}"
        send_discord_message(message)
        
        # 최신 ID 저장
        with open(LAST_ID_FILE, "w") as f:
            f.write(post_id)

if __name__ == "__main__":
    main()
