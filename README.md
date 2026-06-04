# yundrone-codex-logs

YunDrone 团队内部使用的 TeamView 工具仓库。当前仓库主要解决三件事：

- 拉取 TeamView `usage` / `logs` 数据
- 使用 Typst 生成排行榜 PNG
- 运行飞书长连接机器人，响应 Token `报告` 三合一图

当前线上正式运行形态已经收口为：`self-cloudserver` 只保留飞书长连接机器人，不再对外提供 HTTP API，不再运行榜单守护进程，也暂不运行定时群通报。

## 当前生产状态

截至现在，服务器 `self-cloudserver` 的目标状态是：

- `yundrone-codex-feishu-bot.service`: `active` + `enabled`
- `yundrone-codex-logs.service`: `inactive` + `disabled`
- `yundrone-codex-report-daemon.service`: `inactive` + `disabled`
- `yundrone-codex-feishu-group-reporter.service`: `inactive` + `disabled` 或不存在
- `47593` 端口不监听

这意味着：

- 生产环境只通过飞书长连接机器人工作
- 当前没有公网 HTTP 接口可供拉取 JSON 或 PNG
- 旧 Matplotlib 海报、all-in-one 图、定时 09:30 群通报已经退场

详细部署步骤见 [docs/deploy-self-cloudserver.md](docs/deploy-self-cloudserver.md)。

## 仓库结构

```text
.
├── assets/NotoSansSC/          # Noto Sans SC 字体，Git LFS 管理
├── deploy/systemd/             # systemd unit 模板
├── docs/                       # 部署与运维文档
├── scripts/                    # 仓库级运行入口
├── switchbase_teamview/        # 核心 Python 包
├── tests/                      # 测试
├── typst/                      # Typst 海报模板
├── .codex/check-maxline.json   # 单文件行数约束
├── .env.template               # 环境变量模板
├── teamview_whitelist.template.json
└── README.md
```

## 环境要求

- Python 3.12+
- `uv`
- Git LFS
- Typst 0.14+

首次克隆后先准备字体资源：

```bash
git lfs install
git lfs pull
uv sync
```

说明：

- `assets/NotoSansSC/*.otf` 通过 Git LFS 管理
- 如果字体没拉完整，海报里容易出现方框字或字重失效
- 飞书即时报告和手动 PNG 导出都依赖 `typst` 命令在 `PATH` 中

## 本地配置

先复制模板文件：

```bash
cp .env.template .env
cp teamview_whitelist.template.json teamview_whitelist.json
```

`.env` 至少需要这些变量：

```env
SWITCHBASE_TEAMVIEW_API_KEY=stv_your_api_key_here
SWITCHBASE_TEAMVIEW_WHITELIST_FILE=./teamview_whitelist.json
SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai
FEISHU_APP_ID=cli_your_app_id_here
FEISHU_APP_SECRET=your_feishu_app_secret_here
FEISHU_LOG_LEVEL=INFO
```

可选变量：

```env
SWITCHBASE_TEAMVIEW_OUTPUT_DIR=./outputs
SWITCHBASE_TEAMVIEW_API_HOST=127.0.0.1
SWITCHBASE_TEAMVIEW_API_PORT=8000
SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN=change_this_to_a_long_random_token
```

说明：

- `.env` 和 `teamview_whitelist.json` 已在 `.gitignore` 中忽略
- 所有入口都会自动向上查找并加载 `.env`
- 白名单文件用 `email:` / `username:` / `id:` 匹配用户，`include` 控制是否进入白名单榜单，`alias` 控制展示名
- 飞书即时机器人不需要固定群聊 ID，回复目标来自飞书消息事件

## 主要能力

### 1. TeamView CLI

包入口：

```bash
uv run teamview-cli validate
uv run teamview-cli usage --username groove --json
uv run teamview-cli logs --size 10 --json
```

脚本入口：

```bash
uv run python scripts/run_cli.py validate
```

### 2. Typst 海报生成

推荐使用 Typst 单图入口，一次刷新 TeamView 数据、导出 Typst CSV，并编译出 9 张 PNG：

```bash
uv run python scripts/render_typst_posters.py
```

默认输出到：

```text
outputs/typst-posters/<metric>/<period>.png
```

其中 `metric` 是 `tokens`、`quota`、`intensity`，`period` 是 `daily`、`weekly`、`monthly`。也可以只生成一张图：

```bash
uv run python scripts/render_typst_posters.py --metric quota --period daily
uv run python scripts/render_typst_posters.py --output-dir outputs/typst-posters --ppi 200
```

Typst 入口只负责单 metric + 单 period 的图，不生成 all-in-one 图。如果命令提示找不到 `typst`，先安装 Typst 或确认 `typst` 已在 `PATH` 中。

### 3. 飞书机器人

本项目当前最重要的生产能力是飞书长连接机器人：

```bash
uv run teamview-feishu-bot
```

或者：

```bash
uv run python scripts/run_feishu_bot.py
```

机器人行为：

- 使用飞书官方 `lark-oapi` 长连接，不需要公网回调 URL
- 订阅 `im.message.receive_v1`
- 支持群聊 `@机器人 报告`
- 支持单聊直接发 `报告`
- 如果只是 `@机器人`、发送空白或发送其他内容，会返回使用方法卡片
- `日报`、`周报`、`月报`、`总览`、`quota`、`成本强度` 等旧命令会返回使用方法
- 如果群消息包含 `@所有人`，会被直接忽略，不回复 help 也不发图
- 即时交互会给原消息添加状态表情：处理中 `Alarm`，成功 `DONE`，非法输入 `THINKING`，处理失败 `SWEAT`
- 收到 `报告` 后按当前分钟即时生成 Typst Token 日/周/月三合一图
- 统计窗口固定使用 `Asia/Shanghai`
- 回复使用 `whitelist` scope，只展示 `teamview_whitelist.json` 中 `include=true` 的成员
- 全局同一时间只允许制作一张图，制作中会提示 `正在制作中，请勿重复请求`
- 成功发图后的 10 秒内再次请求，会提示剩余冷却秒数
- 同一分钟复用缓存，跨分钟自动失效
- 命中 `teamview_whitelist.json` 里的 `alias` 后会展示该名称，未命中则回退上游显示名

三合一海报包含：

- 日报：当天 `00:00` 到当前分钟
- 周报：本周一 `00:00` 到当前分钟
- 月报：本月 1 日 `00:00` 到当前分钟

缓存目录：

```text
outputs/feishu-cache/whitelist/tokens/trio/<YYYYMMDDHHMM>/
```

例如：

- `12:23:12` 请求报告，会生成日/周/月三个窗口到 `12:23`
- `12:23:59` 再请求报告，会复用同一分钟缓存
- `12:24:00` 之后首次请求，会生成新的 `12:24` 版本

幂等与去重：

- 同一条飞书消息在处理进行中重投时，只会处理一次
- 只有“成功发图”后才会写入成功去重状态
- 如果生成失败或上传失败，平台重投同一 `message_id` 时会再次尝试
- 非法输入的使用方法提示会记为成功回复

日志里可以看到这些结果：

- `generated`
- `cache-hit`
- `duplicate-inflight`
- `deduped-succeeded`
- `failed-generate`
- `failed-send-image`
- `failed-send-text`

### 4. 可选 API 服务

仓库仍保留 `teamview-api` / `scripts/run_api.py`，适合本地开发或内网只读 JSON 调试。当前 API 只保留 `/api/public-rankings/<period>`，不再提供 `/api/generated-reports/*`。

它不是当前生产部署的一部分。

## 字体说明

仓库内置 `assets/NotoSansSC/*.otf`。如果发现海报字体异常，优先检查：

1. `git lfs pull` 是否执行过
2. `assets/NotoSansSC/` 是否是真实 OTF 文件，而不是 LFS pointer
3. 运行入口是否通过仓库源码启动，而不是误用了旧 site-packages 安装版本

## 当前生产部署约定

生产服务器当前只保留一个 systemd 服务：

- `yundrone-codex-feishu-bot.service`

它使用的入口是：

```text
/home/groove/apps/yundrone-codex-logs/.venv/bin/python -m scripts.run_feishu_bot
```

生产上不再保留：

- `yundrone-codex-logs.service`
- `yundrone-codex-report-daemon.service`
- `yundrone-codex-feishu-group-reporter.service`

也不再监听：

- `47593`

## 本地验证

运行测试：

```bash
uv run pytest -q
```

检查 maxline：

```bash
python3 /Users/groove/.codex/skills/check-maxline/scripts/check_maxline.py --root .
```

## 相关文档

- 部署与运维: [docs/deploy-self-cloudserver.md](docs/deploy-self-cloudserver.md)
- 本地字体资源: `assets/NotoSansSC/`
- 飞书 systemd unit 模板: `deploy/systemd/yundrone-codex-feishu-bot.service`
