from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.admin_ui import (
    admin_hero_summary_card,
    admin_overview_card,
    admin_overview_strip,
    admin_page_hero,
    render_admin_page,
)
from app.core.security import verify_admin_basic_auth
from app.templating import render_template


router = APIRouter()


@router.get("/admin/phase2", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase2_console() -> str:
    return render_template("admin/phase2.html")


@router.get("/admin/phase5", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase5_console() -> str:
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


@router.get("/admin/phase6", response_class=HTMLResponse, tags=["admin"], dependencies=[Depends(verify_admin_basic_auth)])
def phase6_console() -> str:
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
