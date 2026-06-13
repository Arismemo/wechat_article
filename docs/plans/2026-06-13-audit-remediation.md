# 评审整改执行计划 · 2026-06-13

> 来源:本仓库自主评审(阶段 0–4)。分支 `chore/audit-remediation`,多 commit 单 MR。
> 测试基线:`FEEDBACK_SYNC_PROVIDER=mock pytest -q` → 125 passed(干净环境无 `.env` 时默认 disabled 会有 1 例非 hermetic 失败,见 T1)。
> 执行方式:subagent-driven,每 task 实现 → 规格评审 → 质量评审 → 提交。

## 核心目标对齐

让单人运营者用最少人工,把"别人的爆款"稳定重构成**能过微信合规、不被判抄袭、像人写、且真实数据有效**的原创公众号稿。三大根问题:质量无法度量、失败接不住会丢稿、前端债压制迭代。

## 任务清单(按依赖与 ROI 排序)

### T1 · CI 门禁 + 测试 hermetic 化(R4)
- **解决**:无 CI(#4);非 hermetic 测试(干净环境 1 例失败)。
- **做法**:
  1. 新增 `tests/conftest.py`,在导入期为测试设定确定性默认环境(至少 `FEEDBACK_SYNC_PROVIDER=mock`),使套件在无 `.env` 时全绿。
  2. 新增 `.github/workflows/ci.yml`:Python 3.13 → `pip install -e .[dev]` → `pytest -q` → `ruff check`(仅 `E9,F` 真错误,非风格)→ alembic 单 head 校验。
  3. `pyproject.toml` 增 `[tool.ruff]` 最小配置 + 把 `ruff` 加入 dev 依赖。
- **验收**:干净 checkout(无 `.env`)`pytest -q` 全绿;workflow YAML 合法;`ruff check --select E9,F` 通过。
- **文件**:`tests/conftest.py`(新)、`.github/workflows/ci.yml`(新)、`pyproject.toml`。

### T2 · 广度冻结决策 + 双依赖清单收敛(R6 + R8)
- **解决**:过早扩广度(#10);双清单漂移(#13)。
- **做法**:
  1. 新增 `docs/plans/2026-06-13-breadth-freeze.md`:明确选题情报 / 因子库**暂停扩张**,gate = R1 质量回环用真实数据证明核心写作有效后再解冻。
  2. `requirements.runtime.txt` 顶部加显式 "single source of truth = pyproject" 说明并与 pyproject 对齐(不删,避免动 deploy 脚本)。
- **验收**:文档存在且自洽;runtime.txt 与 pyproject deps 完全一致。
- **文件**:`docs/plans/2026-06-13-breadth-freeze.md`(新)、`requirements.runtime.txt`。

### T3a · worker 可靠性:重试分类 + 退避 + DLQ(R2)
- **解决**:失败任务静默丢弃(#2 致命)。
- **做法**:
  1. `settings.py` 增 `*_max_retries`(默认 3)与 `*_retry_backoff_seconds`。
  2. 队列 service 增 `dead_key`(`phase{n}:dead`)与 `move_to_dead(task_id, reason)`、`requeue_for_retry(task_id)`。
  3. worker 循环:捕获异常后分类 —— 可重试(超时/网络/5xx)→ `Task.retry_count++` + 退避后重入队;超 `max_retries` → 进 DLQ + 置 `*_FAILED`;不可重试(解析/校验)→ 直接 DLQ + FAILED。沿用现有 `acknowledge`。
  4. 复用现有 `Task.retry_count` 字段(此前为死字段)。
- **验收**:新增单元测试覆盖三条分支(重试重入队、超限进 DLQ、不可重试进 DLQ);`retry_count` 真实自增;现有测试不回归。
- **文件**:`app/settings.py`、`app/services/phase{2,3,4}_queue_service.py`、`app/services/feedback_queue_service.py`、`scripts/run_phase{2,3,4}_worker.py`、`scripts/run_feedback_worker.py`、`tests/`(新)。

### T3b · 幂等键:重复处理不产重复产出(R2)
- **解决**:崩溃后重跑产生重复 Generation(#2 子项)。
- **做法**:pipeline service 在创建 Generation / 关键产物前,按 `(task_id, phase, version_no)` 查重;已存在则复用/跳过而非新建。语义完成判定:产物存在且 status 有效才算完成。
- **验收**:新增测试:同一 task 重跑同 phase 不产生重复行;现有测试不回归。
- **文件**:`app/services/phase{3,4}_pipeline_service.py`、相关 repository、`tests/`(新)。

### T4 · phase 级事务 + LLM 响应 schema 校验(R5)
- **解决**:分步 commit 留半成品(#6);LLM 解析无校验崩任务/静默模板(#5#9)。
- **做法**:
  1. pipeline runner 改为 phase 级事务边界:一个 phase 内步骤全成功才 commit,任一失败 rollback + 置 FAILED(与 T3a 的分类协同)。
  2. `llm_service.complete_json` 调用方用 pydantic 模型校验返回;缺键/类型错抛 `LLMSchemaError`(归类为可重采样),不再 `payload["x"]` 裸取或静默回退模板。
- **验收**:新增测试:LLM 返回缺键 → 抛 schema 错(被 T3a 当可重试处理),不崩不静默;phase 中途失败不留半成品;现有测试不回归。
- **文件**:`app/core/pipeline*.py`、`app/steps/runner.py`、`app/services/llm_service.py`、`app/services/phase{3,4}_pipeline_service.py`、`tests/`(新)。

### T5 · 质量度量回环(R1)
- **解决**:产出好坏无真实信号(#1 致命)。
- **做法**:
  1. 新增 `scripts/enqueue_recent_feedback.py` + `deploy/systemd/*feedback-sync.timer/.service` 模板:定时调用现有 `enqueue_recent_sync`(链路代码已具备)。
  2. home/console snapshot API 增"单篇真实表现"字段(读 `publication_metrics`:read/like/share),并在后台对应位置最小化展示,与审稿分并列。UI 改动保持外科手术级,勿大改巨型 HTML 文件。
- **验收**:新增脚本可 dry-run 列出将入队任务;snapshot 接口返回真实指标字段并有测试;现有测试不回归。
- **文件**:`scripts/enqueue_recent_feedback.py`(新)、`deploy/systemd/`(新模板)、`app/services/admin_monitor_service.py`、`app/schemas/admin_monitor.py`、`app/api/admin_console.py`(最小改)、`tests/`(新)。

### T6 · 合规 + 原创性硬约束(R7)
- **解决**:洗稿平台/法律红线无显式约束(#14)。
- **做法**:
  1. 确认 `phase4_similarity_max` 在推草稿策略中是**硬门禁**(超阈值阻止自动推稿,转人工);补测试。
  2. 审稿/写稿 prompt 导向"换信息结构 / 换论证角度",显式反对"近义替换 / 语序调整"(微信点名手法)。
  3. `docs/` 增合规说明:产出需人工确认差异度与授权。
- **验收**:相似度超阈值时不自动推稿的测试通过;prompt 文案更新;合规文档存在。
- **文件**:`app/services/wechat_push_policy_service.py`、`app/services/phase4_pipeline_service.py`、`docs/`、`tests/`。

### T7 · 前端去字符串化 slice 1:Jinja2 + htmx 脚手架 + 迁移 `/admin/settings`(R3)
- **解决**:11k LOC HTML-in-Python(#3);两个巨型上帝文件(#8)。
- **做法**:
  1. 引入 Jinja2(加 `jinja2` 依赖)+ `app/templates/` + 共享 `base.html`;vendored htmx(14KB,放 `app/static/`)。
  2. 把 `/admin/settings`(route 较小)从 f-string 迁到 Jinja 模板,**保留所有现有 id / data-* / 脚本钩子**,route 测试不回归。
  3. **显式标注**:console / admin 主台 / phase5 / phase6 / topics / factors 各页为后续 slice,本次不迁。
- **验收**:`/admin/settings` 经模板渲染,`test_app_routes` / 设置页测试全绿;新增模板渲染测试;f-string 版本删除。
- **文件**:`app/templates/`(新)、`app/static/htmx.min.js`(新)、`app/api/admin_settings.py`、`app/main.py`(挂静态/模板)、`pyproject.toml`、`tests/`。

## 不做(明确排除)
- Layui / SPA 全量重写(findings.md 已反复踩坑证伪)。
- 给内部调用链加防御层 / 再抽象一层 LLM provider 工厂。
- 继续扩选题情报 / 因子库(冻结,见 T2)。
- 删 `requirements.runtime.txt` 改动 deploy 脚本(风险高,仅对齐内容)。

## 收尾
全部 task 完成后:整分支终审 → 自验(`pytest` 全绿 + 关键路径)→ 按 `finishing-a-development-branch` 决定 MR。
