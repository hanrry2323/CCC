# CCC 战略地图

> **按需阅读**：先读 [`VISION.md`](VISION.md)（叙事）+ 根目录 `STARTUP-BRIEF.md`；需要全景再读本文。  
> **当前版本**：以根目录 `VERSION` 为准（本文历史段落可能落后，冲突时以 VERSION / VISION / CHANGELOG 为准）。

---

## 0. CCC 是什么（现行口径）

**CCC = Connect–Claude Code = Loop Engineer**

| 层 | 组件 |
|----|------|
| 对话面 | **CCC Hub**（入口；已替代第三方 Agent IDE 编排壳） |
| 编排面 | Engine + Board（串行 Loop、验收、重试、进化） |
| 执行面 | 工具路由（Claude / OpenCode / …）+ Token 治理 |

**无穷角色**：任务 → 路由工具 → Skill + Prompt = 本次角色。  
`skills/ccc-*` 是**阶段默认能力包**，不是用户点选的角色菜单。

**看板**：待办 `backlog(epic)` 常驻；流转 `planned(work) → in_progress → testing → verified → released`（小卡不可跳列；大卡永不离开 backlog）

**不做**（红线）：

- agent 自主启用 CCC（须用户显式触发）  
- 把「固定角色超市」当产品形态  
- 自动合并飞轮候选到 red-lines（须人工 review）  

下文从 §1 起保留**范式演进史**与实现细节（含历史上的「7 角色」表述）；阅读时请用本节口径翻译：  
「7 角色」= Engine 的 **7 个默认阶段能力包（seed，可扩）**。机制 SSOT：[`product/role-formation.md`](product/role-formation.md)。

---

## 0.1 文档索引（现行）

| 文档 | 用途 |
|------|------|
| [`VISION.md`](VISION.md) | 产品叙事 SSOT |
| [`GETTING-STARTED.md`](GETTING-STARTED.md) | 安装与第一条闭环 |
| [`USAGE.md`](USAGE.md) | 三类用户 |
| [`CONTROL.md`](CONTROL.md) | 控制面 |
| [`ccc-hub-ports.md`](ccc-hub-ports.md) | Hub 端口 |

---

## 1. 范式演进史（v0.5 → v0.28.1+）

> 以下为史实归档。v0.42+ 产品入口以 Hub 为准（见 VISION）。

| 版本 | 范式 | 关键产出 |
|------|------|----------|
| v0.5–0.7 | 4 文件契约 + 3 角色流水线 | 13 红线、Plan→Exec→Verify |
| v0.8 | 切到 opencode CLI | 红线 X1/X2/X3（进程管理） |
| v0.9–0.11 | model provider + 飞轮 + 钩子 | loop/flash、install-ccc-scheduler |
| v0.12–0.15 | bug fix + 跨项目 + 真自动化 | ccc-auto-dev.sh（已移除）→ launcher |
| **v0.16** | **7 角色定时开发系统** | 任务看板 + 7 launchd plist（历史） |
| v0.17–0.19 | 战略地图 + 存储抽象 | FileBoardStore、OpenCodeExecutor |
| **v0.20.1** | **CCC Engine 串行执行** | 取消 7 角色定时（X6 废止） |
| v0.21–0.23 | 门控强化 + product 智能化 | LLM reviewer、audit 收纳 |
| **v0.24+** | **Phase 感知调度** | depends_on、失败传染、R- 红线 |
| v0.25–0.26 | 全链路对齐 + Board Protocol | 跨 IDE 看板契约 |
| **v0.28.0** | **流层加固 + backlog 自动消费** | F-1 product 自动拆分 |
| **v0.28.1** | **复杂度分流** | small 曾跳过审测 → **v0.53+ 取消 stub 跳过** |

---

## 2. 阶段能力包（Engine 串行驱动）

> **现行口径**：下表是 Engine 调度的**默认阶段能力包**（Skill+Prompt），不是给用户点选的角色菜单。见 [`VISION.md`](VISION.md)。  
> **v0.20.1 起**：以下「历史频率」列仅作 v0.20.0 及之前存档；Engine 模式下无定时，有 task 即执行。

### 2.1 阶段矩阵

> **v0.28.1 复杂度分流**：task `complexity` 字段（small/medium/large）影响 reviewer/tester 是否跳过。
> small → 跳过 reviewer+tester 直通 kb；medium/large → 走完整阶段包。详见 `references/board-task-schema.md` §12。

| 阶段 | 历史频率 (v0.20.0) | Engine 调度 | 扫哪列 | 处理后挪到 | 入口 | 复杂度影响 |
|------|-------------------|-------------|--------|------------|------|-----------|
| **product** | 4h | pending epic → Claude 扇出 work×N（v0.42.2） | backlog(epic) | **创建** planned(work)；patch epic | `ccc-board.py product` / Engine | 赋 color_group |
| **dev** | 10min | Engine 自动（仅 work） | planned + in_progress | in_progress → testing | `ccc-engine.py dev_role_*()` | 不变 |
| **reviewer** | 2h | dev 完成后立即 | testing | testing → verified | `ccc-engine.py → reviewer_role()` | small=跳过 |
| **tester** | 4h | dev 完成后立即 | testing | testing → verified | `ccc-engine.py → tester_role()` | small=跳过 |
| **ops** | 30min | 手动/可选（空闲不默认重扫） | 所有列 | — | `ccc-board.py ops` | 不变 |
| **kb** | 每天 23:00 | **verified 列非空即跑**（v0.38 `_run_verified_kb_gate`） | verified | verified → released | `ccc-engine.py → kb_role()` | small 也调 |
| **regress** | 每天 23:30 | 独立定时或 Engine 空闲 | released | released → backlog | `ccc-board.py regress` | 不变 |

**引擎约束**：有 task 即串行执行全链路；真·空闲（无列任务）只写 heartbeat，默认不 auto-replenish/evolve（v0.37+）。

### 2.2 看板流转图

```
┌─────────────────┐  Claude 扇出   ┌──────────┐   ┌──────────────┐
│ backlog (epic)  │ ─────────────→ │ planned  │ → │ in_progress  │
│ 大卡常驻不离开   │  work×N        │ (work)   │   │   (work)     │
└─────────────────┘                └──────────┘   └──────────────┘
  Hub 定稿 / 回归                              ↓
                                         ┌──────────────┐
                                         │   testing     │
                                         └──────────────┘
                                            ↓        ↑
                                        reviewer    tester
                                            ↓        ↓
                                         verified → kb → released
                                                         ↓
                              全部子卡 released → epic done 沉底
```

### 2.3 Engine + board-server 装上后

```bash
$ launchctl list | grep com.ccc
com.ccc.engine          # KeepAlive，ccc-engine.py 主循环
com.ccc.board-server    # 看板 HTTP 服务
# 旧 7 角色 plist 已废弃；--upgrade 会卸载
```

安装：
```bash
bash ~/program/CCC/scripts/install-ccc-roles.sh
# 从旧 7 plist 迁移：
bash ~/program/CCC/scripts/install-ccc-roles.sh --upgrade
```

---

## 3. 任务看板 `.ccc/board/`

6 列目录：
```
.ccc/board/
├── backlog/         # epic 大卡队列（常驻）
├── planned/         # work 小卡（各带 plan+phases）
├── in_progress/     # work：dev 在写
├── testing/         # work：等 reviewer/tester
├── verified/        # 双检查通过
├── released/        # kb 归档 + tag
├── abnormal/        # work quarantine
├── index.json       # 状态总览
└── README.md        # 流转规则
```

**单 task JSONL 格式**（schema 1.2+；时间戳用 `+08:00`）：
```json
{"id":"my-epic","title":"...","status":"backlog","card_kind":"epic",
 "split_status":"pending","complexity":"medium","schema_version":"1.2",
 "created_at":"2026-07-12T15:00:00+08:00","updated_at":"..."}
```

**操作命令**：
```bash
python3 ~/program/CCC/scripts/ccc-board.py index
python3 ~/program/CCC/scripts/ccc-board.py product --promote
python3 ~/program/CCC/scripts/ccc-board.py dev
bash ~/program/CCC/scripts/install-ccc-roles.sh [--upgrade]
```

---

## 4. 完整调用链（v0.28.1）

```
老板 (你)
  ↓ "按 CCC 跑 X" 或 create_task 落 backlog
.ccc/board/backlog/<task>.jsonl
  ↓ Engine Step 1.5 (v0.28 F-1): backlog 非空 → product_role
  写 .ccc/plans/<task>.plan.md + .ccc/phases/<task>.phases.json
  挪 task → planned/
  ↓ Engine: planned 有 task → dev_role_launch
  读 phases.json → phase 边界调度 → opencode run --model loop/flash
  opencode 写代码 + 写 report
  挪 task → in_progress/ → testing/
  ↓ Engine: dev 完成 → reviewer_role + tester_role（small 跳过）
  LLM 审查 + pytest + plan 验收清单
  通过则挪 task → verified/
  ↓ Engine: verified → kb_role
  git tag board-<task> + git push
  挪 task → released/
  ↓ regress (23:30 或 Engine 空闲)
  从 released 取任务，每日回测
  发现回归 bug → 建 bug task → 挪到 backlog/
```

---

## 5. 红线（永久约束）

| # | 红线 | 短句 |
|---|------|------|
| 1 | 不动系统文件 | /etc、~/.env、密钥 |
| 2 | 验收可执行 | 自然语言 + 命令 |
| 3 | 不超出 plan 文件范围 | 白名单 |
| 4 | 单 phase 单 commit | 兜底脚本做 |
| 5 | phases.json 必写全 | JSONL，不嵌套 |
| 6 | 角色不互串 | 边界硬性 |
| 7 | 启动顺序固定 | 读 profile 第一 |
| 8 | 每步必 commit | 不攒 |
| 9 | Executor 卡死立即止损 | kill + 接管 |
| 10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| 11 | Verifier 必写 verdict 文件 | 口头 PASS 不算 |
| 12 | 禁止 agent 自主启用 CCC | 老板显式触发 |
| X1 | OpenCode 进程池 ≤ 3 | M1 8GB 内存敏感 |
| X2 | 每 phase 必杀 opencode | finally + watchdog |
| X3 | OpenCode 启动前必跑残留 watchdog | launcher Step 1 |
| **X4** | **每 phase 必走看板流转** | 跨角色不可跳列 |
| **X5** | **Engine + board-server plist 必装** | install-ccc-roles.sh |
| **X6** | **角色频率（v0.20.1 起不再适用）** | 保留历史索引 |
| R-12 | medium/large fallback 强制 quarantine | 禁止 py_compile 静默 verified |

完整版：`references/red-lines.md`

---

## 6. 自动化 / 定时 / 钩子全表

| 能力 | 实现 | 工件 |
|------|------|------|
| 单 phase 启动 | `scripts/ccc-exec-launcher.sh` | watchdog → pre-exec → exec → on-error → post-exec |
| 多 phase 队列 | `scripts/ccc-queue.sh` | 3 次失败升级 L3 |
| **Engine 串行** | launchd `com.ccc.engine` | KeepAlive，ccc-engine.py |
| **看板 HTTP** | launchd `com.ccc.board-server` | GET/POST + token 认证 |
| 进程池 | `scripts/opencode-pool.py` | Semaphore(3) |
| 必杀 | `scripts/opencode-watchdog.sh` | killpg + pkill -f 兜底 |
| 钩子 | `~/.ccc/hooks/{pre-exec,post-exec,on-error}.sh` | 模板在 `templates/hooks/` |
| 通知 | `scripts/ccc-notify.sh` | L1/L2/L3 桌面通知 |
| **看板流转** | `scripts/ccc-board.py` | 阶段能力调度 + 看板 |
| **自动 commit+push** | `templates/hooks/post-exec.sh` | CCC_PUSH=1 默认 |
| regress 定时 | 23:30 或 Engine 空闲 | `ccc-board.py regress` |

> **已移除**：`ccc-auto-dev.sh`、`ccc-precheck.sh`、`ccc-finish.sh`（v0.7-slim 后不再使用）

---

## 7. 模型路由

```bash
opencode run --model loop/flash "<msg>"     # 唯一允许
```

**禁止**：省略 `--model`、裸 provider 名、硬编码 claude-/gpt-/minimax-* 等。

**注意**：opencode 1.17+ 命令是 `run` 不是 `exec`（Lesson 32+33）。
长 prompt 走 `--file` 附件（v0.11 修）。

---

## 8. 沉淀教训

**关键教训**（任何 agent 必读）：
- **Lesson 27**：`claude -p` 是 print 模式，prompt 走 stdin
- **Lesson 28**：口头 PASS ≠ 真 PASS，Verifier 必写 verdict 文件
- **Lesson 32**：opencode 模型名必须带 provider 前缀（loop/flash）
- **Lesson 33**：opencode run positionals 截断 200 字符，长 prompt 走 --file
- **Lesson 36**：bug 分类（数据泄漏 / 静默失败 / 配置硬编码）
- **Lesson 39**：Engine 每次 move_task 后必须 update_index

---

## 9. 怎么用本文件

| 你是 | 读 | 然后 |
|------|----|------|
| 新 cloud agent 启动 | `STARTUP-BRIEF.md` | 按需读本文件 / grep red-lines / lessons |
| 老板（你）| 决策点 | 说"按 CCC 跑 X" |
| 任何 agent 调红线条目 | `references/red-lines.md` | 12 + R- + X- 全表 |

---

## 10. 当前状态（v0.28.1）

- ✅ Engine 串行 + phase 感知 + 失败传染
- ✅ backlog 自动消费（F-1）
- ✅ complexity 分流（small 跳过 reviewer+tester）
- ✅ Board Protocol + 跨 IDE 契约
- 🔜 dev worktree 隔离（roadmap v0.27+）

---

**最后更新**: 2026-07-12 v0.28.1
**维护者**: 任何 agent 改完后追加 changelog
**优先级**: 全景参考（启动首选 STARTUP-BRIEF.md）
