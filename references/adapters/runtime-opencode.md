# Runtime: OpenCode（v0.8 执行器契约）

CCC 框架在 **OpenCode CLI** 环境下的执行规范。

> **v0.8 重大变化**：本文件是**执行器契约**，不是普通的"加载指引"。
> CCC 用 OpenCode **只做执行器**，不做 serve / HTTP / API server。
> 所有调用走 `opencode exec` 子进程（CLI 模式）。

---

## 一、定位

| 角色 | 谁 |
|------|-----|
| Plan / Verify | Claude Code（本机主 session） |
| **Execute** | **OpenCode CLI（CLI 模式）** |

OpenCode = CCC 的"执行器"，Claude = CCC 的"大脑"。

---

## 二、安装（必做一次性）

```bash
# 1. opencode CLI（必须）
which opencode || echo "请先装 opencode: https://opencode.io"
opencode --version  # 期望 ≥ 1.17

# 2. CCC 执行器脚本（已随项目带）
ls ~/program/CCC/scripts/opencode-exec.py

# 3. 进程池 + 监控 + 通知脚本
ls ~/program/CCC/scripts/opencode-pool.py
ls ~/program/CCC/scripts/opencode-watchdog.sh
ls ~/program/CCC/scripts/ccc-notify.sh

# 4. launchd 守护（可选，定时调度才需要）
ls ~/Library/LaunchAgents/com.ai-loop-router.openai.plist
```

**禁用**：`opencode serve` / HTTP API / `:4096` 端口监听 — v0.8 不用。

---

## 三、调用规范

### 3.1 单 phase 调用（标准入口）

```bash
bash ~/program/CCC/scripts/ccc-exec-launcher.sh <phase-id> <prompt-file> \
  [--timeout 1800] [--cwd <dir>]
```

**内部链路**：

```
ccc-exec-launcher.sh
  ├── Step 1: opencode-watchdog.sh    # 残留扫描
  ├── Step 2: ccc-hook.sh pre-exec    # 用户钩子
  ├── Step 3: opencode-exec.py        # 实际执行
  │    └── opencode exec --model flash -  # prompt 走 stdin（Lesson 27）
  ├── Step 4: ccc-hook.sh post-exec   # 完成后钩子
  └── Step 5: ccc-hook.sh on-error    # 失败钩子（仅 L2 错误时）
```

### 3.2 多 phase 并发（进程池）

```bash
# 准备 tasks.json
cat > /tmp/tasks.json <<EOF
[
  {"phase_id": "p1", "prompt_file": "/tmp/p1.txt", "timeout": 1800},
  {"phase_id": "p2", "prompt_file": "/tmp/p2.txt", "timeout": 600},
  {"phase_id": "p3", "prompt_file": "/tmp/p3.txt", "timeout": 600}
]
EOF

# 进程池跑（max 3 并发）
python3 ~/program/CCC/scripts/opencode-pool.py /tmp/tasks.json
```

### 3.3 prompt 写盘（标准做法）

```bash
# Planner 把 prompt 写到文件（不是 inline 字符串）
cat > /tmp/phase-1.prompt.md <<'EOF'
# Phase 1: 修复 net exposure
## 目标
…
EOF

# launchd 调 launcher
bash ccc-exec-launcher.sh phase-1 /tmp/phase-1.prompt.md
```

---

## 四、进程管理红线（v0.8 新增）

| 红线 | 内容 | 触发后果 |
|------|------|---------|
| **X1** | **最多 3 个 opencode 进程并行** | 超出由 `opencode-pool.py` 排队，拒绝硬塞 |
| **X2** | **每 phase 必杀 opencode 进程** | finally 兜底 + watchdog 二重；残留由 watchdog 清 |
| **X3** | **启动前必跑 watchdog** | `ccc-exec-launcher.sh` 强制 Step 1 = watchdog |

**X1 实现**：`asyncio.Semaphore(3)` 在 `opencode-pool.py` 硬限。
**X2 实现**：
- `opencode-exec.py` 用 `async with` + `finally` 块杀进程（先 TERM，5s 后 KILL）
- `opencode-watchdog.sh` 扫 `~/.ccc/opencode-pids/*.pid` 兜底
**X3 实现**：`ccc-exec-launcher.sh` Step 1 强制调 watchdog，失败 exit 1。

---

## 五、通知规范

升级链通知走 `ccc-notify.sh`（macOS 桌面通知）：

```bash
# L1 失败（仅日志，不打扰）
bash ccc-notify.sh L1 "title" "message"

# L2 失败（桌面通知 + 默认声音）
bash ccc-notify.sh L2 "opencode FAIL: phase-3" "exit=124 timeout"

# L3 失败（桌面通知 + Basso 强烈声音 + subtitle 强调）
bash ccc-notify.sh L3 "需要老板拍板" "phase 升级 L3"
```

**v0.8 不接飞书 / 微信 / 邮件**。只用本机桌面通知 + `~/.ccc/alerts/<时间戳>.md` 永久存档。

---

## 六、模型选择（硬规则）

**所有 opencode exec 必须显式指定 `--model loop/flash`**。

```bash
opencode run --model loop/flash "msg"   # 唯一允许
```

**模型映射**（v0.9a 实测）：
- 对外名称：`flash`（CLAUDE.md 红线：唯一对外模型名）
- 实际 opencode 模型：`loop/flash`（走 `localhost:4002` 中转站，~/.opencode/opencode.json 注册）
- 中转站：AI Loop Router `http://localhost:4002/v1`

**禁止**：
- 省略 `--model`（落到 opencode 默认值 `loop/code`，不是 flash）
- 写成 `--model flash`（v0.9a 前 v0.8 踩坑：opencode 没注册名为 `flash` 的模型，会报 Unexpected server error）
- 硬编码 `claude-opus-*` / `claude-sonnet-*` / `claude-haiku-*` / `claude-fable-*`
- 硬编码 `minimax-*` / `deepseek-*` / `gpt-*` / `gemini-*` / `glm-*`

---

## 七、目录约定

| 路径 | 用途 |
|------|------|
| `~/.ccc/opencode-pids/` | 每 phase 一个 `<phase-id>.pid` 文件，启动时写，结束删 |
| `~/.ccc/logs/launcher-<phase>-<ts>.log` | launcher 链路日志 |
| `~/.ccc/logs/opencode-<phase>.json` | opencode-exec 结构化输出 |
| `~/.ccc/alerts/<ts>-<L>.md` | L1/L2/L3 告警存档 |
| `~/.ccc/hooks/<point>.sh` | 用户钩子（pre-exec / post-exec / pre-commit / on-error）|

---

## 八、smoke test（每个能力必跑）

| 能力 | 验证命令 | 预期 |
|------|---------|------|
| CLI 可调 | `opencode exec --model flash - <<< 'print("hi")'` | stdout 出现 `hi` |
| Watchdog 干净 | `bash scripts/opencode-watchdog.sh; echo $?` | 0 |
| 桌面通知 | `bash scripts/ccc-notify.sh L2 "test" "smoke"` | 屏幕弹通知 + `~/.ccc/alerts/` 落文件 |
| Launcher 启动 | `bash scripts/ccc-exec-launcher.sh test-p /tmp/p.txt` | 跑完 exit 0，pid 文件已清 |
| 必杀兜底 | 故意造超时（timeout=2） | 进程被 kill，pid 文件已清 |
| 池并发上限 | tasks.json 写 5 个 phase 慢任务 | 同时跑 ≤ 3，剩余排队 |

每条都必须**实跑通过**，不算 smoke = 失败。

---

## 九、与 v0.7 的差异

| 维度 | v0.7 | v0.8 |
|------|------|------|
| 执行器 | claude CLI（直接调） | **opencode CLI**（`opencode exec`） |
| HTTP/serve | 无 | **禁止**（已卸 launchd 守护） |
| 进程池 | 无 | **max 3 并发**（红线 X1） |
| 必杀机制 | 软退出 | **TERM → KILL + watchdog 兜底**（X2） |
| 残留扫描 | 无 | **每次启动前必跑**（X3） |
| 通知 | 无 | **macOS 桌面通知 + 告警存档** |
| Hook | 无 | **pre-exec / post-exec / on-error / pre-commit** |

---

## 十、参考

- 红线全文：`~/program/CCC/references/red-lines.md`（X1/X2/X3 在 §OpenCode 进程管理）
- CCC 4 文件契约：`~/program/CCC/references/file-contract.md`
- 教训沉淀：`~/program/CCC/docs/lessons.md`
