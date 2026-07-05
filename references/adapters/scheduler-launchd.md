# Scheduler: launchd (macOS)

macOS 原生守护进程管理。当 IPC cron 不可用或需要系统级持久化调度时使用。

---

## 何时使用

- IPC cron 未运行或不稳定
- 需要系统重启后自动恢复轮询
- 任务需要在用户未登录时执行

## 安装

将以下 plist 保存到 `~/Library/LaunchAgents/ccc.qxo.<task>.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ccc.qxo.<task></string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/apple/.local/bin/claude</string>
        <string>-p</string>
        <string>$(cat /path/to/executor-prompt.txt)</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/tmp/ccc-qxo-<task>.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ccc-qxo-<task>.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

## 使用

```
# 加载
launchctl load ~/Library/LaunchAgents/ccc.qxo.<task>.plist

# 卸载
launchctl unload ~/Library/LaunchAgents/ccc.qxo.<task>.plist

# 检查状态
launchctl list | grep ccc.qxo

# 查看日志
cat /tmp/ccc-qxo-<task>.out
cat /tmp/ccc-qxo-<task>.err
```

## 跨平台

仅 macOS。Linux 使用 crontab（非 systemd — CCC 无需持久 daemon，cron 轮询即可）：

```
*/5 * * * * /path/to/claude -p "$(cat /path/to/prompt.txt)" >> /tmp/ccc-task.log 2>&1
```
