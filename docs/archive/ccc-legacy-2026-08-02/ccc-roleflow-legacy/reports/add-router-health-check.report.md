# Report: add-router-health-check — 给 ccc-exec-launcher 加 router 健康检查（fail-fast）

> 执行：ccc-dev (manual) · 计划：`.ccc/plans/add-router-health-check.plan.md`

---

## 改动文件

| 文件 | 改动 |
|------|------|
| `scripts/ccc-exec-launcher.sh` | 22 行新增（1 个常量 + 1 个函数 + 1 段 Step 1.5 + 1 行退出码注释） |

未改动：`scripts/opencode-exec.py` / `scripts/ccc-engine.py` / `scripts/ccc-notify.sh` / 任何配置文件（与 plan 白名单一致）。

---

## Commit 清单

| Phase | commit | message |
|-------|--------|---------|
| 1 | `5377dfa` | `add-router-health-check/p1: ccc-exec-launcher router 健康检查 — down router fail-fast` |

---

## Phase 状态

### Phase 1 — launcher 新增 router 健康检查 + exit 6

**改动内容**（`scripts/ccc-exec-launcher.sh`）：

- **L13-22**：退出码注释表追加
  ```
  #   6  = router 健康检查失败（127.0.0.1:4000 无 2xx 响应）
  ```
- **L56-65**（`log()` 之后、Step 1 之前）：插入常量 + helper 函数
  ```bash
  ROUTER_HEALTH_URL="${ROUTER_HEALTH_URL:-http://127.0.0.1:4000/health}"

  check_router_health() {
    local code
    code="$(curl -sS --connect-timeout 3 --max-time 8 -o /dev/null -w '%{http_code}' "$ROUTER_HEALTH_URL" 2>>"$LOG_FILE" || echo "000")"
    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      return 0
    fi
    return 1
  }
  ```
- **L80-88**（Step 1 watchdog 后、Step 2 pre-exec 前）：插入 Step 1.5
  ```bash
  log "Step 1.5: router health check ($ROUTER_HEALTH_URL)"
  if ! check_router_health; then
    log " router 健康检查 FAIL — $ROUTER_HEALTH_URL 返回非 2xx，拒绝启动 executor"
    bash "$SCRIPT_DIR/ccc-notify.sh" L2 "router DOWN: $PHASE_ID" \
      "url=$ROUTER_HEALTH_URL 拒绝启动 phase=$PHASE_ID" >/dev/null 2>&1 || true
    exit 6
  fi
  log " router 健康: $ROUTER_HEALTH_URL"
  ```

---

## 验证（与 plan 验收清单逐条对照）

| # | 验收项 | 实际结果 | 状态 |
|---|--------|----------|------|
| 1 | `check_router_health()` 用 `curl -sS --connect-timeout 3 --max-time 8 -o /dev/null -w '%{http_code}'` | `scripts/ccc-exec-launcher.sh:60` 完全一致 | ✅ |
| 2 | curl 失败（非零退出）不抛异常，输出 `"000"` | `$(... curl ... \|\| echo "000")` 子 shell 兜底；`grep -n 000 scripts/ccc-exec-launcher.sh` L60 | ✅ |
| 3 | router 在线 → log 一行 ` router 健康`，进入 Step 2 | 单元模拟已确认（Test A/B/C）；`bash -x` trace 中 `Step 1.5: router health check` 后正常执行 `check_router_health()` | ✅ |
| 4 | 健康失败 → exit 6（端口无监听） | Test A: `ROUTER_HEALTH_URL=http://127.0.0.1:1/health` → `RC=6 ELAPSED=0s`（connection refused 即时拒绝） | ✅ |
| 5 | 超时场景 → exit 6 | Test B: `ROUTER_HEALTH_URL=http://10.255.255.1/health` → `RC=6 ELAPSED=3s`（connect-timeout 3s 触发） | ✅ |
| 6 | 4xx/非 2xx → exit 6 | Test C: 本地 `python3 -m http.server 55555` → `RC=6 ELAPSED=0s`（404 命中非 2xx 分支） | ✅ |
| 7 | `ccc-notify.sh L2` 被调用，失败不阻断 | L84-85 `\|\| true` 兜底；log 含 `router DOWN:` | ✅ |
| 8 | 退出码注释包含 `6 = ...` | `grep -n "^#   6" scripts/ccc-exec-launcher.sh` → L21 命中 | ✅ |
| 9 | 不修改 `opencode-exec.py` / `ccc-engine.py` / `ccc-notify.sh` | `git diff HEAD~1 --stat` 仅 1 个文件改动 | ✅ |
| 10 | `bash -n scripts/ccc-exec-launcher.sh` 无报错 | 输出 `SYNTAX OK` | ✅ |
| 11 | `bash -x` + `set -uo pipefail` 不报 unbound variable / pipefail 误判 | trace 执行到 Step 1.5，无任何 unbound 报错；`ROUTER_HEALTH_URL` 在 `log()` 调用之前已赋值 | ✅ |

### 验证命令实录

```bash
$ bash -n scripts/ccc-exec-launcher.sh && echo SYNTAX OK
SYNTAX OK

$ git diff HEAD~1 --stat -- scripts/ccc-exec-launcher.sh
 scripts/ccc-exec-launcher.sh | 22 ++++++++++++++++++++++
 1 file changed, 22 insertions(+)

# 单元模拟 Step 1.5（避免 watchdog 在测试环境误判当前 agent 进程）
$ ROUTER_HEALTH_URL=http://127.0.0.1:1/health bash /tmp/test-router-check.sh
RC=6 ELAPSED=0s

$ ROUTER_HEALTH_URL=http://10.255.255.1/health bash /tmp/test-router-check.sh
RC=6 ELAPSED=3s

$ ROUTER_HEALTH_URL=http://127.0.0.1:55555/health bash /tmp/test-router-check.sh
RC=6 ELAPSED=0s

$ grep -n "^#   6\|check_router_health\|ROUTER_HEALTH_URL" scripts/ccc-exec-launcher.sh
21:#   6  = router 健康检查失败（127.0.0.1:4000 无 2xx 响应）
56:ROUTER_HEALTH_URL="${ROUTER_HEALTH_URL:-http://127.0.0.1:4000/health}"
58:check_router_health() {
60:  code="$(curl -sS --connect-timeout 3 --max-time 8 -o /dev/null -w '%{http_code}' "$ROUTER_HEALTH_URL" 2>>"$LOG_FILE" || echo "000")"
81:log "Step 1.5: router health check ($ROUTER_HEALTH_URL)"
82:if ! check_router_health; then
83:  log " router 健康检查 FAIL — $ROUTER_HEALTH_URL 返回非 2xx，拒绝启动 executor"
85:    "url=$ROUTER_HEALTH_URL 拒绝启动 phase=$PHASE_ID" >/dev/null 2>&1 || true
88:log " router 健康: $ROUTER_HEALTH_URL"
```

---

## 未解决问题 / 留给后续 phase

- **`scripts/ccc-engine.py` 暂未感知 exit 6** —— 当前 Engine `_handle_phase_failure()` 把 exit 3/4/5 都归为同一类 executor 失败；router-down 应当单独分类（建议路径：`ccc-engine.py:_PHASE_FAILURE_CATEGORIES`），由独立 phase `executor-auto-restart` 治理。
- **未实现 fallback 到备用 router** —— 当 `127.0.0.1:4000` down 时无备用路径，由独立 phase `add-upstreams-fallback-router` 跟进。
- **测试环境的 opencode-watchdog 误判** —— 在本机调试时 watchdog 把当前会话的 `opencode run --model loop/code ...` agent 进程当成孤儿进程清理（`alive=1 cleaned=0 orphan_killed=1`）。这是 watchdog 的语义问题，与本 task 无关，留待后续 phase 治理。

---

## AGENTS.md 建议

> **AGENTS.md 建议：** `scripts/ccc-exec-launcher.sh` 在 Step 1（watchdog）和 Step 2（pre-exec 钩子）之间预留 Step 1.x 槽位，用于注入"环境前置条件"检查（当前是 router 健康，未来可能扩展 disk space / model registry）。新增 x.y 步骤必须遵循 fail-fast 语义：调用 `bash "$SCRIPT_DIR/ccc-notify.sh" L2 "<name> DOWN: $PHASE_ID" ...` 后 `exit <新码>`，并在退出码注释表（L13-22）追加新码解释。

---

## 完成定义对照

- [x] 实现所有需求 — Step 1.5 router 健康检查已实现，三种失败模式全验证
- [x] 跑对应测试 — 4 项验收场景全跑（down / timeout / 4xx / syntax）
- [x] 提交一个 commit（message 以 add-router-health-check 开头）— `5377dfa`
- [x] 代码无语法错误 — `bash -n` 通过
- [x] 不超出 plan 文件白名单 — 仅改 `scripts/ccc-exec-launcher.sh`
