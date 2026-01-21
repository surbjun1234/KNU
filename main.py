import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정]
# 실사용 시에는 None 으로 설정하세요.
# -----------------------------------------------------------
TEST_LAST_ID = None
# TEST_LAST_ID = 1336480 

# -----------------------------------------------------------
# [설정] URL
# -----------------------------------------------------------
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [공통 헤더] 크롬 브라우저인 척하기
# -----------------------------------------------------------
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Referer': LIST_URL, 
    'Upgrade-Insecure-Requests': '1'
}

def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        
        response = requests.get(url, headers=COMMON_HEADERS, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 내용을 찾을 클래스 후보군 (board_cont 최우선)
        candidates = [
            '.board_cont',      # ★ 사용자 확인 완료
            '.board_view_con',  
            '.view_con',        
            '.bbs_view',        
            '.content',         
        ]

        content_div = None
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div:
                break
        
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        else:
            return "본문 내용을 찾을 수 없습니다."
            
    except Exception as e:
        return f"본문 로딩 실패: {e}"

def send_discord_message(webhook_url, title, link, doc_id, content):
    if not content: content = "(내용 없음)"
    
    # 디스코드 글자수 제한 고려 (1000자)
    if len(content) > 1000:
        display_content = content[:1000] + "\n\n...(내용이 길어 생략되었습니다. 링크를 확인하세요)..."
    else:
        display_content = content

    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [{
            "title": title,
            "description": display_content,
            "url": link,
            "color": 12916017, # KNU Red
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

    # ID 설정
    if TEST_LAST_ID is not None:
        last_id = int(TEST_LAST_ID)
        print(f"🎯 기준 ID (테스트): {last_id}")
    else:
        latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
        try:
            with open(latest_id_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                last_id = int(content) if content else 0
        except FileNotFoundError:
            last_id = 0
        print(f"📂 기준 ID (파일): {last_id}")

    # 목록 접속
    try:
        response = requests.get(LIST_URL, headers=COMMON_HEADERS, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"🚨 목록 접속 실패: {e}")
        return

    rows = soup.select("tbody > tr")
    if not rows: rows = soup.select("tr") 

    new_posts = []

    for row in rows:
        cols = row.select("td")
        if len(cols) < 2: continue
        
        title_tag = cols[1].find("a")
        if not title_tag: continue

        title = title_tag.text.strip()
        href_content = title_tag.get('href', '')
        
        match = re.search(r"(\d+)", href_content)
        if match:
            doc_id = int(match.group(1))
            
            if doc_id > last_id:
                real_link = VIEW_URL_BASE + str(doc_id)
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link})

    if new_posts:
        print(f"✨ 총 {len(new_posts)}개의 새 공지 발견!")
        
        # 과거순 정렬 (옛날 글 -> 최신 글)
        new_posts.sort(key=lambda x: x['id'])
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        
        if webhook_url:
            for post in new_posts:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, post['title'], post['link'], post['id'], content)
                time.sleep(1)
        else:
            print("❌ WebHook URL 없음")

        # 파일 업데이트 (테스트 아닐 때만)
        if TEST_LAST_ID is None:
            max_id = max(p['id'] for p in new_posts)
            latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(max_id))
            print(f"💾 ID 업데이트 완료: {max_id}")
    else:
        print("💤 새 공지가 없습니다.")

if __name__ == "__main__":
    main()
