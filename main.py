import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드]
# 테스트가 끝나면 모두 None으로 설정하세요.
# -----------------------------------------------------------
TEST_IDS = {
    "general": None,    
    "academic": None,    
    "electronic": None   
}

# -----------------------------------------------------------
# [게시판 설정]
# -----------------------------------------------------------
BOARDS = [
    {
        "id_key": "general",
        "name": "📢 전체공지",
        "url": "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67",
        "view_base": "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no=",
        "file": "latest_id_general.txt",
        "type": "knu_general",
        "env_key": "WEBHOOK_GENERAL"
    },
    {
        "id_key": "academic",
        "name": "🎓 학사공지",
        "url": "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42",
        "view_base": "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?search_type=&search_text=&popupDeco=&note_div=row&menu_idx=42&bbs_cde=stu_812&bltn_no=",
        "file": "latest_id_academic.txt",
        "type": "knu_academic",
        "env_key": "WEBHOOK_ACADEMIC"
    },
    {
        "id_key": "electronic",
        "name": "⚡ 전자공학부",
        "url": "https://see.knu.ac.kr/content/board/notice.html",
        "view_base": "https://see.knu.ac.kr/content/board/notice.html",
        "file": "latest_id_electronic.txt",
        "type": "see_knu",
        "env_key": "WEBHOOK_ELECTRONIC"
    }
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [헤더]
# -----------------------------------------------------------
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        headers = COMMON_HEADERS.copy()
        
        if "see.knu.ac.kr" in url:
            headers['Referer'] = "https://see.knu.ac.kr/"
        else:
            headers['Referer'] = "https://www.knu.ac.kr/"
        
        response = requests.get(url, headers=headers, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        candidates = ['.contentview', '.board_cont', '.board-view', '.view_con', '.content', '.tbl_view']
        
        content_div = None
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div: break
        
        if not content_div:
            tds = soup.select("td")
            for td in tds:
                if len(td.get_text(strip=True)) > 200: 
                    content_div = td
                    break

        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"본문 로딩 실패: {e}"

def send_discord_message(webhook_url, board_name, title, link, doc_id, original_content):
    clean = original_content[:500] + ("..." if len(original_content) > 500 else "")
    if not clean.strip():
        clean = "(본문 없음 혹은 이미지)"

    data = {
        "content": f"🔔 **{board_name} 업데이트**",
        "embeds": [{
            "title": title,
            "description": f"**[본문 미리보기]**\n{clean}",
            "url": link,
            "color": 3447003,
            "footer": {"text": f"{board_name} • ID: {doc_id}"}
        }]
    }
    try:
        requests.post(webhook_url, json=data)
        print(f"🚀 [전송 성공] {title}")
    except:
        pass

def main():
    requests.packages.urllib3.disable_warnings()
    print("--- [크롤러 시작] ---")
    
    for board in BOARDS:
        print(f"\n🔍 검사 중: {board['name']}")
        
        webhook_url = os.environ.get(board['env_key'])
        if not webhook_url:
            print(f"   🚨 웹훅 미설정. 건너뜀.")
            continue

        # 1. ID 로드
        test_id = TEST_IDS.get(board['id_key'])
        if test_id is not None:
            last_id = int(test_id)
            print(f"   ⚠️ [테스트] 최신글 1개만 가져옵니다.")
        else:
            file_path = os.path.join(BASE_DIR, board['file'])
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    last_id = int(content) if content else 0
            except FileNotFoundError:
                last_id = 0
            print(f"   📂 읽어온 ID: {last_id}")

        # 2. 접속
        try:
            headers = COMMON_HEADERS.copy()
            headers['Referer'] = board['url']
            response = requests.get(board['url'], headers=headers, verify=False)
            response.encoding = 'UTF-8'
            soup = BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"   🚨 접속 실패: {e}")
            continue

        rows = soup.select("tbody > tr")
        if not rows: rows = soup.select("tr") 

        new_posts = []

        for row in rows:
            cols = row.select("td")
            if len(cols) < 2: continue
            
            title_tag = row.find("a")
            if not title_tag: continue

            # 제목 정리
            title = title_tag.text.strip()
            title = re.sub(r'\[(.*?)\]', r'<\1>', title)

            href = title_tag.get('href', '')
            doc_id = 0
            real_link = ""
            
            try:
                # A. 전자공학부 (ID 추출 로직 개선)
                if board['type'] == 'see_knu':
                    # 1순위: no=숫자
                    match = re.search(r"no=(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                    else:
                        # 2순위: 링크에 있는 '가장 큰' 숫자 (페이지 번호 등 회피)
                        nums = re.findall(r"(\d+)", href)
                        if nums:
                            # 숫자 리스트 중 가장 큰 값을 ID로 사용
                            doc_id = max([int(n) for n in nums])
                    
                    if doc_id > 0:
                        if href.startswith('?'):
                            real_link = board['view_base'] + href
                        else:
                            real_link = urljoin(board['view_base'], href)

                # B. 학사공지
                elif board['type'] == 'knu_academic':
                    numbers = re.findall(r"(\d+)", href)
                    for num in numbers:
                        if len(num) > 10: 
                            doc_id = int(num)
                            real_link = f"{board['view_base']}{doc_id}"
                            break

                # C. 전체공지
                else: 
                    match = re.search(r"(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                        real_link = board['view_base'] + str(doc_id)

            except Exception:
                continue

            # 새 글 판단
            if doc_id > 0 and doc_id > last_id:
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link})

        # 4. 전송 및 저장
        if new_posts:
            new_posts.sort(key=lambda x: x['id'])
            
            if test_id is not None:
                new_posts = new_posts[-1:]
            
            for post in new_posts:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, board['name'], post['title'], post['link'], post['id'], content)
                time.sleep(1)

            # ★ ID 저장 (가장 중요)
            if test_id is None:
                max_id = max(p['id'] for p in new_posts)
                file_path = os.path.join(BASE_DIR, board['file'])
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(max_id))
                # 디버깅: 실제로 저장된 번호를 출력
                print(f"   💾 [저장 완료] 파일: {board['file']} / ID: {max_id}")
            else:
                print("   🚫 [테스트] 파일 저장 건너뜀")
        else:
            print("   💤 새 글 없음")

if __name__ == "__main__":
    main()
