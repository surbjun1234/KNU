import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [설정] 0 = 테스트용(무조건 전송) / None = 실사용(새 글만 전송)
# -----------------------------------------------------------
TEST_IDS = {
    "general": 0,    
    "academic": 0,    
    "electronic": 0   
}

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
    
    if len(content) < 100: return content

    # Gemini 2.5 Flash-Lite 모델 적용 URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt = f"아래 대학교 공지사항 본문을 학생들이 보기 편하게 핵심만 4줄 이내 번호 리스트로 요약해줘. 날짜와 장소는 반드시 포함해:\n\n{content[:3000]}"
    
    data = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 600, "temperature": 0.2}}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        res_json = response.json()
        return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        return f"❗ 요약 생성 실패 (미리보기):\n{content[:300]}..."

# -----------------------------------------------------------
# [본문 추출 및 정리]
# -----------------------------------------------------------
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_post_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        res.encoding = 'UTF-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 영역 탐색
        content_div = soup.select_one('.contentview') or soup.select_one('.board_cont') or soup.select_one('.view_con')
        if not content_div: return "본문 내용을 찾을 수 없습니다."
        
        return clean_text(content_div.get_text(separator=" "))
    except:
        return "본문 로딩 실패"

# -----------------------------------------------------------
# [디스코드 전송]
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
    res = requests.post(webhook_url, json=data)
    if res.status_code in [200, 204]:
        print(f"   🚀 전송 성공: {title[:20]}...")
    else:
        print(f"   ❌ 전송 실패: {res.status_code}")

# -----------------------------------------------------------
# [메인 로직]
# -----------------------------------------------------------
def main():
    print("--- [크롤러 + Gemini 요약 시작] ---")
    requests.packages.urllib3.disable_warnings()

    for board in BOARDS:
        print(f"\n🔍 {board['name']} 확인 중...")
        main_webhook = os.environ.get(board['env_key'])
        
        # ID 파일 읽기
        file_path = os.path.join(BASE_DIR, board['file'])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                last_id = int(f.read().strip() or 0)
        except: last_id = 0

        # 게시판 접속
        try:
            res = requests.get(board['url'], headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
            res.encoding = 'UTF-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("tbody tr")
        except Exception as e:
            print(f"   🚨 접속 에러: {e}"); continue

        new_posts = []
        for row in rows:
            a_tag = row.find("a")
            if not a_tag: continue
            
            title = " ".join(a_tag.get_text().split())
            href = a_tag.get('href', '')
            
            # ID 추출
            doc_id = 0
            if board['type'] == 'see_knu':
                match = re.search(r"fidx=(\d+)", href) or re.search(r"no=(\d+)", href)
                if match: doc_id = int(match.group(1))
            else:
                match = re.search(r"(\d+)", href)
                if match: doc_id = int(match.group(1))

            # 새 글 판정
            if doc_id > 0 and (TEST_IDS[board['id_key']] == 0 or doc_id > last_id):
                if not any(p['id'] == doc_id for p in new_posts):
                    # 전자공학부 태그 추출
                    tag = None
                    if board['id_key'] == 'electronic':
                        title = re.sub(r'\[(.*?)\]', r'<\1>', title)
                        t_match = re.search(r'<(.*?)>', title)
                        if t_match: tag = t_match.group(1)
                    
                    new_posts.append({'id': doc_id, 'title': title, 'link': board['view_base']+str(doc_id), 'tag': tag})

        if new_posts:
            new_posts.sort(key=lambda x: x['id'])
            # 테스트 모드 시 최신 2개만
            if TEST_IDS[board['id_key']] == 0: new_posts = new_posts[-2:]

            for post in new_posts:
                content = get_post_content(post['link'])
                summary = summarize_content(content)
                
                # 1. 메인 채널 전송
                send_discord_message(main_webhook, board['name'], post['title'], post['link'], post['id'], summary)
                
                # 2. 전자공학부 세부 카테고리 전송
                if board['id_key'] == 'electronic' and post['tag']:
                    tag = post['tag']
                    sub_key = None
                    if "수업" in tag: sub_key = "WEBHOOK_ELEC_CLASS"
                    elif "학적" in tag: sub_key = "WEBHOOK_ELEC_RECORD"
                    elif "취업" in tag: sub_key = "WEBHOOK_ELEC_JOB"
                    elif "장학" in tag: sub_key = "WEBHOOK_ELEC_SCHOLARSHIP"
                    elif "행사" in tag: sub_key = "WEBHOOK_ELEC_EVENT"
                    elif "기타" in tag: sub_key = "WEBHOOK_ELEC_ETC"
                    
                    if sub_key:
                        sub_webhook = os.environ.get(sub_key)
                        send_discord_message(sub_webhook, f"{board['name']} ({tag})", post['title'], post['link'], post['id'], summary)
                
                time.sleep(1)

            # 최신 ID 저장
            if TEST_IDS[board['id_key']] is None:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(max(p['id'] for p in new_posts)))
        else:
            print("   💤 새 글 없음")

if __name__ == "__main__":
    main()
