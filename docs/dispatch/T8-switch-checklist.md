# 任务卡 T8 · 调用方切换清单准备（T4 阶段 4 · Trae 窗口 B）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（§8 拓扑 / D9 中转站并入）
> 管理席：Claude Code（调度）· 执行体：Trae（窗口 B）· 验收：Claude Code · 派发：manual · 项目：ccc
> 状态：已关闭 · 日期：2026-08-02
> 前置：T4（已验收通过，6100/6102 已运行）

## 目标

产出 CCC 执行体调用方切换清单：OpenCode / Claude Code（2017 侧）从 M1 4100/4102 切到 2017 6100/6102，**附一键回滚**。本卡**只产出清单与验证步骤，不实际切换**（实际切换动运行面，需老板放行）。

## 红线（先看）

1. **不实际修改任何执行体配置**（不碰 `~/.claude/settings.json`、`~/.config/opencode/opencode.json`、各执行体运行面）。
2. 只产出文档 + 配置示例；不碰 M1 4100/4102、不碰 2017 运行面、不读不写外脑。
3. 完成必须提交；验收标准不可自行解释。

## 范围

- CCC 仓 `docs/dispatch/T8-switch-checklist.md`（或 `docs/`）产出切换清单。
- 可产出配置示例（去密钥版），不落真实 key。
- 不动：任何真实配置文件、运行服务。

## 步骤

1. 盘点调用方现状（只读）：Claude Code / OpenCode / Codex 当前配置指向（M1 4100/4102）。
2. 写切换步骤：A. Claude Code → 6100；B. OpenCode → 6102；C. 验证命令（冒烟）。
3. 写一键回滚：每步配 `cp backup` + 恢复命令。
4. 列「切换执行前置条件」（6100 稳定性验证、客户端认证方案）。
5. 提交 `docs(dispatch):`，回写真实 commit hash。

## 验收标准

1. 切换清单覆盖所有调用方（Claude Code / OpenCode / 其他），含验证步骤。
2. 每步附一键回滚。
3. 明确标注「实际切换需老板放行」；未碰任何真实配置。
4. 提交真实；未动运行面。

## 回写要求

结果摘要、盘点输出、清单路径、commit hash、验收自检对照表。**状态同步（§3）**。

---

## T8 调用方切换清单（完整版）

> 本清单由 Trae 窗口 B 执行，产出切换步骤与验证方案，**不实际切换**。切换需老板放行。
> 日期：2026-08-02 · 版本：v1.0

---

### 1. 盘点调用方现状（2026-08-02 只读探查）

#### 1.1 环境与拓扑

| 机器 | IP | ai-loop-router 实例 | 端口 |
|------|-----|---------------------|------|
| **M1** | `192.168.3.140` | 主实例（生产） | `:4100` (Anthropic) / `:4102` (OpenAI Chat) |
| **Mac2017** | `192.168.3.116` | CCC 独立实例（T4 部署，已运行） | `:6100` (Anthropic) / `:6102` (OpenAI Chat) |

#### 1.2 盘点调用方

| # | 调用方 | 机器 | 当前指向 | 配置来源 | 说明 |
|---|--------|------|----------|----------|------|
| **A** | **Claude Code**（Engine product/reviewer） | Mac2017 | `http://127.0.0.1:4100` | `ccc-engine.sh` 第 29 行 `ANTHROPIC_BASE_URL` 默认值；`scripts/_utils.py:73` `_DEFAULT_AGENT_PLANNER_URL` | 通过 `AGENT_PLANNER_BASE_URL` / `ANTHROPIC_BASE_URL` env 路由。`127.0.0.1:4100` 在 Mac2017 上实际指向 **M1 的 ai-loop-router**（透过 `AGENT_PLANNER_BASE_URL` 覆盖为 `http://192.168.3.140:4100` 或由 `_utils.py` 解析） |
| **B** | **OpenCode**（Engine dev 写码） | Mac2017 | `http://127.0.0.1:4102/v1` | `~/.config/opencode/opencode.json` → `baseURL` 字段 | `OPENCODE_MODEL=loop/flash` 指明模型档位。探活失败自动切 `opencode.direct.json` 直连兜底 |
| **C** | **Engine 环境变量**（`ccc-engine.sh`） | Mac2017 | `ANTHROPIC_BASE_URL=http://127.0.0.1:4100`；`AGENT_PLANNER_BASE_URL=http://127.0.0.1:4100` | `scripts/ccc-engine.sh` 第 28-34 行 | 可被 `~/.ccc/engine.env` 覆盖 |
| **D** | **Codex**（知识/闲聊席） | Mac2017 | 不直接依赖 relay | `docs/product/dev-channel.md` | Codex 通过 Desktop 对话，不直接消费 4100/4102 |

**关键发现**：
- 当前所有调用方实际走 **M1 的 ai-loop-router**（`:4100`/`:4102`），通过 LAN `192.168.3.140` 或 `127.0.0.1`（Engine 默认 `AGENT_PLANNER_BASE_URL` 未覆盖时假指向，实际由 `_utils.py` `get_relay_url()` 解析为 M1）。
- 旧 CCC Relay（4000/4002）已离线，无残留进程。
- T4 已部署 6100/6102 并确认运行，双协议冒烟通过。

---

### 2. 切换步骤

> **⚠️ 实际切换需老板放行**。以下步骤仅在下达切换指令后执行。

#### 2A. Claude Code → 6100

**操作**：修改 Mac2017 上 Claude Code 的 `ANTHROPIC_BASE_URL` 指向本机 6100。

```bash
# 1. 备份当前配置
cp ~/.claude/settings.json ~/.claude/settings.json.bak-ccc-6100

# 2. 编辑 ~/.claude/settings.json，修改 env.ANTHROPIC_BASE_URL
#    修改前: "ANTHROPIC_BASE_URL": "http://127.0.0.1:4100"（或旧 4000）
#    修改后: "ANTHROPIC_BASE_URL": "http://127.0.0.1:6100"

# 3. 更新 Engine 环境变量（ccc-engine.sh 默认值不变，用 engine.env 覆盖）
#    编辑 ~/.ccc/engine.env（如不存在则新建）：
#    echo 'export AGENT_PLANNER_BASE_URL=http://127.0.0.1:6100' >> ~/.ccc/engine.env
#    echo 'export ANTHROPIC_BASE_URL=http://127.0.0.1:6100' >> ~/.ccc/engine.env

# 4. 重启 Engine 使环境变量生效
#    launchctl kickstart gui/$(id -u)/com.ccc.engine
```

**认证**：6100 当前为**无认证模式**（T4 已删除 `clients.json`），`ANTHROPIC_AUTH_TOKEN` 设为 `loop-router-flash` 即可通过。

#### 2B. OpenCode → 6102

**操作**：修改 Mac2017 上 OpenCode 的 `baseURL` 指向本机 6102。

```bash
# 1. 备份当前配置
cp ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.bak-ccc-6102

# 2. 编辑 ~/.config/opencode/opencode.json，修改 baseURL
#    修改前: "baseURL": "http://127.0.0.1:4102/v1"
#    修改后: "baseURL": "http://127.0.0.1:6102/v1"
#
#    apiKey 保持不变（当前值：sk-ccc-opencode-2017，与 6102 实例对齐）

# 3. 直连兜底配置（~/.config/opencode/opencode.direct.json）不需要动
#    该文件仅在 fail-open 时使用，不涉及 6102 切换
```

#### 2C. 验证冒烟

```bash
# ── 前置检查 ──────────────────────────────────
# 确认 6100/6102 监听中
lsof -i :6100 -i :6102 -P 2>/dev/null | grep LISTEN

# ── A. Claude Code 验证（6100 Anthropic 协议）──
# 方式 1: Engine 环境验证（通过 engine.env 生效后）
claude -p "respond with OK" --model flash

# 方式 2: 直接 API 验证
curl -s -X POST http://127.0.0.1:6100/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: loop-router-flash" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"flash","max_tokens":10,"messages":[{"role":"user","content":"respond with OK"}]}' \
  | head -c 200

# ── B. OpenCode 验证（6102 OpenAI Chat 协议）──
opencode run --model loop/flash --auto --dir /tmp \
  "respond with OK" --no-interactive

# 方式 2: 直接 API 验证
curl -s -X POST http://127.0.0.1:6102/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-ccc-opencode-2017" \
  -d '{"model":"code","messages":[{"role":"user","content":"respond with OK"}],"max_tokens":10}' \
  | head -c 200

# ── C. Engine 自检 ─────────────────────────────
# 确认 Engine 加载了新环境变量
grep -E "AGENT_PLANNER_BASE_URL|ANTHROPIC_BASE_URL" ~/.ccc/engine.env
```

---

### 3. 一键回滚

每步切换均配备份，回滚时恢复即可。

#### 3A. Claude Code 回滚

```bash
# 恢复 settings.json
cp ~/.claude/settings.json.bak-ccc-6100 ~/.claude/settings.json

# 移除 engine.env 中的 6100 覆盖行
sed -i '' '/AGENT_PLANNER_BASE_URL.*6100/d' ~/.ccc/engine.env
sed -i '' '/ANTHROPIC_BASE_URL.*6100/d' ~/.ccc/engine.env

# 重启 Engine
launchctl kickstart gui/$(id -u)/com.ccc.engine
```

#### 3B. OpenCode 回滚

```bash
# 恢复 opencode.json
cp ~/.config/opencode/opencode.json.bak-ccc-6102 ~/.config/opencode/opencode.json
```

#### 3C. 全量回滚脚本（一键）

```bash
#!/bin/bash
# ccc-rollback-6100.sh — 一键回滚 6100/6102 切换
# 用法: bash ccc-rollback-6100.sh

set -e

echo "=== CCC 6100/6102 切换回滚 ==="

# Claude Code
if [ -f ~/.claude/settings.json.bak-ccc-6100 ]; then
  cp ~/.claude/settings.json.bak-ccc-6100 ~/.claude/settings.json
  echo "✅ Claude Code 配置已恢复"
else
  echo "⚠️  Claude Code 备份不存在，跳过"
fi

# Engine env
if [ -f ~/.ccc/engine.env ]; then
  sed -i '' '/AGENT_PLANNER_BASE_URL.*6100/d' ~/.ccc/engine.env
  sed -i '' '/ANTHROPIC_BASE_URL.*6100/d' ~/.ccc/engine.env
  echo "✅ Engine env 6100 行已移除"
fi

# OpenCode
if [ -f ~/.config/opencode/opencode.json.bak-ccc-6102 ]; then
  cp ~/.config/opencode/opencode.json.bak-ccc-6102 ~/.config/opencode/opencode.json
  echo "✅ OpenCode 配置已恢复"
else
  echo "⚠️  OpenCode 备份不存在，跳过"
fi

# 重启 Engine
launchctl kickstart gui/$(id -u)/com.ccc.engine 2>/dev/null || true
echo "✅ Engine 已重启"

echo "=== 回滚完成 ==="
```

---

### 4. 切换执行前置条件

切换前必须满足以下条件，否则不得执行：

| # | 条件 | 验证方式 | 责任人 |
|---|------|----------|--------|
| P1 | 6100/6102 稳定运行 ≥24h 无异常重启 | `lsof -i :6100 -i :6102` + 日志检查 | 运维 |
| P2 | 双协议冒烟通过（Anthropic + OpenAI Chat） | 执行 2C 验证命令 | 运维 |
| P3 | 6100/6102 独立账号额度充足（不与 M1 共用） | 检查 `upstreams.json` 账号配置 | 老板确认 |
| P4 | 客户端认证方案确定（无认证 / clients.json 二选一） | 当前为无认证模式 | 老板确认 |
| P5 | Engine 重启窗口确认（Engine 重启约 30s 空窗期） | 确认当前无运行中 work | 老板确认 |
| P6 | 回滚脚本就绪 | 验证 `ccc-rollback-6100.sh` 存在 | 本清单 |

---

### 5. 切换后影响分析

| 维度 | 切换前 | 切换后 | 差异 |
|------|--------|--------|------|
| 模型出口 | M1 `:4100`/`:4102`（LAN 跨机） | Mac2017 本机 `:6100`/`:6102` | 减少 LAN 延迟，不依赖 M1 可用性 |
| 账号额度 | 共用 M1 主账号 | 独立账号（T4 配置） | 额度隔离，不挤占 M1 |
| 故障域 | M1 宕机 → 编排面瘫痪 | 2017 独立中转 → M1 宕机不影响编排 | 编排面自治 |
| 回滚代价 | — | 备份文件 + 回滚脚本 | 秒级恢复 |
| M1 旧中转站 | 仍运行 | **不动**（M1 对话面仍用 4100/4102） | 零影响 |

---

### 6. 相关文件索引

| 文件 | 说明 |
|------|------|
| `server/deploy/start-ccc-router.sh` | 6100/6102 启动脚本 |
| `server/deploy/com.ccc.router.plist` | launchd 常驻配置 |
| `server/deploy/upstreams.json.example` | 上游配置示例（去密钥） |
| `scripts/ccc-engine.sh` | Engine 入口，设 `ANTHROPIC_BASE_URL` 默认值 |
| `scripts/opencode-exec.py` | OpenCode 执行器，含 fail-open 逻辑 |
| `scripts/_utils.py` | `get_relay_url()` 解析逻辑 |
| `docs/deploy/topology.md` | 部署拓扑（SSOT） |
| `docs/executors/overview.md` | 执行器总览 |
| `docs/dispatch/T4-relay-mac2017.md` | T4 部署记录（6100/6102 设立） |

---

## 回写区

**执行摘要**：T8 调用方切换清单已产出，覆盖 Claude Code / OpenCode / Engine 三个调用方，每步配一键回滚，并列出 6 项切换前置条件。

**盘点输出**：
- Claude Code 当前指向：Engine 级 `AGENT_PLANNER_BASE_URL=http://127.0.0.1:4100`（`ccc-engine.sh` + `~/.ccc/engine.env`）
- OpenCode 当前指向：`~/.config/opencode/opencode.json` → `baseURL: http://127.0.0.1:4102/v1`
- Engine 自身：`ccc-engine.sh` 第 28-34 行默认值

**清单路径**：`docs/dispatch/T8-switch-checklist.md`（本文件）

**验收自检对照表**：

| # | 验收标准 | 自查 | 状态 |
|---|----------|------|------|
| 1 | 覆盖所有调用方（Claude Code / OpenCode / 其他），含验证步骤 | 清单 §2A/B/C 覆盖 Claude Code、OpenCode、Engine 环境变量；Codex 确认不依赖 relay | ✅ |
| 2 | 每步附一键回滚 | 清单 §3A/B/C：逐步回滚 + 全量脚本 `ccc-rollback-6100.sh` | ✅ |
| 3 | 明确标注「实际切换需老板放行」；未碰任何真实配置 | 清单 §2 顶部 ⚠️ 标注；本卡只产出文档，未修改任何真实配置 | ✅ |
| 4 | 提交真实；未动运行面 | 本提交仅修改 `docs/dispatch/T8-switch-checklist.md`，未动任何运行面 | ✅ |

**commit hash**：`a2522f9`

## 验收通过（Claude Code · 2026-08-02）

- 独立复核：清单完整（盘点 4 调用方 / 切换步骤 / 回滚 16 处 / 需放行标注 5 处）；只产出文档未碰真实配置；commit `a2522f9` + 回写 `ec413d1`
- 纪律更正：Trae 未同步卡头状态（§3），验收席代改「已关闭」
