# KNU: 경북대학교 공지사항 크롤링 시스템

## 프로젝트 개요

`KNU` 프로젝트는 경북대학교의 전체 공지사항 및 전자공학부 공지사항을 주기적으로 크롤링하여 새로운 공지사항이 있을 경우 사용자에게 알림을 제공하는 자동화된 시스템입니다. 이 시스템은 학생들이나 교직원들이 중요한 학교 공지를 놓치지 않도록 돕는 것을 목표로 합니다.

## 주요 기능

*   **경북대학교 공지사항 크롤링**: 경북대학교 웹사이트에서 전체 공지사항, 학사 공지사항, 전자공학부 공지사항을 주기적으로 수집합니다.
*   **새로운 공지 감지**: 이전에 수집된 공지사항과 비교하여 새로운 공지사항이 게시되었는지 확인합니다.
*   **웹훅 알림**: 새로운 공지사항이 감지되면 설정된 웹훅(예: Discord)을 통해 관련 정보를 전송합니다.
*   **유연한 게시판 설정**: 다양한 게시판을 쉽게 추가하고 관리할 수 있도록 설계되었습니다.

## 사용 기술

*   **Python**: 핵심 크롤링 로직 구현
*   **`requests`**: 웹 페이지 요청
*   **`BeautifulSoup4`**: HTML 파싱 및 데이터 추출
*   **`os`, `re`, `time`, `urllib.parse`**: 파일 시스템, 정규 표현식, 시간 지연, URL 처리 등
*   **GitHub Actions**: 스케줄링된 작업 실행 (예상)

## 설치 및 실행 방법

1.  **레포지토리 클론**: 
    ```bash
    git clone https://github.com/surbjun1234/KNU.git
    cd KNU
    ```

2.  **의존성 설치**: 
    ```bash
    pip install -r requirements.txt
    ```

3.  **환경 변수 설정**: 
    `WEBHOOK_GENERAL`, `WEBHOOK_ACADEMIC`, `WEBHOOK_ELECTRONIC` 등 각 게시판에 해당하는 웹훅 URL을 환경 변수로 설정해야 합니다. 이는 GitHub Secrets를 통해 관리하는 것이 권장됩니다.

4.  **실행**: 
    ```bash
    python main.py
    ```
    이 스크립트는 주로 GitHub Actions와 같은 CI/CD 환경에서 주기적으로 실행되도록 설계되었습니다.

## 파일 구조

```
KNU/
├── README.md
├── main.py                 # 핵심 크롤링 및 알림 로직
├── requirements.txt        # Python 의존성 목록
├── latest_id_academic.txt  # 학사 공지사항의 마지막 ID 기록
├── latest_id_electronic.txt# 전자공학부 공지사항의 마지막 ID 기록
└── latest_id_general.txt   # 전체 공지사항의 마지막 ID 기록
```

## 기여

이 프로젝트에 기여하고 싶으시다면, Pull Request를 통해 코드 개선이나 새로운 기능 제안을 해주세요.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 `LICENSE` 파일을 참조하세요. (현재 `LICENSE` 파일은 없지만, 추가될 수 있습니다.)
