"""前端去字符串化第二刀：/admin/phase2|5|6 迁移到 Jinja2 模板。

这些测试钉住"模板渲染 + admin 框体包裹后的输出，与迁移前逐字节一致"的不变量。
迁移前这三页是 ``app/api/admin.py`` 里的纯 dedent 字符串（无任何
双花括号 / 服务端插值），现源自 ``app/templates/admin/<name>.html``（整段 ``{% raw %}``
包裹，避免 JS ``${...}`` 与 CSS 花括号被 Jinja 误解析）。

逐字节等价的“黄金值”由各路由的等价组合式重建：

- phase2：路由直接返回 ``render_template("admin/phase2.html")``（不过框体）。
- phase5 / phase6：路由返回 ``render_admin_page(html.replace(__ADMIN_HERO__, ...)
  .replace(__ADMIN_OVERVIEW__, ...), active)``，其中 ``html`` 即模板渲染结果。

本测试用同一组合式（不依赖被删除的内联字符串）断言路由输出逐字节等价，并加结构锚点
（``<title>`` / 关键 ``id`` / 中文标题）作为可读的回归护栏。
"""

import unittest

from app.api.admin import phase2_console, phase5_console, phase6_console
from app.api.admin_ui import (
    admin_hero_summary_card,
    admin_overview_card,
    admin_overview_strip,
    admin_page_hero,
    render_admin_page,
)
from app.templating import render_template


class Phase2TemplateTests(unittest.TestCase):
    def test_phase2_console_equals_template_render(self) -> None:
        """phase2_console() 直接返回模板渲染结果（不过框体）。"""
        expected = render_template("admin/phase2.html")
        self.assertEqual(phase2_console(), expected)

    def test_phase2_console_anchors(self) -> None:
        out = phase2_console()
        self.assertIn("<title>Phase 2 手动触发台</title>", out)
        for anchor in (
            'id="queue-new"',
            'id="queue-task"',
            'id="query-task"',
            'id="output"',
        ):
            self.assertIn(anchor, out)
        # 整段 raw 包裹：占位符在 phase2 中本就不存在，确认无残留 Jinja 标记。
        self.assertNotIn("{% raw %}", out)
        self.assertNotIn("{% endraw %}", out)


class Phase5TemplateTests(unittest.TestCase):
    def _expected(self) -> str:
        hero_html = admin_page_hero(
            eyebrow="PHASE 5 ADMIN CONSOLE",
            title="审核台",
            description="先看任务，再决定：通过、重写，还是推草稿。",
            status_aria_label="审核台状态",
            status_slot_html='<span class="status" id="status">空闲</span>',
            status_message="先刷新最近任务，再点一条卡片进入工作区。",
            summary_cards_html="".join(
                [
                    admin_hero_summary_card("主要流程", "先选任务，再看工作区，再决定动作。"),
                    admin_hero_summary_card("人工介入点", "通过、重写、允许推稿、禁止推稿。"),
                    admin_hero_summary_card(
                        "当前建议",
                        "先刷新最近任务，再点一条卡片进入工作区。",
                        wide=True,
                        content_id="hero-focus",
                    ),
                ]
            ),
        )
        overview_html = admin_overview_strip(
            "",
            "".join(
                [
                    admin_overview_card("任务", "0", value_id="overview-total"),
                    admin_overview_card("待审核", "0", value_id="overview-manual"),
                    admin_overview_card("待推送", "0", value_id="overview-ready"),
                    admin_overview_card("异常", "0", value_id="overview-failed"),
                ]
            ),
        )
        html = render_template("admin/phase5.html")
        return render_admin_page(
            html.replace("__ADMIN_HERO__", hero_html).replace("__ADMIN_OVERVIEW__", overview_html),
            "review",
        )

    def test_phase5_console_equals_template_through_frame(self) -> None:
        self.assertEqual(phase5_console(), self._expected())

    def test_phase5_console_anchors(self) -> None:
        out = phase5_console()
        self.assertIn("<title>Phase 5 工作台</title>", out)
        for anchor in (
            'id="approve-generation"',
            'id="allow-push"',
            'id="block-push"',
            'id="compare-left"',
            'id="compare-right"',
        ):
            self.assertIn(anchor, out)
        # hero / overview 占位符已被实际 HTML 替换，无残留。
        self.assertNotIn("__ADMIN_HERO__", out)
        self.assertNotIn("__ADMIN_OVERVIEW__", out)
        # 框体锚点（render_admin_page 包裹后应存在）。
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class Phase6TemplateTests(unittest.TestCase):
    def _expected(self) -> str:
        hero_html = admin_page_hero(
            eyebrow="PHASE 6 FEEDBACK LOOP",
            title="反馈台",
            description="这里负责回收任务反馈、观察 prompt 实验表现，并沉淀已经验证过的写法资产。先锁定任务，再决定是查历史、补录反馈，还是把结论沉淀下来。",
            status_aria_label="反馈页状态",
            status_slot_html='<span class="status" id="status">等待输入</span>',
            status_message="默认复用后台会话。先补 task_id，再选择“查反馈”“同步”或“导入”。",
            summary_cards_html="".join(
                [
                    admin_hero_summary_card("这页负责什么", "把任务表现、实验趋势和复用资产串成一个反馈闭环。"),
                    admin_hero_summary_card("需要准备什么", "task_id，以及必要时的 generation_id 和操作人标识；默认复用后台会话。"),
                    admin_hero_summary_card(
                        "当前建议",
                        "先补 task_id，再看当前任务有没有已有反馈。",
                        wide=True,
                        content_id="hero-focus",
                    ),
                ]
            ),
        )
        overview_html = admin_overview_strip(
            "",
            "".join(
                [
                    admin_overview_card("反馈", "0", value_id="overview-feedback-count"),
                    admin_overview_card("实验", "0", value_id="overview-experiment-count"),
                    admin_overview_card("资产", "0", value_id="overview-asset-count"),
                ]
            ),
        )
        html = render_template("admin/phase6.html")
        return render_admin_page(
            html.replace("__ADMIN_HERO__", hero_html).replace("__ADMIN_OVERVIEW__", overview_html),
            "feedback",
        )

    def test_phase6_console_equals_template_through_frame(self) -> None:
        self.assertEqual(phase6_console(), self._expected())

    def test_phase6_console_anchors(self) -> None:
        out = phase6_console()
        self.assertIn("<title>Phase 6 反馈台</title>", out)
        for anchor in (
            'id="asset-title"',
            'id="asset-content"',
            'id="asset-tags"',
            'id="overview-feedback-count"',
        ):
            self.assertIn(anchor, out)
        self.assertNotIn("__ADMIN_HERO__", out)
        self.assertNotIn("__ADMIN_OVERVIEW__", out)
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


if __name__ == "__main__":
    unittest.main()
