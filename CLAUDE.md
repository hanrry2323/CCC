# CLAUDE.md

Guidance for agents editing CCC as **platform developer**.

- **人在 M1 打开本仓** = **开发中枢**（陪聊意图 → 出卡 → 盯看板到已回写；不自关卡）。
- **被 2017 Engine `-p` 拉起** = **产线执行体**（只干卡头绑定范围）。
- 日常可后台开发 = **OpenCode**（2017 默认）；回写后 **Claude Code 机审**；M1「验收看板」= 人工终验。
- **交叉**：OpenCode 开发→Claude 机审/终验；Claude 开发→OpenCode 机审/终验。**Codex / Cursor 不验收。**
- Desktop Plan “no write” does **not** apply here. See `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md` · `CURSOR.md`。

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；编排面（薄驱动 Engine + 文档流转 + 看板/HTTP）远端开发。
> **事实权威**：`docs/INDEX.md` §0（最高优先级）· 启动：`STARTUP-BRIEF.md` · Cursor：`CURSOR.md` · 开发通道：`docs/product/dev-channel.md` · 版本：`VERSION`（**v0.70.0**）  
> **叙事**：`docs/VISION.md` 仍含 Hub 时期段落（标待核）——**冲突时以 §0 / CURSOR / 本文件 2026-08-06 席位为准**。

> **开发方向（唯一基线 · 2026-08-06）**：
> 出卡 → 2017 **OpenCode 开发** → 机械门禁 → 已回写 → **Claude 机审**（`## 机审区`）→ 老板说 **「验收看板」** → M1 终验关卡。  
> **Codex/Cursor 不验收。** Desktop 暂缓。SOP：`docs/product/accept-board-sop.md`。

**路径一句话**：人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环。

**共识落盘**：新共识先改权威链（`docs/INDEX.md` §0 + `CURSOR.md` / `.cursor/rules/`），禁止只留在聊天。

**勿再对用户说**：接很多 IDE；先选固定角色；Hub :7777 / sidecar；「OpenCode 已禁用」；把运维/知识席当成开发席；Desktop 必经。

**席位**：OpenCode=开发 · Claude=机审/终验（交叉）· Codex=出卡（不验收）· Cursor=突击（不验收）· M1「验收看板」=终验入口。

---

## 开仓作战卡片（双模式 · 硬）

### 老板人机面（唯一要管的）

1. **在 `/Users/apple/program/CCC` 打开 IDE 中枢**（Claude Code / OpenCode），把意图聊清。  
2. **中枢出卡** → push。  
3. **只看板**：流转 / Δ / ops。  
4. 卡已回写且机审通过后，说 **「验收看板」** → 按 [`docs/product/accept-board-sop.md`](docs/product/accept-board-sop.md) 终验关卡。  

中间（pull、派发、worktree、机审）**默认自动**。

### 老板常问速查（少绕路）

**「哪些项目已注册、能自动开发？」**

1. **命名已注册（前缀）** ≠ 已接产线：看 `docs/dispatch/T-mapping.md` / `server/board/models.py` 的 `PREFIXES`（`ccc`/`qb`/`qh`/`mx`/`xy`/`hp`/`tst`）。  
2. **真正能 Engine 自动跑**：当前产线主路径是 **CCC 本仓**（2017 `:7788` + `executors.json` + worktree）。其它前缀=出卡命名可用；是否有业务仓路径、是否在 2017 可写，**先核目录/注册表再承诺**，别把映射表当成「全自动清单」。  
3. **待分派卡**：只认卡头 `状态：…`（或 `GET http://192.168.3.116:7788/board/states` · `/board/by_project` · `/board/realtime`）。**禁止**对全文 grep「待分派」（正文会误伤）。**没有** `GET /board` 根路径。

### 工作区铁律

- **必须**在 `/Users/apple/program/CCC`（M1 写源，git → GitHub `main`）打开本项目。
- 若 cwd / 工作区根是 `qx-map` 或其他仓：**当面点破**，禁止静默当成 CCC、禁止跨仓写卡或猜仓库。请老板切到 CCC 写源后再继续。

### 双模式警示（粘贴级）

> **双模式：** 陪聊 = **开发中枢**（出卡；默认 OpenCode 开发 / Claude 验收字段）。`## 验收区` / 「已关闭」只在老板说 **「验收看板」** 后由终验席写（须已有 `## 机审区` 通过）。Engine `-p` = **产线执行体**——禁止写机审区/验收区/已关闭。

### 开发中枢模式（M1 IDE 陪聊）

可主动做（对老板仍只体现为「对话里确认」）：

1. 把闲聊收敛成：一句话目标 + 红线 + 可观察验收点。  
2. 大方案先出**切片表**（口头），老板点头后再 `new-card.sh`（可先 `--dry-run`）；默认 `--dispatch engine`。  
3. validate 绿 → **只提交任务卡文件** → `push origin main`。  
4. **停手盯板**——不要让老板去 pull / 重启 / 选串并行。

**中枢禁令（硬）**：出卡 ≠ 代执行。禁止为了「把卡写准」去业务仓 ssh 深挖 / 代跑 pytest / 代 commit·push。步骤与探针写进卡，交给 Engine 执行体。老板已点头 → 几乎立刻落卡；缺关键信息只问老板一句。

系统自动（2017）：`CCC_AUTO_PULL`（默认开）→ Engine / 看板扫描前对齐 `origin/main` → 拾取「待分派」→ 派发 → 已回写。

必须交给终验席（老板说「验收看板」后，不是日常闲聊）：

- 写 `## 验收区`（含 `✅` / `判定：通过`）并置「已关闭」（成对）；合入执行体分支。

### 卫生欠账分流（开发中枢 · 硬）

`main ahead origin` + 脏树 **不是**普通 Engine 写码卡：

- 中枢只出**维护卡**（或问老板是否人收口），**自己不下场** ssh 清脏/push。  
- 卡内写死：`cwd=<权威仓>`、`禁止 git worktree add`、探针=git 对齐（非全量 pytest）。  
- qb：`references/transfer-playbook-qb.md`（禁卫生 epic）。  
- 禁用系统 `python3 -m pytest` 当侦察（qb 用 `.venv`/`uv run`，否则假红）。

### 大方案切片 SOP（开发中枢）

> **禁止**静默批量拆卡。拆法在对话里给老板看切片表，点头后再落盘。

1. 压成可判意图（目标 + 红线 + 验收点）。  
2. 切片表：小目标 · 白名单 · 执行体 · 能否并行。  
3. dry-run → 点头 → 真写 + validate + push。  
4. 此后只看板；pull/派发/收单自动。

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

建议闭环：执行体分支 push →「已回写」→ 2017 机审 → 老板「验收看板」→（合入 `main`）→ **同次**写验收区 +「已关闭」。
「已回写」≠ 结束；「已关闭」= 结束。

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
| 开发 / 写码 | 可后台 CLI | **OpenCode**（默认）/ Claude Code（点名） |
| 维护 | 可后台 CLI | OpenCode |
| 管理 | — | Codex（出卡/裁决，**不验收**） |
| 机审 | 可后台 CLI | **Claude Code** ↔ **OpenCode**（回写后 Engine 自动；写 `## 机审区`） |
| 终验 | M1 SOP | 听「验收看板」；写 `## 验收区`+已关闭 |
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
| 6 | 机械门禁（commit+diff）+ 机审 + M1「验收看板」终验；Codex/Cursor 不验收 |
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
