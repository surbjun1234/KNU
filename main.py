import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 설정]
# -----------------------------------------------------------
TEST_LAST_ID = 1336480 

# -----------------------------------------------------------
# [설정] URL
# -----------------------------------------------------------
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        # 헤더를 함수 안에서도 동일하게 사용
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }
        response = requests.get(url, headers=headers, verify=False)
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
    
    print("--- [크롤러 시작 (보안 우회 시도)] ---")

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

    # 1. 헤더 강화 (진짜 크롬 브라우저처럼 보이기)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://www.knu.ac.kr/',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # 세션 사용 (쿠키 유지 등을 위해)
        session = requests.Session()
        response = session.get(LIST_URL, headers=headers, verify=False)
        response.encoding = 'UTF-8'
        
        print(f"📡 응답 코드: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"🚨 접속 실패: {e}")
        return

    # 2. 선택자(Selector) 유연화
    # tbody > tr 이 안 먹힐 경우를 대비해 그냥 tr을 다 찾고 필터링
    rows = soup.select("tbody > tr")
    if not rows:
        print("⚠️ 'tbody > tr'로 행을 못 찾음. 'tr' 전체 검색 시도...")
        rows = soup.select("tr")

    print(f"🔍 총 {len(rows)}개의 행을 검사합니다.")

    # [디버깅] 만약 0개라면 HTML 내용 일부 출력 (차단 여부 확인)
    if len(rows) == 0:
        print("\n🚨 [심각] 게시글을 하나도 못 찾았습니다. 가져온 HTML 내용은 다음과 같습니다:")
        print("----------------------------------------------------------------")
        # HTML의 제목과 앞부분 500자만 출력
        print(f"Title: {soup.title.text if soup.title else 'No Title'}")
        print(soup.prettify()[:1000]) 
        print("----------------------------------------------------------------")
        return

    new_posts = []

    for i, row in enumerate(rows):
        cols = row.select("td")
        # 데이터가 없는 행(헤더 등)은 건너뜀
        if len(cols) < 2: continue
        
        # 화면 번호 확인
        visible_num = cols[0].text.strip()
        
        # 제목 태그 찾기
        title_tag = cols[1].find("a")
        if not title_tag: continue # 제목 링크가 없으면 건너뜀

        title = title_tag.text.strip()
        href_content = title_tag.get('href', '')
        
        # URL 고유번호 추출
        match = re.search(r"(\d+)", href_content)
        
        if match:
            doc_id = int(match.group(1))
            
            # 봇 로그: 현재 보고 있는 글 출력
            print(f"[{i}] 번호:{doc_id} | 제목:{title[:10]}...", end=" ")

            if doc_id > last_id:
                print("✅ [새 글]")
                real_link = VIEW_URL_BASE + str(doc_id)
                new_posts.append({
                    'id': doc_id,
                    'title': title,
                    'link': real_link
                })
            else:
                print("⏹️ [옛날 글]")
        else:
            # 번호 추출 실패 (단순 링크이거나 공지)
            pass

    print(f"\n✨ 발견된 새 공지: {len(new_posts)}개")

    if new_posts:
        new_posts.sort(key=lambda x: x['id'])
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        
        if webhook_url:
            for post in new_posts:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, post['title'], post['link'], post['id'], content)
                time.sleep(1)
        else:
            print("❌ WebHook URL 없음")

        if TEST_LAST_ID is None:
            max_id = max(p['id'] for p in new_posts)
            latest_id_path = os.path.join(BASE_DIR, 'latest_id.txt')
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(max_id))
            print(f"💾 업데이트 완료: {max_id}")
    else:
        print("💤 전송할 공지가 없습니다.")

if __name__ == "__main__":
    main()
