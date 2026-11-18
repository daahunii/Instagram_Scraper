# Instagram Image Scraper for Giftoyou

공개 접근 가능한 Instagram 프로필의 게시물 이미지를 Selenium으로 수집하고, Firebase Storage에 저장해 Giftoyou에 이미지 URL을 전달하는 작은 Python/Flask 프로젝트입니다.

```text
GET /crawl?username=...
  → Storage의 insta_images/{username}/ 조회
  → 기존 이미지가 있으면 URL 반환
  → 없으면 Chrome으로 게시물 이미지 수집 (최대 9개)
  → 이미지 다운로드·Storage 업로드 → URL 반환
```

## 파일 구성

- `insta_scraper.py`: 계정명 검증, 공통 크롤러, Firebase 없이 실행하는 CLI
- `insta_api.py`: 기존 이미지 재사용, 다운로드·업로드, Flask API
- `.env.example`: 실행 환경 설정 항목
- `tests/test_scraper.py`: 외부 서비스를 모킹한 회귀 테스트

API와 CLI는 동일한 크롤러를 사용합니다. ChromeDriver는 Selenium Manager가 관리하므로 별도의 webdriver-manager 패키지는 필요하지 않습니다.

## 실행 환경과 설치

Python 3.11 이상과 Google Chrome이 필요합니다. 최초 브라우저 실행 시 드라이버 다운로드를 위한 네트워크 접근이 필요할 수 있습니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

브라우저만 사용하여 이미지 URL 확인 (Firebase 불필요):

```bash
python insta_scraper.py your_username
```

로그인 자동화나 비공개 계정 접근은 지원하지 않습니다. 본인 소유 또는 수집 권한이 있는 자료에 사용하세요.

## Firebase 설정

Firebase 프로젝트와 Storage 버킷을 준비하고, 서버 실행 환경에서 Application Default Credentials를 설정하세요. 로컬에서는 서비스 계정 JSON을 **저장소 밖**에 보관하고 경로를 지정할 수 있습니다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/outside/repo/service-account.json"
export FIREBASE_STORAGE_BUCKET="your-project.firebasestorage.app"
python insta_api.py
```

서비스 계정에는 필요한 버킷 작업 권한만 부여하세요. 기본 비공개 모드의 V4 서명 URL 생성에는 서명이 가능한 서비스 계정 자격증명 또는 적절한 IAM 서명 설정이 필요합니다. 인증 파일·버킷 접근 권한이 없으면 `/crawl`이 실패합니다. 모듈 import나 루트 조회 시에는 Firebase 연결을 시도하지 않습니다.

`.env.example`은 안내용입니다. `.env` 파일을 자동 로딩하지 않으므로 셸 또는 배포 플랫폼에서 환경변수를 주입하세요.

| 환경변수 | 설명 |
| --- | --- |
| `GOOGLE_APPLICATION_CREDENTIALS` | 로컬 서비스 계정 JSON 경로. 관리 환경에서는 ADC 사용 가능 |
| `FIREBASE_STORAGE_BUCKET` | 필수. 버킷 이름 (`gs://` 제외) |
| `SCRAPER_API_TOKEN` | 선택적 Bearer 접근 토큰. 로컬 기본값은 미설정 |
| `FIREBASE_PUBLIC_IMAGES` | 정확히 `true`일 때만 신규 객체를 공개. 기본값 비공개 |

## HTTP API

기본 주소: `http://127.0.0.1:8080`

```bash
curl --get http://127.0.0.1:8080/crawl --data-urlencode 'username=your_username'
```

성공 응답 형식은 기존 Giftoyou 연동과 동일합니다. `message`의 문구는 바뀔 수 있으므로 동작 분기에 사용하지 마세요.

```json
{
  "username": "your_username",
  "images": ["https://storage.example/temporary-image-url"],
  "message": "New images uploaded"
}
```

- 400: 계정명 누락·형식 오류. 1~30자의 영문·숫자·밑줄·점 허용, 경로·연속 점·마지막 점 거부
- 401: `SCRAPER_API_TOKEN`이 설정됐으나 Bearer 헤더 불일치
- 502: 접근 가능한 게시물 없음, 브라우저·다운로드·Firebase 작업 실패

토큰을 설정한 경우 `Authorization: Bearer <token>` 헤더를 전달하세요. 공급자 오류 원문이나 자격증명 경로는 응답으로 반환하지 않습니다.

## 저장·공개 범위와 기존 앱 호환성

기존 코드는 업로드한 객체에 항상 `make_public()`을 호출했습니다. 이제 기본값은 비공개 업로드와 **15분 유효 서명 URL**입니다. Giftoyou가 URL을 장기 저장한다면 만료 후 `/crawl`로 새 URL을 요청하거나 별도 다운로드 경로를 구현해야 합니다.

기존 공개 URL 동작이 반드시 필요한 경우에만 `FIREBASE_PUBLIC_IMAGES=true`를 명시하세요. 이 모드는 누구나 이미지에 접근할 수 있고, 버킷의 Public Access Prevention 또는 Uniform bucket-level access 설정에 따라 동작하지 않을 수 있습니다.

이 코드 변경은 기존 객체 ACL이나 버킷 IAM을 변경하지 않습니다. 이전 이미지가 공개됐거나 버킷 전체에 공개 읽기가 설정돼 있다면 기존 접근 설정을 별도로 점검해야 합니다. 버킷 IAM이 공개라면 신규 객체도 코드의 비공개 기본값만으로 보호되지 않습니다.

## 수집·운영 한계

- 페이지 구조와 로그인 화면에 따라 수집이 실패할 수 있습니다. 게시물·릴 링크 안의 이미지만 선택하며, 프로필 이미지를 피하기 위해 기존 위치 기반 슬라이싱을 제거했습니다. 모든 게시물을 수집하지 않습니다.
- 기존 이미지가 하나라도 있으면 재사용합니다. 자동 새로고침·캐시 만료·동시 요청 잠금은 없습니다. 업로드 도중 실패하면 일부 객체가 남을 수 있으며 다음 요청에서는 기존 자료로 취급됩니다.
- 다운로드는 Instagram/Facebook CDN의 HTTPS 주소만 허용하고 리디렉션을 따라가지 않습니다. 이미지 MIME 유형과 파일당 10 MiB 제한을 확인합니다. 이미지 디코딩·악성 파일 검사는 포함하지 않습니다.
- 요청마다 Chrome이 실행될 수 있으므로 대량 동시 요청에 적합하지 않습니다. 공개 운영 시 HTTPS, 사용자 인증, 요청 속도 제한과 작업 큐를 별도로 구성해야 합니다. 공유 토큰은 사용자별 권한 관리를 대신하지 않습니다.
- Flask 개발 서버는 로컬용입니다. 디버그는 꺼져 있고 기본적으로 외부 인터페이스에 바인딩하지 않습니다.
- 실제 Instagram·Firebase 동작과 운영 배포는 아래 모킹 테스트로 보장되지 않습니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

계정명·다운로드 URL 검증, 캐시 재사용, 인증·응답 형식, 오류 비노출, 비공개 업로드, 용량 제한, 실패 시 브라우저 종료를 검사합니다. 실제 로그인·크롤링·Storage 업로드는 실행하지 않습니다.

## 참고

- [Firebase Admin SDK 설정](https://firebase.google.com/docs/admin/setup)
- [Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
