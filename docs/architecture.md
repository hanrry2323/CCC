# CCC — 框架说明书

> 本文件解释 CCC v0.70.0 的架构（2026-08-02 重构定稿）。面向维护者，agent 不读本文件。  
> 权威链：[`INDEX.md`](INDEX.md) §0（重构决策定稿 + 契约 v1 最高优先级）。

---

## 一句话定义

**CCC = Loop Engineer**（人定意图，系统自动编排与自主执行）。  
终态架构：**任意设备壳**（HTTP 直连）+ **2017 单端 :7788**（薄驱动 Engine + 文档流转 + 看板/HTTP）+ **执行体**（Claude Code / OpenCode，经注册表派发；模型档 flash vs code）。

任务卡文档 = 唯一事实源；Engine 只做编排不执行；任意设备壳经 HTTP 直连 2017。

---

## 概念模型（v0.70.0 重构定稿）

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
薄驱动 Engine（server/engine/main.py，launchd 常驻）
  ├─ 读取 config/executors.json（契约 §7 注册表）
  ├─ 派发：可后台 CLI → 自动拉起 / 手动 GUI → 挂起等人
  ├─ 收单：按退出码 + 输出判定 → 状态机流转
  └─ 状态更新写入看板接口（store.py）
  │
  ▼
看板服务端（server/board/，launchd 常驻）
  ├─ loader.py：从 docs/dispatch/*.md 解析任务卡 → BoardItem
  ├─ queries.py：实时/7天/项目分类三视图 + 线路图聚合
  └─ export.py：导出 web/data/board.js（零 API 模式）

中转站（server/relay/）
  ├─ 6100 = Anthropic 出口（大脑 Agent Claude Code CLI 走此）
  └─ 6102 = Relay flash/code 上游路由（中转站）
```

---

## 物理形态

```
~/program/CCC/                                  # 本目录（唯一交付物）
├── SKILL.md                                    # ★ 注入 prompt 总纲
├── README.md
├── CLAUDE.md                                   # 平台开发硬规则 + 开发命令
├── STARTUP-BRIEF.md                            # 启动摘要（按终态重写）
├── CHANGELOG.md
├── VERSION                                     # ★ 版本 SSOT (v0.70.0)
├── LICENSE
├── pyproject.toml                              # ruff + pytest 配置（覆盖 server/）
├── .pre-commit-config.yaml                     # 本地 hook
├── .github/workflows/ci.yml                    # CI
│
├── references/                                 # 红线/SOP/契约
│   ├── red-lines.md                            # 红线（18 + X8 + R7）
│   └── board-task-schema.md                    # 任务卡文档契约
│
├── docs/
│   ├── INDEX.md                                # ★ 文档索引 SSOT（§0 重构决策 + 契约 v1）
│   ├── architecture.md                         # 本文件
│   ├── roadmap.md                              # 路线图（当前方向 + 历史归档）
│   ├── VISION.md                               # 叙事
│   ├── STRATEGY-MAP.md                         # 全景演进史
│   ├── dispatch/                               # ★ 任务卡文档（唯一事实源）
│   │   └── <prefix><NNN>-*.md                  #   <prefix>NNN 任务卡（docs/dispatch/<prefix>/）
│   ├── archive/                                # 历史归档（旧 scripts/ 等已迁入）
│   └── ...                                     # 其余专题文档
│
├── server/                                     # ★ 新栈（2026-08-02 重构定稿）
│   ├── README.md                               # 新栈总览
│   ├── engine/                                 # 薄驱动核心
│   │   ├── main.py                             #   入口：--config / --once / 持续模式
│   │   ├── dispatch.py                         #   注册表读取 + decide() 派发决策
│   │   ├── scheduler.py                        #   只读巡检
│   │   ├── store.py                            #   看板接口 + 内存实现
│   │   ├── task.py                             #   Work 数据结构 + 状态机
│   │   └── cluster.py                          #   集群探针
│   ├── board/                                  # 看板服务端
│   │   ├── loader.py                           #   从任务卡解析 → BoardItem
│   │   ├── queries.py                          #   三视图 + 线路图聚合
│   │   ├── export.py                           #   导出 web/data/board.js
│   │   ├── models.py                           #   视图字段 + 状态常量
│   │   └── scheduler.py                        #   只读巡检 + 导出（launchd 常驻）
│   ├── web/                                    # HTTP API + 静态页
│   │   ├── server.py                           #   HTTP 服务端（:7788）
│   │   ├── brain.py                            #   大脑 Agent 代理（调 Claude Code via 6100）
│   │   └── css/                                #   静态页样式
│   ├── relay/                                  # 中转站（模型出口路由）
│   ├── kb/                                     # 知识库（MCP + BM25 本地检索）
│   ├── config/                                 # 配置系统
│   │   ├── loader.py                           #   env 加载器
│   │   ├── config.example.env                  #   运行参数占位
│   │   └── executors.example.json              #   执行体注册表（契约 §7）
│   ├── deploy/                                 # 进程编排
│   │   ├── com.ccc.web-server.plist            #   launchd plist × 3
│   │   ├── com.ccc.engine.plist
│   │   ├── com.ccc.board-scheduler.plist
│   │   └── run.example.sh / health.example.sh
│   └── tests/                                  # 测试（冒烟 + 单元 + HTTP API）
│
├── desktop/                                    # Desktop 壳（SwiftUI，任意设备壳之一）
│   ├── Sources/CCCDesktop/                     #   Swift 源码
│   └── Package.swift                           #   Swift Package
│
├── templates/                                  # plan/phases/report/verdict/AGENTS 模板
│
└── docs/archive/legacy-retired-2026-08-02/     # 旧栈归档（scripts/ 等，已退役）
    └── scripts/                                #   旧 scripts/*.py（勿引用）
```

---

## 终态架构（v0.70.0）

```
┌─────────────────────────────────────────────────────────┐
│  L3: 任意设备壳（Desktop / 网页 / 手机）                  │
│  desktop/ · HTTP 直连 2017:7788                          │
│  产意图 → 写任务卡 docs/dispatch/ · 监控看板状态          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP（账号密码 + token）
┌────────────────────────▼────────────────────────────────┐
│  L2: 2017 单端 :7788（server/web/server.py）             │
│  ┌────────────────────┐  ┌─────────────────────────────┐ │
│  │ /conversation      │  │ /board/* /ops/summary       │ │
│  │ → brain.py         │  │ → board/queries + export    │ │
│  │   (Claude Code     │  │                             │ │
│  │    via 6100)       │  │ /session → 账号密码换 token │ │
│  └─────────┬──────────┘  └─────────────┬─────────────┘ │
│            │                             │               │
│  ┌─────────▼─────────────────────────────▼─────────────┐ │
│  │  engine/main.py（薄驱动，launchd 常驻）             │ │
│  │  + dispatch.py（注册表派发）                        │ │
│  │  + store.py（看板接口）                             │ │
│  │  + task.py（状态机：待分派→执行中→已回写→已关闭）   │ │
│  └─────────┬───────────────────────────────────────────┘ │
│            │                                              │
│  ┌─────────▼──────────────────────────────────────────┐  │
│  │  board/loader.py（任务卡 → BoardItem）              │  │
│  │  board/scheduler.py（只读巡检 + 导出，launchd 常驻）│  │
│  │  config/loader.py + executors.json（契约 §7）       │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ subprocess（按注册表配置）
┌────────────────────────▼────────────────────────────────┐
│  L1: 执行体（经注册表派发）                               │
│  Claude Code CLI（flash/6100）与 OpenCode（code/6102）并列可后台 CLI │
│  注册表分类：可后台 CLI → 自动拉起 / 手动 GUI → 挂起等人  │
└──────────────────────────────────────────────────────────┘
```

### 核心优势

- **任务卡 = 唯一事实源**：`docs/dispatch/*.md` 是任务流转的根；看板数据从任务卡解析派生，不另建数据源。
- **Engine 只编排不执行**：工具名只存在于注册表配置；代码不硬编码工具名/端口/路径。
- **配置集中**：所有参数从 `config.env` 读取，不在代码中硬编码。
- **任意设备壳**：Desktop / 网页 / 手机经 HTTP 直连 2017；壳不写业务逻辑。
- **大脑 Agent**：对话口接 2017 Claude Code（带心智/工具/知识库），非裸模型直答。

---

## 任务卡状态机（契约 §2 五态）

```
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回（附问题清单）→ 待分派（人工重派）
```

- **任务卡文档 = 唯一事实源**：`docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md`，元数据行含 `状态：X` / `执行体：Y` / `日期：Z`。
- **非法状态转移** 一律抛 `IllegalTransitionError`。
- 无旧看板状态机（planned/verified/released）残留。

任务卡文档契约见 `references/board-task-schema.md`。

---

## 执行体注册表（契约 §7）

`server/config/executors.json` 六角色，分类只允许「可后台 CLI」/「手动 GUI」：

| 角色语义 | 分类 | 当前绑定 |
|----------|------|----------|
| 开发 / 写码 | 可后台 CLI | OpenCode（2026-08-15 F5 定：开发仅 OpenCode） |
| 维护 | 可后台 CLI | OpenCode |
| 管理席 | — | Codex |
| 验收 / 机审 | 可后台 CLI | Claude Code / OpenCode |
| 只读取证 / 审计 | — | DSH headless（人工触发，不参与 AUTO 派发） |

派发规则：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人；未知角色 → 不派发。

---

## 与 QXO 的关系

CCC 和 QXO **独立发展，不互相依赖**。两者的互通通过文件格式共享契约实现：
- `references/board-task-schema.md` 定义了任务卡文档的标准格式
- QXO 可按此格式往 `docs/dispatch/` 写入任务卡
- CCC 产出的 report / verdict 也可被 QXO 读取

CCC 做"极简的 Prompt 资产"；QXO 做"可扩展的 AI 中台"。各自专注。

---

## 工程质量闭环

### 双门禁验收

reviewer + tester 同时扫「执行中」列：
1. **reviewer（静态门禁）**: py_compile + git diff 范围核对 → 通过则「已回写」
2. **tester（动态门禁）**: pytest + 验收清单 → 通过则「已回写」

两者任一通过即算「已回写」（多冗余通道）。

---

## 红线

完整见 `references/red-lines.md`。CCC v0.70.0 红线集：
- 18 条编号红线（核心安全/契约/边界）
- X 系列 8 条（扩展场景：成本/可观测性/契约校验）
- R 系列 7 条（回归红线）

---

## 维护者清单

新改 CCC 时检查：

- [ ] 改了 `references/red-lines.md` → 同步加 Lesson
- [ ] 改了 `server/engine/` → 跑 `pytest server/tests/test_engine_*.py`
- [ ] 改了 `server/board/` → 跑 `pytest server/tests/test_board_*.py`
- [ ] 改了 `server/web/` → 跑 `pytest server/tests/test_http_api.py`
- [ ] 改了配置层 (`server/config/`) → 跑 `pytest server/tests/test_skeleton.py`
- [ ] 改了版本号 → `VERSION` + `CHANGELOG.md` 同步
- [ ] `pytest server/tests/ -q` 全绿
- [ ] `ruff check server/` 零告警（新代码）

---

## 相关文件

- `SKILL.md` — 注入 prompt（总纲）
- `CLAUDE.md` — 平台开发硬规则 + 开发命令
- `STARTUP-BRIEF.md` — 启动摘要（按终态重写）
- `docs/INDEX.md` — 文档索引 SSOT（§0 重构决策 + 契约 v1）
- `references/red-lines.md` — 红线细则
- `references/board-task-schema.md` — 任务卡文档契约
- `docs/roadmap.md` — 发展路线图（当前方向 + 历史归档）
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
