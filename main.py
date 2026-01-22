import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드 설정]
# 0 = 최신글 2개 강제 전송 (파일 저장 안 함) -> 테스트용
# None = 새 글이 있을 때만 전송 (파일 저장 함) -> 실사용
# -----------------------------------------------------------
TEST_IDS = {
    "general": 0,    
    "academic": 0,    
    "electronic": 0   
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
        "view_base": "https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=",
        "file": "latest_id_electronic.txt",
        "type": "see_knu",
        "env_key": "WEBHOOK_ELECTRONIC" # 메인 채널 (전체 알림)
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

def clean_electronic_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+\.\s+', '. ', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'(?<!^)(\s)([가-하]\.)', r'\n\n\2', text)
    text = re.sub(r'(?<!^)(\s)(\d+\))', r'\n\2', text)
    text = re.sub(r'(?<!^)(\s)([※-□o·])', r'\n\2', text)
    return text.strip()

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

        content_div = None
        candidates = ['.contentview', '#contentview', '.board_cont', '.board-view', '.view_con', '.content', '.tbl_view']
        
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div: break
        
        if not content_div:
            potential_areas = []
            for tag in soup.find_all(['div', 'td']):
                text_len = len(tag.get_text(strip=True))
                if text_len > 50: 
                    potential_areas.append((text_len, tag))
            if potential_areas:
                potential_areas.sort(key=lambda x: x[0], reverse=True)
                content_div = potential_areas[0][1]

        if content_div:
            if "see.knu.ac.kr" in url:
                raw_text = content_div.get_text(separator=" ")
                return clean_electronic_text(raw_text)
            else:
                raw_text = content_div.get_text(separator="\n")
                cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                return '\n'.join(cleaned_lines)
            
        return "본문 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"본문 로딩 실패: {e}"

def send_discord_message(webhook_url, board_name, title, link, doc_id, original_content):
    if not webhook_url: return

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
        print(f"   🚀 [전송 성공] {title} -> (웹훅 끝자리: {webhook_url[-5:]})")
    except:
        print(f"   ❌ [전송 실패] 웹훅 URL을 확인해주세요.")

def main():
    requests.packages.urllib3.disable_warnings()
    print("--- [크롤러 시작] ---")
    
    for board in BOARDS:
        print(f"\n🔍 검사 중: {board['name']}")
        
        # 메인 웹훅
        main_webhook_url = os.environ.get(board['env_key'])
        
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
            raw_title = title_tag.get_text(separator=" ", strip=True)
            title = " ".join(raw_title.split())
            
            current_tag = None
            
            # [전자공학부 태그 추출 로직]
            if board['id_key'] == 'electronic':
                # 1. [취업] -> <취업>
                title = re.sub(r'\[(.*?)\]', r'
