# weex-cloudserver 部署文档

本文只描述当前真实在线方案：`weex-cloudserver` 只运行飞书机器人，不提供公网 HTTP API，不运行榜单守护进程。

## 当前线上状态

服务器信息：

- SSH 别名：`weex-cloudserver`
- 主机：`103.231.13.190`
- 部署目录：`/home/groove/apps/yundrone-codex-logs`
- 当前启用服务：`yundrone-codex-feishu-bot.service`

当前已核实状态：

- `yundrone-codex-feishu-bot.service`: `active` + `enabled`
- `yundrone-codex-logs.service`: `inactive` + `disabled`
- `yundrone-codex-report-daemon.service`: `inactive` + `disabled`
- `ss -ltnp | grep 47593`: 无输出

这意味着：

- 线上只有飞书机器人
- 当前没有任何公开 HTTP 接口
- nginx 不参与这套链路，也不需要改 nginx

## 线上职责

飞书机器人当前职责：

- 使用飞书官方 `lark-oapi` SDK 建立长连接
- 订阅 `im.message.receive_v1`
- 处理群聊 `@机器人 日报|周报|月报`
- 处理单聊 `日报|周报|月报`
- 按收到消息当时的当前分钟即时生成海报
- 使用 `all-members` scope
- 返回 Top 7
- 复用 `outputs/feishu-cache/` 中同一分钟缓存
- 使用邮箱别名文件修正显示名

时间口径固定为 `Asia/Shanghai`：

- `日报`: 当天 `00:00 -> 当前分钟`
- `周报`: 本周一 `00:00 -> 当前分钟`
- `月报`: 本月 1 日 `00:00 -> 当前分钟`

缓存行为：

- 同一分钟复用
- 跨分钟自动失效
- 缓存路径：

```text
outputs/feishu-cache/all-members/<period>/<YYYYMMDDHHMM>/
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
- `teamview_aliases.json`
- `assets/NotoSansSC/*.otf`
- `outputs/`
- `outputs/feishu-cache/`

当前 `outputs/` 至少会看到：

- `server-get/`
- 飞书机器人按需生成的 `feishu-cache/`

## 环境变量

线上 `.env` 需要至少包含：

```env
SWITCHBASE_TEAMVIEW_API_KEY=stv_xxx
SWITCHBASE_TEAMVIEW_ALIAS_FILE=./teamview_aliases.json
SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai
SWITCHBASE_TEAMVIEW_OUTPUT_DIR=./outputs
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_LOG_LEVEL=INFO
```

说明：

- `SWITCHBASE_TEAMVIEW_API_KEY` 是 TeamView 真源访问凭据
- `SWITCHBASE_TEAMVIEW_ALIAS_FILE` 指向邮箱别名 JSON
- `SWITCHBASE_TEAMVIEW_OUTPUT_DIR` 控制飞书缓存和临时产物根目录
- 当前线上不需要 `SWITCHBASE_TEAMVIEW_API_HOST`、`SWITCHBASE_TEAMVIEW_API_PORT`、`SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN`

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
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/
```

如果远端是通过 Git 拉代码，则必须补一次：

```bash
ssh weex-cloudserver 'cd /home/groove/apps/yundrone-codex-logs && git lfs pull'
```

### 2. 同步私有配置

把本地的 `.env` 和 `teamview_aliases.json` 同步上去：

```bash
rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/.env \
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/.env

rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/teamview_aliases.json \
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/teamview_aliases.json
```

### 3. 安装依赖

```bash
ssh weex-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  python3 -m venv .venv &&
  .venv/bin/python -m pip install --upgrade pip &&
  .venv/bin/pip install .
'
```

### 4. 安装 systemd unit

本地模板文件：

```text
deploy/systemd/yundrone-codex-feishu-bot.service
```

同步并启用：

```bash
rsync -avz \
  /Users/groove/Project/work/YunDrone/codex_logs/deploy/systemd/yundrone-codex-feishu-bot.service \
  weex-cloudserver:/tmp/yundrone-codex-feishu-bot.service

ssh weex-cloudserver '
  echo 123123 | sudo -S cp /tmp/yundrone-codex-feishu-bot.service /etc/systemd/system/yundrone-codex-feishu-bot.service &&
  echo 123123 | sudo -S systemctl daemon-reload &&
  echo 123123 | sudo -S systemctl enable --now yundrone-codex-feishu-bot.service
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
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/
```

如果 `.env` 或别名有变更，再单独同步：

```bash
rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/.env \
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/.env

rsync -avz /Users/groove/Project/work/YunDrone/codex_logs/teamview_aliases.json \
  weex-cloudserver:/home/groove/apps/yundrone-codex-logs/teamview_aliases.json
```

然后在远端重装并重启：

```bash
ssh weex-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  .venv/bin/pip install . &&
  echo 123123 | sudo -S systemctl restart yundrone-codex-feishu-bot.service
'
```

## 验证命令

查看服务状态：

```bash
ssh weex-cloudserver 'systemctl status yundrone-codex-feishu-bot.service --no-pager -l | sed -n "1,20p"'
```

查看最近日志：

```bash
ssh weex-cloudserver 'journalctl -u yundrone-codex-feishu-bot.service -n 120 --no-pager'
```

确认没有 API 端口监听：

```bash
ssh weex-cloudserver 'ss -ltnp | grep 47593 || true'
```

确认字体文件是真实 OTF：

```bash
ssh weex-cloudserver '
  cd /home/groove/apps/yundrone-codex-logs &&
  file assets/NotoSansSC/NotoSansSC-Bold.otf &&
  wc -c assets/NotoSansSC/NotoSansSC-Bold.otf assets/NotoSansSC/NotoSansSC-Medium.otf assets/NotoSansSC/NotoSansSC-Regular.otf
'
```

手动触发联调：

- 群聊：`@Codex用量报告 日报`
- 单聊：`月报`

成功后，日志里应看到类似：

```text
[feishu-bot] message_id=... chat_id=... period=daily outcome=generated
```

或：

```text
[feishu-bot] message_id=... chat_id=... period=daily outcome=cache-hit
```

## 常见问题

### 1. 飞书回复方框字

优先检查：

1. 字体是否完整同步到 `assets/NotoSansSC/`
2. 远端文件是否还是 Git LFS pointer
3. 服务是否以 `python -m scripts.run_feishu_bot` 启动，而不是旧安装残留入口

### 2. 同一条消息回复两次

先看日志里的 `message_id`：

- 如果是同一个 `message_id`，应该只会出现 `duplicate-inflight` 或 `deduped-succeeded`
- 如果是两个不同 `message_id`，说明不是同一事件重投，而是飞书侧投递了两条不同消息对象

日志命令：

```bash
ssh weex-cloudserver 'journalctl -u yundrone-codex-feishu-bot.service -n 200 --no-pager'
```

### 3. 没有回复月报

常见原因：

- TeamView 拉取失败
- 飞书图片上传失败
- 外部网络瞬时异常

现在的去重逻辑已经改成“成功后才去重”，因此如果第一次失败，飞书后续重投同一 `message_id` 时仍会再试一次。

### 4. 本地 `scripts/fetch_server_reports.py` 拉不到文件

这是预期行为。当前生产服务器没有开启 API 服务，也没有对外暴露 `/api/generated-reports/*`。

这个脚本只适用于：

- 你另行启用了 `teamview-api`
- 或者另一套仍对外暴露 JSON / PNG 的环境

## 当前不做的事情

当前线上部署明确不包含：

- `yundrone-codex-logs.service`
- `yundrone-codex-report-daemon.service`
- nginx 代理
- 公网排行榜 URL
- 飞书 webhook 回调

如果后续要重新启用 API 或守护进程，建议作为单独变更处理，不要混进当前机器人运维流程。

