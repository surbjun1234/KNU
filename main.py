import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드]
# 0 = 최신글 2개 강제 전송 (파일 저장 안 함)
# None = 새 글만 전송 (파일 저장 함)
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
        # ★ 수정됨: 링크를 직접 조립하기 위한 기본 주소
        "view_base": "https://see.knu.ac.kr/content/board/notice.html?f=view&no=",
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
            # 1. 텍스트 추출 (줄바꿈 포함)
            text = content_div.get_text(separator="\n", strip=True)
            
            # ★ [공백 제거 로직 강화]
            # 연속된 줄바꿈이 3번 이상(\n\n\n...) 나오면 2번(\n\n)으로 줄임
            # 너무 휑한 공간을 없애줍니다.
            text = re.sub(r'\n\s*\n+', '\n\n', text)
            
            # 본문 시작 부분의 불필요한 공백/줄바꿈 제거
            text = text.lstrip()
            
            return text
            
        return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"본문 로딩 실패: {e}"

def send_discord_message(webhook_url, board_name, title, link, doc_id, original_content):
    # 미리보기 500자
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

        # 1. ID 로드 & 테스트 모드
        test_id = TEST_IDS.get(board['id_key'])
        is_test_mode = test_id is not None
        
        if is_test_mode:
            last_id = 0
            print(f"   ⚠️ [테스트 모드] 최근 게시글 2개를 강제 전송합니다.")
        else:
            file_path = os.path.join(BASE_DIR, board['file'])
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    last_id = int(content) if content else 0
            except FileNotFoundError:
                last_id = 0
            print(f"   📂 저장된 ID: {last_id}")

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

            # 제목 정리: [학적] -> <학적>
            title = title_tag.text.strip()
            title = re.sub(r'\[(.*?)\]', r'<\1>', title)

            href = title_tag.get('href', '')
            doc_id = 0
            real_link = ""
            
            try:
                # A. 전자공학부
                if board['type'] == 'see_knu':
                    match = re.search(r"no=(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                    else:
                        nums = re.findall(r"(\d+)", href)
                        if nums: doc_id = max([int(n) for n in nums])
                    
                    if doc_id > 0:
                        # ★ [링크 수정] 
                        # href를 믿지 않고, ID를 사용하여 주소를 '새로' 만듭니다.
                        real_link = f"{board['view_base']}{doc_id}"

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

            if doc_id > 0 and doc_id > last_id:
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link})

        # 4. 전송 및 저장
        if new_posts:
            new_posts.sort(key=lambda x: x['id'])
            
            if is_test_mode:
                new_posts = new_posts[-2:]
                print(f"   ⚠️ [테스트] 발견된 글 중 최신 {len(new_posts)}개를 전송합니다.")
            
            for post in new_posts:
                content = get_post_content(post['link'])
                send_discord_message(webhook_url, board['name'], post['title'], post['link'], post['id'], content)
                time.sleep(1)

            if not is_test_mode:
                max_id = max(p['id'] for p in new_posts)
                with open(os.path.join(BASE_DIR, board['file']), 'w', encoding='utf-8') as f:
                    f.write(str(max_id))
                print(f"   💾 ID 업데이트: {max_id}")
            else:
                print("   🚫 [테스트] 파일 저장 건너뜁니다.")
        else:
            print("   💤 새 글 없음")

if __name__ == "__main__":
    main()
