# yundrone-codex-logs

YunDrone 团队内部使用的 TeamView 管理工具仓库，包含：

- TeamView 外部接口 Python 包
- 命令行验证工具
- 成员用量与日榜 / 周榜 / 月榜单页看板

项目主体代码保留在 `switchbase_teamview/`，运行入口放在 `scripts/`，仓库层次更适合直接发布和协作。

## 目录结构

```text
.
├── switchbase_teamview/        # 核心 Python 包
├── scripts/                    # 仓库级运行入口与工具子系统
│   └── poster/                 # 海报生成子系统
├── tests/                      # 测试
├── .codex/check-maxline.json   # 单文件行数约束
├── .env.template               # 环境变量模板
├── teamview_aliases.template.json
├── pyproject.toml
└── README.md
```

## 环境要求

- Python 3.12+
- `uv`

## 安装依赖

```bash
uv sync
```

如果是首次克隆仓库，先安装 Git LFS，再拉取字体资源：

```bash
git lfs install
git lfs pull
```

说明：

- `assets/NotoSansSC/*.otf` 使用 Git LFS 管理
- 这样可以保留字体随仓库分发，同时避免普通 Git 历史被大体积二进制文件持续膨胀

## 本地配置

不要直接提交真实配置。先复制模板文件：

```bash
cp .env.template .env
cp teamview_aliases.template.json teamview_aliases.json
```

然后按需修改 `.env`：

```env
SWITCHBASE_TEAMVIEW_API_KEY=stv_your_api_key_here
SWITCHBASE_TEAMVIEW_ALIAS_FILE=./teamview_aliases.json
SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai
SWITCHBASE_TEAMVIEW_WEB_HOST=127.0.0.1
SWITCHBASE_TEAMVIEW_WEB_PORT=8000
SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN=change_this_to_a_long_random_token
```

说明：

- `.env` 和 `teamview_aliases.json` 已在 `.gitignore` 中忽略
- CLI 和 Web 会自动读取当前工作目录向上查找到的 `.env`
- 邮箱别名文件以邮箱为主键，格式示例见 `teamview_aliases.template.json`

## 命令行用法

使用包入口：

```bash
uv run teamview-cli validate
uv run teamview-cli usage --username groove --json
uv run teamview-cli logs --size 10 --json
```

使用仓库入口脚本：

```bash
uv run python scripts/run_cli.py validate
```

## Web 看板

启动方式：

```bash
uv run teamview-web
```

或者：

```bash
uv run python scripts/run_web.py
```

启动后访问：

```text
http://127.0.0.1:8000
```

可查看：

- 固定时间段的全员用量
- 日榜 / 周榜 / 月榜总量排行（分别按今日累计 / 本周累计 / 本月累计统计，时区固定为 Asia/Shanghai）
- 邮箱主键的别名维护

## 给 Aily / 外部调度器使用的公开榜单接口

服务额外提供了 3 个只读接口：

- `/api/public-rankings/daily?token=...`
- `/api/public-rankings/weekly?token=...`
- `/api/public-rankings/monthly?token=...`

示例：

```bash
curl "http://127.0.0.1:8000/api/public-rankings/daily?token=$SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN"
```

说明：

- `token` 来自 `.env` 中的 `SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN`
- `daily` / `weekly` / `monthly` 分别表示今日累计 / 本周累计 / 本月累计，时区固定为 `Asia/Shanghai`
- 这是一层“带随机 key 的 URL 门槛”，适合 Aily 这类外部定时器直接拉取
- 它能降低被随手扫到就拿到数据的风险，但**不等于严格鉴权**
- 如果后续要长期公网开放，建议再叠加 IP 限制、反向代理鉴权或签名校验

## 测试

```bash
uv run pytest
```

## 准备发布到 GitHub

当前仓库整理目标是“确认后可直接 push”。如果你还没初始化本地 git，可以按下面执行：

```bash
git init
git add .
git commit -m "chore: bootstrap teamview usage dashboard repo"
git branch -M main
git remote add origin https://github.com/GrooveWJH/yundrone-codex-logs.git
git push -u origin main
```

如果你已经初始化过，只需要确认以下文件不会被提交：

- `.env`
- `teamview_aliases.json`
- `.venv/`
- `.pytest_cache/`

## 核心能力

### Python 包

`switchbase_teamview/` 提供：

- TeamView `usage` 接口客户端
- TeamView `logs` 接口客户端
- Web 看板服务聚合逻辑
- `.env` 自动加载支持

### 单页看板

看板支持：

- 预设时间范围与自定义时间范围
- 全成员表格视图
- 日榜 / 周榜 / 月榜 Top 排行（今日 / 本周 / 本月累计）
- 行内编辑别名并持久化到本地 JSON 文件

### 海报生成子系统

海报代码已经从单体脚本拆分到 `scripts/poster/`，现在分成：

- `models.py`：标准化 snapshot / config / request 类型
- `policy.py`：成员纳入范围、忽略名单、Top N 等策略
- `loaders.py`：API / JSON / memory 三种入口
- `layout.py`：几何和刻度计算
- `render.py`：生成 Matplotlib `Figure`
- `export.py`：负责 PNG 导出
- `cli.py` / `__main__.py`：命令行入口

推荐用法：

```bash
uv run python -m scripts.poster \
  --input-source json \
  --period daily \
  --input-file ./tmp/daily.json
```

也可以直接拉公开榜单接口：

```bash
uv run python -m scripts.poster \
  --input-source api \
  --period all \
  --base-url http://127.0.0.1:8000/api/public-rankings \
  --token "$SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN" \
  --json-dir ./tmp
```

默认行为：

- poster CLI 会自动读取当前工作目录树中的 `.env`
- 若未传 `--token`，会优先读取 `.env` / 环境变量中的 `SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN`
- 若未传 `--output`，会默认写入 `./outputs/`
  - `daily` -> `outputs/daily-poster.png`
  - `weekly` -> `outputs/weekly-poster.png`
  - `monthly` -> `outputs/monthly-poster.png`
  - `all` -> `outputs/all-poster.png`
- 运行时会打印 `[poster] ...` 调试日志，方便 Agent 或脚本定位卡在哪一步

典型运行输出：

```text
[poster] loaded env path=/path/to/repo/.env
[poster] start source=api periods=daily output=/path/to/repo/outputs/daily-poster.png json_dir=/path/to/repo/tmp
[poster] load snapshot period=daily source=api
[poster] saved payload period=daily path=tmp/daily.json
[poster] render snapshots=1
[poster] saved png path=/path/to/repo/outputs/daily-poster.png
```

常用策略参数：

- `--include-all-members`
- `--top-n 10`
- `--allowed-domain yundrone.cn`
- `--exclude-email codex@yundrone.cn`

## Maxline

仓库现在使用 `.codex/check-maxline.json` 约束 Python 文件单文件不超过 `300` 行。

本地检查：

```bash
python3 /Users/groove/.codex/skills/check-maxline/scripts/check_maxline.py --root .
```

当前仅对白名单中的历史技术债放宽：

- `tests/test_dashboard_service.py`
