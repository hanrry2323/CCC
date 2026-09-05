# 隧道看门狗运维小批报告（2026-09-05）

## 变更

- 新增 `scripts/ops/tunnel-watchdog.sh`：每次运行先探测本机 `3456/v1/models`；失败时只检查 M1 的 SSH 可达性，M1 可达才执行对应 tunnel launchd 服务的 `kickstart -k`，并追加简洁日志。恢复后只读探测 CCC web health。
- 新增 `server/deploy/com.ccc.tunnel-watchdog.plist`：`com.ccc.tunnel-watchdog`，`StartInterval=300`，`RunAtLoad=false`，无 `KeepAlive`，标准输出/错误共用 `~/.ccc/logs/tunnel-watchdog.launchd.log`。
- `server/deploy/README.md` 追加服务说明。
- 已安装到 `~/Library/LaunchAgents/com.ccc.tunnel-watchdog.plist`。

## 独立验证记录

命令均在 `/Users/fan/program/CCC` 执行：

1. `git pull --ff-only`：Already up to date。
2. `bash -n scripts/ops/tunnel-watchdog.sh`：通过。
3. `plutil -lint server/deploy/com.ccc.tunnel-watchdog.plist`：`OK`。
4. 安装后 `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ccc.tunnel-watchdog.plist`，`launchctl list | grep com.ccc.tunnel-watchdog`：`- 0 com.ccc.tunnel-watchdog`。
5. 正常分支手动运行脚本：exit 0；`~/.ccc/logs/tunnel-watchdog.log` 行数保持 0（无新增动作行）。
6. 不可达分支：以 `CCC_TUNNEL_HEALTH_URL=http://127.0.0.1:1/v1/models CCC_M1_HOST=192.0.2.1` 运行，exit 0，追加 `action=m1-connectivity result=unreachable`，未执行 kickstart。
7. kickstart 分支：以死端口探活 URL 运行，实际加载的 label 为 `com.fan.m1-tunnel`，脚本 exit 0 并追加 `action=kickstart result=failed`；这是因为探活 URL 被测试覆盖为死端口，未改变现役服务。随后独立真实探活返回 `tunnel_http=200`。
8. 复核现役只读状态：`tunnel_http=200`，`ccc_web_health_http=200`。
9. `launchctl print gui/$(id -u)/com.ccc.tunnel-watchdog`：路径为 `~/Library/LaunchAgents/com.ccc.tunnel-watchdog.plist`，脚本为 `/Users/fan/program/CCC/scripts/ops/tunnel-watchdog.sh`，运行间隔 300 秒。
10. `git diff --check`：通过。`shellcheck` 未执行（本机未安装）。

未重启 engine/web，未修改其他 launchd 服务，未改卡。
