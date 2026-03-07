# ADR-0001：从文件拷贝切换到 Git 部署

更新时间：2026-03-07
状态：Accepted

## 背景

阶段 1 和阶段 2 初期使用 `tar + ssh` 把本地代码同步到服务器。该方式虽然快，但在 macOS 环境下会反复带入 AppleDouble `._*` 文件，已经两次污染远端目录并触发 Alembic `null bytes` 错误。

## 决策

项目切换到 Git 为中心的部署方式：

- 本地仓库初始化 Git
- `.gitignore` 持续忽略 `._*`、`.DS_Store`、`.env`、`data/`
- 后续推送到 GitHub 远程仓库
- 服务器改为 `git pull --ff-only` 拉取代码，而不是继续接收 `tar + ssh` 文件拷贝

## 原因

- Git 可以天然避免未追踪垃圾文件进入远端工作区
- 代码变更可追溯
- 服务器部署流程更可重复
- 后续阶段引入多人协作和回滚时更稳

## 当前状态

已完成：

- `.gitignore` 已覆盖 `._*`
- 已配置 GitHub `origin`
- 新增 `scripts/sync_to_server.sh` 作为临时过渡同步方案，并显式禁用 macOS 扩展属性打包
- 新增 `scripts/deploy_from_git.sh` 作为服务器侧 Git 部署入口
- 新增 `scripts/repair_server_git_checkout.sh`，用于修复服务器损坏的 `.git` 元数据并保留 `.env` / `data/`
- Dockerfile 已拆分依赖层与代码层，`requirements.runtime.txt` 与 Playwright 浏览器层可在代码变更后继续复用缓存

待完成：

- 将服务器正式部署路径从“临时 `sync_to_server.sh` + 容器注入代码”完整切到“纯 Git 拉取 + 正常镜像构建”

## 追加记录

2026-03-07 晚间，服务器目录 `/home/liukun/j/code/wechat_artical/.git` 出现损坏：

- `git rev-parse HEAD` 报错 `bad object HEAD`
- `refs/heads/main`、`refs/remotes/origin/main` 指向失效对象

为避免再次依赖手工排查，仓库新增：

- `scripts/repair_server_git_checkout.sh`
  - 备份远端旧 `.git`
  - 原地重建 `main` 分支 Git 工作树
  - 重新绑定 `origin`
  - `git fetch --depth=1 origin main`
  - `git reset --hard origin/main`
- `scripts/deploy_from_git.sh`
  - 增加坏 Git 工作树前置检查
  - 支持 `SERVICES=...` 与 `SKIP_BUILD=1` 两个部署参数
- `Dockerfile`
  - 改为先安装 `requirements.runtime.txt` 中的运行时依赖
  - 再执行 `python -m playwright install --with-deps --no-shell chromium`
  - 最后才复制 `app/`、`migrations/`、`scripts/`
  - 这样普通代码改动不会导致 Playwright 浏览器层失效

## 影响

- 后续部署默认路径应从“文件同步”转为“Git 拉取 + 容器重建 + migration”
- 服务器上不再接受任意目录覆盖式同步，降低误覆盖风险
