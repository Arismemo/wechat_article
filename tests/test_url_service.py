import unittest

from app.services.url_service import detect_source_type, normalize_url


class UrlServiceTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_parameters(self) -> None:
        raw_url = (
            "https://mp.weixin.qq.com/s?"
            "__biz=abc&mid=123&idx=1&sn=xyz&scene=1&chksm=foo&utm_source=bar"
        )
        normalized = normalize_url(raw_url)
        self.assertEqual(
            normalized,
            "https://mp.weixin.qq.com/s?__biz=abc&idx=1&mid=123&sn=xyz",
        )

    def test_detect_source_type_for_wechat(self) -> None:
        self.assertEqual(detect_source_type("https://mp.weixin.qq.com/s?__biz=abc"), "wechat")

    def test_detect_source_type_for_generic_web(self) -> None:
        self.assertEqual(detect_source_type("https://example.com/article"), "web")


if __name__ == "__main__":
    unittest.main()
