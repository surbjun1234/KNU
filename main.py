import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드 설정]
# 0 = 최신글 2개 강제 전송 / None = 새 글만 전송
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
        "view_base": "https://see.knu.ac.kr/content/board/notice.html?pg=vv&gtid=notice&opt=&sword=&page=1&f_opt_1=&fidx=",
        "file": "latest_id_electronic.txt",
        "type": "see_knu",
        "env_key": "WEBHOOK_ELECTRONIC"
    }
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# -----------------------------------------------------------
# [제미나이 요약 함수]
# -----------------------------------------------------------
def summarize_content(content):
    if not GEMINI_API_KEY:
        return "⚠️ 요약 실패: API 키가 설정되지 않았습니다."
    
    # 본문이 너무 짧으면 요약 생략
    if len(content) < 100:
        return content

    # Gemini 2.0 Flash-Lite API 호출 주소
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-preview-02-05:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    prompt = f"""
    아래는 대학교 공지사항 본문이야. 
    학생들이 바쁘니까 핵심 내용을 3줄 이내의 번호 리스트 형태로 요약해줘.
    중요한 날짜나 장소는 반드시 포함해줘.
    
    [본문]
    {content[:3000]}  # 텍스트가 너무 길면 잘라서 보냄
    """
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "maxOutputTokens": 500,
            "temperature": 0.2 # 정확도를 위해 낮게 설정
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        res_json = response.json()
        summary = res_json['candidates'][0]['content']['parts'][0]['text']
        return summary.strip()
    except Exception as e:
        return f"⚠️ 요약 생성 중 오류 발생 (본문 미리보기로 대체됩니다.)\n\n{content[:300]}"

# -----------------------------------------------------------
# [본문 정리 함수]
# -----------------------------------------------------------
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = None
        candidates = ['.contentview', '#contentview', '.board_cont', '.board-view', '.view_con', '.content', '.tbl_view']
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div: break
        
        if content_div:
            if "see.knu.ac.kr" in url:
                raw_text = content_div.get_text(separator=" ")
                return clean_electronic_text(raw_text)
            else:
                raw_text = content_div.get_text(separator="\n")
                cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                return '\n'.join(cleaned_lines)
        return "본문을 읽을 수 없습니다."
    except:
        return "본문 로딩 실패"

# -----------------------------------------------------------
# [디스코드 전송 함수]
# -----------------------------------------------------------
def send_discord_message(webhook_url, board_name, title, link, doc_id, summary_content):
    if not webhook_url: return

    data = {
        "content": f"🔔 **{board_name} 업데이트**",
        "embeds": [{
            "title": title,
            "description": f"✨ **AI 핵심 요약**\n{summary_content}",
            "url": link,
            "color": 3447003,
            "footer": {"text": f"{board_name} • ID: {doc_id}"}
        }]
    }
    requests.post(webhook_url, json=data)

def main():
    print("--- [크롤러 + Gemini 요약 시작] ---")
    for board in BOARDS:
        webhook_url = os.environ.get(board['env_key'])
        test_id = TEST_IDS.get(board['id_key'])
        is_test_mode = test_id is not None
        
        file_path = os.path.join(BASE_DIR, board['file'])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                last_id = int(f.read().strip() or 0)
        except:
            last_id = 0

        # 크롤링 로직 (생략 - 기존과 동일)
        # ... (Soup으로 게시글 리스트 가져오기) ...
        # (new_posts 리스트 생성)

        # 전송 루프 예시 (중요 부분만 표시)
        for post in new_posts:
            full_content = get_post_content(post['link'])
            # ★ 제미나이 요약 호출 ★
            summary = summarize_content(full_content)
            
            # 메인 전송
            send_discord_message(webhook_url, board['name'], post['title'], post['link'], post['id'], summary)
            
            # 전자공학부 세부 채널 전송 로직 (생략 - 기존과 동일)
            # ...
            
    # ID 업데이트 (생략)
