# P4 砍减版完成报告 · 粘合自动化（watchdog 分级 stale + token 自动换发）

> 日期：2026-09-07 · 指令：`/Users/fan/.ccc/instructions/2026-09-07-p4-glue-automation.md`
> 目标仓：`/Users/fan/program/CCC` · 交付头部：见本报告末尾

## 结论

P4 全部改动落地并验证：**全量 pytest 1482 passed + 2 skipped，ruff 净，`bash -n` 全部修改脚本绿**。
粘合工作中「看门狗心跳分级 + 重启风暴熔断」「重派 401 自动换 token」两项结构性根因消除，
`--renew-auth` 提供人工换发入口；token 全程内存态、不落盘不进日志。

## 改动清单（3 项，逐模块一波 commit+push）

### 1. `scripts/watchdog-ccc.sh` — 分级 stale + spawn 熔断（与现有 watchdog 合并增强，不新建脚本）

- **心跳源多选**：slot `engine-metrics.jsonl` 与 `engine.stderr.log` 取 mtime 最新者为真实心跳源
  （替换旧固定优先 slot、缺失回退 stderr 的单源逻辑）；新增 `wd_path_mtime` 跨 BSD/Linux。
- **三级分级**（`wd_heartbeat_status`，阈值可经 env 覆盖，默认 90s/180s）：
  - normal（<90s）：不动作；
  - borderline（90–180s）：写 `WARN: engine 心跳 borderline（source=… age=…s）` 到 watchdog.log；
  - stale（≥180s）：进 engine 故障列表 → 防旋闸确认后 kickstart 重启 + 写 `ERROR` +
    重启成功后尝试 `/health` 验证（200→「自愈验证」；非 200→WARN）。
- **spawn 熔断**（1 小时内 stale 重启 ≥3 次 → 不再自动重启）：状态 `watchdog-state/spawn.state`
  逐行记 `restart_stamp`；窗口滑动去陈旧行；达到阈值写 `CRITICAL` 到
  `~/.ccc/logs/watchdog-critical.log`，仅人工清除 spawn.state 后恢复（红线：不自动解除）。
- **熔断不置 FAILED**（保持 exit 0）：launchd `KeepAlive.SuccessfulExit=false` 遇非零退出会立即
  重启 watchdog 本体 → 自持风暴；熔断已完成取证并落 CRITICAL，此后按 StartInterval 复检等人工。
- DRY-RUN 路径同样过熔断闸（演练结果与真实一致）；stale 自愈成功才记 restart_stamp。

### 2. `scripts/redispatch-card.sh` — token 自动换发（401 → /session → 重试一次）

- 新增 `_fetch_token`：POST `/session`（凭据源 `~/.ccc/web-auth.txt`），token 只存内存变量
  `BOARD_TOKEN`，**绝不落盘/进日志/stdout**；响应体经临时文件解析后立即删除（机会窗口最小）。
  `_parse_auth_file` 兼容现网格式（标题 + `账号:` + `口令:`）、单行 `user:pass`、单行口令（账号 ccc）。
- transition（及任务详情读）返回 **401/403 → 自动 `/session` 换 token → 重试一次**；
  同轮 `TOKEN_RENEWED=1` 防 401 死循环反复登录。
- 新增 `--renew-auth` 旗标：强制重新登录换 token（供轮换/脱敏后手动换发）。
- `board_req` 统一带 HTTP code 捕获（`-w %{http_code}` + 临时文件 body），跨 BSD（macOS）head 兼容。
- 鉴权失败清晰报错（HTTP code），不产生「半成功」假象。

### 3. 测试

- `server/tests/test_ccc083_antispin.py` 扩 12 用例（P4.1 分级 + 熔断，不碰真实服务）：
  - 镜像分类器精确边界：89 normal / 90 borderline / 179 borderline / 180 stale / 181 stale；
  - e2e（mock mtime）：40 normal 无 WARN、100 borderline 写 WARN、250 stale 触发故障；
  - 熔断：1h 内 3 次 restart 达阈 → `watchdog-critical.log` 写 CRITICAL + 拦截；<3 次不熔断；
  - stale 自愈路径在 DRY-RUN 下记录 kick 意图。
- 新增 `scripts/tests/test-redispatch-renew-auth.sh`（本地 mock HTTP 服务器，仿真实
  `/session` + `/tasks/{id}` + transition 门禁语义）：
  - 静态：默认 LAN 地址 + `--renew-auth` 存在 + `bash -n`；
  - 无 token 启动 → 自动登录 → transition 成功；
  - transition 401（旧 token 注入）→ 自动 `/session` 换发 → 重试 `[OK]`；
  - `--renew-auth` 强制登录成功；
  - 错误凭据 → 干净失败（rc≠0、无 `[OK]`、有清晰提示）；
  - token/口令不泄漏到 stdout/日志/非白名单文件。

## 验证记录

| 项 | 结果 |
|---|---|
| 全量 pytest | **1482 passed, 2 skipped**（P4 新增 +12 用例） |
| ruff check server/ | **All checks passed** |
| `bash -n` 全部修改脚本 | watchdog-ccc / redispatch-card / 两个 shell 测试 均绿 |
| 真实环境 DRY-RUN（live HOME） | 「健康」exit 0；preset-hash 告警为既有观测项（非本改动引入） |
| 401→自动换发→重试 手动路径 | mock 下 `stale-old-token → /session → mock-token-1 → [OK]`（RC=0） |
| 错误凭据路径 | `/session` 401 → 干净失败 RC=1，无假成功 |
| /health | **200**（改动前后均健康） |

## 红线核对

- ✅ 不改 xianyu 业务仓（零触碰）
- ✅ 不改已关闭卡（未动 docs/dispatch 卡文件）
- ✅ 不动 CardStateStore/phase2（纯 shell 侧改动；engine/python 侧零改动）
- ✅ watchdog spawn 熔断 ≥3/h 后只写 CRITICAL，**不自动解除**（须清除 spawn.state 人工恢复）
- ✅ token/密码不落盘、不进日志、不进 git（测试含泄漏断言）

## 部署说明

- watchdog launchd 已按 StartInterval 周期自动读最新脚本；本次改动仅 shell 侧，**无需重启 engine**。
- engine/web `/health` 全程 200，进程未受影响。
- `watchdog-critical.log` 为新增告警落盘点（spawn 熔断时写入），目录复用 `~/.ccc/logs/`。

## 交付头部

```
P4-GLUE-AUTOMATION-DONE 400692578 46644
```