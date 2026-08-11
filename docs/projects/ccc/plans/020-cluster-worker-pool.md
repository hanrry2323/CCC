# 方案 · 集群 Worker 池（Cluster Worker Pool）蓝图

> 项目：ccc · 编号：ccc-plan-020 · 状态：A 轨四项 + 收尾全部完成（平台根治落地）；252 实跑挂账等网络 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-11
> 关联卡：clw019（跨节点路由实证，已回写）
> 关联方案：011-loop-observer-architecture（巡查）、014-delivery-gate-sop（交付）、007-100卡基线、021-sidecar-lifecycle-contract

## 目标

把 CCC 从「2017 单机执行」升级为「**集群 Worker 池**」：任意终端（装 OpenCode/Claude Code）注册为 Worker 后即可认领卡片开发、担任定时运维（diff 审查/红线巡查），通过中转站多通道接入不同模型，横向扩展集群算力，突破 2017 单机并发瓶颈。

## 背景

### 现状瓶颈（实测）
- 2017 单机一个工具实例，5 卡并发已达性能极限（探查 A：ccc058 执行体打转计数）
- 一台电脑只能装一个 OpenCode/Claude Code 实例，并发受单机算力上限
- Worker 标签体系已落地 v1（ccc-plan-020 前身：`executors.json` 加 worker_id，卡头执行体支持 W 号）——寻址底座已通

### 突破点（老板洞察，2026-08-10）
1. 任意终端注册 = Worker（装工具即插即用）
2. Worker 认领卡片开发（**绑定任务**：开发/验收）
3. Worker 担任定时运维（**非绑定任务**：diff 审查/红线巡查/巡检）
4. 中转站多通道 = 不同 Worker 用不同模型（6100/6102/闪客/官方直连）
5. 集群算力最大化（2017 满 5 卡 + 252 带 3 进程 + 未来更多节点横向扩展）

## 蓝图架构

```
                    ┌─────────────────────────────────────┐
                    │         中转站（2017 :6100/:6102）     │
                    │   多通道：flash / code / pro / 直连     │
                    └──────┬──────────┬──────────┬─────────┘
                           │          │          │
                    注册 Worker   注册 Worker   注册 Worker
                           ▼          ▼          ▼
                    ┌─────────┐ ┌─────────┐ ┌─────────┐
                    │ W4 OpenCode│ │ W9 Claude(252)│ │ Wn 未来节点│
                    │ 2017     │ │ 移动终端   │ │ ...     │
                    └─────────┘ └─────────┘ └─────────┘
                      开发/验收      开发+巡检      待接入
```

### 核心机制

**1. 注册即接入（Worker 池）**
- 终端装 OpenCode/Claude Code → 配 GitHub 只读 key → clone qx-map + CCC → 在 workers.md 登记一行（W 号 + 位置/能力/定位）→ **立即可被 CCC 派发**
- 任务卡执行体字段写 W 号（已支持），Engine 按 W 查 executors 绑定实例

**2. 绑定任务（卡片开发）**
- Worker 认领卡片：开发执行体 / 验收席，走既有卡流程（出卡→派发→回写→机审→合入）
- 任务卡上留 W 号 = 追溯（谁干了什么可查）

**3. 非绑定任务（定时运维）**
- Worker 可被指定担任定时巡查：diff 审查 / 红线巡查 / 巡检 / 性能监控
- 复用 Loop Observer 框架（ccc-plan-011），Worker 作为 observer 的执行宿主
- 定时触发：launchd 或 scheduler 注册

**4. 多通道模型路由**
- 中转站多通道：不同 Worker 可配置不同模型档位（开发用 code、巡检用 flash、高判断用 pro）
- 通过 `executors.json` 的模型字段 / 中转站路由规则实现

### 机制 v2（2026-08-10 老板洞察 · 核心升级）

**5. 任务卡定义角色（通用智能体 → 按任务变专家）**

> 借鉴 Workbuddy 专家团，但更高效：Workbuddy 把一个 Agent 固定为某专家；我们让**通用智能体根据任务卡成为某专家**，任务完成回到通用状态。

```
通用 Worker（W4/W9...）
   │  任务卡「角色：巡检专家」→ 注入对应 skills+MCP
   ▼
专家 Worker（本次=巡检专家）
   │  完成 → 回到通用状态
   ▼
通用 Worker（可接下一任务，再变另一专家）
```

- **三层注入**：
  - ① 通用心智（qx-map 集群全貌/身份/红线）——所有 Worker 都要有
  - ② 专用技能（skills+MCP）——按「角色」加载
  - ③ 任务角色（任务卡「角色」字段决定本次当什么专家）——注入点
- **落地**：任务卡头加「角色」字段（如 `角色：开发专家/审查专家/巡检专家`），Engine 派发时按角色注入对应 skills+MCP 到执行提示，Worker 完成后回到通用状态。
- **落地状态（2026-08-11）**：任务卡「角色」字段已实现（new-card.sh --role），role-skills.yaml 映射已建，prompt_inject 注入生效（clw019 实证）。**2017 已对接 qx-map 心智**（对照 252 标准化接入：clone qx-map + 全局 CLAUDE.md 加集群资源指针）。

**6. Engine 调度：轮询 → 事件监听（写卡即响应）**

> 现状 Engine 是 pull（每 N 秒轮询 dispatch 目录）。集群化后 M1 写卡要能即时调动集群 Worker，改事件驱动。

```
现状（pull）: Engine 每 N 秒扫 dispatch → 发现待分派 → 派发（有延迟，浪费轮询）
目标（push）: M1 写卡 → dispatch 目录变化 → Engine 即时感知 → 按卡路由到空闲 Worker
```

- **改动**：dispatch 目录文件监听（watchdog）替代 N 秒轮询，M1 一写卡 Engine 立即响应
- **Worker 绑定**：每张卡指定 W 号（已支持），Engine 按 W 路由——Worker 池越大，Engine 越像调度器
- **按卡调度**：Engine 只负责「把卡给对的 Worker + 收割结果」，Worker 自主完成任务

### 关键设计原则
1. **标签 = 寻址底座**（已落地）：派发认 W 号，不认机器名
2. **注册即放心用**（老板定调）：登记 = 可派发，不限制能力
3. **绑定 + 非绑定双轨**：卡片任务与定时运维并行
4. **节点即插即用**：新终端 5 分钟接入，Engine 零改动
5. **回溯追溯**：卡上留 W 号，谁干的查得到

## 验证计划（用 252 实测）

### 场景（蓝图可行性验证，每项给结论）
| # | 验证点 | 方法 | 预期 |
|---|--------|------|------|
| 1 | 252 注册 Worker | SSH 配置 252（装 claude + clone qx-map/CCC） | W9 登记成功 |
| 2 | 252 认领开发卡 | 出卡 `执行体：W9`，Engine 派发到 252 | 252 Claude 认领开发 |
| 3 | 252 担任巡检 | 252 定时跑 observer/diff 审查 | 巡检报告落盘 |
| 4 | 多通道模型 | 252 走不同中转站通道 | 模型档位可配 |
| 5 | 集群并发扩展 | 2017+252 同时执行不同卡 | 并发总量上升 |

### 第一轮验证结果（2026-08-10 实测）

| 验证点 | 结果 | 证据 | 问题点 |
|--------|------|------|--------|
| **1a. 252 接入 GitHub** | ✅ 通过 | CCC + qx-map 均 clone 成功（deploy key + host 别名） | **P1：单终端多仓库 key 路由**——deploy key 仓库级绑定，同一 host 只能一个 key；解决=host 别名（github.com 主 key + github.com-qxmap 别名） |
| **3. 252 自举** | ✅ 通过 | 252 Claude Code 读 qx-map 心智，准确回答 Worker 身份/定位 | **P2：节点级心智缺失**——252 读 M1 的 CLAUDE.md 把自己当 W1；需节点专属心智注入（252 标 W9/移动终端） |
| **2. 252 认领任务（绑定）** | ✅ 通过 | 252 经中转站 6100 完成任务，产出 Worker 自检报告 | **P3-P6 见下** |

### 252 Worker 自检报告的 4 个待完善点（P3-P6，蓝图反哺）

> 来源：252 Claude Code 实际接入自检报告（docs/notes/252-worker-selfcheck-2026-08-10.md），全部为实操发现。

| # | 问题点 | 建议 |
|---|--------|------|
| **P3** | 权限矩阵未落地：workers.md 给 W9 标 dev/write-card，但权限矩阵=只读消费——**标签与权限未对齐** | 落只读 deploy key + workers.md W9 标注「权限=只读消费」 |
| **P4** | 能力标签缺「是否可 push」维度：dev 不区分"能写能提交"vs"只能执行" | workers.md 标签体系补写权限维度 |
| **P5** | W9 登记仍是"示例"，未正式激活 | 确认 W9 正式激活，去"示例"标注，跑 check-tool-roles.py |
| **P6** | 缺一键接入 bootstrap，新节点靠人工拼文档 | 写 docs/bootstrap.md 固化接入清单 |

### 第二轮验证结果（2026-08-11 实测 · 跨节点路由全链路）

> 关联卡：clw019「前端设计角色注入验证」——由 W9（252 移动终端 Claude Code）跨节点认领执行，全流程跑通。

| 验证点 | 结果 | 证据 |
|--------|------|------|
| **✅ 跨节点 Worker 路由** | 通过 | clw019 执行体=W9 + 派发 manual → 252 认领 → 只读审查 clwarp → 产出报告 → 主写源收口 → 已回写+机审通过 |
| **✅ 角色→Skill 注入** | 通过 | 卡头「角色：前端设计」→ 执行提示注入 ui-ux-pro-max → 252 加载并按设计准则审查 |
| **✅ 253 源码访问** | 通过 | clwarp 只读 deploy key（id_ed25519_clwarp + host 别名 github.com-clwarp）clone 成功 |
| **✅ 主写源收口** | 通过 | 252 只读消费，报告由 2017 提交 clwarp main（权限矩阵生效） |
| **✅ 报告质量** | 通过 | 4 项建议（配色/排版/UX/一致性），含文件:行号引用，严格只读边界 |
| 3b. 252 定时巡检（非绑定任务） | 待测 | — |
| 5. 集群并发扩展（2017+252 同时） | 待测 | — |

> **意义**：这是集群 Worker 池的**首个跨节点实证**——突破 2017 单机并发瓶颈的技术路径已验证：任意终端注册 W 号 + 角色注入 = 立即成为可用 Worker。clw019 报告见 `clwarp/docs/notes/clw019-ui-review-2026-08-11.md`，教训见 `docs/notes/2026-08-11-clw-cross-node-worker-lessons.md`。

### 待验证（第三轮）
| 验证点 | 状态 |
|--------|------|
| 3b. 252 定时巡检（非绑定任务） | 待测 |
| 5. 集群并发扩展 | 待测 |

### 验证结论 → 蓝图修正
- 每项实测通过 → 蓝图该点成立
- 实测有阻 → 记录问题点 → 修正蓝图 → 丰满成执行计划

## 验收标准（蓝图级）

- [x] 252 完成注册（W9），Engine 能按 W 号派发到 252
- [x] 252 认领 ≥1 张开发卡并完成（绑定任务）——clw019 已回写+机审通过
- [ ] 252 执行 ≥1 次巡检（非绑定任务）
- [x] 中转站多通道在 252 上可配不同模型（6100 flash 实测）
- [ ] 2017 + 252 并发执行验证集群扩展
- [ ] 全部验证结论回写本方案，修正蓝图，转执行计划

## 转执行计划（蓝图验证后细化）

- [ ] 拆解为卡（注册 SOP / 派发路由 / 巡检宿主 / 多通道配置 / 并发调度）
- [ ] 每卡给文件级改动清单 + 测试
- [ ] 按平台自研红线：Engine/派发改造 = M1 主窗口直接开发，异席机审

## 备注

- 本方案为**蓝图**（架构方向），验证后才能转执行计划
- 依托已落地：W 号寻址 v1（executors worker_id）、Loop Observer 框架（011）、中转站多通道、任务卡「角色」字段 + role-skills.yaml、Engine 事件感知（写卡即响应）
- **已实证（2026-08-11）**：跨节点 Worker 路由全链路（clw019）——252(W9) 认领执行 + 角色→Skill 注入生效 + 主写源收口
- 252 验证是蓝图可行性的试金石，也是第一个「集群 Worker 池」真实节点
- 待验证：252 定时巡检（非绑定）、2017+252 集群并发扩展

---

# 执行计划 v2 · Worker 模型 + 认领协议（A 轨第 2 项 · 跨节点真路由）

> 依据：ENGINEERING-CANON §三-2（Engine 建造型假设 vs 集群 Worker）· 红线 6（平台自研 M1 直接开发）
> 状态：**设计草案（待异席审）** · 2026-08-11
> 核心目标：把「手动 GUI + manual 派发」两层补丁，换成**真正的 Worker 模型 + 认领协议**——Worker 是一级对象（带地址与状态），Engine 投递 + Worker 认领 + 收单，替代"Engine 只能本机 spawn"的建造型假设。

## 一、现状根因（已核实）

### RC4：决策/执行寻址语义相反
- **执行路径** `cli_entry_for_binding`（dispatch.py:142）认 W 号：`re.fullmatch(r"W\d+")` → `cli_entry_for_worker_id`
- **决策路径** `decide_work`（dispatch.py:285）用 `rows_for_binding(work.executor)`：W9 时 binding 匹配不到 → 回退 `decide(role)` → 角色含「开发执行体」OpenCode CLI 行 → **AUTO → 2017 本地拉起**
- **实测**：`W9+engine` 会回退 2017 本地拉起（两层补丁里 W9 靠手动 GUI + manual 派发绕开，非真路由）

### RC7：注册表双源漂移
- `executors.example.json`：W1-W4 有 worker_id
- `2017 生产 executors.json`：**W1-W4 无 worker_id**（仅 W9 有）
- 两文件不一致 → 派发寻址不可信

### Worker 现状
`ExecutorEntry` 仅 `worker_id: str = ""`（追溯标签），无 host/transport/status——Worker 不是一级对象。

## 二、Worker 模型设计（字段定义）

`ExecutorEntry` 新增字段（向后兼容，缺省=本机）：

```python
host: str = ""            # Worker 地址：空=本机(2017)；"ssh://user@252" 或 "git://github.com:hanrry2323/qx-map" 等
transport: str = "local"  # 传输通道："local"(本机 spawn) | "ssh"(远端 ssh) | "git"(认领协议，git 信道)
worker_status: str = ""   # Worker 状态：""(未知/未登记) | "ready" | "busy" | "offline"（观测更新，非决策硬依赖）
remote_workdir: str = ""  # 远端 worker 的工作目录（认领协议执行位置）
```

**Worker = 一级对象**：`worker_id` 是唯一键，`host/transport/worker_status` 描述其能力与位置。注册即接入（workers.md 登记 + executors.json 补行）。

## 三、决策态（REMOTE）

`DispatchDecision` 加 `REMOTE = "remote"`：

| 决策态 | 条件 | 动作 |
|--------|------|------|
| **AUTO** | 执行体命中「可后台 CLI」且 `transport=local` | Engine 本机 spawn（现状不变） |
| **REMOTE** | 执行体命中 `worker_id` 且 `transport=git/ssh` | **投递到远端 Worker 认领**（认领协议） |
| **MANUAL** | 仅命中「手动 GUI」或 `派发：manual` | 挂起等人（仅真·人工） |
| **NONE** | 席行/未知 | 不派发 |

**RC4 修复**：`decide_work` 改认 worker_id（对齐执行路径 `cli_entry_for_binding`）：
```
work.executor = "W9" → rows_for_worker_id("W9") → 命中 → transport=git → REMOTE
work.executor = "W4" → rows_for_worker_id("W4") → 命中 → transport=local → AUTO
work.executor = "OpenCode" → rows_for_binding → transport=local → AUTO（向后兼容）
```

## 四、认领协议 v1（复用 git 信道）

> 最省事的正确解：不引入新传输（RPC/队列），Worker 拉 origin + lock marker 认领，Engine 按 git 状态收单。

```
时序图（远端 Worker W9 认领卡 C）：

Engine(2017)                          Worker W9(252)                   Git origin
    │ 卡C 标「待认领」（REMOTE 决策）         │                              │
    │── 写卡 C 卡头派发=REMOTE → origin ────►│                              │
    │                                     │ 轮询 pull origin（cron/daemon）│
    │                                     │←────────────── 拉到卡 C ──────┤
    │                                     │ 认领：写 lock marker           │
    │                                     │── 提交 {card}.claimed ←───────►│
    │ 轮询 origin，见 claimed marker       │                              │
    │── 卡 C 记「已认领/in_flight」───────►│                              │
    │                                     │ 执行卡 C（走既有开发流程）       │
    │                                     │── 回写卡 C → origin ─────────►│
    │ 轮询 origin，见回写（已回写态）       │                              │
    │── 按「认领/在途/回写」收单 ──────────►│                              │
```

**关键状态位**（`{card}.claimed` lock marker 约定）：
- **待认领**：卡头 `派发=REMOTE` + `认领=待认领`（Engine 投递，无 Worker 认领）
- **已认领**：卡头 `认领=W9`（Worker 写，标记谁在干）+ `认领时间`（追溯 + 超时）
- **收单判定**：Engine 不再靠本地 PID（`pool.alive_ids`/marker），改看「认领位 + 回写态」——卡有 `认领=W9` 且磁盘卡到「已回写」→ 收单；有认领但超时未回写 → 回收待认领

**Engine 侧**：
- `_claim_marker_alive` 判定认领卡在途（替代 `_audit_marker_alive` 本地 PID 逻辑的远端版本）
- 认领超时回收：`认领时间` 超 `EXECUTOR_TIMEOUT_SECONDS` 且未回写 → 清认领位回待认领
- 收单不再依赖 `subprocess.Popen` 存活，改看 git 回写证据

**Worker 侧**（新增脚本 `scripts/worker-claim.sh`）：
- Worker daemon/cron 定期 `git pull` origin → 找 `派发=REMOTE 且 认领=待认领` 且 `执行体=W9` 的卡
- 写 `认领=W9 + 认领时间` → push origin → 执行卡（读卡 → 走既有 worktree/回写链路）
- 完成后回写卡 → push origin

## 五、机审适配（remote 卡无本地 worktree）

- **现状**：机审用 `_worktree_hint_for` 找本地 worktree → remote 卡无本地路径
- **修复**：`_audit_evidence_passed`/`_run_machine_audit_after_writeback` 对 `transport=git/ssh` 的卡：
  - 优先检查**业务仓/CCC 仓对应 codex 分支**的机审区证据（`git show origin/<branch>:<card>`）
  - 无本地 worktree 时跳过 `_worktree_card_candidate`，走分支信封证据判定
- **生产卡兜底路径正式化**：已有 `_card_machine_audit_passed(work.card_path)`（生产卡）分支，remote 卡默认走此

## 六、落地步骤（设计审后执行）

1. **ExecutorEntry 加字段** + DispatchDecision 加 REMOTE + decide_work 改认 worker_id（修 RC4）
2. **2017 生产 executors.json 补 W1-W4 worker_id + host/transport**（修 RC7 双源漂移）
3. **认领协议**：Engine 侧 `_claim_marker_alive` + 认领超时回收 + 收单改认领态；新增 `scripts/worker-claim.sh`
4. **机审 remote 适配**：机审证据检查走分支信封
5. **单测**（新增 `test_worker_routing.py`）：
   - W9+engine → REMOTE（不本地拉起）✅
   - W1-W4 各自命中（W4→AUTO local、W9→REMOTE）✅
   - 认领协议闭环：待认领 → 认领 → 回写 → 收单
   - 认领超时回收
   - 机审 remote 卡走分支信封
6. 提交推送 + 异席机审

## 七、执行约束（错峰）

- 动 Engine 内核（decide_work/收单）期间，B 轨 CLW 只出「不依赖状态机的卡」
- 每步带单测自证 + 提交推送，异席机审
- 平台自研红线：改 server/engine / server/board / scripts 一律 M1 直接开发，不走卡

---

# A 轨第 2 项完成汇总（Worker 模型 + 认领协议 · 2026-08-11）

> 状态：**已完成并上线**（设计 c9d40b86 → 三步改码 d02414fa / 22c2a442 / 8c40e151 / abe608aa）
> 依据：ENGINEERING-CANON §三-2 + 红线 6（平台自研 M1 直接开发 + 异席机审）

## ① 交付清单

| 项 | 落点 | 内容 |
|----|------|------|
| REMOTE 决策态 | dispatch.py | `DispatchDecision.REMOTE`；decide_work 对 `派发=scheduler\|remote` + 执行体 W 号 → REMOTE，不回退角色本地拉起（修 RC4） |
| 防假执行中 | main.py run_once | REMOTE 卡保持待分派（不标执行中/不占槽/不写 marker），Worker 认领后才写执行中（clw020 事故修复） |
| Worker 模型字段 | dispatch.py | ExecutorEntry 加 `host/transport/worker_status/remote_workdir`；load_registry 解析 + 远端行豁免本地命令 |
| RC7 修复 | 2017 executors.json | W9 行补 `transport=git` + 分类「可后台 CLI」 |
| 认领脚本 | scripts/worker-claim.sh | Worker 侧：pull→找执行体=W号待分派卡→写卡头认领标记→执行→回写 |
| 认领态收单 | main.py `_claim_round` | 有认领+已回写→收单；无认领→保持待分派；claim 字段进心跳 |
| 超时回收 | main.py `_clear_claim_marker` | 认领超时→清卡头认领→卡回待分派可重认领（断点续传地基） |
| 机审 remote | main.py `_audit_evidence_passed` | `_is_remote_work` 判定；无 worktree 走 `git show origin/<codex分支>:<卡>` 分支信封读机审区，生产卡兜底 |

## ② 测试结果

- `test_worker_routing.py`：**13 用例全绿**（Worker 路由 8：scheduler+W9→REMOTE 事故回归 / remote+W9 / W 号 local/remote / 工具名兼容 / manual→NONE / 未认领保持待分派；认领协议 3：in_flight / 未认领待分派 / 超时回收；机审 remote 2：分支信封读机审区 / 回退生产卡）
- 全仓 `server/tests/` 通过 + ruff 干净
- 相关改造带单测自证（d02414fa / 22c2a442 / 8c40e151 / abe608aa 各 commit 独立可查）

## ③ 生产验证

- 2017 engine 重启加载新代码，心跳含 `claim_collected/reclaimed/in_flight` 字段
- **clw020 事故闭环**：修复前 W9+scheduler → 2017 本地拉起跑 5 次假执行中；修复后 → `远端卡待 Worker 认领（保持待分派）`，不再本地拉起
- 看板 clw020 保持「待分派」等 252 Worker 认领（REMOTE 决策正确）

## ④ 遗留问题

| 级 | 问题 | 状态 |
|----|------|------|
| P1 | **Worker 侧 daemon 未部署**：worker-claim.sh 已就位，252 未配置 cron/daemon 定期跑认领 | 待 252 接入（B 轨/集群落地） |
| P2 | **remote 卡机审执行**：`_run_machine_audit_after_writeback` 走 `_dispatch_and_collect` audit 路径，remote 无本地 worktree 时机审 agent 在 2017 审分支信封——已适配证据读，但机审拉起本身仍需 2017 验收席 CLI | 已可用，优化待后续 |
| P3 | **认领冲突**：两 Worker 同时认领同卡（并发 lock）——当前靠「认领标记已存在跳过」，无原子 CAS | 集群并发扩展时补 |
| P3 | **executors.example.json vs 2017 生产**：W1-W4 transport 字段 example 未同步补 | 文档收敛待做 |

## ⑤ 建议下一步

1. **252 Worker daemon 接入**：252 配置 cron/launchd 定期跑 `worker-claim.sh --claim-only` + 执行器，实测 clw020 类 REMOTE 卡真跨节点闭环
2. **A 轨第 4 项 role-skills 一致性**：skill 进仓一键下发 + 注入点改派发时动态（配合 Worker 认领加载角色技能）
3. **认领冲突原子化**：并发 Worker 池扩展前补 CAS（git lock marker 原子）
4. **观测补强**：claim 字段进 Loop Observer（认领/回收/在途指标），数据反哺调度

## 状态更新

- 020 方案从「蓝图 + 执行计划 v2 设计」→ **Worker 模型 + 认领协议已落地**
- 待办：252 实跑闭环（跨节点真执行）、巡检非绑定任务、集群并发验证

---

# A 轨第 4 项完成汇总（role-skills 一致性 · 2026-08-11）

> 状态：**已完成并上线**（三步：skill 进仓 7be6a5e8 → 注入动态 1387d731）
> 依据：ENGINEERING-CANON §五-2（role-skills 一致性）+ 红线 6

## ① 交付清单

| 项 | 落点 | 内容 |
|----|------|------|
| skill 进仓 | server/config/opencode-skills/ | ui-ux-pro-max 收进仓（544K 28 文件，无 __pycache__）；claude-skills/code-review 保留 |
| 下发/校验 | scripts/sync-skills.py | 仓→M1/2017/252 节点 skill 目录 rsync 同步 + SKILL.md hash 版本一致性校验（--check） |
| 派发时动态注入 | main.py _dispatch_and_collect | 派发时按卡「角色」实时查 role-skills.yaml 补注入（出卡烘死 → 派发刷新，存量卡改 yaml 也生效） |
| 认领前 skill 校验 | worker-claim.sh | 认领执行前调 sync-skills --check，MISMATCH → 自动同步再执行 |

## ② 测试结果

- `test_role_skills.py` **8 用例全绿**：SSOT 加载/注入/未知角色/无角色/仓内完整性 + 派发时动态注入 2 + sync-skills hash 判定 1
- 全仓 `server/tests/` 通过 + ruff 干净

## ③ 生产验证

- M1/2017 `sync-skills.py --check` 实测 hash 一致（ui-ux-pro-max/code-review）
- engine 重启加载动态注入代码，心跳 claim_collected=1（clw020 认领收单）+ 机审正常
- 无在途 AUTO 卡时重启（错峰），无回归

## ④ 遗留问题

| 级 | 问题 | 状态 |
|----|------|------|
| P2 | 其余 SSOT 引用 skill（qx-auto-copycheck/daily-snapshot/hp-kb-operations/motion-graphics）未进仓 | 待后续收仓（claude 节点本地 skill） |
| P3 | 252 节点 skill 目录未配置（NODE_HOST_252 空） | 252 接入时填 |
| P3 | sync-skills 无自动定时（需节点 cron/daemon 定期同步） | 集群落地时配 |

## ⑤ 建议下一步

1. **252 实跑闭环**（集群验证关键路径）：252 配置 cron 跑 worker-claim.sh + sync-skills，实测 clw020 类 REMOTE 卡跨节点执行 + skill 注入
2. **skill 全量收仓**：SSOT 引用全部 skill 收进仓（claude-skills 补 4 个），消除节点本地 skill 双源
3. **观测**：sync-skills --check 结果入 Loop Observer（节点 skill 健康度）
4. **A 轨整体**：四项全完成 → 集群 Worker 池可用性验证（252 实跑 + 并发扩展）

---

# A 轨收尾汇总（2026-08-11 · 平台根治全部落地）

> 状态：**A 轨四项 + 收尾全部完成**。集群机制（认领协议/skill 同步/clw020 闭环含机审）已实证。
> 252 实跑挂账（SSH banner 超时客观阻塞，等网络修复或 252 本机操作）。

## A 轨交付总览

| 项 | 状态 | 交付 | 证据 |
|----|------|------|------|
| 第 1 项 sidecar 生命周期契约 | ✅ | ccc-plan-021 + 四分支收口 + 收敛器入 run_once | 全仓测试绿 |
| 第 2 项 Worker 模型 + 认领协议 | ✅ | REMOTE 决策/worker-claim/_claim_round/超时回收/机审 remote | test_worker_routing 13 用例 + clw020 闭环 |
| 第 3 项 机审打回可执行性 | ✅ | 机审 SOP 定稿（a78f0cb0） | — |
| 第 4 项 role-skills 一致性 | ✅ | skill 进仓 + sync-skills + 派发动态注入 + 认领前校验 | test_role_skills 9 用例 |
| **收尾** skill 全量收仓 | ✅ | SSOT 6 skill 全在仓（5 claude + 1 opencode） | M1/2017 --check OK |
| **收尾** sync-skills 定时 | ✅ | 2017 com.ccc.sync-skills（每日 3:00）+ M1 同款（3:15） | launchctl list 可见 |
| **挂账** 252 实跑 | ⏸ | onboarding SOP 已给命令清单 | 252 SSH banner 超时 |

## skill 收仓清单（SSOT 全覆盖）

| skill | 角色 | 来源 |
|-------|------|------|
| ui-ux-pro-max | 前端设计 | M1 ~/.opencode/skills → opencode-skills/ |
| code-review | 代码审查/swift开发 | 2017 ~/.claude/skills → claude-skills/ |
| daily-snapshot | 巡检专家 | 2017 ~/.claude/skills |
| hp-kb-operations | 知识维护 | 2017 ~/.claude/skills |
| motion-graphics | 视频制作 | 2017 ~/.claude/skills（23 文件） |
| qx-auto-copycheck | 文案检查 | qx-map .claude/skills |

## 遗留问题

| 级 | 问题 | 状态 |
|----|------|------|
| P1 | 252 SSH banner 超时（客观网络） | 等网络修复或 252 本机操作（onboarding SOP） |
| P3 | 252 节点定时认领未配 | 252 接入时配（schtasks 命令在 SOP） |
| P3 | sync-skills 无循环观测 | 建议后续入 Loop Observer |

## 建议下一步

1. **252 网络修复后实跑**（关键路径）：252 本机配计划任务 → REMOTE 卡真跨节点执行 → 集群实证
2. **集群并发扩展验证**：多 Worker 同时认领不同卡（认领冲突 CAS 是前置）
3. **平台观测**：claim/skill 健康度入 Loop Observer，数据反哺调度

## 状态更新

- 020 方案 → **A 轨四项 + 收尾全部完成**；集群 Worker 池机制就绪，待 252 实跑闭环（外部网络条件）
- 平台侧（Engine/认领/skill）不再有建造型阻塞
