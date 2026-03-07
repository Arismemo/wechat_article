# 微信公众号读取与浏览器控制方案调研

更新时间：2026-03-07

## 1. 检索范围

| 方向 | 检索关键词示例 | 目的 |
| --- | --- | --- |
| 微信公众号文章读取 | `微信公众号 文章 导出 markdown mp.weixin crawler` | 查找可直接复用的文章抓取、导出、评论/阅读量方案 |
| 微信公众号订阅/RSS | `公众号 RSS github` | 查找偏历史跟踪、订阅、定时更新的替代方案 |
| Claude Code / Skill | `Claude Code skill playwright`, `agent-browse`, `browser skill` | 查找可直接接入 Claude Code 或类似 coding agent 的技能/插件 |
| 浏览器自动化 | `Playwright MCP`, `Stagehand`, `browser-use`, `Patchright` | 查找 2026 仍活跃、可作为抓取兜底或复杂站点自动化的方案 |

说明：

- 本文只记录本轮已核实的公开结果，不包含未验证的论坛讨论或二手转载。
- “适配判断”一列是基于当前仓库目标做的推断，不是来源原文。

## 2. 微信公众号文章读取方案

| 方案 | 类型 | 已核实信息 | 主要来源 | 对当前仓库的适配判断 |
| --- | --- | --- | --- | --- |
| `wechat-article-exporter` | 公众号文章下载/导出平台 | 支持搜索公众号、抓取文章链接、抓取文章内容、抓取阅读量与评论数据、导出 `html/txt/markdown/excel/json/docx`、缓存文章数据、按作者/标题/发布时间/原创过滤、合集下载、API、Docker、Cloudflare。项目 README 明确写到 HTML 可 `100%` 还原文章排版与样式。原理说明里写明：借助公众号后台写文章时可搜索其它公众号文章这一能力来抓取指定公众号全部文章。 | [GitHub](https://github.com/wechat-article/wechat-article-exporter) <br> [Features](https://docs.wxdown.online/misc/features) <br> [私有部署](https://docs.wxdown.online/advanced/private-deploy) | 很适合“批量抓历史文章、评论、阅读量、导出多格式”的扩展场景；对当前“单篇链接进入生成流水线”的主链路来说偏重。 |
| `wxdown-service` | `wechat-article-exporter` 配套增强服务 | README 说明这是 `down.mptext.top` 的增强服务。它会启动 `mitmproxy` 并加载 `credential.py` 插件，拦截微信流量写入 `credentials.json`，再由 watcher 监听文件变化并通过 websocket 通知浏览器；适合自动拿公众号 `Credential`。提供 PyInstaller 打包和源码构建方式。 | [GitHub](https://github.com/wechat-article/wxdown-service) | 如果后续要接入 `wechat-article-exporter` 体系，值得直接复用；单独接入当前仓库意义不大。 |
| `自动抓取 Credential (mitmproxy 插件版)` | 凭据采集流程 | 文档说明可通过 `mitmdump -s credential.py -q` 启动插件，监控微信内置浏览器打开的文章页面，自动抓到公众号 `Credential`，并在凭据过期时重新打开文章自动刷新。 | [文档](https://docs.wxdown.online/advanced/auto-detect-credential) | 对“公开文章正文抓取”不是必需；对“批量抓取历史文章、评论、阅读量”非常关键。 |
| `we-mp-rss` | 公众号订阅/RSS 系统 | GitHub 页面的 about 文案直接列出：转 Markdown、转 PDF、定时更新订阅文章、生成 RSS、导出订阅源、支持 Webhook / API / AI Agent 接入。 | [GitHub](https://github.com/rachelos/we-mp-rss) | 更适合“长期订阅、RSS、Webhook、定时更新”方向，不适合作为当前按单篇 URL 触发的主抓取方案。 |
| `wewe-rss` | 公众号订阅/RSS 系统 | GitHub about 文案写明：更优雅的微信公众号订阅方式，支持私有化部署、RSS 生成，且“基于微信读书”。 | [GitHub](https://github.com/cooderl/wewe-rss) | 偏订阅入口，不是当前项目需要的单篇抓取管线。 |

## 2.1 本地源码核对后的对接结论

| 项目 | 已核实接口或行为 | 结论 |
| --- | --- | --- |
| `wechat-article-exporter` 单篇下载 | 源码里存在 `GET /api/public/v1/download?url=<article_url>&format=html`，服务端直接抓公众号文章 URL 并输出规范化后的 HTML；同接口还支持 `markdown/text/json`。 | 这条接口足够支撑当前仓库的“单篇文章抓取 PoC”，不需要先接 credentials。 |
| `wechat-article-exporter` 账号解析 | 源码里存在 `GET /api/public/v1/accountbyurl?url=<article_url>`。 | 可以据此从单篇文章 URL 反查公众号 `fakeid`。 |
| `wechat-article-exporter` 历史文章列表 | 源码里存在 `GET /api/public/v1/article?fakeid=<fakeid>&begin=0&size=5`。 | 这条能力适合后续做“历史文章回填 / 同号上下文抓取”。 |
| `wxdown-service` | 本体是 `mitmproxy + credential.py + watchdog + websocket` 的本地程序；职责是写入 `credentials.json` 并通过 websocket 通知浏览器。 | 它不是当前 FastAPI 后端可直接调用的 HTTP 服务，更适合作为 `wechat-article-exporter` 前端或桌面侧辅助工具。 |

当前仓库已落地的 PoC：

- 新增服务适配层：`app/services/wechat_exporter_service.py`
- 新增命令行 PoC：`scripts/wechat_exporter_poc.py`
- 在 `WECHAT_EXPORTER_BASE_URL` 配置存在时，抓取顺序会自动变成 `httpx -> exporter -> Playwright`

## 3. Claude Code Skill / 插件结果

| 方案 | 类型 | 已核实信息 | 主要来源 | 对当前仓库的适配判断 |
| --- | --- | --- | --- | --- |
| `lackeyjb/playwright-skill` | Claude Code Playwright Skill | README 说明这是 Claude Code 插件格式的 skill，可通过 `/plugin marketplace add lackeyjb/playwright-skill` 和 `/plugin install playwright-skill@playwright-skill` 安装；定位是让 Claude 自动写并执行 Playwright 自动化。 | [GitHub](https://github.com/lackeyjb/playwright-skill) | 适合参考其 skill 结构和交互方式；但当前仓库本身已有 Playwright Python 依赖，直接抄用价值有限。 |
| `browserbase/agent-browse`（已重定向到 `browserbase/skills`） | Claude Code 插件/Skill 集合 | README 说明这是 Browserbase 的 Claude Code skill 集合，其中 `browser` skill 支持通过 CLI 自动化浏览器，并支持远程 Browserbase session、anti-bot stealth、CAPTCHA solving、residential proxies。安装入口仍使用 `browserbase/agent-browse`。 | [GitHub](https://github.com/browserbase/skills) | 如果后面要处理更复杂的登录态、风控、代理和远程浏览器，这条线值得评估；对当前公开微信文章读取场景偏重。 |

## 4. 浏览器控制与无头浏览器方案

| 方案 | 类型 | 已核实信息 | 主要来源 | 对当前仓库的适配判断 |
| --- | --- | --- | --- | --- |
| `Playwright MCP` | 官方 MCP 浏览器控制服务 | README 写明其关键特性是使用 Playwright 的 accessibility tree，而不是像素输入；不需要视觉模型；更 deterministic。文档同时给出了 Claude Code 和 Codex 的安装方式。配置里支持 `chrome/firefox/webkit/msedge`，也支持 CDP endpoint。 | [GitHub](https://github.com/microsoft/playwright-mcp) | 如果后面要把浏览器操作交给 MCP 客户端，这是最稳的官方基线；但对当前 FastAPI 服务端抓取逻辑，不如直接保留 Python Playwright 简单。 |
| `Playwright Python Browsers 文档` | 官方浏览器运行模式说明 | 官方文档明确写到 `chromium` channel 可启用 “new headless mode”；引用 Chrome 官方描述称它是“real Chrome browser”，更真实、更可靠、功能更多，更适合高精度端到端测试或扩展测试。 | [官方文档](https://playwright.dev/python/docs/browsers) | 这是当前仓库最应优先落地的增强项：保留 Playwright 兜底，但切到更接近真实 Chrome 的运行方式。 |
| `Stagehand` | Browserbase 的 AI 浏览器自动化框架 | 文档和 GitHub 都强调它结合自然语言和代码，核心原语有 `act`、`extract`、`observe`、`agent`；强调可重复、可组合、能适应站点变化，并兼容 Chromium 系浏览器。 | [Stagehand 文档](https://docs.stagehand.dev/) <br> [GitHub](https://github.com/browserbase/stagehand) | 很适合复杂站点、多步骤工作流、需要结构化抽取的场景；对当前微信文章抓取是备选，不应先于官方 Playwright。 |
| `Stagehand act()` | 单步自愈动作 | 文档写明 `act()` 支持自然语言动作、self-healing、caching，并自动处理 iFrame 与 Shadow DOM。 | [官方文档](https://docs.stagehand.dev/v3/basics/act) | 如果后面发现页面结构变化频繁、CSS 选择器不稳定，这比手写 selector 更抗变。 |
| `Stagehand agent()` | 多步 agent 模式 | 文档写明 `agent()` 可做复杂浏览器工作流，并提供 `CUA / DOM / Hybrid` 三种模式；功能表里明确 DOM/Hybrid 支持变量、流式、结构化输出、DOM-based actions。 | [官方文档](https://docs.stagehand.dev/v3/basics/agent) | 适合更“agent 化”的采集任务；当前项目阶段还不需要上这么重。 |
| `Stagehand + Selenium` | 共享会话集成 | 文档写明 Stagehand v3 可与 Selenium WebDriver 操作同一浏览器 session，但该集成要求 Browserbase，不支持 `env: "LOCAL"`。 | [官方文档](https://docs.stagehand.dev/v3/integrations/selenium) | 对当前仓库没有直接价值，可忽略。 |
| `Browser Use MCP Server` | 托管/本地 MCP 浏览器控制 | 文档写明 Browser Use 提供托管 MCP Server，可用于 Claude Code；也提供本地开源 `uvx browser-use --mcp`。托管版支持 `browser_task`、`list_browser_profiles`、`monitor_task`，并支持持久认证 profile。 | [官方文档](https://docs.browser-use.com/customize/integrations/mcp-server) | 如果要快速接入带登录态的远程浏览器任务，它很方便；但会引入云端 API 与额外成本。 |
| `Browser Use Documentation MCP` | 只读文档 MCP | 文档写明它为 Claude Code / Codex 等提供只读文档访问，不提供浏览器控制能力。 | [官方文档](https://docs.browser-use.com/customize/integrations/docs-mcp) | 对写代码和查 API 有帮助，但不能直接解决抓取。 |
| `Browser Use CodeAgent` | 本地 Python 代码代理 | 文档写明 CodeAgent 会在本地写并执行 Python 代码，面向可复用的数据抽取任务；“Best for” 里明确提到适合 `100s-1000s of items` 的规模化数据抽取和可重复工作流。 | [官方文档](https://docs.browser-use.com/legacy/code-agent/basics) | 如果后面要做大规模采集或离线抽取任务，这条路线可研究；当前项目没必要先引入。 |
| `Browser Use Sandbox` | 云端生产运行 | 文档写明云端 sandbox 负责 agents、browsers、persistence、auth、cookies、LLMs，并支持 `cloud_profile_id`、代理国家、超时等参数。 | [官方文档](https://docs.browser-use.com/legacy/sandbox/quickstart) | 对处理登录态、代理、云端运行有吸引力，但会把抓取链路绑定到第三方云。 |
| `Patchright Python` | Playwright stealth 变体 | GitHub about 文案写明它是 “Undetected Python version of the Playwright testing and automation library”。 | [GitHub](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) | 只在遇到明显反自动化或指纹限制时再考虑；不建议作为当前主链路默认选型。 |

## 5. 本轮可落地结论

| 优先级 | 结论 | 原因 | 关联方案 |
| --- | --- | --- | --- |
| 高 | 当前主链路继续保持 `httpx + HTML 解析`，只把 Playwright 当兜底。 | 你现在已经跑通了“公开微信文章 URL -> 草稿箱”的最小闭环，主链路没有必要升级成更重的 agent 框架。 | 当前仓库实现；[Playwright Python 文档](https://playwright.dev/python/docs/browsers) |
| 高 | 优先把 Playwright 兜底升级到更接近真实 Chrome 的运行方式。 | 官方文档已明确 “new headless mode” 更真实、更可靠，风险最低。 | [Playwright Python 文档](https://playwright.dev/python/docs/browsers) |
| 中 | 如果后续要补“批量历史文章、评论、阅读量、导出多格式”，优先评估 `wechat-article-exporter` / `wxdown-service`。 | 这套体系已经把公众号搜索、评论/阅读量、Credential 采集、导出格式、Docker/Cloudflare 都做了。 | [wechat-article-exporter](https://github.com/wechat-article/wechat-article-exporter) <br> [wxdown-service](https://github.com/wechat-article/wxdown-service) |
| 中 | 如果后续遇到 DOM 波动大、站点流程复杂、需要结构化抽取，可再评估 Stagehand。 | 它在“自然语言动作 + 可控代码 + 自愈 + 缓存”这条线上更强，但也明显更重。 | [Stagehand](https://docs.stagehand.dev/) |
| 低 | Browser Use、Browserbase skill、Patchright 先不接主链路。 | 这些方案都更偏云端托管、代理/反爬、复杂 agent 或 stealth 需求，目前还不是首要问题。 | [Browser Use MCP](https://docs.browser-use.com/customize/integrations/mcp-server) <br> [browserbase/skills](https://github.com/browserbase/skills) <br> [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) |

## 6. 推断与空白

| 项目 | 结论 |
| --- | --- |
| 专用“微信公众号文章读取” Claude Code Skill | 基于本轮公开搜索，未发现一个成熟且公开的专用 Claude Code skill。公开可见的方案主要分成两类：通用浏览器 skill / MCP，以及公众号下载或 RSS 系统。 |
| 当前仓库短期最值得做的改动 | 不是引入新框架，而是把现有 Playwright fallback 调稳，并单独评估是否需要接入 `wechat-article-exporter` 生态。 |
