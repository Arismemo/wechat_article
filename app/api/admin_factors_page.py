"""因子库管理页面 — 完整改进版（4 批 25 项评审改进）。

页面的 CSS/HTML/JS 已从 Python 字符串迁移到 ``app/templates/admin/factors.html``
（整段 ``{% raw %}`` 包裹，保护 JS ``${...}`` 模板字面量与 CSS/JS 花括号）。路由只负责
渲染模板并交给 ``render_admin_page`` 套后台框体，逐字节等价由
``tests/test_admin_pages_template.py::FactorsTemplateTests`` 钉住。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import render_admin_page
from app.core.security import verify_admin_basic_auth
from app.templating import render_template

router = APIRouter()


@router.get("/admin/factors", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def admin_factors_page() -> str:
    """渲染因子库页面：模板渲染结果交给 render_admin_page 套后台框体。"""
    return render_admin_page(render_template("admin/factors.html"), "factors")
