import requests
from bs4 import BeautifulSoup
import os
import re
import time

# -----------------------------------------------------------
# [테스트 모드 설정] ★여기를 수정하세요★
# 테스트하고 싶은 게시판의 None을 '기준 번호(숫자)'로 바꾸세요.
# 예: "general": 1336480
# 테스트가 끝나면 다시 모두 None으로 돌려놓으세요 (자동 모드).
# -----------------------------------------------------------
TEST_IDS = {
    "general": None,      # 📢 전체공지 (doc_no 기준)
    "academic": None,     # 🎓 학사공지 (bltn_no 기준)
    "electronic": None    # ⚡ 전자공학부 (no 기준)
}

# -----------------------------------------------------------
# [게시판 설정]
# -----------------------------------------------------------
BOARDS = [
    {
        "id_key": "general", # TEST_IDS의 키와 일치
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
        "view_base": "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42",
        "file": "latest_id_academic.txt",
        "type": "knu_academic",
        "env_key": "WEBHOOK_ACADEMIC"
    },
    {
        "id_key": "electronic",
        "name": "⚡ 전자공학부",
        "url": "https://see.knu.ac.kr/content/board/notice.html",
        "view_base": "https://see.knu.ac.kr/content/board/notice.html?f=view&no=",
        "file": "latest_id_electronic.txt",
        "type": "see_knu",
        "env_key": "WEBHOOK_ELECTRONIC"
    }
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [헤더] 보안 우회용
# -----------------------------------------------------------
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# -----------------------------------------------------------
# [기능 1] 본문 크롤링
# -----------------------------------------------------------
def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        headers = COMMON_HEADERS.copy()
        
        # 전자공학부는 Referer가 자기 자신이어야 잘 됨
        if "see.knu.ac.kr" in url:
            headers['Referer'] = "https://see.knu.ac.kr/"
        else:
            headers['Referer'] = "https://www.knu.ac.kr/"
        
        response = requests.get(url, headers=headers, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 본문 찾기 후보군 (경북대 본관 + 전자공학부 스타일)
        # .board-view : 전자공학부 스타일
        # .board_cont : 경북대 본관 스타일
        candidates = ['.board_cont', '.board-view', '.view_con', '.content', '.tbl_view', '.board_view_con']
        
        content_div = None
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div: break
        
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        print(f"   본문 크롤링 에러: {e}")
        return "본문 로딩 실패"

# -----------------------------------------------------------
# [기능 2] 디스코드 전송
# -----------------------------------------------------------
def send_discord_message(webhook_url, board_name, title, link, doc_id, original_content):
    # 본문 미리보기 (500자 제한)
    clean = original_content[:500] + ("..." if len(original_content) > 500 else "")
    
    # 내용이 너무 없으면 안내 메시지
    if not clean.strip():
        clean = "(본문 내용이 없거나 이미지를 포함한 게시글입니다)"

    description = f"**[본문 미리보기]**\n{clean}"
    footer_text = f"{board_name} • ID: {doc_id}"

    data = {
        "content": f"🔔 **{board_name} 업데이트**",
        "embeds": [{
            "title": title,
            "description": description,
            "url": link,
            "color": 3447003, # Blue
            "footer": {"text": footer_text}
        }]
    }
    
    try:
        requests.post(webhook_url, json=data)
        print(f"🚀 [전송 성공] {title}")
    except Exception as e:
        print(f"❌ [전송 실패] {e}")

# -----------------------------------------------------------
# [메인] 로직
# -----------------------------------------------------------
def main():
    requests.packages.urllib3.disable_warnings()
    print("--- [통합 공지 크롤러 시작] ---")
    
    for board in BOARDS:
        print(f"\n🔍 검사 중: {board['name']}")
        
        # 1. 테스트 ID 확인
        test_id = TEST_IDS.get(board['id_key'])
        
        if test_id is not None:
            last_id = int(test_id)
            print(f"   ⚠️ [테스트 모드] 강제 기준 ID: {last_id}")
        else:
            # 파일에서 읽기
            file_path = os.path.join(BASE_DIR, board['file'])
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    last_id = int(content) if content else 0
            except FileNotFoundError:
                last_id = 0
            print(f"   📂 저장된 ID (파일): {last_id}")

        # 2. 웹훅 URL 확인
        webhook_url = os.environ.get(board['env_key'])
        if not webhook_url:
            print(f"   🚨 경고: 웹훅({board['env_key']}) 없음. 건너뜀.")
            continue

        # 3. 목록 접속
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
            
            # 제목 찾기 (a 태그)
            title_tag = cols[1].find("a") 
            if not title_tag: 
                # 전자공학부 등 구조가 다를 경우를 대비해 row 전체 검색
                title_tag = row.find("a")
            
            if not title_tag: continue

            title = title_tag.text.strip()
            href = title_tag.get('href', '')

            # 4. ID 추출 및 링크 생성
            doc_id = 0
            real_link = ""
            
            try:
                # A. 전자공학부 (no=...)
                if board['type'] == 'see_knu':
                    match = re.search(r"no=(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                        real_link = board['view_base'] + str(doc_id)

                # B. 학사공지 (bltn_no, inpt_nbr)
                elif board['type'] == 'knu_academic':
                    numbers = re.findall(r"(\d+)", href)
                    if numbers:
                        doc_id = int(numbers[0])
                        # 링크 조립 (inpt_nbr이 있으면 같이 넣음)
                        if len(numbers) >= 2:
                             real_link = f"{board['view_base']}&btin.bltn_no={numbers[0]}&btin.inpt_nbr={numbers[1]}"
                        else:
                             real_link = f"{board['view_base']}&btin.bltn_no={numbers[0]}"

                # C. 전체공지 (doc_no)
                else: 
                    match = re.search(r"(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                        real_link = board['view_base'] + str(doc_id)

            except Exception:
                continue

            # 5. 새 글 판단
            if doc_id > 0 and doc_id > last_id:
                print(f"   ✅ 새 글 발견: {doc_id} - {title}")
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link})

        # 6. 전송 및 저장
        if new_posts:
            # 과거순 정렬
            new_posts.sort(key=lambda x: x['id'])
            
            for post in new_posts:
                # 본문 긁어오기
                content = get_post_content(post['link'])
                # 디스코드 전송
                send_discord_message(webhook_url, board['name'], post['title'], post['link'], post['id'], content)
                time.sleep(1)

            # ★ 중요: 테스트 모드가 아닐 때만 파일 업데이트
            if test_id is None:
                max_id = max(p['id'] for p in new_posts)
                file_path = os.path.join(BASE_DIR, board['file'])
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(max_id))
                print(f"   💾 파일 업데이트 완료: {max_id}")
            else:
                print("   ⚠️ [테스트 모드] 파일 저장을 건너뜁니다.")
        else:
            print("   💤 새 글 없음")

if __name__ == "__main__":
    main()
