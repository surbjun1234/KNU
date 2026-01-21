import requests
from bs4 import BeautifulSoup
import os
import re
import time
import google.generativeai as genai

# -----------------------------------------------------------
# [설정] URL 및 테스트 옵션
# -----------------------------------------------------------
# 테스트가 끝나면 None으로 설정하여 자동 모드로 사용하세요.
TEST_LAST_ID = 1336485 
# TEST_LAST_ID = 1336480 

LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL_BASE = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action?btin.bbs_cde=1&btin.appl_no=000000&menu_idx=67&btin.doc_no="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------
# [헤더] 경북대 보안 우회용 (목록/본문 공통 사용)
# -----------------------------------------------------------
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Referer': LIST_URL,
    'Upgrade-Insecure-Requests': '1'
}

# -----------------------------------------------------------
# [기능 1] Gemini 요약 (요청하신 모델 적용)
# -----------------------------------------------------------
def get_gemini_summary(text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None 

    try:
        genai.configure(api_key=api_key)
        
        # ★ 요청하신 모델명 적용
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        prompt = f"""
        너는 대학생을 위한 공지사항 알리미야. 
        아래 대학교 공지사항 내용을 읽고 핵심만 뽑아서 3줄 이내로 명확하게 요약해줘.
        인사말이나 부가 설명 없이 요약 내용만 한국어로 출력해.
        
        [공지 내용]
        {text[:10000]} 
        """
        
        # API 호출
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"⚠️ Gemini 요약 실패 (모델명/키 확인 필요): {e}")
        # 에러 발생 시 None을 반환하여 원본 미리보기로 대체
        return None 

# -----------------------------------------------------------
# [기능 2] 본문 크롤링
# -----------------------------------------------------------
def get_post_content(url):
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(url, headers=COMMON_HEADERS, verify=False)
        response.encoding = 'UTF-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 확인된 클래스 (.board_cont) 최우선 검색
        candidates = ['.board_cont', '.board_view_con', '.view_con', '.bbs_view', '.content']
        content_div = None
        for selector in candidates:
            content_div = soup.select_one(selector)
            if content_div: break
        
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return "" # 본문 없음
    except Exception as e:
        print(f"크롤링 에러: {e}")
        return ""

# -----------------------------------------------------------
# [기능 3] 디스코드 전송
# -----------------------------------------------------------
def send_discord_message(webhook_url, title, link, doc_id, summary, original_content):
    # 요약 성공 여부에 따라 내용 구성
    if summary:
        description = f"**[AI 3줄 요약]**\n{summary}"
        footer_text = f"Gemini 2.5 Flash Lite • Doc ID: {doc_id}"
    else:
        # 요약 실패 시 원본 500자 미리보기
        clean_content = original_content[:500] + ("..." if len(original_content) > 500 else "")
        description = f"**[본문 미리보기]**\n{clean_content}"
        footer_text = f"원본 미리보기 • Doc ID: {doc_id}"

    data = {
        "content": "🔔 **경북대 학사공지 업데이트**",
        "embeds": [{
            "title": title,
            "description": description,
            "url": link,
            "color": 12916017, # KNU Red
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
    print("--- [크롤러 시작] ---")

    # 1. ID 설정
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
        print(f"📂 기준 ID: {last_id}")

    # 2. 목록 접속
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

    # 3. 새 글 탐색 (전수 조사)
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
                print(f"✅ 새 글 발견: {doc_id}")
                real_link = VIEW_URL_BASE + str(doc_id)
                new_posts.append({'id': doc_id, 'title': title, 'link': real_link})

    # 4. 처리 및 전송
    if new_posts:
        print(f"✨ 총 {len(new_posts)}개의 새 공지 처리 중...")
        # 과거순 정렬
        new_posts.sort(key=lambda x: x['id'])
        
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK")
        
        if webhook_url:
            for post in new_posts:
                # 본문 긁기
                content = get_post_content(post['link'])
                
                # 요약 시도 (실패 시 None 반환됨)
                summary = None
                if content:
                    summary = get_gemini_summary(content)
                
                # 디스코드 전송
                send_discord_message(webhook_url, post['title'], post['link'], post['id'], summary, content)
                
                # 순서 꼬임 방지 대기
                time.sleep(1)
        else:
            print("❌ WebHook URL이 설정되지 않았습니다.")

        # 5. ID 저장 (테스트 아닐 때만)
        if TEST_LAST_ID is None:
            max_id = max(p['id'] for p in new_posts)
            with open(latest_id_path, 'w', encoding='utf-8') as f:
                f.write(str(max_id))
            print(f"💾 ID 업데이트 완료: {max_id}")
    else:
        print("💤 전송할 새로운 공지가 없습니다.")

if __name__ == "__main__":
    main()
