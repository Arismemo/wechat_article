# ADR-0001：从文件拷贝切换到 Git 部署

更新时间：2026-03-08
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
- 新增 `scripts/deploy_prebuilt_from_local.sh`，用于服务器冷构建过慢时的本地预构建兜底

当前正式路径：

- GitHub 仍是唯一源码基线
- 服务器工作树仍坚持 `git pull --ff-only`
- 由于服务器下载 Chromium 过慢，当前正式镜像发布路径改为：
  - 本地预构建 `linux/amd64` 镜像
  - `docker save | ssh ... docker load`
  - 服务器执行 migration
  - `docker compose up -d --no-build --force-recreate`
- 这不是回退到“文件覆盖式同步”，因为镜像和源码版本都仍由 Git 提交固定

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
- `scripts/deploy_prebuilt_from_local.sh`
  - 本地构建 `linux/amd64` 镜像并打多个服务标签
  - 通过 `docker save | ssh ... docker load` 推到服务器
  - 服务端仍先 `git pull`，再做 migration 和 `docker compose up -d --no-build --force-recreate`
  - 支持 `SKIP_LOCAL_BUILD=1 BASE_IMAGE=...`，在本机已有同版本镜像时直接复用

## 影响

- 后续部署默认路径已从“文件同步”切为“Git 拉取 + 预构建镜像重建 + migration”
- 服务器上不再接受任意目录覆盖式同步，降低误覆盖风险
- 版本固定时，应同时固定：
  - Git commit
  - Git tag
  - 预构建镜像 tag
