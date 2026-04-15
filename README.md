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
├── scripts/                    # 仓库级运行入口
├── tests/                      # 测试
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
- 日榜 / 周榜 / 月榜总量排行
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
- 日榜 / 周榜 / 月榜 Top 排行
- 行内编辑别名并持久化到本地 JSON 文件
