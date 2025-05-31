from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
from io import BytesIO
import uuid
import firebase_admin
from firebase_admin import credentials, storage

# ✅ Firebase 초기화
cred = credentials.Certificate("giftoyou-ad070-firebase-adminsdk-fbsvc-6aa9b1ca63.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'giftoyou-ad070.firebasestorage.app'
})

bucket = storage.bucket()
print("✅ 현재 연결된 버킷 이름:", bucket.name)

app = Flask(__name__)

# ✅ 기존 이미지 존재 확인
def check_existing_images(username):
    blobs = list(bucket.list_blobs(prefix=f"insta_images/{username}/"))
    return [blob.public_url for blob in blobs if blob.name.endswith(('.jpg', '.jpeg', '.png'))]

# ✅ Instagram 이미지 크롤링
def crawl_instagram_images(username):
    url = f"https://www.instagram.com/{username}/"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'svg[aria-label="감지"]'))  # 필요 시 '닫기'로 변경
        )
        close_button.click()
        print("팝업 닫기 완료")
    except Exception as e:
        print("팝업이 없거나 닫기 실패:", e)

    time.sleep(3)
    images = driver.find_elements(By.CSS_SELECTOR, 'img')
    image_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
    driver.quit()

    if len(image_urls) >= 2:
        selected = image_urls[1:10]
        if len(selected) < 9 and len(selected) > 1:
            selected = selected[:-1]
    else:
        selected = image_urls[:1]

    return selected

# ✅ Firebase 업로드
def upload_images_to_firebase(image_urls, username):
    uploaded_urls = []

    for idx, url in enumerate(image_urls):
        print(f"▶️ 이미지 {idx+1}: {url}")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                image_data = BytesIO(response.content)
                filename = f"{username}_{uuid.uuid4()}.jpg"
                blob = bucket.blob(f"insta_images/{username}/{filename}")
                blob.upload_from_file(image_data, content_type='image/jpeg')
                blob.make_public()
                print(f"✅ 업로드 성공: {blob.public_url}")
                uploaded_urls.append(blob.public_url)
            else:
                print(f"❌ 이미지 응답 오류: {response.status_code}")
        except Exception as e:
            print(f"❌ 업로드 실패: {e}")
            continue

    print(f"📦 최종 업로드된 이미지 수: {len(uploaded_urls)}")
    return uploaded_urls

# ✅ 기존 또는 신규 이미지 반환
def get_firebase_or_crawl(username):
    existing = check_existing_images(username)
    if existing:
        print(f"📄 기존 이미지 {len(existing)}개 발견, 크롤링 생략")
        return existing, "✅ 기존 이미지 사용 완료"
    
    new_images = crawl_instagram_images(username)
    uploaded = upload_images_to_firebase(new_images, username)
    return uploaded, "✅ 신규 이미지 업로드 완료"

# ✅ API 엔드포인트
@app.route('/crawl', methods=['GET'])
def crawl():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'username is required'}), 400

    try:
        result_urls, msg = get_firebase_or_crawl(username)
        return jsonify({
            'username': username,
            'images': result_urls,
            'message': msg
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ✅ 루트
@app.route('/')
def index():
    return '📷 Welcome to Insta Crawler API! Use /crawl?username=your_id'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)