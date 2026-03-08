# Phase 7 统一控制台部署记录

更新时间：2026-03-08
状态：Completed

## 1. 本次目标

将 Phase 7C 第一刀发布到服务器：

- 统一控制台接入 SSE 实时流
- 增加监控快照接口
- 增加统计卡片
- 保持 `/admin` 单入口不变

## 2. 本次提交

- Git commit：`c6f02a2`
- 标题：`Start phase 7C realtime monitoring`

## 3. 本地验证

- `pytest -q`
  - 结果：`64 passed`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
  - 结果：通过

新增验证重点：

- `GET /api/v1/admin/monitor/snapshot`
- `GET /admin/console/stream?once=true`
- `/admin/console` 页面渲染文案

## 4. 服务器发布方式

本次优先尝试“预构建镜像发布”：

1. 本地构建 `linux/amd64` 镜像
2. 通过 `docker save | ssh ... docker load` 上传到服务器
3. 服务器 `git pull --ff-only`
4. `docker compose up -d --no-build --force-recreate api`

实际结果：

- 预构建镜像已在本地成功构建
- 远端镜像加载较慢，但最终服务器已完成：
  - `git pull --ff-only origin main`
  - `api` 容器重建
  - `alembic upgrade head`
- 本次无 schema 变更，worker 无需跟随重启

## 5. 服务器验收

服务器环境：

- 远端工作树：`/home/liukun/j/code/wechat_artical`
- 远端 HEAD：`c6f02a2`
- 服务状态：`wechat_artical_api` healthy

实际 smoke test：

- `GET https://auto.709970.xyz/healthz`
  - 返回：`{"status":"ok"}`
- `GET https://auto.709970.xyz/admin/console`
  - 页面已包含：
    - `统一控制台`
    - `自动实时更新（优先 SSE，失败时回退轮询）`
    - `当前模式：等待连接`
- `GET https://auto.709970.xyz/api/v1/admin/monitor/snapshot?limit=5`
  - 使用当前服务器 `API_BEARER_TOKEN` 验证通过
  - 返回统计摘要和最近任务列表
- `GET https://auto.709970.xyz/admin/console/stream?once=true&limit=5`
  - 使用后台 Basic Auth 验证通过
  - 返回 `event: snapshot`

## 6. 当前结果

Phase 7 当前已具备：

- `/admin`
  - 单入口控制台
- `/admin/console`
  - 监控首页
  - 统计卡片
  - SSE 实时推送
  - 轮询回退
- `/admin/settings`
  - 运行参数网页配置
- `/admin/phase5`
  - 审核台
- `/admin/phase6`
  - 反馈台

## 7. 后续建议

下一刀建议进入 Phase 7D：

- 只读环境变量状态面板
- 告警入口
- 更完整的成功率和异常卡片
