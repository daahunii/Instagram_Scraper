import os
import unittest
from unittest.mock import Mock, patch
import insta_api as api
import insta_scraper as scraper


class ScraperTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.client = api.app.test_client()

    def test_username_blocks_paths_and_urls(self):
        for value in [None, "", "../x", "https://example.com", "a..b", "a.", "a" * 31]:
            with self.assertRaises(ValueError):
                scraper.validate_username(value)
        self.assertEqual(scraper.validate_username("hello.world_1"), "hello.world_1")

    def test_download_hosts(self):
        for url in ["http://s.cdninstagram.com/a", "https://localhost/a", "https://s.cdninstagram.com:bad/a",
                    "https://s.cdninstagram.com.evil.test/a", "https://user@s.cdninstagram.com/a"]:
            self.assertFalse(scraper.is_image_url(url))
        self.assertTrue(scraper.is_image_url("https://s.cdninstagram.com/a"))

    def test_invalid_request_does_not_start_work(self):
        with patch.object(api, "get_firebase_or_crawl") as work:
            self.assertEqual(self.client.get("/crawl?username=../x").status_code, 400)
            work.assert_not_called()

    def test_cached_images_skip_browser(self):
        with patch.object(api, "check_existing_images", return_value=["url"]), patch.object(api, "crawl_instagram_images") as crawl:
            self.assertEqual(api.get_firebase_or_crawl("example")[0], ["url"])
            crawl.assert_not_called()

    def test_error_details_are_not_returned(self):
        with patch.object(api, "get_firebase_or_crawl", side_effect=RuntimeError("private-key-path")):
            response = self.client.get("/crawl?username=example")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private-key-path", response.get_data(as_text=True))

    def test_auth_and_response_contract(self):
        os.environ["SCRAPER_API_TOKEN"] = "test-token"
        self.assertEqual(self.client.get("/crawl?username=example").status_code, 401)
        with patch.object(api, "get_firebase_or_crawl", return_value=(["url"], "ok")):
            response = self.client.get("/crawl?username=example", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(response.json, {"username": "example", "images": ["url"], "message": "ok"})

    def test_upload_is_private_by_default(self):
        blob = Mock()
        bucket = Mock()
        bucket.blob.return_value = blob
        blob.generate_signed_url.return_value = "temporary-url"
        with patch.object(api, "get_bucket", return_value=bucket), patch.object(api, "download_image", return_value=(b"image", "image/png")):
            self.assertEqual(api.upload_images_to_firebase(["url"], "example"), ["temporary-url"])
        blob.make_public.assert_not_called()
        self.assertTrue(bucket.blob.call_args.args[0].endswith(".png"))

    def test_oversized_download_rejected(self):
        response = Mock(status_code=200, headers={"Content-Type": "image/jpeg"})
        response.iter_content.return_value = [b"x" * 5, b"x" * 5]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(api.requests, "get", return_value=response), patch.object(api, "MAX_IMAGE_BYTES", 6):
            with self.assertRaises(ValueError):
                api.download_image("https://s.cdninstagram.com/image")

    def test_browser_closed_on_navigation_error(self):
        driver = Mock()
        driver.get.side_effect = RuntimeError("navigation failed")
        with patch("selenium.webdriver.Chrome", return_value=driver):
            with self.assertRaises(RuntimeError):
                scraper.crawl_instagram_images("example")
        driver.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
