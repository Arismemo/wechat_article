import unittest

from app.services.wechat_layout_service import WechatLayoutService


class WechatLayoutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = WechatLayoutService()

    def test_render_markdown_supports_wechat_friendly_subset(self) -> None:
        result = self.service.render_markdown(
            "# 标题\n\n"
            "> 导语引用\n\n"
            "这是 **重点**，也可以放一个 [链接](https://example.com)。\n\n"
            "- 第一条\n"
            "- 第二条\n\n"
            "1. 步骤一\n"
            "2. 步骤二\n\n"
            "![配图说明](https://example.com/demo.png)\n\n"
            "---\n"
        )

        self.assertIn('<h1 style="', result.html)
        self.assertIn("<blockquote", result.html)
        self.assertIn("<strong", result.html)
        self.assertIn("<a href=\"https://example.com\"", result.html)
        self.assertIn("<ul", result.html)
        self.assertIn("<ol", result.html)
        self.assertIn("<img src=\"https://example.com/demo.png\"", result.html)
        self.assertIn("<hr", result.html)
        self.assertEqual(result.residual_markdown_markers, [])

    def test_normalize_markdown_flattens_unsupported_structures(self) -> None:
        result = self.service.render_markdown(
            "# 标题\n\n"
            "```python\n"
            "print('hello')\n"
            "```\n\n"
            "| 列1 | 列2 |\n"
            "| --- | --- |\n"
            "| A | B |\n\n"
            "- [x] 已完成\n"
            "<div>HTML</div>\n"
        )

        self.assertIn("code_fence_flattened", result.normalization_warnings)
        self.assertIn("table_flattened", result.normalization_warnings)
        self.assertIn("task_list_flattened", result.normalization_warnings)
        self.assertIn("raw_html_stripped", result.normalization_warnings)
        self.assertNotIn("```", result.normalized_markdown)
        self.assertNotIn("| 列1 | 列2 |", result.normalized_markdown)
        self.assertNotIn("- [x]", result.normalized_markdown)
        self.assertNotIn("<div>", result.normalized_markdown)
        self.assertEqual(result.residual_markdown_markers, [])
        self.assertNotIn("```", result.html)


if __name__ == "__main__":
    unittest.main()
