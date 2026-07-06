# Runtime: ZCode (智谱 AI 编码助手)

ZCode 下的 CCC skill 加载与执行方式。

---

## 修订说明 (v1.2.1, 2026-07-06)

**之前的"ZCode 没有 `claude -p` 等价的非交互 CLI"说法在本系统上不成立** —— 实测 `claude` 二进制位于 `/Users/apple/.local/bin/claude`,ZCode 是其 GLM-branded 桌面/Electron 包装。

本文档已重写,补充:

- **CLI Fallback 段**: 直接用 `claude -p` 配合 `ANTHROPIC_BASE_URL` 路由到 BigModel
- **Cluster Bus 集成段**: `ccc-znode-register.py` 注册节点 + 心跳
- **统一的 spawn recipe**: 替代原"必须走 skill + subagent"的不准确描述

Lesson 31 同步沉淀到 `docs/lessons.md`。

---

## 何时使用

- 开发者使用 ZCode session 工作
- 需要 CCC 三角色管线(Planner → Executor → Verifier)调度独立 session
- 默认模型为 GLM-5 / GLM-5-Turbo(智谱 BigModel)
- 需要与 cluster-bus 协同做跨设备调度

---

## 安装

ZCode 通过 skill 发现加载 CCC:

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `<project>/.zcode/skills/ccc-protocol/` | 项目级 |
| 2 | `<project>/.agents/skills/ccc-protocol/` | 跨工具标准 |
| 3 | `~/.zcode/skills/ccc-protocol/` | **用户级**(已装) |
| 4 | `~/.agents/skills/ccc-protocol/` | 跨工具用户级 |

```bash
# 验证安装
ls -la ~/.zcode/skills/ccc-protocol/SKILL.md
```

---

## CLI Fallback (实测路径, v1.2.1+)

**核心结论**: ZCode 与 `claude -p` 共享同一二进制。spawn 独立 session:

```bash
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic \
  claude -p \
    --permission-mode bypassPermissions \
    --dangerously-skip-permissions \
    --model glm-5 \
    --add-dir <workspace> \
    --session-id "$(uuidgen)" \
    < /tmp/executor-prompt.txt
```

**关键参数**:

| 参数 | 必须 | 说明 |
|------|------|------|
| `ANTHROPIC_BASE_URL` | 是 | 指向 BigModel 的 Anthropic 兼容 endpoint |
| `ANTHROPIC_AUTH_TOKEN` | 是 | GLM API key(从 `~/.zcode/v2/credentials.json` 自动读,或环境变量) |
| `--model glm-5` | 是 | 默认模型,可换 `claude-sonnet-4-5`(直 Anthropic) |
| `--session-id <UUID>` | **是**(红线 6) | 独立 session 隔离,UUID 落盘 `.ccc/plans/<task>-<role>-session-id.txt` |
| `--permission-mode bypassPermissions` | 是 | 不弹权限框(ZCode 桌面环境无 TTY) |
| stdin 喂 prompt | **是**(Lesson 27) | 永远 `claude -p < file`,绝不 `claude -p "..."` |

### 全自动包装: ccc-zcode-bridge.sh

为避免重复 boilerplate,使用 `scripts/ccc-zcode-bridge.sh`:

```bash
bash scripts/ccc-zcode-bridge.sh <workspace> <task> <role> [--dry-run]
  role ∈ {executor, verifier}
```

**自动处理**:

- UUID 分配/复用(读 `.ccc/plans/<task>-<role>-session-id.txt`)
- watchdog 前置(`scripts/executor-watchdog.sh`)
- GLM provider + bypassPermissions
- spawn 报告落 `.ccc/dispatches/spawn-<task>-<role>-<UUID>.json`
- claude stdout/stderr 落 `/tmp/ccc-zcode-bridge-<UUID>.log`

**已验证**: 9/9 smoke tests PASS(`tests/scripts/test_ccc_zcode_bridge_smoke.py`)。

---

## Cluster Bus Integration

把当前 ZCode 机器注册到 cluster-bus,声明 capability:

```bash
python3 scripts/ccc-znode-register.py \
  --node-id zcode-$(hostname) \
  --capabilities zcode glm-5 claude-p shell git python \
  [--daemon]  # 启 30s 心跳守护线程
```

**默认 capabilities**(供 `ccc-dispatch.py` 路由匹配):

| Tag | Level | 含义 |
|-----|-------|------|
| `zcode` | L2 | ZCode IDE wrapper 标记 |
| `glm-5` | L2 | GLM-5 模型 provider |
| `claude-p` | L2 | `claude -p` 能力(同二进制) |
| `shell` | L1 | bash |
| `git` | L1 | git |
| `python` | L1 | python3 |

**bus 不可达 = 单机模式**: 注册失败不致命,脚本 exit 0 + warning,任务继续单跑。

**跨设备调度**: 注册后,`scripts/ccc-dispatch.py --plan <plan.md> --workspace <ws>` 会列出本机为候选节点,自动评分。

---

## End-to-End Orchestration

一键走完 6 步全链路:

```bash
bash scripts/ccc-zcode-orchestrate.sh <workspace> <task> [--dry-run] [--skip-register]
# 或
ccc run <workspace> <task> [--dry-run] [--skip-register]
```

**流程**:

```
0. precheck   → ccc-precheck.sh (5 gates, 红线 2/3/5/7/9)
1. register   → ccc-znode-register.py (cluster-bus, 可选)
2. executor   → ccc-zcode-bridge.sh <task> executor
3. commit     → ccc-exec-commit.sh (红线 4+8 单 phase 单 commit)
4. watchdog   → executor-watchdog.sh (红线 9 卡死检测)
5. verifier   → ccc-zcode-bridge.sh <task> verifier (独立 session-id)
6. finish     → ccc-finish.sh (5 gates, 红线 11 verdict 真文件)
```

**每步 exit code 校验** + `.ccc/dispatches/orchestrate-<task>-<ts>.json` 报告记录。

**已知妥协**:

- ccc-exec-commit.sh 解析 JSONL 格式的 phases.json 有 bug,触发时只 warning 不 fatal(独立 task 修)
- cluster-bus mTLS 未实装(cluster-protocol.md §4.3 TODO P1-2),只绑 127.0.0.1 plaintext

---

## 与 `claude -p` 的对比 (修正版)

| 方面 | claude -p | ZCode (v1.2.1 后) |
|------|-----------|-------------------|
| 执行方式 | `claude -p < prompt.txt` 非交互 | **相同**(同二进制) |
| 默认模型 | Claude Opus/Sonnet/Haiku | GLM-5 / GLM-5-Turbo(可改) |
| Provider 路由 | `ANTHROPIC_BASE_URL` 默认 Anthropic | 设 `ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic` 走 GLM |
| Session 隔离 | `--session-id <UUID>` | **相同** |
| Permission | `--permission-mode bypassPermissions` | **相同**(均有效) |
| 预算控制 | `--max-budget-usd N` | **相同**(均有效) |
| 文件契约 | `.ccc/` 4 文件 | **相同** |
| Subagent | 子进程 claude CLI | 通过 `--session-id` 隔离(等价) |
| 桌面 UI | 无 | 有(Electron 包装) |

**结论**: ZCode 与 `claude -p` 在 spawn 能力上无本质差异,差别只在:
1. 默认 provider(Anthropic vs GLM)
2. 桌面 UI 集成
3. 凭证管理(GLM key 在 `~/.zcode/v2/credentials.json`)

---

## 使用方法

### 方法 A: skill 触发(交互式)

在 ZCode session 中:

```
按 CCC 流程处理: <task spec>
```

### 方法 B: 直接引用

```
@ccc-protocol/SKILL.md
```

### 方法 C: 一键编排(推荐,自动 spawn)

```bash
ccc run /path/to/project my-task
```

### 方法 D: 手动分步(更细粒度)

```bash
# 1. 启动 Executor(独立 session)
bash scripts/ccc-zcode-bridge.sh /path/to/project my-task executor

# 2. 提交改动(单 phase 单 commit)
ccc commit /path/to/project my-task

# 3. 启动 Verifier(独立 session-id)
bash scripts/ccc-zcode-bridge.sh /path/to/project my-task verifier

# 4. 后置门控
bash scripts/ccc-finish.sh /path/to/project my-task
```

### 方法 E: 跨设备调度(配合 cluster-bus)

```bash
# 注册本机
python3 scripts/ccc-znode-register.py --node-id zcode-mbp --daemon &

# 触发跨设备 dispatch(列出所有 zcode/claude-p 节点,人工选 yes 确认)
python3 scripts/ccc-dispatch.py --plan .ccc/plans/<task>.plan.md --workspace .
```

---

## 红线遵守清单

| 红线 | 落实方式 |
|------|---------|
| 6 (Planner/Verifier 隔离) | bridge.sh 内 UUID 分配,executor/verifier 不同 UUID 落不同 session-id.txt |
| 9 (卡死止损) | bridge.sh watchdog 前置 + timeout 600,orchestrate.sh Step 4 再次 watchdog |
| 11 (verdict 真文件) | bridge.sh verifier 角色 + orchestrate.sh Step 6 ccc-finish 校验 |
| 12 (不自主启用) | `ccc run` / `bash orchestrate.sh` 显式触发 |
| 19 (跨设备独立 verifier) | cluster-bus 注册后,dispatcher 可在不同节点间路由 |
| 20 (bash v3 portability) | 所有 .sh 用双引号,不用单引号 `bash -c '...$VAR...'` |
| Lesson 27 | stdin 喂 prompt,绝不 `claude -p "..."` |

---

## 已知限制

1. **GLM provider 凭证依赖**: 假设 `~/.zcode/v2/credentials.json` 已有 BigModel key,或手动 `export ANTHROPIC_AUTH_TOKEN=<key>`。
2. **`claude -p` 偶发 hang** (E2E-DEMO.md §7.1): 长 prompt + bypassPermissions 模式偶发 macOS asyncio stall。通过拆短 prompt(< 100 行)规避。
3. **cluster-bus mTLS 暂未实现**: 仅绑 127.0.0.1 plaintext。跨设备部署前需 P1-2 升级。
4. **跨设备实测未做**: 注册逻辑可工作,但跨 mac2017/M1 节点未做端到端 dispatch 测试。

---

## 配套文件

- `scripts/ccc-zcode-bridge.sh` — 核心 spawn 包装
- `scripts/ccc-znode-register.py` — cluster-bus 节点注册
- `scripts/ccc-zcode-orchestrate.sh` — 6 步端到端编排
- `tests/scripts/test_ccc_zcode_bridge_smoke.py` — 9 项 smoke 测试
- `tests/scripts/test_ccc_znode_register_smoke.py` — 6 项 smoke 测试(含 mock bus)
- `tests/scripts/test_ccc_zcode_orchestrate_smoke.py` — 6 项 smoke 测试
- `docs/lessons.md` Lesson 31 — ZCode = Claude Code + GLM wrapper

---

**v1.2.1 修订**: 修正"无 claude -p 等效"说法;新增 CLI Fallback + Cluster Bus + Orchestration 三大段。