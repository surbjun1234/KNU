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
        "env_key": "WEBHOOK_ELECTRONIC" # 메인 채널
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
        print(f"   ❌ [전송 실패] 웹훅 오류")

def main():
    requests.packages.urllib3.disable_warnings()
    print("--- [크롤러 시작] ---")
    
    for board in BOARDS:
        print(f"\n🔍 검사 중: {board['name']}")
        
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
                title = re.sub(r'\[(.*?)\]', r'<\1>', title)
                
                # 2. 맨 앞 단어가 카테고리일 경우 < > 씌우기
                categories = r"^(취업|장학|학적|수업|일반|행사|공지|국제|졸업)(?=\s|$)"
                title = re.sub(categories, r'<\1>', title)
                
                # 3. 태그 추출
                match = re.search(r'<(.*?)>', title)
                if match:
                    current_tag = match.group(1)
            
            href = title_tag.get('href', '')
            doc_id = 0
            real_link = ""
            
            try:
                if board['type'] == 'see_knu':
                    match = re.search(r"no=(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                    else:
                        nums = re.findall(r"(\d+)", href)
                        if nums: doc_id = max([int(n) for n in nums])
                    
                    if doc_id > 0:
                        real_link = f"{board['view_base']}{doc_id}"

                elif board['type'] == 'knu_academic':
                    numbers = re.findall(r"(\d+)", href)
                    for num in numbers:
                        if len(num) > 10: 
                            doc_id = int(num)
                            real_link = f"{board['view_base']}{doc_id}"
                            break
                else: 
                    match = re.search(r"(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                        real_link = board['view_base'] + str(doc_id)

            except Exception:
                continue

            if doc_id > 0 and doc_id > last_id:
                if any(post['id'] == doc_id for post in new_posts):
                    continue
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link, 'tag': current_tag})

        if new_posts:
            new_posts.sort(key=lambda x: x['id'])
            
            if is_test_mode:
                new_posts = new_posts[-2:]
                print(f"   ⚠️ [테스트] 발견된 글 중 최신 {len(new_posts)}개를 전송합니다.")
            
            for post in new_posts:
                content = get_post_content(post['link'])
                
                # 1. 메인 웹훅 전송
                if main_webhook_url:
                    send_discord_message(main_webhook_url, board['name'], post['title'], post['link'], post['id'], content)
                else:
                    print(f"   ❌ [설정 오류] {board['env_key']} 미설정")

                # 2. 전자공학부 세부 전송 로직
                if board['id_key'] == 'electronic':
                    tag = post['tag']
                    specific_webhook = None
                    env_var_name = ""

                    # 디버그 로그
                    if tag:
                        print(f"   🔎 [태그 감지] '{tag}' -> 세부 채널 전송 시도")
                    else:
                        print(f"   💨 [태그 없음] '{post['title']}' -> 전체방에만 전송")

                    if tag and "수업" in tag:
                        env_var_name = "WEBHOOK_ELEC_CLASS"
                    elif tag and "학적" in tag:
                        env_var_name = "WEBHOOK_ELEC_RECORD"
                    elif tag and "취업" in tag:
                        env_var_name = "WEBHOOK_ELEC_JOB"
                    elif tag and "장학" in tag:
                        env_var_name = "WEBHOOK_ELEC_SCHOLARSHIP"
                    elif tag and "행사" in tag:
                        env_var_name = "WEBHOOK_ELEC_EVENT"
                    elif tag and "기타" in tag:
                        env_var_name = "WEBHOOK_ELEC_ETC"
                    
                    if env_var_name:
                        specific_webhook = os.environ.get(env_var_name)
                        if specific_webhook:
                            send_discord_message(specific_webhook, f"{board['name']} ({tag})", post['title'], post['link'], post['id'], content)
                        else:
                            print(f"   ⚠️ [설정 주의] 태그 '{tag}' 감지됨, 그러나 Secrets에 '{env_var_name}' 없음")

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
