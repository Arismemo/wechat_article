# 标准发布流程

更新时间：2026-03-09
状态：Active

## 1. 目标

把版本发布从“热同步兜底 + 脏工作树运行”收回到可追踪、可回滚、可复现的标准流程。

正式版本发布时：

- 本地工作区必须可解释
- 版本号、CHANGELOG 和发布说明必须同步更新
- 服务器应回到 Git 可追踪状态
- 发布后的 tag、部署记录和 smoke test 结果必须留档

## 2. 发布前检查

在准备 tag 前，至少完成以下动作：

1. 清理非产品产物
   - 删除或忽略 `output/`
   - 删除临时计划文件 `task_plan.md` / `findings.md` / `progress.md`
   - 清理服务器 `.deploy-backup/` 和 `._*` 残留
2. 更新版本信息
   - `README.md`
   - `CHANGELOG.md`
   - `pyproject.toml`
   - `app/main.py`
3. 更新发布与阶段文档
   - `docs/README.md`
   - 当前版本发布说明，例如 `docs/release-v1.1.1.md`
   - 相关阶段文档与部署记录
4. 运行验证
   - `pytest -q`
   - 必要时 `python3 -m compileall app tests`
   - 最少一轮 `/admin`、`/admin/phase5`、`/admin/console/stream` 烟测

## 3. Git 要求

正式发布前应满足：

- 本地完成提交
- 当前分支可推送到远端
- 准备发布的 tag 指向一个明确 commit
- 服务器不应继续长期运行脏工作树

不建议把以下方式当作正式发布：

- 只做 `docker cp`
- 只做热同步覆盖
- 服务器停留在 `git status` 大量脏文件的状态

热同步只能作为临时兜底，不作为正式版本结论。

## 4. 推荐发布步骤

推荐顺序：

1. 本地完成代码、文档和版本号更新
2. 运行：

```bash
pytest -q
```

3. 提交发布 commit
4. 创建 tag，例如：

```bash
git tag -a v1.1.1 -m "Release v1.1.1"
```

5. 推送分支和 tag：

```bash
git push origin main
git push origin v1.1.1
```

6. 使用当前标准部署路径发布：

```bash
bash scripts/deploy_local_from_git.sh
```

如果只是纯代码更新，且不需要重新同步依赖：

```bash
SKIP_SETUP=1 bash scripts/deploy_local_from_git.sh
```

基础设施容器只通过 `scripts/docker_infra.sh` 管理，不再把应用层发布到 Docker。

## 5. 发布后验收

至少检查：

- `GET /healthz`
- `GET /admin`
- `GET /admin/phase5`
- `GET /admin/console/stream?once=true&limit=3`
- `GET /api/v1/admin/monitor/snapshot`

如果本次涉及 worker 观测或队列逻辑，还要确认：

- 5 个 worker 都处于 `healthy`
- `queue_depth / processing_depth / pending_count` 字段正常返回

## 6. 发布留档

每次正式版本发布后，至少更新：

- `CHANGELOG.md`
- 对应版本发布说明
- 阶段部署记录

发布说明中应包含：

- 版本范围
- 本地验证结果
- 线上 smoke test 结果
- 已知边界与不做项
- tag / 发布时间
