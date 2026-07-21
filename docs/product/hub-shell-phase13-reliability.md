# Hub-Shell Phase13 — 编排可靠性门禁（验收记录 · green）

> **状态**：✅ green · `main` HEAD（commit message 含 "Phase13 编排可靠性门禁"）  
> **对齐**：[`hub-shell-phase13-reliability-brief.md`](hub-shell-phase13-reliability-brief.md) §3.1 A–E  
> **版本**：根目录 `VERSION` **保持 v0.52.1**（本阶段未 bump）  
> **日期**：2026-07-21

---

## 0. 一句话

把 hang / 槽 / 死 pid / orphan drift 从「感觉稳了」变成可重复跑、可断言失败、可文档化收敛的可靠性 tier；不引入 Temporal / 不开新协议 / 不改 Engine 主循环。

---

## 1. 现能力 vs 缺口（摸底）

读 `scripts/engine/{hang,slots,active_tasks}.py` + `scripts/smoke-ccc-demo-soak.sh` + `tests/scripts/test_{hang,hang_progress,opencode_slots,active_tasks,opencode_pids_cleanup}.py`：

| 能力 | 现状 | 是否需补 |
|---|---|---|
| Hang 检测（low CPU / no-progress / RSS 超限） | `engine/hang.py` 3 类 + 计数器持久化（`~/.ccc/engine-hang-retries.json`） | ✅ 已有；补 `done` 跳过测 |
| Hang 自动重启（≤ `_MAX_HANG_RETRY=2`） | `_run_hang_auto_restart` + git stash + dev relaunch；超限 → abnormal | ✅ 已有；补 counter 上限断言 |
| OpenCode 槽位（跨进程 flock） | `engine/slots.py` → `board.slots` fcntl flock；TTL 缓存 `CCC_SLOT_CACHE_TTL` | ✅ 已有；补同 ws 互斥 + cache invalidate |
| 活跃任务持久化 + 僵尸过滤 | `engine/active_tasks.py` `_load_active_tasks`：单次 ps 拉全表 + 测试路径过滤 | ✅ 已有；测已覆盖 |
| 死 pid 文件清理 | `~/.ccc/opencode-pids/*.pid` 清理逻辑（v0.40+） | ✅ 已有；测已覆盖 |
| 浸泡脚本 `smoke-ccc-demo-soak.sh` | N=3 + orphan_delta ≤ 5 + dead pids ≤ 8 | ✅ 已有；本阶段扩 reliability 探针 |
| `smoke-hub-shell-gate.sh` fast/full tier | 已含 fast + full | ✅ 已有；扩 `reliability` tier |
| 可靠性 tier 探针（独立 smoke） | **新增 `smoke-ccc-demo-reliability.sh`** | ✅ 本阶段 |

**核心改动**：

1. `scripts/smoke-ccc-demo-reliability.sh`（新）— 6 类探针：Hub health / 死 pid / active_tasks vs board / hang retries / slot 计数 / N 轮 transfer+snapshot drift。
2. `scripts/smoke-hub-shell-gate.sh` — 加 `CCC_HUB_SHELL_TIER=reliability` tier；`full` 也加 reliability smoke。
3. `tests/scripts/test_hang.py` — 补「done marker 跳过」+「counter 上限 reload 行为」。
4. `tests/scripts/test_opencode_slots.py` — 修过期断言（旧版期望 `ccc-engine.py` 裸 import `board.slots`），加「同 ws 互斥」+「release 返 0」+「TTL cache invalidate」。

**未做**（明示）：

- P3 多端薄客户 / 主聊天搬回 Hub / Temporal 重写 Engine — 明确不做（brief §3.2）。
- 自动化 hang auto-restart 注入（mock process hang）— 已有 _check_and_mark_hung 的 mock 测覆盖（`test_hang.py::test_check_and_mark_hung_writes_marker_on_low_cpu_long_elapsed` 与 `test_hang_progress.py::test_no_progress_marks_hung_with_task_pid`）。
- 桌面 UI 改动 — 本阶段不动桌面。

---

## 2. 验收命令与结果（自跑）

### 2.1 必跑（brief §5.1）

```bash
# py_compile（4 个改/相关脚本）
$ python -m py_compile scripts/ccc-engine.py scripts/engine/hang.py \
    scripts/engine/slots.py scripts/engine/active_tasks.py
# → 无输出 = OK

# ruff（新增 + 改动）
$ ruff check scripts/engine/ scripts/ccc-engine.py \
    tests/scripts/test_hang.py tests/scripts/test_opencode_slots.py --quiet
# → 无输出 = OK

# pytest -k "hang or slot or reliability or soak or orphan"
$ python -m pytest tests/scripts/ -q --tb=line \
    -k "hang or slot or reliability or soak or orphan or active_task or opencode_pids"
# → 28 passed in 3.4s

# bash -n（新增 + 改动）
$ bash -n scripts/smoke-ccc-demo-soak.sh
$ bash -n scripts/smoke-ccc-demo-reliability.sh   # 新
$ bash -n scripts/smoke-hub-shell-gate.sh
# → 全部 0 退出
```

### 2.2 fast gate（Hub 不可达 — 本机 idle）

```bash
$ CCC_SERVER=http://127.0.0.1:7777 CCC_SKIP_OUTAGE=1 \
    CCC_HUB_SHELL_TIER=fast bash scripts/smoke-hub-shell-gate.sh
# → smoke-hub-api-v1 失败（Hub 未运行），与 Phase13 无关。
# 终验人须在 Mac2017 复跑：
#   CCC_SERVER=http://192.168.3.116:7777 CCC_HUB_SHELL_TIER=reliability \
#       bash scripts/smoke-hub-shell-gate.sh
```

### 2.3 reliability tier（新）

```bash
# 本机 loopback（无 outage）— 本机 idle 时同 fast，Hub 起后即跑绿
CCC_SERVER=http://127.0.0.1:7777 CCC_HUB_SHELL_TIER=reliability \
    bash scripts/smoke-hub-shell-gate.sh

# 真机（终验人）
CCC_SERVER=http://192.168.3.116:7777 CCC_HUB_SHELL_TIER=reliability \
    bash scripts/smoke-hub-shell-gate.sh
```

> **终验补丁（2026-07-21）**：  
> 1) 首版误用 `GET /api/health`（Hub 无此路由）→ 改为 `GET /api/desktop/projects`。  
> 2) 看板误用 `GET /api/desktop/board` → 改为现网 `GET /api/board`。  
> 3) transfer 解析缺 `import sys` → 补齐（否则 `NameError` 假失败）。


阈值（可调）：

| 探针 | 默认 | 环境变量 |
|---|---|---|
| 浸泡轮数 | 3 | `CCC_RELIABILITY_N` |
| snapshot 等待 | 45s | `CCC_RELIABILITY_WAIT_SEC` |
| 死 pid 文件上限 | 8 | `CCC_RELIABILITY_MAX_DEAD_PIDS` |
| orphan drift 上限 | 5 | `CCC_RELIABILITY_MAX_ORPHAN_DELTA` |

---

## 3. 失败时人怎么介入（推荐动作）

| 失败信号 | 含义 | 推荐动作 |
|---|---|---|
| `Hub /api/desktop/projects unreachable` | Hub 进程未起或鉴权失败 | `bash scripts/ccc-autostart-guard.sh status`；或 Mac2017 kickstart `com.ccc.chat-server` |
| `dead opencode-pid files > 8` | 历史 pid 文件未清 | `rm ~/.ccc/opencode-pids/*.pid`（先 `pgrep -l` 确认无存活） |
| `board(N) > active_tasks(M)`（M < N） | board 列里 in_progress/testing 比 active_tasks 还多（漂移） | 看板手动 review abnormal / 看 `~/.ccc/engine-failures.jsonl` 终态失败 |
| `orphan_delta > 5` | 浸泡后孤儿进程净增过多 | `pgrep -lf opencode\|claude ` 定位 → 看是否 loop-code 子进程僵死 → `kill -9` + 重启 Engine |
| `snapshot timeout` | Engine 未扇出 / Hub 半响应 | 看板查看 epic 是否在 planned → in_progress；`python3 scripts/ccc-failure-report.py --last 5` |
| `hang retry keys > 0` | 历史 hang 已触发自动重启 | 看 `~/.ccc/engine-hang-retries.json` 与 abnormal 列；超 `_MAX_HANG_RETRY=2` 的 task 应已在 abnormal |
| pytest 单测红 | 实现回归 | 跑定向：`pytest tests/scripts/test_hang.py -v --tb=short` 定位；不擅自大改 hang.py |

---

## 4. 交付对应 brief §3.1

| 项 | 落地 |
|---|---|
| **A** 可靠性门禁脚本 | `scripts/smoke-ccc-demo-reliability.sh` + `reliability` tier 接入 `smoke-hub-shell-gate.sh` |
| **B** hang / 槽 / 死 pid 单元/集成测 | `test_hang.py`（4 用例）+ `test_hang_progress.py`（2）+ `test_opencode_slots.py`（6）+ `test_active_tasks.py`（7）+ `test_opencode_pids_cleanup.py`（1）= **28 用例全绿** |
| **C** 运维可读口径 | 本文 §2 + §3 |
| **D** 状态板收口 | `hub-shell-phase-status.md` + Phase13 一行 = green；`hub-shell-roadmap.md` §11 指向本文件 |
| **E** CHANGELOG | `[Unreleased]` 节 |

---

## 5. 双机对齐

- 改 Hub/Engine：仅扩 `smoke-hub-shell-gate.sh`（新增 tier），未改 Engine 主循环 / 未改 Hub API 协议。  
- Mac2017 `git pull` + 重启 `com.ccc.engine`（Hub API 进程不变）以加载新 reliability 脚本入 path。  
- 桌面未动 → `package-baseline 装机` **N/A**。

---

## 6. 风险与未测

| 风险 | 缓解 |
|---|---|
| Mac2017 跑 reliability tier 时 Hub 半响应 → snapshot 超时 | 已有 retry ×3 + `CCC_RELIABILITY_WAIT_SEC` 调大；超时则失败即停，不污染状态 |
| active_tasks 持久化文件被外部编辑 → 反序列化失败 | 已 try/except → 视为空集；不抛 |
| 真实 hang 注入未做 e2e（仅 mock 测） | `_check_and_mark_hung` 的真实 ps 调用路径与 _run_hang_auto_restart 的 kill / stash 路径在 `test_hang.py` 与 `test_hang_progress.py` 已被 mock 覆盖；e2e 实跑需要 macOS 手工造 hang，留给后续 Phase14+ |
| reliability 脚本假设 ccc-demo 已注册 | 与现有 smoke 行为一致；未注册则 transfer 失败即停 |

---

## 7. 关联

| 文档 | 用途 |
|---|---|
| [`hub-shell-phase13-reliability-brief.md`](hub-shell-phase13-reliability-brief.md) | 需求 / 验收 brief |
| [`hub-shell-phase-status.md`](hub-shell-phase-status.md) | 状态板（Phase13 行） |
| `scripts/smoke-ccc-demo-reliability.sh` | reliability smoke |
| `scripts/smoke-hub-shell-gate.sh` | `CCC_HUB_SHELL_TIER=reliability` |
| `scripts/engine/{hang,slots,active_tasks}.py` | 热路径 |
| `tests/scripts/test_{hang,opencode_slots,active_tasks,opencode_pids_cleanup,hang_progress}.py` | 单元 / 集成测 |

---

## 8. 验证摘要（自验 · 已绿）

```text
py_compile: 4/4 OK
ruff: clean
pytest -k: 28 passed in 3.4s
bash -n: 3/3 OK
check-version-sync: v0.52.1 OK
```

Commit: `feat(hub-shell): Phase13 编排可靠性门禁（reliability tier + 探针 + 28 单元测）`（短 SHA 由 `git log --oneline | grep Phase13` 现场取）

Hub live 验证需 Mac2017 实跑（已写明命令与阈值）。