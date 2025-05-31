from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

def crawl_instagram_images(username):
    url = f"https://www.instagram.com/{username}/"

    # 브라우저 자동 설치 및 실행
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    try:
        # 팝업창 닫기
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'svg[aria-label="닫기"]'))
        )
        close_button.click()
        print("팝업 닫기 완료")
    except Exception as e:
        print("팝업이 없거나 닫기 실패:", e)

    time.sleep(3)

    # 이미지 수집
    images = driver.find_elements(By.CSS_SELECTOR, 'img')
    image_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]

    driver.quit()

    # 피드 이미지만 추출 (두 번째부터 최대 9개)
    if len(image_urls) >= 2:
        selected_images = image_urls[1:10]  # 최대 9개
        if len(selected_images) < 9 and len(selected_images) > 1:
            selected_images = selected_images[:-1]  # 마지막(프로필 가능성 높은) 제거
    else:
        selected_images = image_urls[:1]

    print(f"[{username}] 피드 이미지 수집 결과 ({len(selected_images)}개):")
    for idx, url in enumerate(selected_images, start=1):
        print(f"{idx}: {url}")

    return selected_images

# ✅ 테스트 실행
if __name__ == "__main__":
    crawl_instagram_images("poem_s._.tree")