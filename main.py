import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정]
# -----------------------------------------------------------
TEST_LAST_ID = 1336480  # 테스트용 (이 번호보다 큰 글을 찾음)

# -----------------------------------------------------------
# [설정] URL
# -----------------------------------------------------------
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(url, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.select_one('.board_view_con') or soup.select_one('.view_con')
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return "본문 없음"
    except:
        return "크롤링 실패"

def send_discord_message(webhook_url, title, link, doc_id, content):
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
            "footer": {"text": f"Doc ID: {doc_id}"}
        }]
    }
    try:
        requests.post(webhook_url, json=data)
        print(f"🚀 [전송 성공] {title}")
    except Exception as e:
        print(f"❌ [전송 실패] {e}")

def main():
    requests.packages.urllib3.disable_warnings()
    
    print("--- [크롤러 시작] ---")

    # 1. 기준 ID 설정
    if TEST_LAST_ID is not None:
        last_id = int(TEST_LAST_ID)
        print(f"🎯 기준 ID (테스트): {last_id} (이 번호보다 커야 알림)")
    else:
        latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
        try:
            with open(latest_id_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                last_id = int(content) if content else 0
        except FileNotFoundError:
            last_id = 0
        print(f"📂 기준 ID (파일): {last_id}")

    # 2. 목록 접속
    try:
        response = requests.get(LIST_URL, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"🚨 접속 실패: {e}")
        return

    rows = soup.select("tbody > tr")
    print(f"🔍 총 {len(rows)}개의 게시글 행을 검사합니다.\n")

    new_posts = []

    for i, row in enumerate(rows):
        cols = row.select("td")
        if len(cols) < 2: continue
        
        # 화면에 보이는 번호 (참고용)
        visible_num = cols[0].text.strip()
        title = cols[1].find("a").text.strip()
        
        # 링크에서 진짜 ID 추출
        href_content = cols[1].find("a").get('href', '')
        match = re.search(r"(\d+)", href_content)
        
        if match:
            doc_id = int(match.group(1))
            
            # 로그 출력 (봇이 뭘 보고 있는지 확인)
            print(f"[{i+1}] 화면번호:{visible_num} | 고유ID:{doc_id} | 제목:{title[:10]}...", end=" ")

            if doc_id > last_id:
                print(f"✅ [새 글!]")
                real_link = VIEW_URL_BASE + str(doc_id)
                new_posts.append({
                    'id': doc_id,
                    'title': title,
                    'link': real_link
                })
            else:
                print(f"⏹️ [옛날 글]") 
                # ★ 중요: 여기서 break 하지 않고 계속 검사합니다!
                # 고정 공지 때문에 순서가 뒤섞여 있을 수 있기 때문입니다.
        else:
            print(f"[{i+1}] ID 추출 실패 (공지 등): {visible_num}")

    print(f"\n✨ 총 발견된 새 공지: {len(new_posts)}개")

    # 3. 전송 로직
    if new_posts:
        # ID 기준 오름차순 정렬 (옛날 글 -> 최신 글 순서로 전송)
        new_posts.sort(key=lambda x: x['id'])
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        
        if webhook_url:
            for post in new_posts:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, post['title'], post['link'], post['id'], content)
                time.sleep(1)
        else:
            print("❌ WebHook URL이 설정되지 않았습니다.")

        # 테스트 아닐 때만 파일 업데이트
        if TEST_LAST_ID is None:
            # 가장 큰 ID 찾기
            max_id = max(p['id'] for p in new_posts)
            latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(max_id))
            print(f"💾 파일 업데이트 완료: {max_id}")
    else:
        print("💤 전송할 새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
