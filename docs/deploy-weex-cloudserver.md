# weex-cloudserver 部署文档

本文记录 `yundrone-codex-logs` 在服务器 `weex-cloudserver` 上的实际部署方式，目标是方便后续更新、排障和迁移。

## 部署目标

- 服务器别名：`weex-cloudserver`
- 实际主机：`103.231.13.190`
- 部署目录：`/home/groove/apps/yundrone-codex-logs`
- 监听端口：`47593`
- systemd 服务名：`yundrone-codex-logs.service`

## 设计取舍

这台服务器上的 nginx 已经承载多个现有服务，80/443 也在长期运行。

为了避免误伤线上程序，这次部署**没有修改现有 nginx 配置，也没有 reload / restart nginx**。应用直接监听：

```text
0.0.0.0:47593
```

这样做的好处：

- 不影响现有 80/443 流量
- 不碰复杂 nginx 站点配置
- systemd 可以独立管理应用生命周期

## 已部署内容

以下内容已经通过 rsync 同步到服务器：

- 项目代码
- 当前 `.env`
- 当前 `teamview_aliases.json`

远端 `.env` 已调整为：

```env
SWITCHBASE_TEAMVIEW_API_KEY=***
SWITCHBASE_TEAMVIEW_ALIAS_FILE=./teamview_aliases.json
SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai
SWITCHBASE_TEAMVIEW_WEB_HOST=0.0.0.0
SWITCHBASE_TEAMVIEW_WEB_PORT=47593
```

说明：

- API Key 真实值只保留在服务器上的 `.env`，不要写回仓库
- 别名文件以邮箱为主键，保留在部署目录根下

## 运行环境

服务器环境：

- Ubuntu 24.04.3 LTS
- Python 3.12.3

部署过程中额外安装了：

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv
```

项目虚拟环境位于：

```text
/home/groove/apps/yundrone-codex-logs/.venv
```

依赖安装方式：

```bash
cd ~/apps/yundrone-codex-logs
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install .
```

## systemd 配置

服务文件：

```text
/etc/systemd/system/yundrone-codex-logs.service
```

当前配置等价于：

```ini
[Unit]
Description=YunDrone TeamView Usage Dashboard
After=network.target

[Service]
Type=simple
User=groove
Group=groove
WorkingDirectory=/home/groove/apps/yundrone-codex-logs
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/groove/apps/yundrone-codex-logs/.venv/bin/python scripts/run_web.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用与启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yundrone-codex-logs.service
```

## 常用运维命令

查看状态：

```bash
ssh weex-cloudserver 'sudo systemctl status yundrone-codex-logs.service --no-pager -l'
```

查看日志：

```bash
ssh weex-cloudserver 'sudo journalctl -u yundrone-codex-logs.service -n 100 --no-pager'
```

重启服务：

```bash
ssh weex-cloudserver 'sudo systemctl restart yundrone-codex-logs.service'
```

确认监听端口：

```bash
ssh weex-cloudserver 'ss -ltnp | grep 47593'
```

本机验证：

```bash
ssh weex-cloudserver 'curl -s "http://127.0.0.1:47593/api/dashboard?preset=today" | sed -n "1,5p"'
```

外网验证：

```bash
curl -s 'http://103.231.13.190:47593/api/dashboard?preset=today' | sed -n '1,5p'
```

## 更新部署流程

后续更新建议继续沿用 rsync，不要直接在服务器上手改代码：

```bash
rsync -az --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  /Users/groove/Project/work/YunDrone/codex_logs/ \
  weex-cloudserver:~/apps/yundrone-codex-logs/
```

同步后重新安装并重启：

```bash
ssh weex-cloudserver '
  cd ~/apps/yundrone-codex-logs &&
  .venv/bin/pip install . &&
  sudo systemctl restart yundrone-codex-logs.service
'
```

如果 `.env` 或 `teamview_aliases.json` 在本地有更新，需要确认 rsync 没有把远端配置覆盖成错误值。

## nginx 说明

本次部署已经检查过 nginx：

- nginx 服务保持运行
- 未新增 `47593` 相关 server block
- 未 reload / restart nginx

这不是遗漏，而是刻意的隔离策略。当前应用通过独立端口提供服务，避免影响已有 80/443 业务。

如果后续要把它挂到域名或反向代理到 nginx，再单独评估并设计，不建议在现有复杂配置上直接手改。
