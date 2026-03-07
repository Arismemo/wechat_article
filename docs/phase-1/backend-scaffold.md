# 阶段 1 后端骨架文档

更新时间：2026-03-07
状态：Completed

## 1. 目标

阶段 1 的目标是建立可持续扩展的后端基础骨架，而不是一次性把所有业务逻辑写完。

本阶段必须完成：

- FastAPI 应用入口
- 配置系统
- 数据库连接与模型注册
- 第一版迁移脚本
- 最小 API：任务创建、状态查询
- 审计留痕
- `docker compose` 运行方案

## 2. 目录结构

```text
app/
├── api/
├── core/
├── db/
├── models/
├── repositories/
├── schemas/
├── services/
└── main.py
```

## 3. 设计原则

- 状态机先于复杂业务逻辑。
- 数据库模型先于 worker。
- 审计日志从第一天开始就落库。
- 接口先做“最小可用”，后续再加任务队列和异步编排。
- 固定可靠的服务优先容器化，避免服务器环境漂移。
- 遇到端口冲突时，只修改本项目容器端口映射，不调整服务器上其它服务。

## 4. 本阶段交付

- `app/main.py`
- `app/settings.py`
- `app/models/*`
- `app/api/ingest.py`
- `app/api/tasks.py`
- `migrations/versions/20260307_0001_init_core_tables.py`
- `.env.example`
- `Dockerfile`
- `docker-compose.yml`

## 5. 阶段 1 完成标准

- 可以启动 FastAPI 应用
- 可以创建任务并写入数据库
- 可以查询任务状态
- 可以记录审计日志
- 代码结构足以承接阶段 2 抓取和阶段 3 研究层扩展

## 6. 当前验证结果

- Python 语法编译通过：`python3 -m compileall app migrations`
- FastAPI 应用对象导入通过：`from app.main import app`
- 单元测试通过：`python3 -m unittest discover -s tests -p 'test_*.py'`
- 服务器侧 `docker compose` 部署完成
- `alembic upgrade head` 执行成功
- `POST /api/v1/ingest/link` 与 `GET /api/v1/tasks/{task_id}` smoke test 通过

当前已知缺口：

- 当前本机运行环境未安装 `psycopg`
- 但服务器侧已经完成真实数据库连接和 API 写库验证
- 详细部署结果见 `docs/phase-1/deployment-log.md`
