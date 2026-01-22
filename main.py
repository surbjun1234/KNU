import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# -----------------------------------------------------------
# [테스트 모드 설정] 
# 0으로 설정했으니 실행 시 무조건 2개씩 전송을 시도할 것입니다.
# -----------------------------------------------------------
TEST_IDS = {
    "general": 0,    
    "academic": 0,    
    "electronic": 0   
}

# (게시판 설정 BOARDS 부분은 기존과 동일하므로 생략 - 그대로 두시면 됩니다)

# -----------------------------------------------------------
# [디스코드 전송 함수 - 에러 진단 강화]
# -----------------------------------------------------------
def send_discord_message(webhook_url, board_name, title, link, doc_id, summary_content):
    if not webhook_url or len(webhook_url) < 10:
        print(f"   ❌ [설정 오류] {board_name} 웹훅 URL이 비어있거나 너무 짧습니다.")
        return

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

    try:
        # 응답 결과를 response 변수에 담습니다.
        response = requests.post(webhook_url, json=data, timeout=10)
        
        # 200~299 사이의 코드가 아니면 에러를 발생시킵니다.
        if response.status_code == 204:
            print(f"   🚀 [전송 성공] {title} (웹훅 끝: {webhook_url[-5:]})")
        else:
            print(f"   ⚠️ [전송 실패] 상태 코드: {response.status_code}")
            print(f"   💬 서버 응답: {response.text}") # 디스코드가 왜 거절했는지 알려줍니다.
            
    except Exception as e:
        print(f"   🚨 [네트워크 오류] 전송 중 예외 발생: {e}")

# (나머지 summarize_content, main 함수 등은 기존 최종본과 동일하게 유지)
