# mac os 기준 venv 가상환경 사용 시 실행이 안되는 경우

## 1. 이전 가상환경 디렉토리 삭제
rm -rf venv

## 2. 새로 가상환경 생성
python3 -m venv venv

## 3. 가상환경 활성화
source venv/bin/activate  # zsh/bash
## 또는
. venv/bin/activate

## 4. 가상환경 안에서 flask 설치
pip install flask
pip install requests beautifulsoup4
pip install selenium
pip install webdriver-manager
pip install firebase-admin
