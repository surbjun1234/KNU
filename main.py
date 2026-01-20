# [수정된 fetch_latest_notice 함수]
def fetch_latest_notice():
    # 봇 차단을 막기 위한 '완벽한 위장' 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.knu.ac.kr/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        # Session을 사용해 쿠키/세션 처리까지 모사
        session = requests.Session()
        res = session.get(NOTICE_URL, headers=headers, timeout=20)
        res.raise_for_status()
        
        # 인코딩 강제 설정 (한글 깨짐 방지)
        res.encoding = 'utf-8' 
    except Exception as e:
        print(f"❌ 접속 오류: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # 1. 일반적인 게시판 형태 (tbody > tr)
    rows = soup.select("tbody tr")
    
    # 2. 만약 없으면 다른 클래스 이름으로 재시도
    if not rows:
        rows = soup.select(".board_list tbody tr")

    if not rows:
        print("❌ 여전히 게시물을 못 찾았습니다.")
        # 디버깅용: 타이틀이나 본문 앞부분을 찍어서 무슨 페이지로 갔는지 확인
        print(f"현재 페이지 제목: {soup.title.string if soup.title else '없음'}")
        print(f"HTML 내용 일부: {soup.text[:100].strip()}")
        return None

    # 최신 공지 찾기
    latest_notice = None
    
    for row in rows:
        # 제목 칸 찾기 (subject 또는 title 클래스)
        subject_td = row.select_one("td.subject a") or row.select_one("td.title a")
        
        # 만약 제목 칸이 없거나, '공지' 배지가 달린 행이면 건너뛰기
        # (번호 칸이 숫자가 아닌 경우 보통 공지임)
        num_td = row.select_one("td.num")
        if num_td and not num_td.get_text(strip=True).isdigit():
            continue

        if not subject_td:
            continue
            
        title = subject_td.get_text(strip=True)
        href = subject_td.get("href")
        
        # 링크 파싱
        post_id = None
        full_url = NOTICE_URL

        if href and "btin_idx=" in href:
            post_id = href.split("btin_idx=")[1].split("&")[0]
            full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?btin_idx={post_id}&menu_idx=42"
        elif href and "nttId=" in href:
            post_id = href.split("nttId=")[1].split("&")[0]
            full_url = f"https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/view.action?nttId={post_id}&menu_idx=42"
        
        if not post_id:
            post_id = title # ID 못 찾으면 제목을 ID로

        latest_notice = {"id": post_id, "title": title, "url": full_url}
        break # 가장 위의 일반 게시물 하나만 잡고 종료

    return latest_notice
