import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정]
# -----------------------------------------------------------
TEST_LAST_ID = 1336480  # 테스트용 기준 ID

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

def send_discord_message(webhook_url, title, link, post_id, content):
    if len(content) > 1500:
        display_content = content[:1500] + "\n\n..."
    else:
        display_content = content

    data = {
        "content": "🧪 **디버그 테스트 메시지**",
        "embeds": [{
            "title": title,
            "description": display_content,
            "url": link,
            "color": 12916017,
            "footer": {"text": f"ID: {post_id}"}
        }]
    }
    try:
        requests.post(webhook_url, json=data)
    except:
        pass

def main():
    requests.packages.urllib3.disable_warnings()
    
    print("--- [디버그 모드 시작] ---")
    
    # 1. ID 설정 확인
    if TEST_LAST_ID is not None:
        last_id = int(TEST_LAST_ID)
        print(f"👉 기준 ID (강제 설정): {last_id}")
    else:
        print("👉 파일 모드 (테스트 아님)")
        return

    # 2. 접속 시도
    print(f"👉 접속 시도: {LIST_URL}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(LIST_URL, headers=headers, verify=False)
        response.encoding = 'UTF-8'
        print(f"👉 응답 코드: {response.status_code}")
        
        # 내용이 비었는지 확인
        if len(response.text) < 100:
            print("🚨 경고: 가져온 HTML 내용이 너무 짧습니다. (차단 의심)")
            print(response.text)
            return

        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"🚨 접속 에러 발생: {e}")
        return

    rows = soup.select("tbody > tr")
    print(f"👉 찾은 게시글 행(row) 개수: {len(rows)}개")

    new_posts = []

    # 3. 한 줄씩 검사 내용을 출력
    for i, row in enumerate(rows):
        cols = row.select("td")
        if len(cols) < 2:
            print(f"[{i}] 칸 부족 (패스)")
            continue
        
        num_text = cols[0].text.strip()
        title = cols[1].text.strip()[:10] + "..." # 제목 짧게 출력
        
        print(f"[{i}] 번호칸: '{num_text}' | 제목: {title}")

        if num_text.isdigit():
            current_id = int(num_text)
            
            if current_id > last_id:
                print(f"    ✅ 새 글 발견! ({current_id} > {last_id})")
                
                title_full = cols[1].find("a").text.strip()
                href_content = cols[1].find("a").get('href', '')
                match = re.search(r"(\d+)", href_content)
                
                if match:
                    real_id = match.group(1)
                    real_link = VIEW_URL_BASE + real_id
                    new_posts.append({'id': current_id, 'title': title_full, 'link': real_link})
                else:
                    print(f"    ❌ 링크에서 ID 추출 실패: {href_content}")
            else:
                print(f"    ⏹️ 여기부터는 옛날 글입니다 ({current_id} <= {last_id}). 탐색 종료.")
                break
        else:
            print("    Pass (숫자가 아님 - 공지사항 등)")

    # 4. 결과 처리
    print(f"\n👉 최종 발견된 새 글: {len(new_posts)}개")
    
    if new_posts:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        for post in reversed(new_posts):
            print(f"🚀 전송 시도: {post['title']}")
            if webhook_url:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, post['title'], post['link'], post['id'], content)
                time.sleep(1)
            else:
                print("web hook url 없음")
    else:
        print("❌ 전송할 것이 없음")

if __name__ == "__main__":
    main()
