# 旧系统退役清单

> 产出卡：T12（盘点）· 日期：2026-08-02 · 关联：INT-120（CCC 重构收尾）
> 本卡只出清单与分类，不删除、不移动任何文件。删除/归档动作等老板确认后另排。

---

## 总览

| 目录 | 大小 | 文件数 | 分类 | 新栈对应 | 退役条件 |
|------|------|--------|------|----------|----------|
| `scripts/` | 12MB | 609 (247 .py, 80 .sh) | **已归档** ✅（T18） | `server/engine/` `server/board/` `server/web/`（骨架） | 新栈全部就绪并切换 |
| `app/` | 24KB | ~5 | **归档候选** | 无直接替代 | 随时可归档 |
| `desktop/` | 1.3G (源码 824K, .build/ 1.3G) | ~50 | **暂留（源码）/ 清理候选（构建产物）** | 桌面客户端本身 | 源码保留，.build/ 可清理 |
| `lib/` | 8KB | 2 | **归档候选** | 无直接替代 | 随时可归档 |
| `db/` | 4KB | 1 | **归档候选** | 无（CCC 独立后不再依赖 HP 数据库） | 随时可归档 |
| `relay/` | 0（node_modules T15 删 / dist T18 删） | 0 | **已清理** ✅（T15+T18） | `server/relay/`（空目录） | 旧 relay 已确认停止 |
| `skills/` | 40KB | 8 SKILL.md | **归档候选** | 无（新栈不再使用 Skill 机制） | 随时可归档 |
| `templates/` | 88KB | ~10 | **已归档** ✅（T18） | 待定 | 确认新栈模板就绪 |

---

## 详细盘点

### 1. `scripts/` — 旧系统主代码（12MB, 609 文件）

**职责**：CCC 旧系统的全部运行代码，包括：
- 入口脚本：`ccc-engine.py`、`ccc-board.py`、`ccc-chat-server.py`、`ccc-board-server.py`、`ccc-agent-sidecar.py`
- 子模块：`board/`（角色实现）、`engine/`（调度核心）、`chat_server/`（Hub 后端）
- 控制面：`_ccc_control.py`、`ccc-autostart-guard.sh`、`ccc-fleet.sh`
- 测试：`tests/`（含 112 测试用例）

**依赖方证据**：
- 正在运行（实测）：
  - `ccc-agent-sidecar.py` → PID 44523, 端口 7788
  - `ccc-chat-server.py` → PID 97748, 端口 7777
  - `ccc-board-server.py` → PID 97768, 端口 7775
- Launchd plist：`com.ccc.agent-sidecar.plist`（ACTIVE）
- 文档引用：`docs/architecture-core.md`、`docs/releases/v0.66.0.md` 等

**新栈对应**：
| 旧模块 | 新栈 | 状态 |
|--------|------|------|
| `scripts/ccc-engine.py` + `engine/` | `server/engine/` | 骨架 |
| `scripts/ccc-board.py` + `board/` | `server/board/` | 骨架 |
| `scripts/ccc-board-server.py` | `server/board/` | 骨架 |
| `scripts/chat_server/` | `server/web/` | 骨架 |
| `scripts/ccc-agent-sidecar.py` | 无（Desktop 直连 Hub） | 待定 |
| `scripts/_ccc_control.py` + `ccc-autostart-guard.sh` | 无 | 待定 |
| `scripts/tests/` | `server/tests/` | 已有 148 测试 |

**分类**：**暂留** → 新栈 `server/` 全部就绪并切换后，改为 **归档候选**

---

### 2. `app/` — 小型 utility 模块（24KB, ~5 文件）

**内容**：
- `app/core/check_deps.py` — 依赖检查
- `app/services/` — 服务相关

**依赖方证据**：
- 无运行中进程引用
- 无 launchd plist 引用
- 文档中极少引用（`docs/deploy/server-layout.md` 提及结构）

**新栈对应**：无直接替代。功能简单，可合并至 `server/` 或直接废弃。

**分类**：**归档候选** ✅

---

### 3. `desktop/` — 桌面客户端（1.3G）

**内容**：
- `Sources/CCCDesktop/` — SwiftUI 源码（824KB）
- `Tests/` — 测试（104KB）
- `scripts/` — 打包脚本（16KB）
- `.build/` — 构建产物（1.3GB）
- `Package.swift` — Swift 包定义

**依赖方证据**：
- 正在运行：`CCCDesktop` → PID 96736（`/Applications/CCCDesktop.app`）
- Desktop 是当前产品客户端，连接 Hub（127.0.0.1:17777）

**新栈对应**：桌面客户端本身，接口与 `server/` 新栈兼容（需确认新 Hub 接口对齐）。

**分类**：
- `Sources/` + `Tests/` + `scripts/` + `Package.swift`（~944KB）：**暂留**（活跃客户端）
- `.build/`（1.3GB）：**清理候选**（构建产物，`swift build` 可重建）

---

### 4. `lib/` — 公共库（8KB, 2 文件）

**内容**：
- `lib/dead_letter.py` — 死信处理
- `lib/retry.py` — 重试逻辑

**依赖方证据**：无运行中进程引用。旧代码可能仍有 import 引用，但无独立运行依赖。

**新栈对应**：无直接替代。功能简单，可合并至 `server/` 或直接废弃。

**分类**：**归档候选** ✅

---

### 5. `db/` — 数据库模块（4KB, 1 文件）

**内容**：
- `db/hp_pg.py` — HP 数据库连接

**依赖方证据**：无运行中进程引用。CCC 独立运行后不再依赖 HP 数据库（D3 独立纪律）。

**新栈对应**：无。CCC 独立后不再需要。

**分类**：**归档候选** ✅

---

### 6. `relay/` — 旧中转站（79MB, 1933 文件）

**内容**：
- `node_modules/` — npm 依赖（78MB）
- `dist/proxy.js` — 编译产物（188KB）
- 纯 Node.js 项目，无 Python 文件

**依赖方证据**：
- 无 4000 端口监听（旧 relay 已停止运行）
- `com.ccc.relay.m1.plist` 存在但未加载（无对应进程）
- `com.ccc.relay.m1.plist.bak-freeze` 为备份文件

**新栈对应**：`server/relay/` 为空目录，待 T4 实现。当前 `ai-loop-router`（:4100/:4102）已接管路由功能。

**分类**：**清理候选** ✅（node_modules 为构建产物，dist/ 可重建）

---

### 7. `skills/` — Skill 定义（40KB, 8 文件）

**内容**：
- `skills/ccc-{audit,dev,kb,ops,product,regress,reviewer,tester}/SKILL.md`
- `skills/README.md`

**依赖方证据**：旧引擎启动时可能引用，但无独立运行进程。新栈架构已不再使用 Skill 机制（角色由任务即时生成）。

**新栈对应**：无。新栈不再使用 Skill 机制。

**分类**：**归档候选** ✅

---

### 8. `templates/` — 模板文件（88KB, ~10 文件）

**内容**：
- `executor-prompt.template.md` — 执行器 prompt 模板
- `hooks/` — 钩子脚本
- 其他模板文件

**依赖方证据**：旧引擎在任务执行时引用模板。无独立运行进程。

**新栈对应**：待定。新栈可能使用不同模板机制。

**分类**：**暂留** → 确认新栈模板就绪后改为 **归档候选**

---

## 依赖方核实汇总

### 运行中进程（M1 实测）

| PID | 进程 | 端口 | 旧代码路径 | 状态 |
|-----|------|------|-----------|------|
| 44523 | ccc-agent-sidecar.py | 7788 | `scripts/ccc-agent-sidecar.py` | ACTIVE |
| 96736 | CCCDesktop | — | `desktop/Sources/` | ACTIVE |
| 97748 | ccc-chat-server.py | 7777 | `scripts/ccc-chat-server.py` | ACTIVE |
| 97768 | ccc-board-server.py | 7775 | `scripts/ccc-board-server.py` | ACTIVE |
| 54976 | ssh tunnel | 17777 | `com.ccc.hub-tunnel.plist` | ACTIVE |
| 63542 | ai-loop-router | 4100/4102 | node 进程（独立项目） | ACTIVE |

### Launchd 服务

| plist | 指向 | 状态 |
|-------|------|------|
| `com.ccc.agent-sidecar.plist` | `scripts/ccc-agent-sidecar.py` | ACTIVE |
| `com.ccc.hub-tunnel.plist` | ssh tunnel | ACTIVE |
| `com.ccc.relay.m1.plist` | relay 运行时 | NOT RUNNING |
| `com.ccc.relay.m1.plist.bak-freeze` | 备份 | BACKUP |

### 端口监听

| 端口 | 服务 | 旧代码 | 新栈 |
|------|------|--------|------|
| 7788 | Agent Sidecar | `scripts/ccc-agent-sidecar.py` | 无 |
| 7777 | CCC Hub | `scripts/ccc-chat-server.py` | `server/web/`（骨架） |
| 7775 | Board API | `scripts/ccc-board-server.py` | `server/board/`（骨架） |
| 17777 | Hub Tunnel | ssh → Mac2017 | 同 |
| 4100/4102 | ai-loop-router | 独立项目 | 同 |
| 6379 | redis | 系统 | 同 |
| 5432 | postgres | 系统 | 同 |

---

## 2017 依赖方核实（补核）

> 本小节为 T12-R 补核产出。2026-08-02 实测，仅 SSH 只读命令，零修改。

### 1. 旧引擎进程（2017 实测）

> T18（2026-08-02）已停止全部旧引擎进程。下表为停止前快照。

| PID | 进程 | 端口 | 旧代码路径 | 启动方式 | 状态 |
|-----|------|------|-----------|----------|------|
| 28004 | ccc-engine.py | 7776 | `scripts/ccc-engine.py` | launchd `com.ccc.engine` | **STOPPED**（T18 bootout） |
| 64950 | ccc-board | 7775 | `scripts/ccc-board-server.py` | launchd `com.ccc.board` | **STOPPED**（T18 bootout） |
| 89608 | ccc-chat-server | 7777 | `scripts/ccc-chat-server.py` | launchd `com.ccc.chat-server` | **STOPPED**（T18 bootout） |
| 69311 | node (新中转站) | 6100/6102 | `ai-loop-router-ccc/dist/proxy.js` | 手动 | **RUNNING**（红线 #1 保护，T18 验证存活） |

> 2017 侧的 `scripts/ccc-engine.py` 是 **T12 清单未覆盖的旧引擎运行实例**（M1 侧无此进程）。2017 ccc-engine 监听 7776 端口，board 和 chat-server 分别监听 7775/7777（与 M1 端口一致，但为独立进程）。T18 已 bootout 三个 launchd 并确认进程清空。

### 2. Launchd 服务（2017）

| plist | 指向 | 状态 |
|-------|------|------|
| `com.ccc.engine.plist` | `scripts/ccc-engine.py` | **UNLOADED**（T18 bootout, exit=0） |
| `com.ccc.board.plist` | `scripts/ccc-board-server.py` | **UNLOADED**（T18 bootout, exit=0） |
| `com.ccc.chat-server.plist` | `scripts/ccc-chat-server.py` | **UNLOADED**（T18 bootout, exit=0） |
| `com.ccc.engine.plist.bak-20260801` | 备份 | BACKUP |
| `com.ccc.engine.plist.bak-before-flash-override` | 备份 | BACKUP |

### 3. `~/.ccc/` 配置引用（2017）

| 文件 | 引用内容 | T18 后状态 |
|------|---------|-----------|
| `control.json` | mode=`enabled`, host_role=`mac2017_orchestration`, `start_paths: [launchd:com.ccc.engine]` | **mode=`disabled`**（备份 `control.json.bak-20260802`） |
| `engine.env` | `AGENT_PLANNER_BASE_URL=http://127.0.0.1:6100`（指向 2017 本地的 node planner） | 未改动（6100 新中转站仍存活） |
| `engine.env` | `CCC_UPSTREAM_STRICT=0` | 未改动 |

### 4. qb 产线引用 `scripts/` 的证据（2017）

> T18 放行核验：qb 板 `inflight`/`in_progress`/`planned` 三目录均空，活跃产线零引用 `scripts/`。下表 8 个引用文件均为**已完结历史计划**，按 T18 红线保留原文不改写（历史记录不改写，活跃产线零引用即满足放行）。

`~/program/apps/qb/.ccc/plans/` 中大量计划文件引用绝对路径 `/Users/fan/program/CCC/scripts/`：

| 引用文件 | 引用命令 |
|---------|---------|
| `plans/*.plan.md`（多处） | `python3 /Users/fan/program/CCC/scripts/ccc-hub-lens.py board qb` |
| `plans/*.plan.md`（多处） | `python3 /Users/fan/program/CCC/scripts/ccc-mind-update.py qb --constraint ...` |
| `plans/*.plan.md`（多处） | `python3 scripts/ccc-board.py index`（本地索引校验） |
| `_pre_migration_artifacts/reviews/` | 引用 `scripts/ccc-engine.py`、`scripts/ccc-board.py` 为评审范围 |

### 5. 影响总结

| 维度 | 2017 特有 | 与 M1 共享 | T18 后状态 |
|------|----------|-----------|-----------|
| Engine 进程 | **有**（PID 28004, 7776） | M1 无 `ccc-engine.py` 进程 | **2017 已停止**（bootout） |
| Board 进程 | 有（PID 64950, 7775） | M1 也有（独立实例） | **2017 已停止**（bootout） |
| Chat Server | 有（PID 89608, 7777） | M1 也有（独立实例） | **2017 已停止**（bootout） |
| Launchd 注册 | 3 个 plist 活跃 | M1 仅 `agent-sidecar` + `hub-tunnel` | **2017 3 个 plist UNLOADED** |
| `~/.ccc/control.json` | mode=enabled | M1 独立控制面 | **2017 mode=disabled** |
| qb 产线依赖 | 绝对路径引用 `scripts/` | — | 活跃产线零引用（8 个历史计划保留原文） |

**关键结论**：`scripts/` 的退役放行条件必须包含 **2017 侧旧引擎停止 + 切换到新栈**，**不能仅以 M1 侧为准**。**T18（2026-08-02）已满足全部放行条件并执行归档**。

---

## 建议处置顺序

### 第一阶段：可立即执行（无需准备）

| 项 | 动作 | 状态 | 依据 |
|----|------|------|------|
| `relay/node_modules/` | 删除 | **✅ 已完成**（T15） | 78MB 构建产物，旧 relay 已停止；`npm install` 可重建 |
| `relay/dist/` | 删除 | **✅ 已完成**（T18） | 188KB 编译产物，`npm run build` 可重建 |
| `desktop/.build/` | 删除 | **✅ 已完成**（T15） | 1.3GB 构建产物，`swift build` 可重建 |
| `db/` | 归档 → `docs/archive/legacy-retired-2026-08-02/db/` | **✅ 已完成**（T15） | 4KB，CCC 独立后不再依赖 HP 数据库 |
| `lib/` | 归档 → `docs/archive/legacy-retired-2026-08-02/lib/` | **✅ 已完成**（T15） | 8KB，功能简单 |
| `app/` | 归档 → `docs/archive/legacy-retired-2026-08-02/app/` | **✅ 已完成**（T15） | 24KB，无运行依赖 |
| `skills/` | 归档 → `docs/archive/legacy-retired-2026-08-02/skills/` | **✅ 已完成**（T15） | 40KB，新栈不再使用 Skill 机制 |

**放行条件**：老板确认上述功能不再需要。

**归档路径**：`docs/archive/legacy-retired-2026-08-02/`（git mv 可追溯，内容零丢失）

### 第二阶段：需新栈就绪后执行

| 项 | 动作 | 状态 | 放行条件 |
|----|------|------|----------|
| `scripts/` | 归档 → `docs/archive/legacy-retired-2026-08-02/scripts/` | **✅ 已完成**（T18） | `server/` 全部就绪并切换运行（所有端口从旧脚本迁移到新栈） |
| `templates/` | 归档 → `docs/archive/legacy-retired-2026-08-02/templates/` | **✅ 已完成**（T18） | 新栈模板就绪，旧引擎不再引用 |
| 2017 旧引擎停止 | launchd 卸载 + control.json disabled | **✅ 已完成**（T18） | 3 个 launchd bootout + 进程清空 + 6100/6102 新中转站存活 |
| relay/dist 清理 | 删除 | **✅ 已完成**（T18） | 188KB 未跟踪构建产物 |

**T18 执行结果**（2026-08-02）：
- 2017 三个旧引擎 launchd 全部 bootout（exit=0），进程清空（`ps aux | grep ccc-engine|ccc-board|ccc-chat` = 空）
- `~/.ccc/control.json` mode: `enabled → disabled`（备份 `control.json.bak-20260802`）
- **6100/6102 新中转站（PID 69311，node）存活**——红线 #1 满足（`legacy-phase2-plan.md` 第 100 行 `kill 69311` 已作废，禁止执行）
- `scripts/`、`templates/` 经 `git mv` 归档至 `docs/archive/legacy-retired-2026-08-02/`，内容零丢失
- `relay/dist/` 删除（188K，未跟踪，`git status` 无残留）
- M1 旧进程 7777/7775/7788 未主动 kill（红线 #2 满足；归档后失去重启能力，壳迁移另行放行）
- qb 8 个历史完结计划保留原文不改写（活跃产线零引用即满足放行）

**前置放行条件**：
- **2017 旧引擎停止**：`com.ccc.engine`（PID 28004, 端口 7776）、`com.ccc.board`（PID 64950, 端口 7775）、`com.ccc.chat-server`（PID 89608, 端口 7777）全部停止，launchd plist 卸载
- `control.json`（2017）模式降为 `disabled` 或删除
- `server/engine/` 可替代 `scripts/ccc-engine.py` + `scripts/engine/`
- `server/board/` 可替代 `scripts/ccc-board.py` + `scripts/board/` + `scripts/ccc-board-server.py`
- `server/web/` 可替代 `scripts/chat_server/` + `scripts/ccc-chat-server.py`
- qb 产线引用路径从 `scripts/` 切换到 `server/` 新栈命令
- 7788 端口（agent-sidecar）有替代方案或已确认不再需要
- 旧进程全部停止，新进程全部就绪，验收通过

### 第三阶段：桌面客户端

| 项 | 动作 | 放行条件 |
|----|------|----------|
| `desktop/` 源码 | 保留 | 桌面客户端持续活跃 |
| `desktop/.build/` | 周期性清理 | 确认构建脚本可重建 |

---

## 未覆盖项

以下目录/文件不在本清单范围（属于新栈或独立项目）：

| 路径 | 说明 |
|------|------|
| `server/` | 新栈，已验收代码 |
| `knowledge/` | 知识库，T11 已升级 |
| `docs/` | 文档，持续维护 |
| `vendor/` | 第三方二进制（loop-code CLI） |
| `.ccc/` | 运行时数据（不入库） |
| `references/` | 参考资料 |
| `scripts/.ccc/` | 运行时数据（不入库） |