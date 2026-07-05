# a2-fix-executor-hang — Changelog

> **任务**：Sprint A2 — 修 Mavis Executor 卡死的根因（防 Lesson 7/8 再次发生）
> **范围**：CCC 框架文件（不在 git）+ 历史沉淀文件
> **执行模式**：Planner 越界兜底（用户授权"必须修好" + Executor 已知失败）
> **时间**：2026-07-01 00:22 → 00:30（Asia/Shanghai，~8 分钟）

---

## TL;DR

| 项 | 值 |
|---|---|
| 文件改动 | 4 个 (1 新建 + 3 编辑) |
| 新建 | `~/program/CCC/scripts/executor-watchdog.sh` (180 行 bash) |
| 编辑 | `~/program/CCC/templates/executor-prompt.template.md` (加 Step 0 + 完成执行顺序) |
| 编辑 | `~/program/CCC/CLAUDE.md` (红线 9 — Executor 卡死立即止损) |
| 编辑 | `~/program/CCC/projects/qxo/lessons.md` (加 Lesson 9) |
| 验证 | watchdog 跑测 exit=0 (available=1937MB, no hang, no stuck) |

---

## 文件改动详情

### 1. `scripts/executor-watchdog.sh` (新建 · 180 行)

完整实现的 bash 脚本，4 个 check + `--force-kill` 自动清理 + `--quiet` 静默模式。

**验证**（实际跑过）：
```
[watchdog] ──── Check 1: hang claude process scan ────
[watchdog] Check 1: no hang claude process found (threshold=15min)
[watchdog] ──── Check 2: mavis stuck session scan ────
[watchdog] Check 2: no stuck mavis session found
[watchdog] ──── Check 3: /tmp/qx-stream-*.jsonl cleanup ────
[watchdog] ──── Check 4: free memory check ────
[watchdog] Check 4: available=1937MB (page_size=16384B, free+inactive+speculative, OK)
[watchdog] ──── watchdog passed ────
REAL_EXIT=0
```

**迭代过程**（修过 2 次 bug）：
1. 第一次：PAGES_FREE × 4096 算 MB → 错（macOS 现代 page size 是 16384）
2. 第二次：awk `-F'[][]' '/page size of/'` 解析失败 → PAGE_SIZE 空字符串
3. 第三次（最终）：改用 `grep -oE '[0-9]+ bytes'` + fallback 4096
4. 阈值从 1024MB free pages 改为 1024MB available（含 inactive + speculative）— 避免高负载 false positive

### 2. `templates/executor-prompt.template.md` (编辑)

两处改动：
- **bash 命令前置**：加 `bash ~/program/CCC/scripts/executor-watchdog.sh || { ... }`
- **prompt text 加 Step 0**：watchdog warning acknowledged 确认
- **完成执行顺序加 Step 0**：caller 已跑 watchdog，warning 必标注
- **启动顺序加第 5 步**：确认 watchdog warning（如有）

### 3. `CLAUDE.md` (编辑)

加红线 9 — Executor 卡死必须立即止损：

```
9. **Executor 卡死必须立即止损**（A2 新增 · Lesson 7 + Lesson 9 修复）：
   - 触发条件：bash ~/program/CCC/scripts/executor-watchdog.sh 返回非零，
     或 claude 子进程 etime > 15min && pcpu < 1%
   - 立即动作：caller 立即 kill -9 <claude_pid> 或 mavis session abort <session_id>，
     不要等自然结束
   - 决策路径：
     - 1 次卡死 → watchdog --force-kill + 重试
     - 连续 2 次同 session 卡死 → 不再尝试第 3 次，Planner 接管
   - 端口冲突 / OOM 等硬件层卡死 → caller 必须重启 daemon：pkill -f opencode
```

### 4. `lessons.md` (编辑 · Lesson 9)

完整的 A2 修法说明 + 4 条防线 + 验证 + 与 Lesson 7/8 的关系链。

---

## 决策链

1. **触发**：用户说"继续" → 我理解为执行 A2（修 Executor 卡死根因）
2. **诊断**：
   - 跑 `mavis session list agent-194cd50170e9 --limit 5` → 只有当前 root session
   - 当前 session frameworkType=opencode（非 `claude -p`）
   - 跑 `pgrep -fl claude` → pid 4574, 18min, CPU 14.8%, RSS 316MB → **不是 hang**
3. **结论**：Lesson 7 推测的"`claude -p` 累积 session"不成立（每次 `claude -p` 是新进程）。当前 root session 是 OpenCode framework。
   但跑 `claude -p` 任务的 Executor 卡死是历史事实（fix-tag-dangling + P2-1/P2-2 都是）。
   推测真正根因：(a) heavy thinking variant 在某些分支 hang + (b) macOS 内存压力下 OOM killer 介入
4. **修法选择**：
   - A: 仅改 prompt template 加 watchdog 调用 → 选了 + 加 4 条防线（更彻底）
   - B: 加 daemon 重启脚本 → 后续迭代
   - C: 强制 OpenCode session 替代手动 `claude -p` → 太激进，先观察 A2 修法是否有效
5. **执行**：直接 Planner 兜底（同 A1 流程异常，授权链清晰）

---

## 验证结果

### watchdog 当前健康状态

| Check | 状态 | 细节 |
|---|---|---|
| 1. hang claude process | ✅ PASS | no hang (threshold=15min) |
| 2. mavis stuck session | ✅ PASS | no stuck session |
| 3. /tmp/qx-stream stale | ✅ PASS | 没有陈旧文件 |
| 4. free memory | ✅ PASS | available=1937MB (>1GB) |
| **EXIT CODE** | **0** | Safe to launch Executor |

### 修过的 bug 迭代

| 版本 | bug | 修法 |
|---|---|---|
| v1 | PAGES_FREE * 4096 错算 MB | 改为 `* PAGE_SIZE`，page_size 用 grep 解析 |
| v2 | awk `-F'[][]'` 解析 page size 失败 | 改用 `grep -oE '[0-9]+ bytes'` + fallback 4096 |
| v3 | 阈值 1024MB free 太严，高负载 false positive | 改用 available = free + inactive + speculative |

---

## 流程异常说明 ⚠️

同 A1 — Planner 越界兜底（用户授权"必须修好" + Executor 已知失败）。详见
`~/.mavis/memory/user.md` 的"Planner 越界兜底规则"。

本次改动没动 qx-observer 项目源代码（CCC 框架文件不在 git，不能 commit），
所以没有 commit hash。改动的"提交"是：
1. watchdog 文件物理写入 → chmod +x
2. CLAUDE.md / template / lessons.md → 直接编辑（无 commit，但有 changelog 这份 evidence）

---

## 后续迭代

1. **A2-2**：写 daemon 重启脚本 `~/program/CCC/scripts/restart-opencode.sh`
2. **A2-3**：写 ESCALATION 协议（卡死 → 自动 abort → 自动重启 → 通知用户）
3. **A3**：在 A2 修法保护下，做真实集成测试（前端 SSE + 5 阶段 E2E）
4. **未来 CCC v3**：考虑把 CCC framework 放到 git（目前不在 git，无法 commit）

---

## 文件交付物

| 文件 | 类型 | 行数 |
|---|---|---|
| `~/program/CCC/scripts/executor-watchdog.sh` | 新建 | ~180 行 bash |
| `~/program/CCC/templates/executor-prompt.template.md` | 编辑 | +20 行 |
| `~/program/CCC/CLAUDE.md` | 编辑 | +13 行（红线 9）|
| `~/program/CCC/projects/qxo/lessons.md` | 编辑 | +63 行（Lesson 9）|
| `~/program/CCC/projects/qxo/history/a2-fix-executor-hang/changelog.md` | 新建 | 本文件 |
| `~/program/CCC/projects/qxo/history/a2-fix-executor-hang/phases.json` | 新建 | 1 行 phase 1 |
