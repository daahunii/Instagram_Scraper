"""Small best-effort scraper for publicly accessible Instagram profile images."""
import argparse
import json
import re
from urllib.parse import urlsplit

MAX_IMAGES = 9


def validate_username(username):
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,29}", username):
        raise ValueError("username must be 1-30 letters, digits, underscores or dots")
    if username.endswith(".") or ".." in username:
        raise ValueError("username contains invalid dots")
    return username


def is_image_url(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and port in (None, 443)
            and not parsed.username and not parsed.password
            and any(host.endswith("." + domain) for domain in ("cdninstagram.com", "fbcdn.net")))


def crawl_instagram_images(username):
    validate_username(username)
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(30)
        driver.get(f"https://www.instagram.com/{username}/")
        # Login overlays may be absent or localized. Do not suppress browser errors.
        try:
            close = WebDriverWait(driver, 3).until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'svg[aria-label="닫기"], svg[aria-label="Close"]')))
            close.click()
        except TimeoutException:
            pass
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img")))
        # Prefer post links; exclude profile/navigation images rather than slicing by position.
        images = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"] img, a[href*="/reel/"] img')
        urls = []
        for image in images:
            url = image.get_attribute("src")
            if url and is_image_url(url) and url not in urls:
                urls.append(url)
            if len(urls) >= MAX_IMAGES:
                break
        return urls
    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    args = parser.parse_args()
    try:
        print(json.dumps(crawl_instagram_images(args.username), ensure_ascii=False, indent=2))
    except Exception:
        parser.exit(1, "Image collection failed; check username, Chrome and profile accessibility.\n")
