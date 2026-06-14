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

import json as _json
import unittest
from textwrap import dedent

from fastapi import Response

from app.api.admin import phase2_console, phase5_console, phase6_console
from app.api.admin_console import (
    pipeline_console,
    unified_admin_portal,
    unified_console,
)
from app.api.admin_factors_page import admin_factors_page
from app.api.admin_topics import admin_topics_console
from app.api.admin_ui import (
    admin_hero_summary_card,
    admin_overview_card,
    admin_overview_strip,
    admin_page_hero,
    render_admin_page,
)
from app.core.pipeline_registry import ARTICLE_PIPELINE, serialize_pipeline
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


class TopicsTemplateTests(unittest.TestCase):
    def _expected(self) -> str:
        overview_html = admin_overview_strip(
            "选题概览",
            "".join(
                [
                    admin_overview_card("启用来源", "0", "当前处于启用状态的抓取来源。", value_id="summary-source-enabled"),
                    admin_overview_card("候选总量", "0", "当前候选池规模。", value_id="summary-candidate-total"),
                    admin_overview_card("已计划", "0", "已经形成计划但尚未推进到任务。", value_id="summary-planned-total"),
                    admin_overview_card(
                        "24h 新信号",
                        "0",
                        "最近 24 小时新进入系统的公开信号。",
                        highlight=True,
                        value_id="summary-new-signal-24h",
                    ),
                ]
            ),
        )
        html = render_template("admin/topics.html")
        return render_admin_page(html.replace("__TOPICS_OVERVIEW__", overview_html), "topics")

    def test_topics_console_equals_template_through_frame(self) -> None:
        """admin_topics_console() 的输出与等价组合式逐字节相同。"""
        self.assertEqual(admin_topics_console(), self._expected())

    def test_topics_console_anchors(self) -> None:
        out = admin_topics_console()
        self.assertIn("<title>选题情报台</title>", out)
        for anchor in (
            'id="topics-source-list"',
            'id="topics-candidate-list"',
            'id="topics-workspace"',
            'id="topic-status-filter"',
            'id="refresh-snapshot"',
        ):
            self.assertIn(anchor, out)
        # 占位符已被实际 HTML 替换，无残留。
        self.assertNotIn("__TOPICS_OVERVIEW__", out)
        # 框体锚点（render_admin_page 包裹后应存在）。
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class FactorsTemplateTests(unittest.TestCase):
    """/admin/factors 是混合 f-string 页：迁移前 CSS/HTML/JS 来自三个 Python 字符串
    helper（``_page_css`` / ``_page_html`` / ``_page_js``），由外层 f-string 拼装后过框体。

    迁移后整页（含三段 helper 的字面内容）内联进 ``app/templates/admin/factors.html``，
    整段 ``{% raw %}`` 包裹（JS 里含 ``${...}`` 模板字面量与 ``}}`` 对象字面量闭合）。
    等价组合式直接复刻路由：``render_admin_page(render_template(...), "factors")``。
    """

    def _expected(self) -> str:
        return render_admin_page(render_template("admin/factors.html"), "factors")

    def test_factors_page_equals_template_through_frame(self) -> None:
        """admin_factors_page() 的输出与等价组合式逐字节相同。"""
        self.assertEqual(admin_factors_page(), self._expected())

    def test_factors_page_anchors(self) -> None:
        out = admin_factors_page()
        self.assertIn("<title>因子库</title>", out)
        for anchor in (
            'id="fl-grid"',
            'id="pending-list"',
            'id="extract-panel"',
            'id="fl-modal"',
            'id="fl-drawer"',
            'id="btn-create"',
            'data-dim="opening"',
            'data-status="active"',
        ):
            self.assertIn(anchor, out)
        # 整段 raw 包裹：渲染后无残留 Jinja 标记。
        self.assertNotIn("{% raw %}", out)
        self.assertNotIn("{% endraw %}", out)
        # 框体锚点（render_admin_page 包裹后应存在）。
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class UnifiedAdminPortalTemplateTests(unittest.TestCase):
    """/admin（总览主控台）迁移前是 ``app/api/admin_console.py`` 里的 f-string
    （``dedent(f'''...''')``）——之所以用 f-string，仅仅是因为内联 JS/CSS 花括号被写成双花括号；
    页面本体不做任何服务端 ``{var}`` 插值，``task_id`` 仅作为查询参数保留（前端 JS 自取 URL），
    因此无论 ``task_id`` 取值，渲染结果逐字节一致。

    迁移后页面本体内联进 ``app/templates/admin/portal.html``（整段 ``{% raw %}`` 包裹，
    JS 里含 ``${...}`` 模板字面量与 ``}`` 闭合，CSS 含大量花括号）。等价组合式直接复刻路由：
    ``render_admin_page(render_template("admin/portal.html"), "portal")``，
    ``__ADMIN_SHARED_STYLES__`` / ``__ADMIN_SHARED_SCRIPT_HELPERS__`` 由框体注入。
    """

    def _expected(self) -> str:
        return render_admin_page(render_template("admin/portal.html"), "portal")

    def test_portal_equals_template_through_frame_task_id_none(self) -> None:
        self.assertEqual(unified_admin_portal(task_id=None), self._expected())

    def test_portal_equals_template_through_frame_task_id_value(self) -> None:
        # task_id 不参与服务端插值：给定具体值仍应与组合式逐字节相同。
        self.assertEqual(unified_admin_portal(task_id="abc123"), self._expected())

    def test_portal_invariant_across_task_id(self) -> None:
        # 同一不变量再钉一道：两种 task_id 输入产出完全一致。
        self.assertEqual(
            unified_admin_portal(task_id=None),
            unified_admin_portal(task_id="abc123"),
        )

    def test_portal_anchors(self) -> None:
        out = unified_admin_portal(task_id=None)
        self.assertIn("<title>微信文章工厂</title>", out)
        for anchor in (
            'class="flow-container"',
            'class="input-bar"',
            'class="count-bar"',
        ):
            self.assertIn(anchor, out)
        self.assertNotIn("{% raw %}", out)
        self.assertNotIn("{% endraw %}", out)
        # 共享占位符已由框体注入，无残留。
        self.assertNotIn("__ADMIN_SHARED_STYLES__", out)
        self.assertNotIn("__ADMIN_SHARED_SCRIPT_HELPERS__", out)
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class UnifiedConsoleTemplateTests(unittest.TestCase):
    """/admin/console（高级监控台）迁移前是 ``app/api/admin_console.py`` 里的纯 dedent 字符串
    （非 f-string，单花括号）。迁移后页面本体源自 ``app/templates/admin/console.html``
    （整段 ``{% raw %}`` 包裹）；hero / overview 由 ``admin_*`` helper 现场构造，经
    ``__ADMIN_HERO__`` / ``__ADMIN_OVERVIEW__`` 占位符替换后再过框体。等价组合式复刻路由。
    """

    def _expected(self) -> str:
        hero_html = admin_page_hero(
            eyebrow="ADVANCED OPERATIONS MONITOR",
            title="高级监控台",
            description="这是一张高级排障页，不是日常主入口。它专门负责看任务流、队列和 worker 健康；日常开任务、审稿和回收反馈，仍然回到总览主控台、审核台和反馈台处理。",
            status_aria_label="监控页状态",
            status_slot_html='<span class="status" id="status">等待连接</span>',
            status_message="默认复用后台会话。先拉一次监控快照，再决定是否开启自动实时更新。",
            summary_cards_html="".join(
                [
                    admin_hero_summary_card("这页负责什么", "看任务流、队列与 worker 健康，快速定位哪一批任务最需要你介入。"),
                    admin_hero_summary_card("日常入口在哪", "开任务回总览，审稿去 Phase 5，复盘反馈去 Phase 6。"),
                    admin_hero_summary_card(
                        "当前建议",
                        "先拉一次监控快照，确认今天有哪些任务真正卡住了。",
                        wide=True,
                        content_id="hero-focus",
                    ),
                ]
            ),
            hero_body_html=dedent(
                """\
                <div class="hero-warning" aria-label="使用边界提示">
                  <span class="warning-kicker">只读排障页</span>
                  <strong>不在这里做日常操作。这里只用于队列、worker 和任务卡点排查。</strong>
                  <ul class="warning-list">
                    <li>开新任务、看草稿、做删除，回总览主控台。</li>
                    <li>人工通过 / 驳回 / 推送草稿，去 Phase 5 审核台。</li>
                    <li>导入反馈、复盘效果、跑同步，去 Phase 6 反馈台。</li>
                  </ul>
                </div>
                """
            ),
            hero_links_html=(
                '<div class="hero-links">'
                '<a href="/admin" target="_blank" rel="noreferrer">回到总览主控台</a>'
                '<a href="/admin/phase5" target="_blank" rel="noreferrer">打开 Phase 5 审核台</a>'
                '<a href="/admin/phase6" target="_blank" rel="noreferrer">打开 Phase 6 反馈台</a>'
                "</div>"
            ),
        )
        overview_html = admin_overview_strip(
            "",
            "".join(
                [
                    admin_overview_card("任务", "0", value_id="overview-filtered-count"),
                    admin_overview_card("待处理", "0", value_id="overview-manual-count"),
                    admin_overview_card("队列", "等待快照", value_id="overview-ops-state"),
                ]
            ),
        )
        html = render_template("admin/console.html")
        return render_admin_page(
            html.replace("__ADMIN_HERO__", hero_html).replace("__ADMIN_OVERVIEW__", overview_html),
            "monitor",
        )

    def test_console_equals_template_through_frame(self) -> None:
        self.assertEqual(unified_console(), self._expected())

    def test_console_anchors(self) -> None:
        out = unified_console()
        self.assertIn("<title>高级监控台</title>", out)
        self.assertNotIn("__ADMIN_HERO__", out)
        self.assertNotIn("__ADMIN_OVERVIEW__", out)
        self.assertNotIn("{% raw %}", out)
        self.assertNotIn("{% endraw %}", out)
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class PipelineConsoleTemplateTests(unittest.TestCase):
    """/admin/pipeline（流程配置）迁移前是 ``app/api/admin_console.py`` 里的纯 dedent 字符串
    （非 f-string，单花括号）。迁移后页面本体源自 ``app/templates/admin/pipeline.html``
    （整段 ``{% raw %}`` 包裹）；``__PIPELINE_REGISTRY_JSON__`` 占位符注入流程注册表 JSON，
    再过框体。路由同时设置 ``Cache-Control`` 响应头——本测试一并钉住。
    """

    def _expected(self) -> str:
        registry_json = _json.dumps(serialize_pipeline(ARTICLE_PIPELINE), ensure_ascii=False)
        html = render_template("admin/pipeline.html")
        html = html.replace("__PIPELINE_REGISTRY_JSON__", registry_json)
        return render_admin_page(html, "pipeline")

    def test_pipeline_equals_template_through_frame(self) -> None:
        response = Response()
        self.assertEqual(pipeline_console(response), self._expected())

    def test_pipeline_sets_cache_control_header(self) -> None:
        response = Response()
        pipeline_console(response)
        self.assertEqual(
            response.headers.get("Cache-Control"),
            "no-store, no-cache, must-revalidate",
        )

    def test_pipeline_anchors(self) -> None:
        response = Response()
        out = pipeline_console(response)
        self.assertIn("<title>流程配置</title>", out)
        self.assertNotIn("__PIPELINE_REGISTRY_JSON__", out)
        self.assertNotIn("{% raw %}", out)
        self.assertNotIn("{% endraw %}", out)
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


if __name__ == "__main__":
    unittest.main()
