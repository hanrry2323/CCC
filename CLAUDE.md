# CLAUDE.md

Guidance for agents editing CCC in **开发工具（Claude/OpenCode）**. You are the **platform developer** (full IDE capability on this repo) — **席位里的开发席**。You are **not** Desktop / Claude Code ops / Codex knowledge / OpenCode personal IDE. Personalities independent — Desktop Plan “no write” does **not** apply to you. 合入走开发工具（Claude/OpenCode）（R-15）。See `docs/product/dev-channel.md` · 重构契约见 `docs/INDEX.md` §0（席位工具定位 · 双 Agent 人格独立）.

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；编排面（薄驱动 Engine + 文档流转 + 看板/HTTP）远端开发。
> **事实权威 + 人机共识（最新）**：重构决策定稿 `docs/INDEX.md` §0（最高优先级）· 边界：`docs/product/dialogue-orchestration-boundary.md`（史） · 叙事：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 开发通道：`docs/product/dev-channel.md` · 版本：`VERSION`（**v0.70.0**）

**路径一句话**：人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环；全程只认一个权威仓 + 一份任务卡文档。

**共识落盘**：你我新共识先改权威链文档（`docs/INDEX.md` §0），禁止只留在聊天。

**勿再对用户说**：接很多 IDE 当卖点；让用户先选固定角色；把运维/知识席当成开发席。

**席位**：Claude/OpenCode=开发合入 · Claude Code=运维 · OpenCode=Engine 写码槽 · Codex=知识/闲聊 · Desktop=任意设备壳。

---

## 平台开发硬规则（对齐基线 / 定方案时强制）

1. **新栈在 `server/`**：薄驱动 Engine + 看板服务端 + HTTP API + 中转站 + 知识库 + 配置化 + 部署模板；旧 `scripts/` 已退役（归档于 `.ccc/archive/legacy-retired-2026-08-02/scripts/`），**禁止**在新代码引用旧 `scripts/`。
2. **2017 单端 :7788**：HTTP 直连，账号密码 + token；对话口接大脑 Agent（Claude Code CLI via 6100）；看板/运维/线路图视图经 HTTP API 提供。任意设备壳（Desktop/网页/手机）指向 2017。
3. **任务卡 = 唯一事实源**：`docs/dispatch/*.md` 是任务流转的根；`server/board/loader.py` 从任务卡解析派生看板数据，不另建数据源。
4. **版本 SSOT**：`VERSION` > `CHANGELOG` 最新节 > README badge；不一致只报「对齐版本」类小任务。
5. **禁止越界建议**：非用户主动问闲置/省资源时，**禁止**建议关机或降级服务。
6. **零硬编码**：端口、路径、模型名、上游地址、工具名一律走 `config.env` / 执行体注册表变量；代码与模板出现字面量即验收不通过。
7. **不碰运行面**：本仓只产代码与模板；2017 运行面由部署卡（T22 已落地，三服务常驻）维护。

架构细节：`docs/architecture.md` · 运维页：HTTP `#/ops`（2017 :7788）。

---

## 开发命令

```bash
# Python 语法检查（必做，server/ 新栈代码）
python -m py_compile server/engine/main.py

# 单测（新栈测试，server/tests/）
pytest server/tests/ -q --tb=short

# 单文件测试
pytest server/tests/test_engine_main.py -v --tb=short

# 单用例（-k 支持 name 匹配）
pytest server/tests/test_http_api.py -v -k test_conversation

# Ruff lint（CI 级，覆盖 server/）
ruff check server/ tests/

# 看板导出（从 docs/dispatch/ 解析任务卡 → web/data/board.js）
python3 -m server.board.export

# 引擎单次扫描 + 收单
python3 -m server.engine.main --config server/config/config.env --once

# HTTP API 服务启动（生产部署走 launchd plist）
python3 -m server.web.server --port 7788

# 健康检查（2017 生产端）
curl -s http://192.168.3.116:7788/health
```

> 旧 `scripts/*.py` 命令（`ccc-engine.py` / `ccc-board.py` / `ccc-autostart-guard.sh` 等）已退役，勿引用。

---

## 架构概要

### 终态：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳

```
任意设备壳（Desktop / 网页 / 手机）
  │  HTTP 直连（账号密码 + token）
  ▼
2017 单端 :7788（server/web/server.py）
  ├─ /conversation → 大脑 Agent（Claude Code CLI via 6100，带心智/工具/知识库）
  ├─ /board/*      → 看板视图（snapshot/states/recent/roadmap/summaries）
  ├─ /ops/summary  → 运维聚合（节点/红灯/概览）
  └─ /session      → 账号密码换 token
  │
  ▼
薄驱动 Engine（server/engine/）
  ├─ 读取 config/executors.json（契约 §7 注册表）
  ├─ 派发：按执行体分类（可后台 CLI → 自动拉起 / 手动 GUI → 挂起等人）
  ├─ 收单：按退出码 + 输出判定 → 状态机流转
  └─ 状态更新写入看板接口（store.py）
  │
  ▼
看板服务端（server/board/）
  ├─ loader.py：从 docs/dispatch/*.md 解析任务卡 → BoardItem
  ├─ queries.py：实时/7天/项目分类三视图 + 线路图聚合
  └─ export.py：导出 web/data/board.js（零 API 模式）
```

### 任务卡状态机（契约 §2 五态）

```
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回（附问题清单）→ 待分派（人工重派）
```

- **任务卡文档 = 唯一事实源**：`docs/dispatch/T<n>-*.md`，元数据行含 `状态：X` / `执行体：Y` / `日期：Z`。
- **非法状态转移** 一律抛 `IllegalTransitionError`。
- 无旧看板状态机（planned/verified/released）残留。

### 执行体注册表（契约 §7）

`server/config/executors.json` 五角色，分类只允许「可后台 CLI」/「手动 GUI」：

| 角色 | 分类 | 当前绑定 |
|------|------|----------|
| product | 可后台 CLI | Claude Code |
| dev | 可后台 CLI | OpenCode |
| reviewer | 可后台 CLI | Claude Code |
| tester | 可后台 CLI | OpenCode |
| ops | 手动 GUI | — |

### 入口架构

```
launchd(com.ccc.web-server)        → server/web/server.py :7788（HTTP API + 静态页）
launchd(com.ccc.engine)            → server/engine/main.py（薄驱动主循环）
launchd(com.ccc.board-scheduler)   → server/board/scheduler.py（只读巡检 + 导出）
```

| 端口 | 服务 | 说明 |
|------|------|------|
| 7788 | CCC Web Server | **2017 唯一服务端**（对话/看板/运维/线路图，HTTP 直连） |
| 6100 | Anthropic 出口 | 大脑 Agent Claude Code CLI 走此出口 |
| 6102 | Relay flash | 模型出口上游路由（中转站） |

旧端口（7777 Hub / 7775 Board API / 7788 sidecar / 7778 Cockpit）已退役，勿引用。

---

## 关键资产

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 注入 prompt 总纲（agent 启动时自动加载） |
| `server/engine/` | 薄驱动核心：dispatch / main / scheduler / store / task / cluster |
| `server/board/` | 看板服务端：loader / queries / export / models / scheduler |
| `server/web/` | HTTP API + 静态页：server.py / brain.py（大脑 Agent 代理） |
| `server/relay/` | 中转站：模型出口上游路由与密钥管理 |
| `server/kb/` | 知识库：MCP 服务 + BM25 本地检索（纯 Python） |
| `server/config/` | 配置系统：env 加载器 + 执行体注册表（契约 §7） |
| `server/deploy/` | 进程编排：launchd plist 模板 + 启动/健康检查脚本 |
| `server/tests/` | 测试：冒烟 + 单元 + HTTP API + 各模块 |
| `references/red-lines.md` | 红线 + X/R 系列 |
| `references/board-task-schema.md` | 任务卡文档契约 |
| `docs/dispatch/` | 任务卡文档（唯一事实源） |
| `docs/INDEX.md` | 文档索引 SSOT（§0 重构决策 + 契约 v1 最高优先级） |
| `docs/architecture.md` | 架构概览 |
| `templates/` | plan/phases/report/verdict/AGENTS 模板（Engine 运行时依赖） |

---

## 工程红线（摘要）

| # | 红线 | 一句话 |
|---|------|--------|
| 1 | 不动系统文件 | /etc、~/.env、密钥不改 |
| 2 | 验收必须可执行 | 自然语言 + 可选命令 |
| 3 | 不超出任务卡范围 | 白名单外不动 |
| 4 | 单 phase 单 commit | 兜底 commit 由脚本做 |
| 5 | 任务卡必写全 | 元数据行 + 回写区 |
| 6 | 执行体不互串 | product 不写代码，reviewer 不写 plan |
| 7 | 启动顺序固定 | 读 state.md + profile.md 第一 |
| 8 | 每步必 commit | exec-commit 兜底 |
| 9 | 卡死立即止损 | kill + 下一个角色接管 |
| 10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| **11** | Verdict 必须写 verdict 文件 | 口头 PASS 不算 |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

完整版含 R-/X- 别名 → `references/red-lines.md`。

---

## 模型通道

| 通道 | 用途 | 上游 |
|------|------|------|
| 对话槽（大脑 Agent） | /conversation 对话 + product/reviewer | 2017 Claude Code CLI via 6100（Anthropic 出口） |
| 写码槽（OpenCode，Engine dev） | 后台写码（dev） | Relay 路由 6102（flash/code 档） |

中转站决议（2026-08-02 重构）：6100 = CCC 体系 Anthropic 出口；6102 = Relay flash 出口。详见 `docs/deploy/topology.md` · `docs/executors/overview.md`。

---

## 与 qxo 的关系

独立发展、共享 `board-task-schema.md` 定义的任务卡契约。
CCC 不依赖 QXO 代码，QXO 可写标准任务卡投递到 `docs/dispatch/`。
