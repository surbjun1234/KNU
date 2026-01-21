import requests
from bs4 import BeautifulSoup
import os
import re

# 1. 경북대 학사공지 목록 주소
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
# 2. 상세 페이지 안전 주소
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_post_content_preview(url):
    """상세 페이지 내용을 긁어와서 앞부분만 반환합니다."""
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(url, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 경북대 홈페이지 본문이 들어있는 클래스 찾기
        # 보통 board_view_con 또는 view_con 안에 텍스트가 있음
        content_div = soup.select_one('.board_view_con')
        
        # 만약 못 찾으면 다른 이름으로 시도
        if not content_div:
            content_div = soup.select_one('.view_con')
            
        if content_div:
            # HTML 태그 제거하고 텍스트만 깔끔하게 추출
            full_text = content_div.get_text(separator="\n", strip=True)
            
            # 너무 길면 디스코드 제한 걸리므로 앞부분 300자만 자름
            if len(full_text) > 300:
                return full_text[:300] + "..."
            return full_text
        else:
            return "본문 영역을 찾을 수 없습니다. (HTML 구조 확인 필요)"

    except Exception as e:
        return f"본문 크롤링 실패: {str(e)}"

def send_discord_message(webhook_url, title, link, post_id, content_preview):
    data = {
        "content": "🔔 **경북대 학사공지 (본문 테스트)**",
        "embeds": [
            {
                "title": title,
                "url": link,
                "color": 12916017,
                "fields": [
                    {
                        "name": "📄 본문 미리보기 (Raw Text)",
                        "value": content_preview, # 여기에 긁어온 내용이 뜹니다
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"게시글 번호: {post_id}"
                }
            }
        ]
    }
    
    try:
        requests.post(webhook_url, json=data)
        print("디스코드 전송 성공")
    except Exception as e:
        print(f"디스코드 전송 실패: {e}")

def crawl_knu_notice():
    requests.packages.urllib3.disable_warnings()
    try:
        response = requests.get(LIST_URL, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except:
        return None

    rows = soup.select("tbody > tr")
    latest_post = None
    
    for row in rows:
        cols = row.select("td")
        if len(cols) < 2: continue
        
        num_text = cols[0].text.strip()
        if num_text.isdigit():
            title = cols[1].find("a").text.strip()
            href_content = cols[1].find("a").get('href', '')
            match = re.search(r"(\d+)", href_content)
            
            if match:
                real_id = match.group(1)
                real_link = VIEW_URL_BASE + real_id
                latest_post = {'id': real_id, 'title': title, 'link': real_link}
                break 

    return latest_post

def main():
    new_post = crawl_knu_notice()
    if not new_post:
        print("공지사항 없음")
        return

    latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
    try:
        with open(latest_id_path, 'r', encoding='utf-8') as f:
            last_id = f.read().strip() or "0"
    except FileNotFoundError:
        last_id = "0"

    print(f"최신글: {new_post['id']} / 저장된글: {last_id}")

    # 테스트를 위해 무조건 실행되도록 조건 임시 완화 (원래는 > )
    # 테스트 끝나면 다시 if int(new_post['id']) > int(last_id): 로 바꾸세요!
    if int(new_post['id']) > int(last_id): 
        print(">>> 새 글 발견! 본문 가져오는 중...")
        
        # 1. 본문 긁어오기 함수 호출
        preview_text = get_post_content_preview(new_post['link'])
        print(f"가져온 내용(일부): {preview_text[:50]}")

        # 2. 디스코드 전송
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        
        if webhook_url:
            send_discord_message(webhook_url, new_post['title'], new_post['link'], new_post['id'], preview_text)
            
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(new_post['id'])
        else:
            print("WebHook URL 없음")
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
