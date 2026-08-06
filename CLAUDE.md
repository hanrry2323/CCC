# CLAUDE.md

Guidance for agents editing CCC as **platform developer**.

- **人在 M1 打开本仓** = **开发中枢**（陪聊意图 → 出卡 → 盯看板到已回写；不自关卡）。
- **被 2017 Engine `-p` 拉起** = **产线执行体**（只干卡头绑定范围）。
- 日常可后台 CLI = **OpenCode / Claude Code**（卡头绑定优先）；**Cursor** = 难度突击手；**Codex** = 出卡/验收。
- Desktop Plan “no write” does **not** apply here. See `docs/product/dev-channel.md` · `CURSOR.md` · `docs/INDEX.md` §0。

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；编排面（薄驱动 Engine + 文档流转 + 看板/HTTP）远端开发。
> **事实权威**：`docs/INDEX.md` §0（最高优先级）· 启动：`STARTUP-BRIEF.md` · Cursor：`CURSOR.md` · 开发通道：`docs/product/dev-channel.md` · 版本：`VERSION`（**v0.70.0**）  
> **叙事**：`docs/VISION.md` 仍含 Hub 时期段落（标待核）——**冲突时以 §0 / CURSOR / 本文件 2026-08-06 席位为准**。

> **开发方向（唯一基线 · 2026-08-06）**：
> **自研期（当前）**：意图在 M1 IDE 聊清并可出卡 → push → 2017 pull → Engine 按卡头绑定派发 **Claude Code 或 OpenCode**（worktree）→ 执行体「已回写」→ Codex（或点名席）验收「已关闭」→ 合入部署。  
> **业务期（自研成熟后）**：老板用壳直聊大脑 Agent；业务任务走 Engine 派发。  
> **OpenCode 可用**（与 Claude Code 并列；模型档 code / 6102 vs flash / 6100）。Codex = 驱动/验收。  
> **人机面**：HTTP 看板/运维为主；Desktop 暂缓。

**路径一句话**：人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环。

**共识落盘**：新共识先改权威链（`docs/INDEX.md` §0 + `CURSOR.md` / `.cursor/rules/`），禁止只留在聊天。

**勿再对用户说**：接很多 IDE；先选固定角色；Hub :7777 / sidecar；「OpenCode 已禁用」；把运维/知识席当成开发席；Desktop 必经。

**席位**：Claude Code / OpenCode = 可后台 CLI · Codex = 驱动/验收 · M1 IDE = 开发中枢 · HTTP 看板 = 实时面 · Desktop = 暂缓壳。

---

## 开仓作战卡片（双模式 · 硬）

### 工作区铁律

- **必须**在 `/Users/apple/program/CCC`（M1 写源，git → GitHub `main`）打开本项目。
- 若 cwd / 工作区根是 `qx-map` 或其他仓：**当面点破**，禁止静默当成 CCC、禁止跨仓写卡或猜仓库。请老板切到 CCC 写源后再继续。

### 双模式警示（粘贴级）

> **双模式：** 人打开 `/Users/apple/program/CCC` 陪聊 = **开发中枢**——收敛意图、出卡（`push main`）、盯看板到执行体「已回写」；但 `## 验收区` / 「已关闭」归验收席（默认 Codex），合入 `main` + 2017 pull + 重启归部署/验收闭环，**不自关、不自推 main 当终态**。被 2017 Engine `-p` 拉起 = **产线执行体**——只做卡头绑定范围，**禁止**重出卡、改验收区、置已关闭、直推 `main`、手改 2017。

### 开发中枢模式（M1 IDE 陪聊）

可主动做：

1. 把闲聊收敛成：一句话目标 + 红线 + 可观察验收点。
2. `scripts/new-card.sh --dry-run ...` 预览 → 老板确认后再真写；默认 `--dispatch engine`，执行体按卡头绑定（Claude Code / OpenCode）。
3. `python -m server.board.validate docs/dispatch` 绿后，只提交任务卡相关文件并 `push origin main`。
4. 盯人机面：`http://192.168.3.116:7788/#/board`、`/tasks/running`；催看到卡头「已回写」+ 回写区三要素。

必须等人确认 / 交接：

- 写 `## 验收区`（含 `✅` 或 `判定：通过`）并置「已关闭」（与标记**成对**，否则 validate/T67 报错）。
- 合入 `main`（若执行体只推了 `codex/<id>-*` 分支）、2017 `pull`、必要时重启三服务。

### 大方案切片 SOP（开发中枢 · 硬）

> **禁止**：聊完大方案就静默拆多张卡推进「待分派」。拆卡是产品判断，须老板确认后才落盘。  
> **Engine 只拾取 2017 生产仓里已存在的卡**；不负责理解大方案，也不自动 `git pull`。

1. **压成可判意图**：一句话目标 + 红线 + 可观察验收点（大方案先瘦身，勿直接开写码）。
2. **输出切片表（先口头/表，不写卡）**：每行至少含——小目标 · 白名单路径 · 建议执行体（Claude Code / OpenCode）· 依赖（可并行？必须先完成哪张？）。卡要小、可单独验收。
3. **逐张 dry-run**：`scripts/new-card.sh ... --dry-run`（默认 `--dispatch engine`）；把路径与卡头摘要给老板看。
4. **老板点头后再真写**：去掉 `--dry-run` → `python -m server.board.validate docs/dispatch` 绿 → **只**提交新卡相关文件 → `push origin main`。
5. **对齐 2017（派发前置）**：生产仓 `git pull --ff-only`（中枢须当面提醒或等部署席完成）。**未 pull = Engine 看不见新卡**。
6. **盯板到已回写**：`http://192.168.3.116:7788/#/board`、`/tasks/running`（执行中可看 Δ dirty）；催回写区三要素。关卡 / 合入分支 / 再 pull **不自做**，交验收席。

切片原则（摘要）：一张卡一个可观察交付；有文件冲突的卡标「串行」；无冲突可并行。勿一张吞完大方案。  
并行上限看 **2017** `EXECUTOR_MAX_CONCURRENT`（实机常为 `1`=串行；代码默认 2，以实机为准）。SOP 切片表里的「可并行」在并发=1 时仍会排队串行执行。

### 产线执行体模式（Engine `-p`）

- 白名单内改动 → 分步 commit+push 到 `codex/<卡id>-<slug>`（不直推 `main`）。
- 卡头改「已回写」；回写区必填：实现说明 / 测试结果 / push 证据（分支 + commit）。
- **停手等验收**。禁止：重新出卡、写验收区、置已关闭、直推 `main`、手改 2017。

### 五态与关卡顺序（摘要）

```
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回 → 待分派（人工重派）
```

建议闭环：执行体分支 push →「已回写」→ 验收席取证 →（合入 `main`）→ **同次**写验收区 +「已关闭」→ 2017 pull。  
「已回写」≠ 结束；「已关闭」= 结束（对照：`ccc001`/`ccc002`/`ccc003`/`T76` 均已关闭）。

人看进度：`http://192.168.3.116:7788/#/board`。

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
# 出卡预览（不写盘）
scripts/new-card.sh --title "example" --slug example --executor "Claude Code" --dispatch engine --dry-run
```

> 旧 `scripts/ccc-engine.py` / `ccc-board.py` 等已退役，勿引用。

---

## 架构概要

```
任意设备壳 → HTTP → 2017 :7788（server/web/server.py）
  ├─ /conversation → 大脑 Agent（Claude Code via 6100）
  ├─ /board/* · /ops/summary · /session
  └─ Engine（server/engine/）按 executors.json 派发 Claude Code / OpenCode
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
