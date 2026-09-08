# 2026-09-04 flowfix 批次二报告

## 结论

批次二代码改动已完成并推送；定向测试与 `server/tests/` 全量测试通过。引擎已重启并确认新 pid。tst905 已被引擎重新认领并执行探针，但本次 10 分钟观察窗口内未重新回写到可供 phase2 审核的状态；执行体随后被引擎回收并重派为「待分派」，因此没有证据证明本轮已进入 1800s 机审派发。

## 改动

1. `server/engine/phase2.py`
   - 分支信封扫描在 main 卡为「打回」时跳过，避免被拒卡重捞。
   - 预检/前置探针类失败不计真实审计 strikes，只写冷却；冷却期再次检查后直接跳过。
   - 真实 auditor 产出 PASS/REJECT 工件后清零历史 infra strikes。
   - 机审打回同步清理未合入的 codex 分支信封；已合入分支复用安全清理校验。
   - 部署探活移动到置「已关闭」之前；探活失败保持「已回写（部署失败）」。
2. `server/web/server.py` + `server/engine/card_state_store.py`
   - 重派经 `CardStateStore.transition` 把卡头从「打回」转为「待分派」，sidecar 只记录重试归零与时间戳。
   - 状态门面允许同态幂等更新，保留 CAS/锁/提交保护。
3. `server/engine/main.py`
   - 冷却 helper 支持 phase2 为瞬态探针故障指定统一 480s 基准，仍受最大冷却上限保护。
4. `server/tests/test_phase2.py`
   - 增加打回分支信封不重捞、探针不增 strikes、部署探活前置、成功清 strikes 等定向覆盖。

## 测试与检查

- 定向：`python3 -m pytest server/tests/test_phase2.py server/tests/test_infra_resilience.py server/tests/test_http_api.py::TestTaskTransition server/tests/test_card_state_store_cas.py -q` → `40 passed`。
- 全量：`python3 -m pytest server/tests/ -q` → `288 passed`（输出 100%，exit code 0）。
- Ruff：`.venv-hub/bin/ruff check server/engine/phase2.py server/engine/main.py server/engine/card_state_store.py server/web/server.py server/tests/test_phase2.py` → passed。
- `git diff --check` → passed。

## Commit

- `0b7a02a92` — `fix(card): unify phase2 cooldown and redispatch`，已推送 `origin/main`。
- 本报告随后单独提交；报告提交不会改变业务改动内容。

## 重启与恢复时间线（UTC）

- `09:10:47`：重启后 runtime sidecar 记录 tst905 为「执行中」，新引擎开始重新认领；launchd 确认 engine pid `98407`。
- `09:14:46`：首次尝试调用重派门面时因未携带 Bearer 被拒；未改动卡。
- `09:15:02`：携带凭证再次调用门面时，卡已被引擎认领为「执行中」，API 按状态机拒绝重派；没有绕过状态机手改卡。
- `09:15:26`：独立卡状态读数为「待分派」；执行日志仍是旧执行体记录。
- `09:16:00`–`09:26:22`：10 分钟观察窗口。tst905 曾进入执行中，但未出现新的成功回写；最终 sidecar 记录 `09:22:25` 被引擎回收为「待分派（Engine 中断未收单，自动重派）」。

## tst905 观察证据

- 执行日志 `/Users/fan/.ccc/logs/exec/tst905.log` 记录执行体探针：主仓短 hash `0b7a02a92`、health `200`、目标文件路径存在；三条只读探针 exit code 均为 `0`。
- `bash scripts/card-status.sh tst905` 在观察窗口结束仍显示 `state=待分派`、`result=已产出`、`gate=ok`。
- 引擎日志显示 tst905 新一轮执行体被拉起，之后记录「Engine 中断未收单，自动重派」；没有独立证据显示「已回写」或 phase2 以 1800s 派发 auditor。
- 现场另有并发卡 tst904 占用 tst 项目唯一执行槽位，期间多次出现 `同业务仓已达并发上限 1`；这是运行现场约束，未扩大范围处理。

## 冲突/未完成项

- 指令要求 tst905 重新回写并以 1800s 重审；本窗口实际只观察到重新认领、探针完成证据和随后自动重派，未观察到回写/机审派发。按审核红线不把执行体自报当作完成证据，故将该项标为未验证，不手动改卡、不手动 git 操作卡。
- 首次无 token 的脚本调用被 web 写端点拒绝；随后已使用既有 web 凭证访问门面。脚本本身权限位不允许直接执行（exit 126），按现场最小动作使用 `bash scripts/redispatch-card.sh`，仍因卡当时已执行中而未执行重派。
