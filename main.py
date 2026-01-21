import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정]
# -----------------------------------------------------------
# 테스트할 때는 1330000 같은 '고유 번호'보다 작은 값을 넣으세요.
# 평소에는 None 으로 두세요.
TEST_LAST_ID = 1336480 
# TEST_LAST_ID = 1336480 

# -----------------------------------------------------------
# [설정] URL 및 경로
# -----------------------------------------------------------
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
# 상세 주소 (맨 뒤에 고유번호가 붙음)
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [기능 1] 본문 내용 긁어오기
# -----------------------------------------------------------
def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(url, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 본문 영역 찾기
        content_div = soup.select_one('.board_view_con') or soup.select_one('.view_con')
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"본문 로딩 실패: {e}"

# -----------------------------------------------------------
# [기능 2] 디스코드 전송
# -----------------------------------------------------------
def send_discord_message(webhook_url, title, link, doc_id, content):
    # 본문 1500자 제한
    if len(content) > 1500:
        display_content = content[:1500] + "\n\n...(내용 생략)..."
    else:
        display_content = content

    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [{
            "title": title,
            "description": display_content,
            "url": link,
            "color": 12916017,
            "footer": {"text": f"고유 번호(Doc ID): {doc_id}"}
        }]
    }
    
    try:
        requests.post(webhook_url, json=data)
        print(f"[전송 완료] {title}")
    except Exception as e:
        print(f"[에러] {e}")

# -----------------------------------------------------------
# [메인] 로직
# -----------------------------------------------------------
def main():
    requests.packages.urllib3.disable_warnings()
    
    # 1. 저장된 ID 불러오기 (URL 속 고유번호 기준)
    if TEST_LAST_ID is not None:
        last_id = int(TEST_LAST_ID)
        print(f"⚠️ [테스트] 기준 고유번호: {last_id}")
    else:
        latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
        try:
            with open(latest_id_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                last_id = int(content) if content else 0
        except FileNotFoundError:
            last_id = 0
        print(f"현재 저장된 고유번호: {last_id}")

    # 2. 목록 접속
    try:
        response = requests.get(LIST_URL, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"접속 실패: {e}")
        return

    rows = soup.select("tbody > tr")
    new_posts = []

    for row in rows:
        cols = row.select("td")
        if len(cols) < 2: continue
        
        # 화면에 보이는 번호 (단순 필터링용)
        visible_num = cols[0].text.strip()
        
        # "공지" 글은 건너뛰고 숫자로 된 글만 확인
        if visible_num.isdigit():
            title = cols[1].find("a").text.strip()
            href_content = cols[1].find("a").get('href', '')
            
            # [핵심] URL(href)에서 실제 고유 번호(doc_no) 추출
            # 예: javascript:fn_view('1336486') -> 1336486 추출
            match = re.search(r"(\d+)", href_content)
            
            if match:
                doc_id = int(match.group(1)) # 이것이 진짜 ID
                
                # 저장된 고유번호보다 크면 새 글
                if doc_id > last_id:
                    real_link = VIEW_URL_BASE + str(doc_id)
                    
                    new_posts.append({
                        'id': doc_id, # 고유번호 저장
                        'title': title,
                        'link': real_link
                    })
                else:
                    # 내림차순이므로 더 작은 번호가 나오면 즉시 종료
                    # (단, 게시판 구조상 순번과 고유번호 순서가 일치한다고 가정)
                    break 

    # 3. 전송 및 저장
    if new_posts:
        print(f"총 {len(new_posts)}개의 새 공지 발견.")
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        if not webhook_url:
            print("WebHook URL 없음")
            return

        # 과거 글(번호 작은 순) -> 최신 글 순서로 전송
        for post in reversed(new_posts):
            content = get_post_content(post['link'])
            send_discord_message(webhook_url, post['title'], post['link'], post['id'], content)
            time.sleep(1)

        # 테스트 아닐 때만 파일 저장
        if TEST_LAST_ID is None:
            latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
            # 가장 큰 고유번호 저장
            newest_id = new_posts[0]['id'] 
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(newest_id))
            print(f"ID 업데이트 완료: {newest_id}")
    else:
        print("새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
