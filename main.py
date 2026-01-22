def send_discord_message(webhook_url, board_name, title, link, doc_id, original_content):
    if not webhook_url:
        print(f"   ⚠️ [주의] {board_name} 웹훅 주소가 비어있습니다!")
        return

    # 주소 앞부분 20자만 출력해서 확인
    print(f"   🔗 [전송 시도] URL: {webhook_url[:20]}...")

    # ... 나머지 전송 코드 ...
