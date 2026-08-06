# CLAUDE.md

Guidance for agents editing CCC as **platform developer**. 开发执行体 = 注册表可后台 CLI（**Claude Code / OpenCode**）；Codex = 出卡/验收；Cursor = 了解/讨论/排查/文档对齐（明确测试卡除外）。人格独立 — Desktop Plan “no write” does **not** apply to 开发工具席。See `docs/product/dev-channel.md` · `CURSOR.md` · `docs/INDEX.md` §0。

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；编排面（薄驱动 Engine + 文档流转 + 看板/HTTP）远端开发。
> **事实权威**：`docs/INDEX.md` §0（最高优先级）· 启动：`STARTUP-BRIEF.md` · Cursor：`CURSOR.md` · 开发通道：`docs/product/dev-channel.md` · 版本：`VERSION`（**v0.70.0**）  
> **叙事**：`docs/VISION.md` 仍含 Hub 时期段落（标待核）——**冲突时以 §0 / CURSOR / 本文件 2026-08-05 席位为准**。

> **开发方向（唯一基线 · 2026-08-06）**：
> **自研期（当前）**：Codex 出卡 → push → 2017 pull → Engine 按卡头绑定派发 **Claude Code 或 OpenCode**（worktree）→ Codex 验收 → 合入部署。  
> **业务期（自研成熟后）**：老板用壳直聊大脑 Agent；业务任务走 Engine 派发。  
> **OpenCode 可用**（与 Claude Code 并列；模型档 code / 6102 vs flash / 6100）。Codex = 驱动/验收。  
> **人机面**：HTTP 看板/运维为主；Desktop 暂缓。

**路径一句话**：人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环。

**共识落盘**：新共识先改权威链（`docs/INDEX.md` §0 + `CURSOR.md` / `.cursor/rules/`），禁止只留在聊天。

**勿再对用户说**：接很多 IDE；先选固定角色；Hub :7777 / sidecar；「OpenCode 已禁用」；把运维/知识席当成开发席；Desktop 必经。

**席位**：Claude Code / OpenCode = 可后台 CLI · Codex = 驱动/验收 · M1 IDE = 开发中枢 · HTTP 看板 = 实时面 · Desktop = 暂缓壳。

---

## 平台开发硬规则（对齐基线 / 定方案时强制）

1. **新栈在 `server/`**：薄驱动 Engine + 看板 + HTTP + 中转站 + 知识库 + 配置 + 部署模板；旧 `scripts/` 已退役（归档），**禁止**在新代码引用旧 `scripts/` 编排脚本。
2. **2017 单端 :7788**：HTTP 直连；对话口接大脑 Agent（Claude Code via 6100）。任意设备壳指向 2017。
3. **任务卡 = 唯一事实源**：`docs/dispatch/*.md`；看板由 `server/board/loader.py` 派生。
4. **版本 SSOT**：`VERSION` > `CHANGELOG` 最新节 > README badge。
5. **禁止越界建议**：非用户主动问闲置/省资源时，**禁止**建议关机或降级服务。
6. **零硬编码**：端口、路径、模型名、上游、工具名走 `config.env` / 执行体注册表。
7. **不碰运行面**：本仓产代码与模板；2017 运行面由部署流程维护（只 pull）。

架构：`docs/architecture.md` · 运维页：HTTP `#/ops`（2017 :7788）。

---

## 开发命令

```bash
python -m py_compile server/engine/main.py
pytest server/tests/ -q --tb=short
ruff check server/
python -m server.board.validate docs/dispatch
python3 -m server.board.export
python3 -m server.engine.main --config server/config/config.env --once
curl -s http://192.168.3.116:7788/health
```

> 旧 `scripts/ccc-engine.py` / `ccc-board.py` 等已退役，勿引用。

---

## 架构概要

```
任意设备壳 → HTTP → 2017 :7788（server/web/server.py）
  ├─ /conversation → 大脑 Agent（Claude Code via 6100）
  ├─ /board/* · /ops/summary · /session
  └─ Engine（server/engine/）按 executors.json 派发 Claude Code
       └─ board/loader.py 从 docs/dispatch/*.md 派生看板
```

### 任务卡状态机（契约 §2 五态）

```
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回 → 待分派（人工重派）
```

### 执行体（现行）

| 语义 | 分类 | 当前绑定 |
|------|------|----------|
| 开发 / 写码 | 可后台 CLI | **Claude Code** / **OpenCode** |
| 维护 | 可后台 CLI | Claude Code（或 OpenCode，按卡头） |
| 管理 / 验收 | — | Codex |
| ops | 手动 GUI | — |

Claude Code（flash/6100）与 OpenCode（code/6102）并列可后台 CLI。注册表模板见 `server/config/executors.example.json`；生产以 2017 实机 `executors.json` 为准。

### 入口

```
launchd(com.ccc.web-server)      → :7788
launchd(com.ccc.engine)          → server/engine/main.py
launchd(com.ccc.board-scheduler) → server/board/scheduler.py
```

| 端口 | 说明 |
|------|------|
| 7788 | 2017 唯一 HTTP 服务端 |
| 6100 | Anthropic 出口（大脑 + Claude Code 执行体） |
| 6102 | Relay flash/code 上游路由 |

旧端口（7777 Hub / 7775 Board / 7788-M1 sidecar / 7778 Cockpit）已退役。

---

## 关键资产

| 路径 | 角色 |
|------|------|
| `CURSOR.md` / `STARTUP-BRIEF.md` / `SKILL.md` | 入口 |
| `server/engine/` · `board/` · `web/` · `kb/` · `config/` · `deploy/` | 新栈 |
| `docs/dispatch/` | 任务卡唯一事实源 |
| `docs/INDEX.md` | 文档索引 §0 |
| `references/red-lines.md` | 红线 |

---

## 工程红线（摘要）

| # | 一句话 |
|---|--------|
| 1 | 不动系统文件 / 密钥 |
| 3 | 任务卡是唯一事实源 |
| 4 | 不超出任务卡范围 |
| 5 | 回写前 push 成功并附证据 |
| 6 | Codex 验收，不采信执行摘要 |
| 7 | 零硬编码（D10） |
| 8 | 运行时零依赖 qx-map/hp-kb（D2） |
| 9 | 免登录仅限局域网配置 |
| 10 | 不碰 2017 运行面手改 |

完整版 → `references/red-lines.md`。

---

## 模型通道

| 通道 | 上游 |
|------|------|
| 对话 + 执行体（Claude Code） | 2017 via **6100** |
| Relay 上游路由 | **6102** |

写码槽经注册表绑定 Claude Code 或 OpenCode。详见 `docs/deploy/topology.md`。

---

## 与 qxo 的关系

独立发展、共享 `board-task-schema.md`。CCC 不依赖 QXO 代码；QXO 可写标准任务卡到 `docs/dispatch/`。
