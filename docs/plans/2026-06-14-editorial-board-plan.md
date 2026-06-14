# 多Agent出版社编委会 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每篇稿件加一道多Agent出版社编委会评审——16 岗独立评审 → 多轮辩论至收敛 → 总编终裁(通过/改/毙 + 修改指令),裁决映射回 ReviewReport 驱动现有门禁。

**Architecture:** 独立 `editorial:queue` + 单实例 board worker(内部并发≤3 限流 GLM-5.2 专用渠道);辩论编排在 `EditorialBoardService`;终裁写新 `editorial_review` 表 + 一条权威 ReviewReport;`EDITORIAL_ENABLED` 时 Phase4 审稿后延后 push、入队编委会。复用 T3a 重试/DLQ、T4 可重试 schema 错误、已迁移 Jinja 模板基座。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 / Alembic / Redis / httpx(同步)/ concurrent.futures(并发闸)/ pydantic / pytest(unittest 风格,sqlite 内存 + UUID shim,LLM 全 mock)。

**依据:** 设计规格 `docs/plans/2026-06-14-editorial-board-spec.md`;角色 rubric 派生自 `/Users/liukun/j/code/wechat_artical/ref/04-report.md`。

---

## File Structure

**新建:**
- `app/services/editorial_llm_client.py` — 专用 GLM-5.2 渠道 + 全局并发闸(BoundedSemaphore)。
- `app/schemas/editorial.py` — `RoleOpinion` / `ConvergenceJudgement` / `EditorialVerdict` pydantic 模型(LLM 结构化输出 + 内部传递)。
- `app/services/editorial_roles.py` — `RoleSpec` + `EDITORIAL_ROLES`(16 岗)+ rubric。
- `app/models/editorial_review.py` — `EditorialReview` 表模型。
- `app/repositories/editorial_review_repository.py` — repo。
- `migrations/versions/20260614_0001_add_editorial_review.py` — 迁移。
- `app/services/editorial_board_service.py` — 辩论编排(round 循环/收敛/终裁/映射 ReviewReport)。
- `app/services/editorial_queue_service.py` — 队列(镜像 T3a Phase4QueueService)。
- `scripts/run_editorial_worker.py` — 单实例 worker(复用 `handle_worker_failure`)。
- `tests/test_editorial_llm_client.py` / `test_editorial_board_service.py` / `test_editorial_queue_service.py` / `test_editorial_integration.py`。

**修改:**
- `app/settings.py` — `EDITORIAL_*` 配置。
- `app/core/enums.py` — `PENDING_EDITORIAL` 状态 + 加入 `ACTIVE_TASK_STATUSES`。
- `app/services/phase4_pipeline_service.py` — 审稿后:`EDITORIAL_ENABLED` 则入队 editorial + 置 `PENDING_EDITORIAL`(延后 push)。
- `.env.example` — `EDITORIAL_*` 占位(无真实值)。
- `app/main.py` + 一个 Jinja 模板 — `/admin/editorial/{task_id}` 辩论查看页(Task 10)。

---

## Task 1: 配置 + 枚举

**Files:**
- Modify: `app/settings.py`
- Modify: `app/core/enums.py`
- Modify: `.env.example`
- Test: `tests/test_editorial_config.py`

- [ ] **Step 1: 写失败测试** `tests/test_editorial_config.py`

```python
import os
import unittest
from unittest.mock import patch

from app.core.enums import TaskStatus, ACTIVE_TASK_STATUSES


class EditorialConfigTests(unittest.TestCase):
    def test_pending_editorial_status_exists_and_active(self) -> None:
        self.assertEqual(TaskStatus.PENDING_EDITORIAL.value, "pending_editorial")
        self.assertIn(TaskStatus.PENDING_EDITORIAL, ACTIVE_TASK_STATUSES)

    def test_editorial_settings_defaults(self) -> None:
        env = {
            "APP_BASE_URL": "https://e.com", "API_BEARER_TOKEN": "t",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/0",
            "LLM_PROVIDER": "Z", "LLM_API_KEY": "k", "LLM_MODEL_ANALYZE": "m",
            "LLM_MODEL_WRITE": "m", "LLM_MODEL_REVIEW": "m", "SEARCH_PROVIDER": "S",
            "WECHAT_APP_ID": "w", "WECHAT_APP_SECRET": "s",
        }
        with patch.dict(os.environ, env, clear=False):
            from app.settings import get_settings
            get_settings.cache_clear()
            s = get_settings()
            self.assertFalse(s.editorial_enabled)
            self.assertEqual(s.editorial_llm_model, "glm-5.2")
            self.assertEqual(s.editorial_llm_max_concurrency, 3)
            self.assertEqual(s.editorial_max_debate_rounds, 4)
            self.assertEqual(s.editorial_queue_key, "editorial:queue")
        get_settings.cache_clear()
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/python -m pytest -q tests/test_editorial_config.py` → FAIL(`PENDING_EDITORIAL` 不存在)。

- [ ] **Step 3: 改 `app/core/enums.py`** — 在 `TaskStatus` 加 `PENDING_EDITORIAL = "pending_editorial"`;在 `ACTIVE_TASK_STATUSES` set 里加 `TaskStatus.PENDING_EDITORIAL`。

- [ ] **Step 4: 改 `app/settings.py`** — 在 `Settings` 加(放 feedback 配置附近):

```python
    editorial_enabled: bool = Field(default=False, alias="EDITORIAL_ENABLED")
    editorial_llm_api_base: str = Field(default="https://open.bigmodel.cn/api/coding/paas/v4", alias="EDITORIAL_LLM_API_BASE")
    editorial_llm_api_key: Optional[str] = Field(default=None, alias="EDITORIAL_LLM_API_KEY")
    editorial_llm_model: str = Field(default="glm-5.2", alias="EDITORIAL_LLM_MODEL")
    editorial_llm_max_concurrency: int = Field(default=3, alias="EDITORIAL_LLM_MAX_CONCURRENCY")
    editorial_llm_timeout_seconds: int = Field(default=120, alias="EDITORIAL_LLM_TIMEOUT_SECONDS")
    editorial_max_debate_rounds: int = Field(default=4, alias="EDITORIAL_MAX_DEBATE_ROUNDS")
    editorial_role_disabled: str = Field(default="", alias="EDITORIAL_ROLE_DISABLED")
    editorial_queue_key: str = Field(default="editorial:queue", alias="EDITORIAL_QUEUE_KEY")
    editorial_processing_key: str = Field(default="editorial:processing", alias="EDITORIAL_PROCESSING_KEY")
    editorial_pending_set_key: str = Field(default="editorial:pending", alias="EDITORIAL_PENDING_SET_KEY")
    editorial_dead_key: str = Field(default="editorial:dead", alias="EDITORIAL_DEAD_KEY")
    editorial_worker_poll_timeout_seconds: int = Field(default=5, alias="EDITORIAL_WORKER_POLL_TIMEOUT_SECONDS")
    editorial_worker_idle_sleep_seconds: int = Field(default=1, alias="EDITORIAL_WORKER_IDLE_SLEEP_SECONDS")
    editorial_worker_heartbeat_key: str = Field(default="editorial:worker:heartbeat", alias="EDITORIAL_WORKER_HEARTBEAT_KEY")
```

- [ ] **Step 5: 改 `.env.example`** — 加 `EDITORIAL_*` 段,`EDITORIAL_ENABLED=false`、`EDITORIAL_LLM_API_KEY=`(留空,真实值只进 `.env`)、`EDITORIAL_LLM_MODEL=glm-5.2`、`EDITORIAL_LLM_MAX_CONCURRENCY=3`、`EDITORIAL_MAX_DEBATE_ROUNDS=4`。

- [ ] **Step 6: 跑测试通过** — `.venv/bin/python -m pytest -q tests/test_editorial_config.py` → PASS。

- [ ] **Step 7: Commit** — `git add app/settings.py app/core/enums.py .env.example tests/test_editorial_config.py && git commit -m "新增: 编委会配置与 PENDING_EDITORIAL 状态"`(commit body 末尾加 Co-Authored-By trailer,下同)。

---

## Task 2: EditorialLLMClient(专用渠道 + 全局并发闸)

**Files:**
- Create: `app/services/editorial_llm_client.py`
- Test: `tests/test_editorial_llm_client.py`

并发闸用模块级 `BoundedSemaphore(max_concurrency)`,在每次 GLM 调用前 acquire,保证**同进程内任意并发调用 ≤ max**。复用 `LLMService` 的 payload 构造与 JSON 解析(组合,不继承),GLM 是 OpenAI 兼容 `/chat/completions`。

- [ ] **Step 1: 写失败测试** `tests/test_editorial_llm_client.py`

```python
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.services.editorial_llm_client import EditorialLLMClient


class EditorialLLMClientTests(unittest.TestCase):
    def test_concurrency_never_exceeds_cap(self) -> None:
        client = EditorialLLMClient(api_base="http://x", api_key="k", model="glm-5.2", max_concurrency=3)
        active = {"n": 0, "max": 0}
        lock = threading.Lock()

        def fake_call(_payload, _timeout):
            with lock:
                active["n"] += 1
                active["max"] = max(active["max"], active["n"])
            time.sleep(0.02)
            with lock:
                active["n"] -= 1
            return {"ok": True}

        with patch.object(client, "_raw_completion", side_effect=fake_call):
            with ThreadPoolExecutor(max_workers=10) as ex:
                list(ex.map(lambda _: client.complete_json(system_prompt="s", user_prompt="u"), range(10)))
        self.assertLessEqual(active["max"], 3)
        self.assertGreaterEqual(active["max"], 1)

    def test_returns_parsed_json(self) -> None:
        client = EditorialLLMClient(api_base="http://x", api_key="k", model="glm-5.2", max_concurrency=3)
        with patch.object(client, "_raw_completion", return_value={"choices": [{"message": {"content": '{"stance":"pass"}'}}]}):
            out = client.complete_json(system_prompt="s", user_prompt="u")
        self.assertEqual(out["stance"], "pass")
```

- [ ] **Step 2: 跑测试确认失败** — module not found。

- [ ] **Step 3: 实现** `app/services/editorial_llm_client.py`

```python
from __future__ import annotations

import threading
from typing import Any, Optional

import httpx

from app.services.llm_service import LLMService, LLMServiceError


class EditorialLLMClient:
    """编委会专用 LLM 渠道(GLM-5.2),全局并发闸保证 ≤ max_concurrency。

    复用 LLMService 的 JSON 提取逻辑;并发上限只在【单进程】内保证,
    因此 editorial worker 必须单实例运行(见 run_editorial_worker.py 注释)。
    """

    def __init__(self, *, api_base: str, api_key: Optional[str], model: str, max_concurrency: int, timeout_seconds: int = 120) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrency))
        self._parser = LLMService(api_base=api_base, api_key=api_key, default_model=model)

    def _completion_url(self) -> str:
        if self.api_base.endswith("/chat/completions"):
            return self.api_base
        return f"{self.api_base}/chat/completions"

    def _raw_completion(self, payload: dict, timeout: int) -> dict:
        response = httpx.post(
            self._completion_url(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            from app.services.llm_service import LLMProviderHTTPError
            raise LLMProviderHTTPError(url=str(exc.request.url), status_code=exc.response.status_code, response_text=exc.response.text) from exc
        return response.json()

    def complete_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        with self._semaphore:
            body = self._raw_completion(payload, self.timeout_seconds)
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise LLMServiceError(f"Unexpected editorial completion content: {content!r}")
        return self._parser._extract_json(content)  # reuse robust JSON extraction
```

- [ ] **Step 4: 跑测试通过** — `.venv/bin/python -m pytest -q tests/test_editorial_llm_client.py` → PASS。

- [ ] **Step 5: ruff** — `.venv/bin/ruff check --select E9,F app/services/editorial_llm_client.py tests/test_editorial_llm_client.py` → 通过。

- [ ] **Step 6: Commit** — `新增: 编委会专用 GLM 渠道与全局并发闸`。

---

## Task 3: 结构化 schema(RoleOpinion / ConvergenceJudgement / EditorialVerdict)

**Files:**
- Create: `app/schemas/editorial.py`
- Test: `tests/test_editorial_schemas.py`

- [ ] **Step 1: 写失败测试** — 构造各模型,断言字段 + `stance`/`decision` 的 Literal 校验拒绝非法值。

```python
import unittest
from pydantic import ValidationError
from app.schemas.editorial import RoleOpinion, ConvergenceJudgement, EditorialVerdict, RevisionDirective


class EditorialSchemaTests(unittest.TestCase):
    def test_role_opinion_ok(self) -> None:
        o = RoleOpinion(role_key="copy_editor", scores={"ai_trace": 70}, issues=["排序词过多"], stance="revise", key_argument="机械腔重")
        self.assertEqual(o.stance, "revise")

    def test_stance_rejects_invalid(self) -> None:
        with self.assertRaises(ValidationError):
            RoleOpinion(role_key="x", scores={}, issues=[], stance="maybe", key_argument="")

    def test_verdict_with_directives(self) -> None:
        v = EditorialVerdict(decision="revise", final_scores={"overall": 72},
                             rationale="标题弱", revision_directives=[RevisionDirective(location="标题", problem="无数字", fix="加具体数字")],
                             dissent_summary="法务保留")
        self.assertEqual(v.revision_directives[0].location, "标题")
```

- [ ] **Step 2: 跑测试确认失败。**

- [ ] **Step 3: 实现** `app/schemas/editorial.py`

```python
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Stance = Literal["pass", "revise", "reject"]


class RoleOpinion(BaseModel):
    role_key: str
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    stance: Stance
    key_argument: str = ""


class ConvergenceJudgement(BaseModel):
    new_substantive_objection: bool
    summary: str = ""


class RevisionDirective(BaseModel):
    location: str
    problem: str
    fix: str


class EditorialVerdict(BaseModel):
    decision: Stance
    final_scores: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""
    revision_directives: list[RevisionDirective] = Field(default_factory=list)
    dissent_summary: str = ""
```

- [ ] **Step 4: 跑测试通过。**
- [ ] **Step 5: Commit** — `新增: 编委会结构化输出 schema`。

---

## Task 4: EditorialReview 模型 + 迁移 + repository

**Files:**
- Create: `app/models/editorial_review.py`, `app/repositories/editorial_review_repository.py`, `migrations/versions/20260614_0001_add_editorial_review.py`
- Modify: `app/models/__init__.py`(注册模型)
- Test: `tests/test_editorial_review_repository.py`

- [ ] **Step 1: 写失败测试** — 用 sqlite 内存 + `@compiles(UUID,"sqlite")` shim(copy from `tests/test_task_repository.py`):创建 task/generation,`EditorialReviewRepository.create(...)` 落库,`get_latest_by_task_id` / `get_by_generation_id` 取回,断言 transcript(JSON)往返。

- [ ] **Step 2: 跑测试确认失败。**

- [ ] **Step 3: 实现模型** `app/models/editorial_review.py`(沿用 `UUIDPrimaryKeyMixin, TimestampMixin`):

```python
from __future__ import annotations
from typing import Optional
from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EditorialReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "editorial_reviews"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_report_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")  # running|converged|max_rounds|failed
    rounds_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # pass|revise|reject
    final_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision_directives: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dissent_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {rounds:[{round_no, opinions:[...]}]}
```

- [ ] **Step 4: 注册** — `app/models/__init__.py` 加 `from app.models.editorial_review import EditorialReview` + `__all__`。
- [ ] **Step 5: 写迁移** `migrations/versions/20260614_0001_add_editorial_review.py` — `down_revision` = 当前 head(先 `.venv/bin/alembic heads` 查),`op.create_table("editorial_reviews", ...)` 含上述列 + FK + index;`downgrade` drop。
- [ ] **Step 6: 实现 repository** — `create`、`get_latest_by_task_id`、`get_by_generation_id`、`update(review)`。
- [ ] **Step 7: 跑测试通过** + 单 head 校验 `.venv/bin/alembic heads`(应 1 个)。
- [ ] **Step 8: Commit** — `新增: editorial_review 模型/迁移/repository`。

---

## Task 5: 角色定义(RoleSpec + 16 岗)

**Files:**
- Create: `app/services/editorial_roles.py`
- Test: `tests/test_editorial_roles.py`

**rubric 来源:** 逐岗从 `/Users/liukun/j/code/wechat_artical/ref/04-report.md` 抽取该岗 rubric(标题→§1、排版→§2、去AI味→§3、传播→§4、CTA→§5、合规→spec/T6)。下面给 `RoleSpec` 与 **2 个完整范例**;其余 14 岗按同模板编写,system_prompt 写清"你是出版社的 X,只从 X 视角评审,立场鲜明",rubric 写清该岗评分维度+扣分点(从 ref 对应节抄要点)。

映射表(每岗 → ref 来源 + rubric 主轴):见 spec §2 表格 + ref 各节。`department` 用 spec §2 的部门名。

- [ ] **Step 1: 写测试** `tests/test_editorial_roles.py`:`EDITORIAL_ROLES` 含 16 条;每条有非空 `key/name/system_prompt/rubric`;`key` 唯一;`active_roles(disabled="copy_editor,proofreader")` 过滤掉 2 个且保留 `chief_editor`;`chief_editor` 永远不可被 disabled(主席必需)。

- [ ] **Step 2: 跑测试确认失败。**

- [ ] **Step 3: 实现** `app/services/editorial_roles.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoleSpec:
    key: str
    name: str
    department: str
    system_prompt: str
    rubric: str
    enabled: bool = True
    weight: float = 1.0


# 2 个完整范例(其余 14 岗按同模板补全,rubric 抄 ref/04-report.md 对应节要点):
EDITORIAL_ROLES: list[RoleSpec] = [
    RoleSpec(
        key="chief_editor", name="总编(主席)", department="决策层",
        system_prompt="你是出版社总编、本次评审主席。综合各岗意见与辩论,做出最终裁决并对结果负责。",
        rubric="终裁 pass/revise/reject;给定稿综合评分;权衡传播力与合规风险;裁决须可执行。",
    ),
    RoleSpec(
        key="headline_editor", name="标题编辑", department="读者增长",
        system_prompt="你是标题编辑,只从'打开率/点进来'的视角评审,立场鲜明。",
        rubric=("评估标题:≤28字且钩子在前15字;是否含≥1具体数字(禁'很多/大量');是否命中公式槽位≥3;"
                "是否有人群/场景标签;是否优先损失厌恶框架;反标题党——标题每个缺口正文是否闭合。来源 ref §1。"),
    ),
    # ... 其余 14 岗(content_editor/copy_editor/proofreader/fact_checker/compliance/
    #     legal_copyright/reader_advocate/growth_editor/layout_editor/platform_seo/
    #     topic_strategist/domain_expert/brand_voice/managing_editor)按同模板补全 ...
]


def active_roles(disabled: str = "") -> list[RoleSpec]:
    blocked = {k.strip() for k in disabled.split(",") if k.strip()}
    blocked.discard("chief_editor")  # 主席不可禁用
    return [r for r in EDITORIAL_ROLES if r.enabled and r.key not in blocked]
```

- [ ] **Step 4: 补全其余 14 岗** rubric(从 ref/04-report.md 抄),确保 16 条。
- [ ] **Step 5: 跑测试通过。**
- [ ] **Step 6: Commit** — `新增: 编委会 16 岗角色定义与 rubric`。

---

## Task 6: EditorialBoardService(辩论编排 / 收敛 / 终裁 / 映射 ReviewReport)

**Files:**
- Create: `app/services/editorial_board_service.py`
- Test: `tests/test_editorial_board_service.py`

**入口** `review(task_id) -> EditorialReview`。依赖注入 `llm_client`(测试传 mock)。流程实现 spec §4。并发:用 `ThreadPoolExecutor(max_workers=settings.editorial_llm_max_concurrency)` 在每轮内 fan-out 各岗调用(client 内部 semaphore 再兜底)。

- [ ] **Step 1: 写失败测试**(mock client,断言:0 轮独立评审产出 N 条 opinion;`new_substantive_objection=false` 时 1 轮后收敛;`MAX_ROUNDS` 兜底;终裁写 ReviewReport + EditorialReview;decision/scores 正确)。给一个返回可控 JSON 的 `FakeClient`,按 prompt 内容路由返回 opinion / convergence / verdict。

- [ ] **Step 2: 跑测试确认失败。**

- [ ] **Step 3: 实现** `app/services/editorial_board_service.py` —— 核心骨架:

```python
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.editorial_review import EditorialReview
from app.models.review_report import ReviewReport
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.editorial import RoleOpinion, ConvergenceJudgement, EditorialVerdict
from app.services.editorial_roles import active_roles
from app.settings import get_settings


class EditorialBoardService:
    def __init__(self, session: Session, llm_client) -> None:
        self.session = session
        self.llm = llm_client
        self.settings = get_settings()
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.editorials = EditorialReviewRepository(session)

    def review(self, task_id: str) -> EditorialReview:
        task = self.tasks.get_by_id(task_id)
        generation = self.generations.get_latest_by_task_id(task_id)
        if task is None or generation is None:
            raise ValueError("editorial: task/generation missing")
        roles = active_roles(self.settings.editorial_role_disabled)
        context = self._build_context(task, generation)  # 原文/brief/稿件 文本拼装

        record = self.editorials.create(EditorialReview(task_id=task_id, generation_id=generation.id, status="running"))
        rounds: list[dict] = []

        # ROUND 0: 独立评审
        opinions = self._fan_out_opinions(roles, context, prior=None)
        rounds.append({"round_no": 0, "opinions": [o.model_dump() for o in opinions]})

        # ROUND 1..N: 辩论
        round_no = 0
        status = "max_rounds"
        for round_no in range(1, self.settings.editorial_max_debate_rounds + 1):
            opinions = self._fan_out_opinions(roles, context, prior=opinions)
            rounds.append({"round_no": round_no, "opinions": [o.model_dump() for o in opinions]})
            conv = self._judge_convergence(opinions, context)
            if not conv.new_substantive_objection:
                status = "converged"
                break

        verdict = self._chief_verdict(opinions, context)
        report = self._persist_review_report(task, generation, verdict)
        record = self.editorials.update_result(record, status=status, rounds_used=round_no, verdict=verdict,
                                                transcript={"rounds": rounds}, review_report_id=report.id)
        return record

    def _fan_out_opinions(self, roles, context, prior) -> list[RoleOpinion]:
        def call(role):
            sys = role.system_prompt
            usr = self._opinion_prompt(role, context, prior)
            raw = self.llm.complete_json(system_prompt=sys, user_prompt=usr)
            raw.setdefault("role_key", role.key)
            return RoleOpinion.model_validate(raw)
        with ThreadPoolExecutor(max_workers=self.settings.editorial_llm_max_concurrency) as ex:
            return list(ex.map(call, roles))

    # _judge_convergence -> ConvergenceJudgement(managing_editor 视角)
    # _chief_verdict -> EditorialVerdict(chief_editor 视角)
    # _persist_review_report -> 把 verdict.final_scores 映射到 ReviewReport 各字段(similarity/policy/factual/
    #   readability/title/novelty/ai_trace + final_decision=verdict.decision),reviews.create(...) 返回 report
    # _build_context / _opinion_prompt -> 文本拼装(稿件 markdown + 原文摘要 + 各岗 rubric + prior 意见摘要)
```

(实现各私有方法:`_judge_convergence` 用 `managing_editor` 角色 prompt + `ConvergenceJudgement` 校验;`_chief_verdict` 用 `chief_editor` prompt + `EditorialVerdict` 校验;`_persist_review_report` 把 `final_scores` 的键映射到 ReviewReport 列,缺省给安全值;`EditorialReviewRepository.update_result` 落 decision/scores/rationale/directives/transcript。)

- [ ] **Step 4: 跑测试通过。** — `.venv/bin/python -m pytest -q tests/test_editorial_board_service.py`。
- [ ] **Step 5: ruff** 通过。
- [ ] **Step 6: Commit** — `新增: 编委会辩论编排服务`。

---

## Task 7: EditorialQueueService(镜像 T3a)

**Files:**
- Create: `app/services/editorial_queue_service.py`
- Test: `tests/test_editorial_queue_service.py`

- [ ] **Step 1: 写失败测试** — 用 `tests/test_phase4_queue_service.py` 的 `KeyAwareFakeRedis` 模式:`enqueue` 去重入队、`pop_next` BRPOPLPUSH、`acknowledge`、`requeue_for_retry`(回队保 pending)、`move_to_dead`(进 dead 列)、`requeue_processing_jobs`。
- [ ] **Step 2: 跑测试确认失败。**
- [ ] **Step 3: 实现** — 复制 `app/services/phase4_queue_service.py` 改键名为 `editorial_*`,方法签名一致(`enqueue/pop_next/acknowledge/requeue_for_retry/move_to_dead/requeue_processing_jobs/idle_sleep/mark_worker_heartbeat/runtime_snapshot`),`name="editorial"`、`label="编委会评审"`。
- [ ] **Step 4: 跑测试通过。**
- [ ] **Step 5: Commit** — `新增: 编委会队列服务`。

---

## Task 8: run_editorial_worker.py(单实例 + 复用 T3a 失败处理)

**Files:**
- Create: `scripts/run_editorial_worker.py`
- Test: `tests/test_editorial_worker_smoke.py`(导入 + main 可构造,不真跑循环)

- [ ] **Step 1: 写 smoke 测试** — import 脚本模块成功;存在 `main` 可调用对象。
- [ ] **Step 2: 跑确认失败。**
- [ ] **Step 3: 实现** — 复制 `scripts/run_phase4_worker.py` 结构,改:用 `EditorialQueueService`;循环里 `EditorialBoardService(session, EditorialLLMClient(...from settings...)).review(task_id)`;`except` 调 `handle_worker_failure(queue, session, task_id, exc, failed_status=TaskStatus.NEEDS_MANUAL_REVIEW.value, max_retries=..., backoff_seconds=..., queue_ref=task_id)`;`finally` outcome!="retried" 才 acknowledge。**文件顶部注释:本 worker 必须单实例运行(并发≤3 仅在单进程内保证)。**
- [ ] **Step 4: 跑测试通过。**
- [ ] **Step 5: Commit** — `新增: 编委会 worker(单实例,复用重试/DLQ)`。

---

## Task 9: Phase4 集成(审稿后入队编委会,延后 push)

**Files:**
- Modify: `app/services/phase4_pipeline_service.py`(`run()` 决策段,~line 142-165)
- Test: `tests/test_phase4_editorial_integration.py`

- [ ] **Step 1: 写失败测试** — `EDITORIAL_ENABLED=true` 时,Phase4 `run()` 审稿后**不**自动推草稿,任务置 `PENDING_EDITORIAL`,且 `EditorialQueueService.enqueue` 被调用(mock 队列断言);`EDITORIAL_ENABLED=false` 时维持旧行为(回归)。
- [ ] **Step 2: 跑确认失败。**
- [ ] **Step 3: 改 `run()`** — 在算出 `review`/`decision` 之后、进入 `_mark_review_passed/_auto_push` 之前插入:

```python
        if self.settings.editorial_enabled:
            self._set_task_status(task, TaskStatus.PENDING_EDITORIAL)
            self._log_action(task.id, "phase4.editorial.enqueued", {"generation_id": generation.id})
            self.session.commit()
            EditorialQueueService().enqueue(task.id)
            return self._editorial_pending_result(task, generation, review)
```

(`_editorial_pending_result` 返回一个 `Phase4PipelineResult`,status=PENDING_EDITORIAL,不触发 push。`EditorialQueueService` 延迟 import 防循环。)

- [ ] **Step 4: 跑测试通过** + 全量回归 `.venv/bin/python -m pytest -q`。
- [ ] **Step 5: Commit** — `集成: Phase4 审稿后入队编委会并延后推草稿`。

---

## Task 10: 后台辩论查看页 + 监控并入

**Files:**
- Create: `app/templates/admin/editorial.html`, `app/api/admin_editorial.py`(或并入 admin_console)
- Modify: `app/main.py`(挂路由)、editorial 队列并入 `queue_observability`/console snapshot
- Test: `tests/test_admin_editorial_page.py`

- [ ] **Step 1: 写测试** — `GET /admin/editorial/{task_id}` 200,含终裁 decision、各轮各岗意见、异议;无该 task 时 404/空态。auth 沿用 `verify_admin_basic_auth`。
- [ ] **Step 2: 跑确认失败。**
- [ ] **Step 3: 实现** — Jinja 模板(复用 `render_admin_page` 壳层 + `{% raw %}` 包 JS);路由读 `EditorialReviewRepository.get_latest_by_task_id` 渲染 transcript;editorial 队列指标加入 console snapshot(沿用 `read_queue_runtime`)。
- [ ] **Step 4: 跑测试通过。**
- [ ] **Step 5: Commit** — `新增: 后台编委会辩论查看页与监控`。

---

## Task 11: 端到端集成测试(全 mock LLM)

**Files:**
- Test: `tests/test_editorial_integration.py`

- [ ] **Step 1: 写测试** — sqlite 内存,构造 task+generation+brief;`EDITORIAL_ENABLED=true`;注入 FakeClient(各岗返回 stance,managing 返回收敛,chief 返回 verdict);跑 `EditorialBoardService.review(task_id)` → 断言:EditorialReview 落库(status/rounds/decision/transcript)、新 ReviewReport 落库且 final_decision==verdict.decision、decision=revise 时 revision_directives 非空。
- [ ] **Step 2: 跑测试通过。**
- [ ] **Step 3: 全量回归 + ruff。**
- [ ] **Step 4: Commit** — `测试: 编委会端到端(全 mock)`。

---

## 完成后

- 全量 `pytest -q` 全绿、`ruff --select E9,F` 干净、`alembic heads` 单 head。
- 终审分支(`superpowers:requesting-code-review`)。
- 运营动作:`.env` 填 `EDITORIAL_LLM_API_KEY`、`EDITORIAL_ENABLED=true`、**单实例**起 `run_editorial_worker.py`。
- 按 `superpowers:finishing-a-development-branch` 决定 PR(stacked on audit-remediation)。

## Self-Review(spec 覆盖核对)

- spec §2 16 岗 → Task 5 ✅;§4 辩论协议 → Task 6 ✅;§5 双轨+延后 push → Task 9 ✅;§6 模型 → Task 4 ✅;§7 队列/worker/并发闸 → Task 2/7/8 ✅;§8 配置/密钥 → Task 1 ✅;§9 可观测 → Task 10 ✅;§10 测试 → 各 Task + Task 11 ✅。
- 类型一致:`RoleOpinion/ConvergenceJudgement/EditorialVerdict`(Task 3)在 Task 6 使用一致;`EditorialQueueService` 方法名(Task 7)与 worker(Task 8)/Phase4(Task 9)调用一致;`EditorialReviewRepository.update_result`(Task 6 用)需在 Task 4 定义 —— **补**:Task 4 Step 6 repository 增 `update_result(review, *, status, rounds_used, verdict, transcript, review_report_id)`。
- 无占位:角色 rubric(Task 5)给模板 + 2 范例 + ref 映射,属内容编写非占位;其余代码完整。
