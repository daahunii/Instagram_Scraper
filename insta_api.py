"""Giftoyou image API with environment-based Firebase configuration."""
from datetime import timedelta
from functools import lru_cache
import hmac
import os
import uuid
import requests
from flask import Flask, jsonify, request
from insta_scraper import MAX_IMAGES, crawl_instagram_images, is_image_url, validate_username

app = Flask(__name__)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@lru_cache(maxsize=1)
def get_bucket():
    import firebase_admin
    from firebase_admin import storage
    name = os.environ.get("FIREBASE_STORAGE_BUCKET", "").strip()
    if not name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET is required")
    # Application Default Credentials: no project-specific filename in source.
    firebase_app = firebase_admin.initialize_app(options={"storageBucket": name}, name="instagram-scraper")
    return storage.bucket(app=firebase_app)


def image_url(blob):
    # Existing public objects remain public; this does not alter their ACLs.
    if os.environ.get("FIREBASE_PUBLIC_IMAGES") == "true":
        return blob.public_url
    return blob.generate_signed_url(version="v4", expiration=timedelta(minutes=15), method="GET")


def check_existing_images(username):
    validate_username(username)
    blobs = get_bucket().list_blobs(prefix=f"insta_images/{username}/", max_results=MAX_IMAGES)
    return [image_url(blob) for blob in blobs
            if blob.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]


def download_image(url):
    if not is_image_url(url):
        raise ValueError("Unsupported image URL")
    with requests.get(url, timeout=(3.05, 10), stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError("Image download failed")
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type not in IMAGE_TYPES:
            raise ValueError("Unsupported image content type")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if len(data) + len(chunk) > MAX_IMAGE_BYTES:
                raise ValueError("Image exceeds size limit")
            data.extend(chunk)
        if not data:
            raise ValueError("Empty image")
        return bytes(data), content_type


def upload_images_to_firebase(image_urls, username):
    validate_username(username)
    uploaded = []
    for url in list(dict.fromkeys(image_urls))[:MAX_IMAGES]:
        data, content_type = download_image(url)
        blob = get_bucket().blob(f"insta_images/{username}/{uuid.uuid4()}{IMAGE_TYPES[content_type]}")
        blob.upload_from_string(data, content_type=content_type)
        if os.environ.get("FIREBASE_PUBLIC_IMAGES") == "true":
            blob.make_public()
        uploaded.append(image_url(blob))
    return uploaded


def get_firebase_or_crawl(username):
    validate_username(username)
    existing = check_existing_images(username)
    if existing:
        return existing, "Existing images reused"
    images = crawl_instagram_images(username)
    if not images:
        raise RuntimeError("No accessible post images")
    uploaded = upload_images_to_firebase(images, username)
    return uploaded, "New images uploaded"


@app.before_request
def authenticate():
    token = os.environ.get("SCRAPER_API_TOKEN", "")
    if token and request.path != "/":
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
            return jsonify({"error": "Unauthorized"}), 401


@app.route("/crawl", methods=["GET"])
def crawl():
    username = request.args.get("username")
    try:
        validate_username(username)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        urls, message = get_firebase_or_crawl(username)
        return jsonify({"username": username, "images": urls, "message": message})
    except Exception:
        # Do not return credential paths, signed URLs or provider details.
        app.logger.error("Image collection or storage operation failed")
        return jsonify({"error": "Image collection or storage unavailable"}), 502


@app.route("/")
def index():
    return jsonify({"service": "Instagram image API", "endpoint": "GET /crawl?username=your_id"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
