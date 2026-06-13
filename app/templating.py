"""共享 Jinja2 模板环境。

后台管理页面把已构建好的 CSS/JS blob（来自 ``app/api/admin_ui.py``）直接注入到
``<style>`` / ``<script>`` 中，这些内容是受信任的、由后端自己生成的，不包含任何来自
外部/用户的数据。因此这里 **刻意关闭 autoescape**——否则注入的 CSS/JS 里的 ``<``、``>``、
``&``、引号都会被 HTML 转义，破坏页面。页面正文里凡是来自不可信来源的数据仍走 JSON API
在客户端渲染（见 ``admin_shared_script_helpers`` 里的 ``escapeHtml``），不在服务端模板里插值。
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# autoescape=False：见模块 docstring。模板里的字面 CSS/JS 用 {% raw %} 包裹，
# 避免 JS 模板字面量 ${...} 之外的花括号被 Jinja 误解析。
env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,
    keep_trailing_newline=True,
)


def render_template(name: str, **context: object) -> str:
    """渲染 ``app/templates`` 下的模板并返回字符串。"""
    return env.get_template(name).render(**context)
