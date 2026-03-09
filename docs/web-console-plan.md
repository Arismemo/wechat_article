# 网页端控制台规划

更新时间：2026-03-09
状态：Historical Reference · Phase 7E Completed

> 这份文档保留为历史规划记录。当前实际发布状态以 `docs/phase-7/*.md` 和 `docs/release-v1.1.0.md` 为准。

## 1. 结论

可以做，而且已经有一半基础。

当前系统已经具备：

- 任务看板与聚合详情：`/admin/phase5`
- 反馈与实验榜：`/admin/phase6`
- 运行参数设置：`/admin/settings`
- 网页主入口：`/admin`
- 监控详情页：`/admin/console`
- 监控快照接口：`/api/v1/admin/monitor/snapshot`
- 人工审核、人工推草稿、推草稿开关
- `workspace` 聚合接口，可作为前端工作台的数据底座

所以目标 1 基本不是从零开始，而是把现有后台页收束成一个真正可日常使用的网页主控台。

目标 2 也能做，但不建议直接把服务器 `.env` 暴露成一个可编辑文本框。更安全的路线是：

- 把“运行时可调参数”抽成数据库配置表
- 只把少数确实需要热修改的项做成网页配置
- 对需要重启才生效的项，明确标记“保存后需重启服务”

## 2. 目标 1：监控任务进度、实时更新、任务历史

### 当前已有能力

- `GET /api/v1/tasks`
  - 最近任务
  - 状态筛选
  - `active_only`
- `GET /api/v1/tasks/{task_id}`
  - 单任务进度、状态、错误
- `GET /api/v1/tasks/{task_id}/workspace`
  - 源文、Brief、generation 历史、review、audit
- `/admin/phase5`
  - 看板、diff、人工审核

### 缺口

- 当前已经具备 SSE 实时推送，但还缺告警与环境面板
- 后台页虽然已有统一入口，但 Phase 5 / Phase 6 仍保留为深链页面
- 历史查询还没有更完整的筛选维度：
  - 时间范围
  - 来源
  - 状态流转
  - 是否已推草稿
  - 是否命中人工阻断

### 建议实现

第一阶段：

- 新增统一控制台页：`/admin/console`
- 自动轮询 `/api/v1/tasks` 和当前选中任务的 `/workspace`
- 增加按状态、来源、关键词、起始时间筛选
- 通过快捷入口跳转到 `/admin/phase5` 和 `/admin/phase6`
- 前端每 3 到 5 秒自动轮询 `/api/v1/tasks` 和 `/workspace`

第二阶段：

- 增加 Server-Sent Events 或 WebSocket
- 任务进度实时推送，不再轮询
- 增加任务统计卡片：
  - 今日提交数
  - 当前运行中
  - 今日草稿成功数
  - Phase 4 审稿通过率

当前进度：

- Phase 7A 已完成：统一入口、自动轮询、筛选和详情
- Phase 7B 已完成：运行参数网页配置
- Phase 7C 第一刀已完成：SSE 实时流、监控快照接口、统计卡片
- Phase 7D 第一刀已完成：环境状态面板、测试告警入口、成功率与异常卡片
- Phase 7E 已完成：队列深度、processing、pending 和 worker 心跳观测
- `/admin` 已重设计为主控台：首页直接支持贴链接、看进度、做动作；旧页面保留为高级深链

## 3. 目标 2：网页端配置与设置

### 不建议直接做的事

- 直接在线编辑整份 `.env`
- 在线显示所有密钥明文
- 任何人登录后都能改生产写稿模型

原因：

- `.env` 包含高敏感密钥
- 其中一部分配置要重启才生效
- 其中一部分配置影响部署、数据库和第三方鉴权，不适合通过普通后台直接改

### 建议拆成两层

#### 3.1 可网页配置的“运行参数”

建议先放进数据库配置表，比如：

- Phase 4 写稿模型名
- Phase 4 审稿模型名
- 自动推草稿开关
- 自动反馈 Provider 开关
- Prompt 版本启用状态
- 默认 day offsets
- 任务轮询刷新间隔

这类配置可通过：

- `system_settings` 表
- `GET /api/v1/admin/settings`
- `PUT /api/v1/admin/settings/{key}`

来做。

#### 3.2 仍保留在环境变量的“基础设施配置”

以下建议继续保留在 `.env`：

- 数据库地址
- Redis 地址
- 微信 App Secret
- Bearer Token
- 反馈 Provider API Key
- 管理后台 Basic Auth 密码

这类值只建议做：

- 只读展示“是否已配置”
- 最多支持单项覆盖和服务重启
- 默认不展示明文

## 4. 建议范围

如果下一阶段要做网页控制台，我建议按这个顺序推进：

1. `Phase 7A`
   - `/admin/console`
   - 统一任务监控首页
   - 自动轮询
   - 历史筛选

2. `Phase 7B`
   - `system_settings` 表
   - 可网页修改的运行参数
   - 配置变更审计日志
   - 当前已落第一批参数：写稿模型、审稿模型、自动推草稿、反馈 provider、反馈 day offsets

3. `Phase 7C`
   - 实时推送
   - 统计卡片
   - 当前已落：`/admin/console/stream`、`/api/v1/admin/monitor/snapshot`

4. `Phase 7D`
   - 告警入口
   - 只读环境变量状态面板
   - 更完整的任务成功率指标

5. `Phase 7E`
   - worker / queue 级观测
   - 当前已落：队列深度、processing、pending、worker 心跳

6. `Phase 7F`
   - 告警分级与静默
   - 趋势图和时间序列统计

## 5. 是否值得做

值得做。

原因不是“界面更漂亮”，而是：

- 现在系统已经不再是一次性脚本，而是持续运行的生产流水线
- 有了 Phase 5 和 Phase 6，数据和操作入口已经成型
- 缺的不是后端能力，而是把已有能力收束成统一控制台

换句话说，网页端控制台现在已经是产品化问题，不是技术可行性问题。
