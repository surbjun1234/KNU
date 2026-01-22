import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드 설정]
# 0 = 최신글 2개 강제 전송 / None = 새 글이 있을 때만 전송
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
        # 학사공지 바로가기 주소 수정 반영
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
        "env_key": "WEBHOOK_ELECTRONIC"
    }
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# -----------------------------------------------------------
# [Gemini 2.5 Flash-Lite 요약 함수]
# -----------------------------------------------------------
def summarize_content(content):
    if not GEMINI_API_KEY:
        return "⚠️ 요약 실패: Gemini API 키가 설정되지 않았습니다."
    
    if len(content) < 150: # 내용이 너무 짧으면 요약 없이 반환
        return content

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt = f"아래 대학교 공지사항 본문을 핵심만 3줄 이내의 번호 리스트로 요약해줘. 날짜, 시간, 장소는 반드시 포함해줘:\n\n{content[:3500]}"
    
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 600, "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        res_json = response.json()
        summary = res_json['candidates'][0]['content']['parts'][0]['text']
        return summary.strip()
    except:
        return f"❗ 요약 생성 실패 (미리보기):\n{content[:300]}..."

# -----------------------------------------------------------
# [텍스트 정리 및 본문 추출]
# -----------------------------------------------------------
def clean_electronic_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(?<!^)(\s)([가-하]\.)', r'\n\n\2', text)
    text = re.sub(r'(?<!^)(\s)(\d+\))', r'\n\2', text)
    text = re.sub(r'(?<!^)(\s)([※-□o·])', r'\n\2', text)
    return text.strip()

def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        headers = {'User-Agent': 'Mozilla/5.0'}
        if "see.knu.ac.kr" in url: headers['Referer'] = "https://see.knu.ac.kr/"
        else: headers['Referer'] = "https://www.knu.ac.kr/"
        
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.select_one('.contentview') or soup.select_one('.board_cont') or soup.select_one('.view_con')
        
        if content_div:
            raw_text = content_div.get_text(separator=" ")
            return clean_electronic_text(raw_text)
        return "본문 내용을 찾을 수 없습니다."
    except:
        return "본문 로딩 실패"

# -----------------------------------------------------------
# [디스코드 전송 함수]
# -----------------------------------------------------------
def send_discord_message(webhook_url, board_name, title, link, doc_id, summary):
    if not webhook_url: return
    data = {
        "content": f"🔔 **{board_name} 업데이트**",
        "embeds": [{
            "title": title,
            "description": f"✨ **Gemini 요약**\n{summary}",
            "url": link,
            "color": 3447003,
            "footer": {"text": f"ID: {doc_id}"}
        }]
    }
    requests.post(webhook_url, json=data)

def main():
    requests.packages.urllib3.disable_warnings()
    print("--- [크롤러 시작] ---")
    
    for board in BOARDS:
        print(f"\n🔍 검사 중: {board['name']}")
        main_webhook_url = os.environ.get(board['env_key'])
        
        test_id = TEST_IDS.get(board['id_key'])
        is_test_mode = test_id is not None
        
        file_path = os.path.join(BASE_DIR, board['file'])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                last_id = int(f.read().strip() or 0)
        except: last_id = 0

        try:
            res = requests.get(board['url'], headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("tbody > tr") or soup.select("tr")
        except: continue

        new_posts = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 2: continue
            a_tag = row.find("a")
            if not a_tag: continue

            title = " ".join(a_tag.get_text().split())
            current_tag = None
            
            # 전자공학부 카테고리 태그 로직
            if board['id_key'] == 'electronic':
                title = re.sub(r'\[(.*?)\]', r'<\1>', title)
                title = re.sub(r"^(취업|장학|학적|수업|일반|행사|공지|국제|졸업)(?=\s|$)", r'<\1>', title)
                match = re.search(r'<(.*?)>', title)
                if match: current_tag = match.group(1)

            href = a_tag.get('href', '')
            doc_id = 0
            if board['type'] == 'see_knu':
                id_match = re.search(r"no=(\d+)", href) or re.findall(r"(\d+)", href)
                doc_id = int(id_match.group(1)) if hasattr(id_match, 'group') else int(max(id_match, key=int))
            else:
                id_match = re.search(r"(\d+)", href)
                if id_match: doc_id = int(id_match.group(1))

            if doc_id > last_id or is_test_mode:
                if not any(p['id'] == doc_id for p in new_posts):
                    new_posts.append({'id': doc_id, 'title': title, 'link': board['view_base']+str(doc_id), 'tag': current_tag})

        if new_posts:
            new_posts.sort(key=lambda x: x['id'])
            if is_test_mode: new_posts = new_posts[-2:]
            
            for post in new_posts:
                raw_content = get_post_content(post['link'])
                summary = summarize_content(raw_content) # AI 요약 실행
                
                # 1. 메인 채널 전송
                send_discord_message(main_webhook_url, board['name'], post['title'], post['link'], post['id'], summary)

                # 2. 전자공학부 세부 카테고리 전송
                if board['id_key'] == 'electronic' and post['tag']:
                    tag = post['tag']
                    env_key = f"WEBHOOK_ELEC_{'CLASS' if '수업' in tag else 'RECORD' if '학적' in tag else 'JOB' if '취업' in tag else 'SCHOLARSHIP' if '장학' in tag else 'EVENT' if '행사' in tag else 'ETC' if '기타' in tag else ''}"
                    sub_webhook = os.environ.get(env_key)
                    if sub_webhook:
                        send_discord_message(sub_webhook, f"{board['name']} ({tag})", post['title'], post['link'], post['id'], summary)

            if not is_test_mode:
                with open(file_path, 'w', encoding='utf-8') as f: f.write(str(max(p['id'] for p in new_posts)))
        else:
            print("💤 새 글 없음")

if __name__ == "__main__":
    main()
