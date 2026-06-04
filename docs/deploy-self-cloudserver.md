# self-cloudserver 部署文档

本文只描述当前真实在线方案：`self-cloudserver` 运行飞书长连接机器人，不提供公网 HTTP API，不运行榜单守护进程，也暂不运行定时群通报。

## 当前线上状态

服务器信息：

- SSH 别名：`self-cloudserver`
- 主机：`103.38.80.82:29402`
- 部署目录：`/home/groove/apps/yundrone-codex-logs`
- 当前启用服务：`yundrone-codex-feishu-bot.service`

目标状态：

- `yundrone-codex-feishu-bot.service`: `active` + `enabled`
- `yundrone-codex-feishu-group-reporter.service`: `inactive` + `disabled` 或不存在
- `yundrone-codex-logs.service`: `inactive` + `disabled`
- `yundrone-codex-report-daemon.service`: `inactive` + `disabled`
- `ss -ltnp | grep 47593`: 无输出

这意味着：

- 线上只通过飞书机器人即时回复工作
- 当前没有任何公开 HTTP 接口
- nginx 不参与这套链路，也不需要改 nginx
- 旧 Matplotlib 海报、all-in-one 图和 09:30 定时群通报都已停用

## 线上职责

飞书机器人当前职责：

- 使用飞书官方 `lark-oapi` SDK 建立长连接
- 订阅 `im.message.receive_v1`
- 处理群聊 `@机器人 报告`
- 处理单聊 `报告`
- 如果只是 `@机器人` 或内容仅为空白，返回使用方法卡片
- 如果输入不属于精确命令，返回使用方法卡片
- 如果群消息包含 `@所有人`，直接忽略，不回复 help 也不发图
- 即时交互会对用户原消息添加状态表情：处理中 `Alarm`，成功 `DONE`，非法输入 `THINKING`，处理失败 `SWEAT`
- 按收到消息当时的当前分钟即时生成 Typst Token 日/周/月三合一海报
- 使用 `whitelist` scope，只展示 `teamview_whitelist.json` 中 `include=true` 的成员
- 全局同一时间只允许制作一张图，制作中会提示 `图片正在制作中，不允许重复点击`
- 成功发图后的 10 秒内再次请求，会提示剩余冷却秒数
- 复用 `outputs/feishu-cache/` 中同一分钟缓存
- 使用白名单条目的 `alias` 字段修正显示名

三合一海报包含：

- 日报：当天 `00:00 -> 当前分钟`
- 周报：本周一 `00:00 -> 当前分钟`
- 月报：本月 1 日 `00:00 -> 当前分钟`

缓存行为：

- 同一分钟复用
- 跨分钟自动失效
- 缓存路径：

```text
outputs/feishu-cache/whitelist/tokens/trio/<YYYYMMDDHHMM>/
```

幂等行为：

- 处理中的同一 `message_id` 重投不会双发
- 已成功发送过的同一 `message_id` 在短时间内会被去重
- 生成失败或上传失败时不会错误写入成功状态，飞书后续重投还能补发

## 服务器目录约定

部署目录：

```text
/home/groove/apps/yundrone-codex-logs
```

关键文件：

- `.env`
- `teamview_whitelist.json`
- `assets/NotoSansSC/*.otf`
- `typst/`
- `outputs/`
- `outputs/feishu-cache/`

## 环境变量

线上 `.env` 需要至少包含：

```env
SWITCHBASE_TEAMVIEW_API_KEY=stv_xxx
SWITCHBASE_TEAMVIEW_WHITELIST_FILE=./teamview_whitelist.json
SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai
SWITCHBASE_TEAMVIEW_OUTPUT_DIR=./outputs
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_LOG_LEVEL=INFO
```

说明：

- `SWITCHBASE_TEAMVIEW_API_KEY` 是 TeamView 真源访问凭据
- `SWITCHBASE_TEAMVIEW_WHITELIST_FILE` 指向用户白名单 JSON，白名单条目的 `alias` 字段同时控制展示名
- `SWITCHBASE_TEAMVIEW_OUTPUT_DIR` 控制飞书缓存和临时产物根目录
- 飞书即时机器人不需要固定群聊 ID，回复目标来自飞书消息事件
- 当前线上不需要 `SWITCHBASE_TEAMVIEW_API_HOST`、`SWITCHBASE_TEAMVIEW_API_PORT`、`SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN`
- 远端系统必须能执行 `typst` 命令

## 首次部署

### 1. 同步代码

如果本地已经拉好了 Git LFS 字体，直接 rsync：

```bash
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  /Users/groove/Project/work/YunDrone/codex_logs/ \
  self-cloudserver:/home/groove/apps/yundrone-codex-logs/
```

如果远端是通过 Git 拉代码，则必须补一次：

```bash
ssh self-cloudserver 'cd /home/groove/apps/yundrone-codex-logs && git lfs pull'
```

### 2. 同步私有配置

把本地的 `.env` 和 `teamview_whitelist.json` 同步上去：

```bash
rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/.env \
  self-cloudserver:/home/groove/apps/yundrone-codex-logs/.env

rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/teamview_whitelist.json \
  self-cloudserver:/home/groove/apps/yundrone-codex-logs/teamview_whitelist.json
```

### 3. 安装依赖和 Typst

```bash
ssh self-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  python3 -m venv .venv &&
  .venv/bin/python -m pip install --upgrade pip &&
  .venv/bin/pip install . &&
  typst --version
'
```

如果 `typst --version` 失败，先在服务器安装 Typst，并确认 `typst` 在 systemd 服务可见的 `PATH` 中。

### 4. 安装 systemd unit

本地模板文件：

```text
deploy/systemd/yundrone-codex-feishu-bot.service
```

同步并启用：

```bash
rsync -avz \
  /Users/groove/Project/work/YunDrone/codex_logs/deploy/systemd/yundrone-codex-feishu-bot.service \
  self-cloudserver:/tmp/yundrone-codex-feishu-bot.service

ssh self-cloudserver '
  echo 123123 | sudo -S cp /tmp/yundrone-codex-feishu-bot.service /etc/systemd/system/yundrone-codex-feishu-bot.service &&
  echo 123123 | sudo -S systemctl daemon-reload &&
  echo 123123 | sudo -S systemctl enable --now yundrone-codex-feishu-bot.service &&
  echo 123123 | sudo -S systemctl disable --now yundrone-codex-feishu-group-reporter.service || true
'
```

当前入口固定为：

```text
ExecStart=/home/groove/apps/yundrone-codex-logs/.venv/bin/python -m scripts.run_feishu_bot
```

## 日常更新

代码或字体更新后：

```bash
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  /Users/groove/Project/work/YunDrone/codex_logs/ \
  self-cloudserver:/home/groove/apps/yundrone-codex-logs/
```

如果 `.env` 或白名单有变更，再单独同步。

然后在远端重装并重启：

```bash
ssh self-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  .venv/bin/pip install . &&
  echo 123123 | sudo -S systemctl restart yundrone-codex-feishu-bot.service
'
```

## 验证命令

查看服务状态：

```bash
ssh self-cloudserver 'systemctl status yundrone-codex-feishu-bot.service --no-pager -l | sed -n "1,20p"'
```

查看最近日志：

```bash
ssh self-cloudserver 'journalctl -u yundrone-codex-feishu-bot.service -n 120 --no-pager'
```

确认没有 API 端口监听：

```bash
ssh self-cloudserver 'ss -ltnp | grep 47593 || true'
```

确认字体文件是真实 OTF：

```bash
ssh self-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  file assets/NotoSansSC/NotoSansSC-Bold.otf &&
  wc -c assets/NotoSansSC/NotoSansSC-Bold.otf assets/NotoSansSC/NotoSansSC-Medium.otf assets/NotoSansSC/NotoSansSC-Regular.otf
'
```

手动触发联调：

- 群聊：`@Codex用量报告 报告`
- 单聊：`报告`
- 仅 `@Codex用量报告`：返回使用方法卡片
- `总览`：返回使用方法卡片
- `日报月报周报`：返回使用方法卡片

成功后，日志里应看到类似：

```text
[feishu-bot] message_id=... chat_id=... command=report outcome=generated
```

或：

```text
[feishu-bot] message_id=... chat_id=... command=report outcome=cache-hit
```

## 常见问题

### 1. 飞书回复方框字

优先检查：

1. 字体是否完整同步到 `assets/NotoSansSC/`
2. 远端文件是否还是 Git LFS pointer
3. `typst` 是否能在服务环境中运行

### 2. 同一条消息回复两次

先看日志里的 `message_id`：

- 如果是同一个 `message_id`，应该只会出现 `duplicate-inflight` 或 `deduped-succeeded`
- 如果是两个不同 `message_id`，说明不是同一事件重投，而是飞书侧投递了两条不同消息对象

### 3. 没有回复报告

常见原因：

- TeamView 拉取失败
- Typst 编译失败或 `typst` 不在 PATH
- 飞书图片上传失败
- 外部网络瞬时异常

现在的去重逻辑是“成功后才去重”，因此如果第一次失败，飞书后续重投同一 `message_id` 时仍会再试一次。

## 当前不做的事情

当前线上部署明确不包含：

- `yundrone-codex-logs.service`
- `yundrone-codex-report-daemon.service`
- `yundrone-codex-feishu-group-reporter.service`
- nginx 代理
- 公网排行榜 URL
- 飞书 webhook 回调
- all-in-one 图

如果后续要重新启用 API 或定时通报，建议作为单独变更处理。
