import requests
from bs4 import BeautifulSoup
import os
import re

# 1. 경북대 학사공지 목록 주소
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"

# 2. 상세 페이지 주소 (필수 파라미터 포함, 맨 뒤에 번호만 붙이면 됨)
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="

# 3. 파일 저장 위치 (GitHub Actions 환경)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def send_discord_message(webhook_url, title, link, post_id):
    """디스코드 웹훅으로 메시지를 보냅니다."""
    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [
            {
                "title": title,
                "description": f"새로운 공지사항이 등록되었습니다.\n게시글 번호: {post_id}",
                "url": link,
                "color": 12916017, # KNU Red Color
                "footer": {
                    "text": "경북대학교 학사공지 알림봇"
                }
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print("[성공] 디스코드 메시지 전송 완료")
        else:
            print(f"[실패] 디스코드 전송 오류: {response.status_code}")
    except Exception as e:
        print(f"[오류] 전송 중 예외 발생: {e}")

def crawl_knu_notice():
    """학교 홈페이지에서 최신글 번호와 제목을 가져옵니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'
    }
    
    # SSL 인증서 경고 무시 설정
    requests.packages.urllib3.disable_warnings()
    
    try:
        response = requests.get(LIST_URL, headers=headers, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"[오류] 홈페이지 접속 실패: {e}")
        return None

    rows = soup.select("tbody > tr")
    latest_post = None
    
    for row in rows:
        cols = row.select("td")
        if len(cols) < 2:
            continue
            
        num_text = cols[0].text.strip()
        
        # '공지' 글은 건너뛰고 '숫자'인 최신글만 잡습니다.
        if num_text.isdigit():
            title_tag = cols[1].find("a")
            title = title_tag.text.strip()
            
            # href에서 숫자 ID 추출 (javascript:fn_view('12345') 형태 대응)
            href_content = title_tag.get('href', '')
            match = re.search(r"(\d+)", href_content)
            
            if match:
                real_id = match.group(1)
                real_link = VIEW_URL_BASE + real_id
                latest_post = {'id': real_id, 'title': title, 'link': real_link}
                break 

    return latest_post

def main():
    # 1. 현재 게시판의 최신글 가져오기
    new_post = crawl_knu_notice()
    
    if not new_post:
        print("게시글을 찾을 수 없습니다. (사이트 구조 변경 가능성)")
        return

    # 2. 내 수첩(latest_id.txt)에 적힌 번호 가져오기
    latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
    
    try:
        with open(latest_id_path, 'r', encoding='utf-8') as f:
            last_id = f.read().strip()
            if not last_id: last_id = "0" # 파일이 비어있으면 0으로 처리
    except FileNotFoundError:
        last_id = "0" # 파일이 없으면 0으로 처리

    print(f"홈페이지 최신글: {new_post['id']} (제목: {new_post['title']})")
    print(f"저장된 마지막글: {last_id}")

    # 3. 비교하기 (새 글 번호 > 저장된 번호)
    if int(new_post['id']) > int(last_id):
        print(">>> 새 글 발견! 알림을 보냅니다.")
        
        # 환경변수 이름 2개 다 확인 (실수 방지용)
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            webhook_url = os.environ.get("DISCORD_WEBHOOK")
            
        if webhook_url:
            send_discord_message(webhook_url, new_post['title'], new_post['link'], new_post['id'])
            
            # 4. 수첩 업데이트 (새 번호로 덮어쓰기)
            # 주의: 여기서 파일만 바꾸고, 실제 저장은 .yml 파일의 git push 단계에서 함
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(new_post['id'])
        else:
            print("[ERROR] GitHub Secrets에 웹훅 주소가 설정되지 않았습니다.")
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
