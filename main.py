import requests
from bs4 import BeautifulSoup
import os
import re  # 정규표현식 사용 (숫자 추출용)

# 게시판 목록 URL
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
# 게시판 상세 보기 기본 URL (경북대 패턴 분석 기반)
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?bbs_cde=1&menu_idx=67&bbs_num="

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def send_discord_message(webhook_url, title, link, post_id):
    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [
            {
                "title": title,
                "description": f"새로운 공지사항이 올라왔습니다.\n게시글 번호: {post_id}",
                "url": link,  # 여기 클릭하면 바로 이동됨
                "color": 12916017,
                "footer": {
                    "text": "바로가기를 클릭해서 내용을 확인하세요."
                }
            }
        ]
    }
    requests.post(webhook_url, json=data)

def crawl_knu_notice():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'
    }
    # SSL 인증서 검증 무시 (verify=False)
    response = requests.get(LIST_URL, headers=headers, verify=False)
    response.encoding = 'UTF-8'
    
    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.select("tbody > tr")
    
    latest_post = None
    
    for row in rows:
        cols = row.select("td")
        if len(cols) < 2:
            continue
            
        num_text = cols[0].text.strip()
        
        # '공지'가 아닌 숫자(일반글)인 경우만
        if num_text.isdigit():
            title_tag = cols[1].find("a")
            title = title_tag.text.strip()
            
            # href 속성 가져오기 (예: "javascript:fn_view('12345');")
            href_content = title_tag.get('href', '')
            
            # 정규식으로 숫자만 추출
            # \d+ 는 숫자가 연속으로 나오는 패턴을 찾음
            match = re.search(r"(\d+)", href_content)
            
            if match:
                real_id = match.group(1) # 추출된 숫자 (예: 12345)
                
                # 상세 페이지로 가는 진짜 URL 만들기
                real_link = VIEW_URL_BASE + real_id
                
                latest_post = {'id': real_id, 'title': title, 'link': real_link}
                break # 최신글 하나만 찾고 종료

    return latest_post

def main():
    new_post = crawl_knu_notice()
    
    if not new_post:
        print("새로운 게시글을 찾을 수 없습니다.")
        return

    latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
    
    # 저장된 ID 불러오기
    try:
        with open(latest_id_path, 'r', encoding='utf-8') as f:
            last_id = f.read().strip()
    except FileNotFoundError:
        last_id = "0"

    print(f"최신글 ID: {new_post['id']} (제목: {new_post['title']})")

    # ID 비교 (문자열이 아닌 정수로 비교)
    if int(new_post['id']) > int(last_id):
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        
        if webhook_url:
            send_discord_message(webhook_url, new_post['title'], new_post['link'], new_post['id'])
            
            # ID 업데이트
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(new_post['id'])
        else:
            print("WebHook URL 미설정")
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()
