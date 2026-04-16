# yundrone-codex-logs

YunDrone 团队内部使用的 TeamView 工具仓库。当前仓库主要解决三件事：

- 拉取 TeamView `usage` / `logs` 数据
- 生成排行榜 JSON 与海报 PNG
- 运行飞书长连接机器人，响应 `日报` / `周报` / `月报`

当前线上正式运行形态已经收口为：`weex-cloudserver` 只保留飞书机器人服务，不再对外提供 HTTP API，也不再常驻运行榜单守护进程。

## 当前生产状态

截至现在，服务器 `weex-cloudserver` 的实际状态是：

- `yundrone-codex-feishu-bot.service`: `active` + `enabled`
- `yundrone-codex-logs.service`: `inactive` + `disabled`
- `yundrone-codex-report-daemon.service`: `inactive` + `disabled`
- `47593` 端口当前没有监听

这意味着：

- 生产环境只有飞书机器人在工作
- 当前没有公网 HTTP 接口可供拉取 JSON 或 PNG
- `scripts/fetch_server_reports.py` 只适用于你另行启用 API 服务的环境，不适用于当前生产服务器

详细部署步骤见 [docs/deploy-weex-cloudserver.md](docs/deploy-weex-cloudserver.md)。

## 仓库结构

```text
.
├── assets/NotoSansSC/          # Noto Sans SC 字体，Git LFS 管理
├── deploy/systemd/             # systemd unit 模板
├── docs/                       # 部署与运维文档
├── scripts/                    # 仓库级运行入口
│   └── poster/                 # 海报生成子系统
├── switchbase_teamview/        # 核心 Python 包
├── tests/                      # 测试
├── .codex/check-maxline.json   # 单文件行数约束
├── .env.template               # 环境变量模板
├── teamview_aliases.template.json
└── README.md
```

## 环境要求

- Python 3.12+
- `uv`
- Git LFS

首次克隆后先准备字体资源：

```bash
git lfs install
git lfs pull
uv sync
```

说明：

- `assets/NotoSansSC/*.otf` 通过 Git LFS 管理
- 如果字体没拉完整，海报里容易出现方框字或字重失效

## 本地配置

先复制模板文件：

```bash
cp .env.template .env
cp teamview_aliases.template.json teamview_aliases.json
```

`.env` 至少需要这些变量：

```env
SWITCHBASE_TEAMVIEW_API_KEY=stv_your_api_key_here
SWITCHBASE_TEAMVIEW_ALIAS_FILE=./teamview_aliases.json
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

- `.env` 和 `teamview_aliases.json` 已在 `.gitignore` 中忽略
- 所有入口都会自动向上查找并加载 `.env`
- 别名文件以邮箱为主键，飞书机器人与本地海报都会复用它

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

### 2. 海报生成

当前海报系统已经拆到 `scripts/poster/`，职责分层是：

- `models.py`: 标准化 snapshot / request / config
- `policy.py`: `filtered` / `all-members` 等策略
- `loaders.py`: `api` / `json` / `teamview` / `memory-test-hook`
- `layout.py`: 刻度、边距、track 几何
- `render.py`: Matplotlib 绘制
- `export.py`: PNG 导出
- `cli.py`: Typer CLI

常用命令：

从本地 JSON 生成海报：

```bash
uv run python -m scripts.poster \
  --input-source json \
  --period daily \
  --input-file ./outputs/daily.json
```

直接从 TeamView 原始数据生成全员榜：

```bash
uv run python -m scripts.poster \
  --input-source teamview \
  --period weekly \
  --scope all-members \
  --top-n 7
```

如果你启用了本地 API，也可以从 API 拉：

```bash
uv run python -m scripts.poster \
  --input-source api \
  --period daily \
  --base-url http://127.0.0.1:8000/api/public-rankings \
  --token "$SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN"
```

关键约束：

- `--scope filtered|all-members`
- `--input-source api` 只允许 `--scope filtered`
- `--scope all-members` 必须配合 `teamview`、`json` 或 `memory-test-hook`
- `--period all` 会一次输出三张图，不会再把三份榜单拼到一张图里
- 默认输出目录是 `./outputs/`
- 运行时会打印 `[poster] ...` 调试日志，方便 Agent 和脚本排障

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
- 支持群聊 `@机器人 日报|周报|月报`
- 支持单聊直接发 `日报|周报|月报`
- 收到消息后按当前分钟即时生成榜单
- 统计窗口固定使用 `Asia/Shanghai`
- 回复使用 `all-members` scope
- 当前固定返回 Top 7
- 同一分钟复用缓存，跨分钟自动失效
- 命中邮箱别名后会展示别名

即时窗口规则：

- `日报`: 当天 `00:00` 到当前分钟
- `周报`: 本周一 `00:00` 到当前分钟
- `月报`: 本月 1 日 `00:00` 到当前分钟

缓存目录：

```text
outputs/feishu-cache/all-members/<period>/<YYYYMMDDHHMM>/
```

例如：

- `12:23:12` 请求日报，会生成 `00:00 -> 12:23`
- `12:23:59` 再请求日报，会复用同一分钟缓存
- `12:24:00` 之后首次请求，会生成新的 `12:24` 版本

幂等与去重：

- 同一条飞书消息在处理进行中重投时，只会处理一次
- 只有“成功发图”后才会写入成功去重状态
- 如果生成失败或上传失败，平台重投同一 `message_id` 时会再次尝试

日志里可以看到这些结果：

- `generated`
- `cache-hit`
- `duplicate-inflight`
- `deduped-succeeded`
- `failed-generate`
- `failed-send-image`
- `failed-send-text`

### 4. 可选服务

仓库里仍然保留两类可选能力，但它们不是当前生产部署的一部分：

- `teamview-api` / `scripts/run_api.py`
- `teamview-report-daemon` / `scripts/run_report_daemon.py`

它们适合：

- 本地开发调试
- 内网环境自行启用
- 需要对外暴露只读 JSON / PNG 接口的单独部署

它们不适合拿来描述当前 `weex-cloudserver` 的线上状态，因为现在那台服务器已经停掉了这两类服务。

## 字体说明

仓库内置 `assets/NotoSansSC/*.otf`，当前渲染逻辑会按用途选不同字重：

- 标题: `Bold`
- 榜单类型: `Bold`
- 用户名: `Medium`
- 时间与数字: `Regular` / `Light`

如果发现海报字体异常，优先检查：

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

- 部署与运维: [docs/deploy-weex-cloudserver.md](docs/deploy-weex-cloudserver.md)
- 本地字体资源: `assets/NotoSansSC/`
- 飞书 systemd unit 模板: `deploy/systemd/yundrone-codex-feishu-bot.service`

