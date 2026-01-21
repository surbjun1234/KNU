import requests
from bs4 import BeautifulSoup
import os
import re
import json

# 경북대 학사공지 URL
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?bbs_cde=1&menu_idx=67&bbs_num="

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def send_discord_message(webhook_url, title, link, post_id):
    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [
            {
                "title": title,
                "description": f"새로운 공지사항이 올라왔습니다.\n번호: {post_id}",
                "url": link,
                "color": 12916017, # 경북대 Red
                "footer": {
                    "text": "경북대학교 학사공지 알림봇"
                }
            }
        ]
    }
    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print("디스코드 전송 성공")
        else:
            print(f"디스코드 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"전송 중 에러 발생: {e}")

def crawl_knu_notice():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'
    }
    # SSL 경고 무시 및 요청
    requests.packages.urllib3.disable_warnings()
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
            
            href_content = title_tag.get('href', '')
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
        print("공지사항을 찾을 수 없습니다.")
        return

    latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
    
    # 저장된 ID 불러오기
    try:
        with open(latest_id_path, 'r', encoding='utf-8') as f:
            last_id = f.read().strip()
    except FileNotFoundError:
        last_id = "0"

    print(f"크롤링한 최신글: {new_post['id']} / 저장된 ID: {last_id}")

    if int(new_post['id']) > int(last_id):
        # ---------------------------------------------------------
        # [수정된 부분] 환경변수 이름을 두 가지 모두 확인합니다.
        # DISCORD_WEBHOOK_URL 또는 DISCORD_WEBHOOK 둘 중 하나만 있어도 작동함
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            webhook_url = os.environ.get("DISCORD_WEBHOOK")
        # ---------------------------------------------------------
        
        if webhook_url:
            print(f"알림 전송 시도: {new_post['title']}")
            send_discord_message(webhook_url, new_post['title'], new_post['link'], new_post['id'])
            
            # ID 업데이트
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(new_post['id'])
        else:
            print("ERROR: 웹훅 URL 환경변수를 찾을 수 없습니다. (Settings > Secrets 확인 필요)")
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
