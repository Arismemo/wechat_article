# v1.1.2 发布说明

更新时间：2026-03-10
状态：Released

## 1. 发布结论

`v1.1.2` 是基于 `v1.1.1` 的补丁发布，范围集中在两类内容：

- Phase 7F 第一刀
  - monitor 趋势图
  - 分级告警
  - 稳定 `dedupe_key`
  - 前端临时静默
- `/admin` 主工作台的会话失效恢复收口

这版不把完整的前端改版视为已完成，只把“开始实施前必须先稳住的监控与上下文恢复基础设施”纳入正式版本。

## 2. 相对 v1.1.1 的新增与变化

### 2.1 `/admin` 会话恢复

- `/admin` 现在会持久化：
  - `task_id`
  - 主筛选
  - 搜索词
  - 未提交链接
- 当后台会话失效时，页面会明确提示“刷新后可恢复上下文”，而不是一律显示泛化失败文案。

### 2.2 Phase 7F 第一刀

- `GET /api/v1/admin/monitor/snapshot` 新增：
  - `alerts`
  - `trends`
- `alerts` 当前覆盖：
  - worker 观测不可用
  - worker `stale / offline`
  - 卡住任务
  - 失败任务
- 每条告警返回：
  - `key`
  - `dedupe_key`
  - `level`
  - `title`
  - `summary`
  - `detail`
  - `count`
  - `action_label`
  - `action_href`
- `trends` 当前固定返回最近 24 小时、8 个 3 小时桶，包含：
  - `submitted`
  - `failed`
  - `review_outcomes`
  - `review_successes`
  - `review_success_rate`
  - `auto_push_candidates`
  - `auto_push_successes`
  - `auto_push_success_rate`

### 2.3 `/admin/console`

- 新增“告警与静默”面板
- 新增“最近 24 小时趋势”面板
- 支持按 `dedupe_key` 做本地临时静默
- 支持“恢复全部静默”

### 2.4 前端方案文档

- [docs/post-v1.1.0-frontend-redesign-plan.md](/Users/liukun/j/code/wechat_artical/docs/post-v1.1.0-frontend-redesign-plan.md) 已升级为正式执行方案
- 文档现在明确写清：
  - 直接加载的 antigravity 前端 skills
  - 交接文档约束
  - 统一视觉与交互原则
  - 五个后台页的逐页方案
  - 共享 UI 基座、实施顺序与验收标准

## 3. 本地验证

已完成：

- `pytest -q`
  - 结果：`99 passed`
- `python3 -m compileall app tests`
  - 结果：通过

重点覆盖：

- `/admin` 会话恢复
- admin monitor 快照新增 `alerts / trends`
- `/admin/console` 页面渲染与脚本断言

## 4. 线上验收

本轮已完成线上 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/admin`
  - 页面包含：
    - `结构化下一步`
    - `当前卡点`
    - `focus-action-card`
    - `cache: "no-store"`
- `GET https://auto.709970.xyz/admin/phase5`
  - 页面包含：
    - `当前采用版本`
    - `采用此版本`
    - `参考文章`
    - `AI 去痕诊断`
    - `流水线时间线`
- `GET https://auto.709970.xyz/admin/console/stream?once=true&limit=3`
  - 返回：`event: snapshot`
  - 返回结果中包含：
    - `alerts`
    - `trends`
    - 4 个 worker 的运行状态
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot`
  - 当前返回：
    - `alerts_count = 1`
    - `trends_count = 8`
  - 当前示例告警：
    - `level = critical`
    - `title = 任务推进卡住`

## 5. 已知边界

当前版本仍不包含：

- 完整的前端改版落地
- 真实 feedback provider 正式切回主链路
- 内容质量卡口的完整收口
- 共享 UI 基座的全面抽取

## 6. 发布结果

- 发布时间：2026-03-10
- 正式 tag：`v1.1.2`
- 核心功能提交：`af101ec`
- 发布收口提交：本次 tag 指向发布文档收口 commit
- 发布方式：
  - 本地 `git push origin main`
  - 本地生成 bundle 并导入服务器仓库
  - 服务器执行 `docker compose up -d --build api phase2_worker phase3_worker phase4_worker feedback_worker`
- 服务器结果：
  - 发布会话中服务器仓库已快进到 `af101ec`
  - `api`、`phase2_worker`、`phase3_worker`、`phase4_worker`、`feedback_worker` 已全部重建启动
  - 发布后公网 smoke test 全部通过
