import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정] ★여기를 수정해서 테스트하세요★
# -----------------------------------------------------------
# 예: 1336480 이라고 적으면, 1336480번 이후의 글을 모두 새 글 취급해서 알림을 보냅니다.
# 테스트가 끝나면 다시 None 으로 바꿔주세요. (평소에는 파일 기록 사용)
TEST_LAST_ID = 1336480
# TEST_LAST_ID = 1336480  <-- 이런 식으로 숫자를 넣으세요

# -----------------------------------------------------------
# [기본 설정] URL 및 경로
# -----------------------------------------------------------
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [기능 1] 본문 내용 긁어오기
# -----------------------------------------------------------
def get_post_content(url):
    """상세 페이지의 텍스트를 가져옵니다."""
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(url, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 경북대 공지사항 본문 영역
        content_div = soup.select_one('.board_view_con') or soup.select_one('.view_con')
            
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        else:
            return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"본문 로딩 실패: {e}"

# -----------------------------------------------------------
# [기능 2] 디스코드 전송
# -----------------------------------------------------------
def send_discord_message(webhook_url, title, link, post_id, content):
    # 본문이 너무 길면 1500자에서 자름
    if len(content) > 1500:
        display_content = content[:1500] + "\n\n...(내용이 길어 생략됨, 링크 확인)..."
    else:
        display_content = content

    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [
            {
                "title": title,
                "description": display_content,
                "url": link,
                "color": 12916017, # KNU Red
                "footer": {
                    "text": f"게시글 번호: {post_id}"
                }
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print(f"[전송 완료] {title}")
        else:
            print(f"[전송 실패] 상태 코드: {response.status_code}")
    except Exception as e:
        print(f"[에러] 디스코드 전송 중 오류: {e}")

# -----------------------------------------------------------
# [메인] 로직
# -----------------------------------------------------------
def main():
    requests.packages.urllib3.disable_warnings()
    
    # 1. 기준 ID 설정 (테스트 값 우선, 없으면 파일 읽기)
    if TEST_LAST_ID is not None:
        last_id = int(TEST_LAST_ID)
        print(f"⚠️ [테스트 모드] 강제로 기준 ID를 {last_id}로 설정했습니다.")
    else:
        latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
        try:
            with open(latest_id_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                last_id = int(content) if content else 0
        except FileNotFoundError:
            last_id = 0
        print(f"현재 저장된 ID (파일): {last_id}")

    # 2. 목록 가져오기
    try:
        response = requests.get(LIST_URL, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"목록 접속 실패: {e}")
        return

    rows = soup.select("tbody > tr")
    new_posts = []

    for row in rows:
        cols = row.select("td")
        if len(cols) < 2: continue
        
        num_text = cols[0].text.strip()
        
        if num_text.isdigit():
            current_id = int(num_text)
            
            # 기준 ID보다 크면 담기
            if current_id > last_id:
                title = cols[1].find("a").text.strip()
                href_content = cols[1].find("a").get('href', '')
                
                match = re.search(r"(\d+)", href_content)
                if match:
                    real_id = match.group(1)
                    real_link = VIEW_URL_BASE + real_id
                    
                    new_posts.append({
                        'id': current_id,
                        'title': title,
                        'link': real_link
                    })
            else:
                break

    # 3. 전송 및 업데이트
    if new_posts:
        print(f"총 {len(new_posts)}개의 새 공지 발견.")
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        if not webhook_url:
            print("ERROR: 웹훅 URL 없음")
            return

        # 과거 글부터 순서대로 전송
        for post in reversed(new_posts):
            content_text = get_post_content(post['link'])
            send_discord_message(webhook_url, post['title'], post['link'], post['id'], content_text)
            time.sleep(1)

        # ★주의★ 테스트 모드일 때는 파일 저장을 안 하는 게 좋습니다.
        # (테스트 끝나고 다시 0번부터 알림이 올 수 있으니까요)
        # 만약 테스트 때도 저장을 원하시면 아래 if 문을 지우세요.
        if TEST_LAST_ID is None:
            latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
            newest_id = new_posts[0]['id']
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(newest_id))
            print(f"ID 파일 업데이트 완료: {newest_id}")
        else:
            print("⚠️ [테스트 모드] 파일 업데이트를 건너뜁니다.")
            
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
