# loop-code 所有权切割 — 剩余一次收口（Phase3–5 基线）

> **状态**：Phase3–5 基线已执行（2026-07-21）  
> **对齐**：[`loop-code-ownership-cut.md`](loop-code-ownership-cut.md)  
> **性质**：把 Phase3+4+5 **基线**一次性做完；不做对话式拆多轮。  
> **Phase5 默认范围**：VERSION 可见 + 会话/历史路径收敛 + 私有 settings 种子。**不做** MCP/hooks/skills 管理大盘。

---

## 0. 已完成 / 本批要完成

| 阶段 | 状态 |
|------|------|
| Phase1 配置家 + 禁 PATH 回落 | ✅ `2eafef2` |
| Phase2 M1 退役原版 CLI | ✅ `2db91da` |
| **Phase3** 2017 `engine-claude` | ✅ closeout |
| **Phase4** 会话 SSOT + VERSION UI | ✅ closeout |
| **Phase5 基线** settings 种子 + sync 指向 | ✅ closeout |
| Phase5+ MCP/hooks UI 等 | **不在本批**（标为后续） |

### 本批结束态

| 面 | 完成态 |
|----|--------|
| **2017** | Engine product/reviewer：`CLAUDE_CONFIG_DIR=~/.ccc/engine-claude`；仍用 x86 `claude` → MiniMax |
| **M1** | Desktop 会话权威 = `LocalSessionStore`；Settings 可见 loop-code VERSION + config_dir；私有 `settings.json` 种子 |
| **叙事** | SSOT Phase3/4/5 基线全绿 |

```text
M1（已 P1/P2）                      本批补齐
Desktop → sidecar → loop-code
         ~/.ccc/loop-code  ──► VERSION in /health + Settings
         LocalSessionStore SSOT
                │ transfer
                ▼
Mac2017 Engine → Claude CLI x86
         CLAUDE_CONFIG_DIR=~/.ccc/engine-claude
```

---

## 1. 明确不做

- 2017 换 loop-code / 双架构 fork  
- 删除整个 `~/.claude`  
- MCP / hooks / skills 管理 UI  
- Hub `/api/chat` 复活  
- 强制 `VERSION` 文件大版本 bump（代码合入即可；产品 VERSION 仅在要求时改）

---

## 2. Phase3 — Mac2017 Engine 配置家

现网：`com.ccc.engine` **无** EnvironmentVariables，靠 `scripts/ccc-engine.sh` + `_executor._claude_env()`。

| 文件 | 改动 |
|------|------|
| `scripts/_claude_cli.py` | `default_engine_claude_config_dir()` + `ensure_engine_claude_config_dir()`（种子短 `CLAUDE.md`：无头扇出） |
| `scripts/ccc-engine.sh` | `export CLAUDE_CONFIG_DIR=.../engine-claude`；启动 ensure |
| `scripts/_executor.py` | `_claude_env()` 强制写入 `CLAUDE_CONFIG_DIR` |
| product/reviewer / `_product_session.py` | 补漏：凡起 Claude 的 env 都带上 |
| `scripts/smoke-engine-claude-config.sh` | 断言目录种子 +（可 SSH）Engine 侧 env |

**2017 落地（同批）**

```bash
ssh mac2017 'cd ~/program/CCC && git pull --ff-only'
# kickstart com.ccc.engine
# 验收：~/.ccc/engine-claude/CLAUDE.md 存在；扇出无 login 回归
```

---

## 3. Phase4 — 会话 SSOT + VERSION

| 项 | 改动 |
|----|------|
| sidecar `/health` | 读 `vendor/loop-code/VERSION`（+ SHA256 短前缀）→ `loop_code_version` |
| Desktop | `APIClient` 解析；Settings 展示 runtime / version / config_dir |
| 打包 | `desktop/scripts/package-baseline.sh` → `/Applications` |
| 历史 | `claude_history` **优先** `CLAUDE_CONFIG_DIR/.../projects`；Desktop 不以个人 `~/.claude/projects` 为权威 |
| 烟测 | `smoke-loop-code-no-personal-claude.sh` 断言 version 非空 |

---

## 4. Phase5 基线 — 私有 settings（非大盘）

| 项 | 改动 |
|----|------|
| ensure_*_config_dir | 无则写最小 `settings.json`（不复制个人家） |
| `ccc-sync-agent-roots.py` | M1 优先同步到 `~/.ccc/loop-code/settings.json`；2017/兼容路径文档标明 |
| SSOT | Phase5 **基线** ✅；MCP UI 等 → Phase5+ 后续 |

---

## 5. 验收矩阵（一次过完）

| # | 检查 | 期望 |
|---|------|------|
| 1 | M1 `command -v claude` | 空 |
| 2 | M1 `/health` | loop-code + config_dir + **version** |
| 3 | M1 Settings | 可见 version / config |
| 4 | `smoke-loop-code-no-personal-claude.sh` | PASS |
| 5 | `smoke-desktop-agent.sh` | PASS |
| 6 | 2017 `~/.ccc/engine-claude/CLAUDE.md` | 存在 |
| 7 | 2017 Engine 子进程 env | 含 `.../engine-claude` |
| 8 | 2017 扇出/闲置 | 无 auth/login 回归 |
| 9 | `~/.claude` | **未删** |

失败即停。

---

## 6. 实现顺序（单波次，不拆对话）

1. 本文 + 更新 `loop-code-ownership-cut.md` / topology / dev-channel / executors/loop-code.md  
2. Phase3 代码 + smoke  
3. Phase4 health + Desktop Settings + history 优先 config_dir + 打包  
4. Phase5 settings 种子 + sync-agent-roots  
5. M1：重装 sidecar、装 Desktop、跑烟测 1–5  
6. 2017：pull + kickstart Engine、验收 6–8  
7. SSOT 标 Phase3/4/5 基线完成 → commit + push  

---

## 7. 回滚

- Phase3：Engine 去掉 `CLAUDE_CONFIG_DIR`；可留 `~/.ccc/engine-claude`  
- Phase4：隐藏 Settings 字段；health 去掉 version 无害  
- Phase5：删私有 `settings.json` 即可回落 CLI 默认  

---

## 8. 关联

- Phase1 brief · Phase2 brief  
- [`desktop-agent-sidecar.md`](desktop-agent-sidecar.md) · [`dev-channel.md`](dev-channel.md) · [`../deploy/topology.md`](../deploy/topology.md)
