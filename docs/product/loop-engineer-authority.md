# Loop Engineer — 事实权威与人机共识（SSOT）

> **状态**：现行 · 2026-07-24（**Ops 运维面**：三面 + 红绿灯；Hub M1 隧道 `:17777`；假绿关门 / 活跃板计数 / VERSION opt-in） 
> **谁读**：老板 / Desktop Agent / Hub·sidecar / Cursor 改平台。  
> **冲突时以本文为准。** 边界流程：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> **规则**：你我共识 → **写入本文（或明确指向本文的一节）** → 再改代码/人格；禁止只留在聊天里。

---

## 一句话（开发路径）

**人定意图 → Hub 下达 → Engine 编排扇出 → 权威仓写码 → 验收纠错 → 回流飞轮；全程只认一个权威仓。**

（叙事：[`../VISION.md`](../VISION.md)。）

---

## 双 Agent 人格独立（硬 · 2026-07-22）

| | **Cursor（平台开发）** | **Desktop Agent（对话面）** |
|--|------------------------|------------------------------|
| 在哪 | Cursor IDE · 本仓 `/Users/apple/program/CCC` | M1 App · sidecar → loop-code |
| 职责 | **改 CCC 平台**：读/写/跑测/提交/排障，完整 IDE 能力 | **定意图**：对齐事实、定稿 epic、转任务；默认 Plan（硬禁写业务仓） |
| 人格 SSOT | 本仓 Cursor 规则 + [`dev-channel.md`](dev-channel.md) | [`desktop-agent-identity.md`](desktop-agent-identity.md) + `hub_voice.py` |
| 工具门禁 | **无** Desktop discuss allowlist；不受 Plan「不写码」约束 | discuss：除 Write/Edit 外全开；engineer 仅 `ccc` |

**禁止串台**：

1. **禁止**把 Desktop Plan 的「不写码 / 只产 epic / 透镜纪律」套到 Cursor 头上，当作 Cursor「能力限制」。  
2. **禁止** Cursor 会话自称 Desktop 对话搭档，或按 Desktop 人格前缀作答。  
3. **禁止** Desktop 人格文案写「你就是 Cursor」或反过来；功课可以深，**身份不可混**。  
4. Desktop 工具/人格改动 **只影响** sidecar→loop-code；**不**削弱 Cursor 改平台的能力。

平台开发通道：[`dev-channel.md`](dev-channel.md)。

---

## 闭环七词

| 词 | 含义 |
|----|------|
| **意图** | 人在 Desktop 聊透目标与验收 |
| **下达** | 定稿 transfer；进队后不逐步人批 |
| **编排** | Engine 扇出 work、调度阶段 |
| **写码** | 只在 2017 权威仓；plan 白名单 |
| **纠错** | verdict 落盘；abnormal 止损 |
| **飞轮** | 归档 / 回测 / 再定意图 |
| **权威** | 代码与看板只在 register 仓；透镜 live |

**已注册 ≠ 可正式开发。** 正式交给 CCC 前须**全面对齐**（baseline + live 透镜 + risks + 可下达边界）。

**平台开发工具：只认 Cursor，不更换**（[`dev-channel.md`](dev-channel.md)）。仓内若残留 Trae/Zed/「用 Claude Code 改平台」等现行指引 → 删除或标史。

---

## 行业共识（我们认可）

| 判断 | 结论 |
|------|------|
| Demo ≠ 上线 ≠ 稳定符合意图 | **行业共性**，非个人特例 |
| AI 擅 happy path；缺边界/验收/纠偏环 | 高级/低级模型都快到「能跑」，后半段才是鸿沟 |
| 接手老仓难于从零 | 隐性规则在人脑；须先对齐再交给 agent |
| 路线曲折、模型误解 | **默认**；产品要做闭环，不幻想一次聊完 |

CCC 卖的不是「更快写出第一版」，而是把后半段**工程化**。  
卖的也不是「更细的 Agent 画布」，而是：**少而硬的意图 + 唯一权威路径 + 偏差默认下的纠错飞轮**（见下节三句）。

---

## 价值立场（2026-07-21 评估 · 2026-07-22 加硬）

| 项 | 口径 |
|----|------|
| 加权约 **7.2/10** | **值得继续做**，只压「闭环工程」 |
| 值钱 | 意图门 · 对话/编排分离 · 权威仓+透镜 · verdict/旁路收死 |
| 不值钱 | 复刻 IDE · 堆角色 · 堆文档 · 「接很多模型/多 IDE」当卖点 · **Agent 工作流画布（节点里叠对话/指令）当写码主控** |
| 平台开发 | **只认 Cursor**；不换工具 |
| 下一程证明 | 已对齐业务仓连续 **3 次**「定稿→在飞→verdict」可复述可纠；达不到就收范围 |

评分画布（讨论产物）：Cursor canvases `ccc-value-scorecard` / `ccc-pain-loop-stages`。

### Vibe coding 真优势三句（硬 · 2026-07-22 · CCC 差异化）

> 人机共识：画布曾显得酷（动效、卡片里塞对话/指令）；**写码闭环里它抬的是失控感，不是胜率。**  
> Agent 执行本就高方差（漏读、误改、半提交、假绿、挂死）；节点上再叠意图 = 不确定之上再叠解释空间。  
> 即使「确定的 plan」在同软件内流转也会出问题——**偏差是默认**，不是例外。

Vibe coding 里真正值钱的**不是「图更细」**，而是这三条——也是 **CCC 相对社区画布/SDK 的优势**：

1. **人定少而硬的意图** — 一两句可验收的目标（意图门窄，不靠节点堆指令）。  
2. **系统强制走同一条权威路径** — 下达 → 权威写码仓 → 门禁（对话面不定码；编排面不另开真理）。  
3. **偏差当默认** — 用 verdict / 回滚 / 重试 / 飞轮收，**不指望** plan 或画布一次画对。

**禁止**把产品路线拐向：Dify / CC Workflow Studio 式「可视化编排 + 卡片内对话」当 CCC 主卖点。社区画布适合业务自动化/RAG；**不适合**当 AI 写码主控台。对标时借稳态与任务板思想（LangGraph / Agent Teams 等），**不借画布炫技。**

---

## 三阶段（都能接，门禁不同）

| 阶段 | 适配 | 交给 CCC 前须齐 |
|------|------|-----------------|
| 从零新建 | 强 | 意图 + 验收标准 |
| 接手老项目 | 中→强 | **全面对齐硬门** |
| 日常维护 | 强 | 小目标 + 白名单 + verdict |

**已注册 ≠ 可正式开发。** 正式交给 CCC 前须**全面对齐**：baseline + live 透镜 + risks + 可下达边界。

**平台开发工具：只认 Cursor，不更换**（[`dev-channel.md`](dev-channel.md)）。仓内若残留 Trae/Zed/「用 Claude Code 改平台」等现行指引 → 删除或标史。

### Desktop 流畅原则（人机共识）

**人只定意图；投递/连通/重试/进 Hub/进队列 = 系统后台，用户不碰。**  
**确认不依赖 Hub 可达**；Hub 灯只表示投递/编排同步健康，不挡确认。  
**唯一冲刷器 = sidecar**（Desktop 只 `enqueue` + 可选 nudge；关 App 不停）。

| 前台（人确认） | 后台（系统扛） |
|----------------|----------------|
| 定稿 / 点转任务 / 切看板 | Hub 连通、投递、重试、卡死恢复 |
| 立刻关 sheet、徽章 `queued`、可继续聊 | 入本机 outbox；**sidecar 常驻 flush** → Hub；成功写 `transfer-receipts.json` |
| 看板始终画列（可空） | 拉板失败保留快照 + 短超时，不整页死白 |

**Agent 定方案（硬）**：讨论 / 定稿时，按用户意图制定**最佳方案**并默认推进；**禁止**每轮甩拍板选择题、**禁止定稿后再问要不要入队**。仅当真缺不可逆信息才最多 1 问。定稿白话给用户可读结论；`ccc-transfer` 契约折叠给 Engine，不把任务 id/路径清单当结论。**板面残卡清场**走 Hub `board-repair`（见下 · Agent 本职），**禁止**默认逼用户再投卫生 epic。偶发仍投卫生卡时：`executor_intent=python`（Hub 对 ops/卫生意图会把 opencode 强制归一为 python）；**不存在 committer 绕过 Engine**；`pipeline=ops` 仍扇出。abnormal / 未核账在飞残卡禁止重复下达同目标卡（须先板务或人显式 override）。

**App Agent 对用户（硬 · 2026-07-24 · Cursor 级语感）**：短人话先结论；自己跑透镜/板务/心智工具；**禁止**把 `transfer-outbox` / Terminal / Hub CLI / 执行器黑话教给老板；平台词只进 `ccc-transfer` 块内。能力对齐 Cursor **对话搭档**（查事实、定方案、清卡点），不是第二 IDE（业务改码仍 transfer→Engine）。

#### Desktop 主路径（硬 · 2026-07-24 · 取代四段硬流程）

```text
聊意图（自由聊；对齐基线=可选深扫）→ 人确认下达（定稿锁契约 或 对话建议→转任务确认）
  → 系统：silent lens + outbox → Hub epic → 必 wake Engine → 右栏扇出/阻塞可解释
```

| 环节 | 人 | Agent / 系统 |
|------|-----|----------------|
| 聊意图 | 自由聊 | 按意图给最佳方案；可选点「对齐基线」深扫；**不必**先点任何芯片 |
| 对齐基线 | 可点；**非硬门槛** | Hub baseline + live lens；扫出残卡 → **优先 `board-repair`**，不默认逼卫生 transfer |
| 看仓况 | 可选芯片（旧名「下一步」已降级） | lens `board`+`git`；阻塞则先板务；**不是**下达必经阶段 |
| 定稿 | 点「定稿」或聊够后契约 | 定稿/转任务前系统静默核实；出 `ccc-transfer`；方案字段锁死 |
| 转任务 | 二级卡确认 | 人仅可改 **title** + **human_note**；goal/acceptance/plan_md/执行面只读；改方案须退回重定稿 |
| 入队后 | 继续聊 | formal/heuristic **同一** transfer 路径；`task_dispatch` 强制 enabled+wake；未扇出须人话阻塞因 |

- **不用对齐基线、直接聊 → 定稿/转任务：放行**（transfer 门禁不查 baseline）。
- **「下一步」不是必经阶段**；核实并入定稿/转任务前静默 lens，或可选「看仓况」芯片。
- 禁 `ssh`；能力靠透镜 + `board-repair` + 提示词硬闸。
- digest/STATUS 勾选不作终局；脚本+报告已在仅文档未勾 → S/同步，禁止 stamp 重开落地卡。
- **凡进 backlog 的 epic 须带起 Engine 消费**；响应带 `engine_wake`（含 `engine_running` / `workspace_eligible`）；超时无 fanout → UI/Agent 明示原因（Engine 未跑 / 上游 / cap / epic=failed），禁止静默饿死。

#### Desktop 板务 · Agent 本职 · 卡点必兜底（硬 · 2026-07-24）

**看板维护是 Desktop App Agent 的本职**，不是可选建议。Engine 跑挂/退出留下的 `abnormal`/残卡/幽灵轨 → Agent **自己**经 Hub **`POST /api/desktop/board-repair`**（一等工具 `hub_repair` / CLI `ccc-hub-lens.py repair`）清场，**绝不**写业务源码。

死循环禁区：板堵 → ready=false → 下不了新产品 → Agent「以为 Plan 不能动板」或甩卫生 epic / Terminal outbox 给老板 → 老板又当运维。**破法**：发现卡点必须先 repair，再谈产品。

| 允许 | 禁止 |
|------|------|
| 归档/隐藏：`abnormal` work、`split_status=failed` 已放弃 epic、已 `done` 僵尸 | 写业务仓文件 / plan 白名单外改码 |
| 剪幽灵轨：`last_epic` / `epic_history` / flow-events 对应 epic | invent / ops-auto 自造产品卡 |
| 瞬态 abnormal 有限 reopen（对齐 failure-learning） | 对 CCC orch 投卡（R-15） |
| 审计日志落盘 | 用 Engine 卫生 epic / 教用户手写 outbox 当清场主路径 |

**清 abnormal 不等人审**。人审只在定稿确认 / inbox 采纳；「止损」= Agent 先修板，修不动再人话说明，**不是**先问「要不要归档」。

未 ready：Agent **必须先 board-repair**；仅业务脏 / 真在飞冲突时拦新产品 epic，并说明人可「仍要下达」（显式 override，记 `human_note`）。板务 = 编排元数据（`.ccc/board` + flow），discuss 允许且应当执行。

禁止：
- 让用户管「是否进 Hub / 是否还在队列 / 要不要重开 App 冲刷」
- 用全局 `busy` 把对话/切页锁死在一次 Hub 往返上
- Desktop 与 sidecar **双 POST** Hub transfer（只认 sidecar 单写）
- 把板面清场做成用户再走一遍「定稿→转任务→Engine」主路径
- 正文出现 `transfer-outbox` / `cat >` / Terminal 清板教程

关 Desktop ≠ 停编排：Hub/Engine 在 2017 继续；本机 outbox 由 `com.ccc.agent-sidecar` 冲刷到 Hub。

### 关再开接续（R1–R12）

| # | 行为 | 结论 |
|---|------|------|
| R1 | 投递徽章 | hydrate 优先 `transfer-receipts.json`，再 outbox / failed / 磁盘 flow |
| R2 | 看板首屏 | `board-cache-<project>.json` 冷启动；失败保留 + stale |
| R3 | 回前台 | `scenePhase.active` → flush + bindFlow + summaries（用户无动作） |
| R4 | fanout 提示 | 未拆分 epic 再开后重挂 **45s** watchdog（人话阻塞因：Engine/eligible/failed） |
| R5 | 空态 | 有 `boundEpicId` 显示「编排同步中…」，禁闪「编排空闲」 |
| R6 | 侧栏灯 | bootstrap 立即 `fetchBoardSummaries`，不等首轮 poll |
| R7 | Chat 页 | 仅 summaries ~20s 刷灯；整板只在 Board 页轮询 |
| R8 | 单 flush | Desktop 只 nudge sidecar；按 receipts/outbox 校正徽章 |
| R9 | 投递耗尽 | 持久 failed 条 + 「后台再试」；**Hub 恢复时自动 requeue**（非只靠用户点） |
| R10 | SSE cursor | 不改协议；靠 snapshot 接续；中间动画可缺 |
| R11 | 聊天半句 | **不做**中途 SSE 重挂；再发可 resume |
| R12 | 全局 busy | Hub 往返（含手动建 epic）不锁 `busy` |

再开 = 磁盘 hydrate + 后台 catch-up；**用户无需点同步**。

### Hub 传输（M1 · 硬 · 2026-07-22）

| 项 | 口径 |
|----|------|
| **权威 Hub 仍在 2017** | 进程听 `*:7777`；契约 / transfer / mind / lens **不变** |
| **M1 主路径** | SSH 本地转发 `127.0.0.1:17777` → 2017 `127.0.0.1:7777`（launchd `com.ccc.hub-tunnel`） |
| **Desktop / sidecar 默认** | `http://127.0.0.1:17777`；**禁止**把 LAN `192.168.3.116:7777` 写成 M1 默认 |
| **为何** | LAN 直连 `:7777` 曾 TCP 通但 HTTP 整段超时（Send-Q 积压）；隧道探活满绿 |
| **文档** | [`hub-ssh-tunnel.md`](hub-ssh-tunnel.md) · [`desktop-connection.md`](desktop-connection.md) |

安装：`bash scripts/install-hub-tunnel-plist.sh --start`。心智 / 透镜 / outbox 一律走同一 `CCC_HUB_URL`。

### Desktop 右栏（项目态势 · 硬 · 2026-07-24）

- 右栏跟**左侧项目**绑定，**不**跟单个对话；同项目任意会话看到同一份右栏。
- 顶条：看板列计数（待办/规划/进行/验收/异常）+ Δ；中：项目级大卡栈 + 扇出竖轨。
- SSOT：`projectFlow` / `projectBoardCounts`；`bindFlowToProject`（Hub `project_single`）。
- 文档：[`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)。

### Desktop Agent 双层心智（人机共识）

| 层 | 内容 | 谁维护 | 落点 |
|----|------|--------|------|
| **L0 不变核** | 身份、红线、转任务闭环、透镜纪律 | **仅 Cursor / 平台仓**（`hub_voice` + 本文） | 每轮强制注入；Agent **禁止写** |
| **L1a 观察脑** | 看板计数、在飞、日报/周报要点、git 脏仓 | **系统编译** | 2017 `apps/<id>/.ccc/agent-mind/observed.json` |
| **L1b 决策脑** | 目标/约束/开放问题/架构取舍 | **Agent 提案 + Hub 校验** | 同目录 `decided.json` |

- API：`GET/PUT /api/desktop/mind/{project_id}/…`；sidecar **每轮**注入 digest（≤2KB），与 live board **并行拉取**，本机短缓存（约 20s）降隧道往返。
- 新鲜度：`live board / lens git` > L1 digest > 聊天 resume。
- 不复活 invent；心智沉淀 ≠ 自动投 backlog。
- Hub 断 / 隧道断：明说 L1 不可达，**禁止**用聊天 resume 编造在飞；转任务仍可 outbox。

### 活跃板计数与 ready（硬 · 2026-07-22）

| 信号 | 含义 |
|------|------|
| **活跃板计数** | lens / mind / baseline 与 Board API **同口径**：跳过 `ui_hidden=true` 与 epic `split_status=done`；`failed` 仍算活跃风险 |
| **pipeline_idle** | 过滤后 planned/in_progress/testing/abnormal=0，且无在飞 inflight |
| **git_clean** | 工作区 porcelain 空 |
| **ready_for_task** | `git_clean` **且** 无活跃 inflight（≠「仅 git 净」；≠「磁盘 backlog 文件数为 0」） |

禁止把 raw `backlog/*.jsonl` 文件数（含已 done+hidden 僵尸）当成「待办队列」推荐挑卡。

### 验收关门与 VERSION（硬 · 2026-07-22）

- **跑完 ≠ 做对**：salvage / 进 testing 前必须过 hollow + acceptance（计划 `## 验收` 可重放命令或交付路径落在 task commit）；`ALL SELF-CHECKS PASSED` 字符串**不足以**单独放行。
- **业务卡禁止散文验收**：`acceptance_prose_with_commit` 仅 ops/卫生；业务须 path 或白名单命令。扇出禁止「完成…可验证」散文种子。
- **审测按卡型适型（硬 · 2026-07-23）**：先认 `dev_path`（script_seed / board_ops / doc_only / opencode），再认 diff 行数。短路径 = py_compile + 验收重放 → 写 verdict，**不进 600s LLM**；真代码 medium/large 仍 LLM。禁止 plan-only PASS；lock skip 写 TIMEOUT。tester 缺 PASS verdict 不得 verified；短路径不强制 cov。
- **L0 / L1 分拆（硬 · 2026-07-23）**：**L0** = 可重放验收 / 短路径确定性（总闸，不过不进 L1）；**L1** = opencode 真代码语义审（Claude 副闸）。禁止把 Claude 当 testing 默认总闸。
- **失败学习 R1/R2/R3（硬 · 2026-07-23）**：FAIL 打回前写 `.ccc/pids/{tid}.review_fail.md`；revert 后 phases 对齐；dev prompt 注入失败摘要。`review_fail_loops≥2` 或 plan_gap → **R2 修订该 work 的 plan**（禁止盲重试原指令；禁止 epic 子卡 product regen）。≥3 → R3 quarantine。**enabled 下**：瞬态 abnormal（非 permanent / 非 loops 耗尽）可有限次自动 reopen→planned（每卡 ≤2；须 work 卡 + 业务仓；禁止 invent/orch）；永久类仍停 abnormal 等人/Cursor。本轮**不做** Ollama / 新 coding CLI。
- **hollow 适型**：仅 OpenCode；优先扫本 phase stdout，避免历史 report 误伤文档 phase；script_seed/board_ops 不跑 hollow。
- **complexity=small** 仅表规模提示，**不** stub 跳过 reviewer/tester。默认 **medium**。多步回归/三件套（acceptance 可执行条 ≥3 或模块标记 ≥3）禁止 small——Hub `resolve_complexity` 会抬升；扇出对真回归不因 small 强制单卡。
- **运行时冒烟验收**：`.venv/bin/python` / `python3` + 显式 `DRY_RUN=true`；禁止裸 `python`。
- **VERSION**：kb 默认 **不** bump；仅 transfer/epic 显式 `bump_version=true`（或 tag `bump-version`）才升版+changelog+tag。
- **看板卫生归属（硬 · 2026-07-23 · 可执行 · 2026-07-24）**：**板面残卡/僵尸 backlog/幽灵轨清场归 Cursor 或 Desktop Agent（Hub `board-repair`）**，**禁止**靠压测/日批投「看板卫生」Engine epic 当主路径。`efficiency_six` **不含 e05**。若偶发仍有 scope∈`.ccc/board/**` 且 executor∈{python,auto,cli} 的卡，Engine 仍可走 board_ops 短路径（兼容），但**不得**用它替代平台清场 / board-repair。
- **卫生卡 seed（硬）**：验收白名单里出现的历史 `.ccc/plans/*.plan.md` **不是** adopt 引用；仅「见/参照/已写入 …plan.md」才收养。Transfer 写 `plan_md` 时须同步合成 phases（保留 `.ccc/` scope）。ops / `.ccc`-only **禁止**强制全仓 pytest（否则卫生卡必挂）。
- **止损清场**（Agent/平台排障）：failed epic + abnormal work 经 board-repair 归档/隐藏后，还必须清 `last_epic` / `epic_history` 与 `~/.ccc/flow-events.jsonl` 中该 epic（API `purge_flow` / `clear_blockers` 一体做），否则右栏 `bound_hint` 幽灵复活。
- **FAIL→planned 上限**：reviewer FAIL/FALLBACK 回弹 ≥3 → quarantine（`reviewer_fail_loop_exhausted`），防无限回弹拉高 gate_wall。

### 上线 ≠ 开发完成 — 后半段自动化补洞（硬 · 2026-07-22）

> **行业坑**：版本号升了 / 卡进了 `released` / Dashboard 能点，**不等于**意图已稳定满足。  
> CCC 不靠人肉盯日志填坑，而把「后半段」拆进编排，可重复跑。

| 阶段 | 名称 | 什么时候算过 | 谁跑 |
|------|------|--------------|------|
| **L** | `code_landed` | epic 子卡 → `released` + verdict 落盘 | Engine 主链 |
| **P** | `intent_probed` | 验收里的**意图探针**可重放绿（paper / DRY_RUN / 契约命令） | 同卡验收 + **regress** 回放 |
| **S** | `intent_stable` | 探针窗口或人确认「稳定符合意图」写入 L1 `decided` | Desktop 定意图 / 心智 PUT |
| **N** | 下一意图 | 仅当本意图达 S（或人显式放弃）才开下一条产品 epic | Desktop 定稿 → transfer |

**硬规则**：

1. **`released` / VERSION bump / smoke README stamp ≠ 产品完成。** Agent 禁止用「已 released N 张」代替「意图已满足」。
2. **产品目标写在 L1 `decided.goals`**，须带可执行退出条件（命令或探针路径）；禁止只写「管道可空转 / 对齐基线」当唯一目标。
3. **空闲优先产品 epic**：`pipeline_idle` 且 `git_clean` 时，下一步默认取 `decided.goals` 未完成项；**禁止**在无卫生风险时优先下卫生/烟测/README stamp 卡。
4. **意图探针进验收**：业务 epic 的 `## 验收` 至少一条可重放探针（`.venv`/`python3` + 显式 `DRY_RUN=…`）；regress 扫 `released` 时重跑这些探针，挂了 → 回 backlog 建回归 epic（飞轮），不假装完成。
5. **VIP→P1 排序跟业务仓 DEV_PLAN**：钱能不能保住（paper/testnet）→ alpha → 单机运维 → 集群（门槛未齐冻结）。

**自动化落点（现行 · v0.60 已落地）**：

```text
人定意图(含退出条件) → transfer(探针门+N门) → Engine(L) → verdict
 → regress 重放意图探针(P) → 人/心智 mark stable(S) → 再定下一意图(N)
```

| 能力 | 落点 |
|------|------|
| 探针解析/白名单/执行 | `scripts/_intent_probe.py` |
| 机械探针短路径（禁 opencode hang） | `board/roles/script_seed.py` · Engine 优先于 opencode · transfer 强制 `python` |
| transfer 业务须探针；卫生豁免 | `transfer_gate.validate_transfer_payload` |
| 下一意图门（未 S 须 supersede/abandon） | `transfer_gate.check_next_intent_gate` |
| acceptance / tester 共用白名单 | `_acceptance_gate` / `tester` |
| regress 重放探针 | `board/roles/regress.py` |
| L1 goals 结构 + `intent_stable` | `agent_mind` + `POST …/goals/{id}/status` |
| 空闲优先产品目标 | `_project_baseline.next_product_goal` |
| 出门清单 | [`lpsn-ship-gate.md`](lpsn-ship-gate.md) |
| 飞轮自动化（规划 · 未实现） | [`../briefs/2026-07-24-lpsn-flywheel-auto.md`](../briefs/2026-07-24-lpsn-flywheel-auto.md) · T1 seed / T2 probed / T3 人点 stable / T4 next_goal |

平台只认这一条飞轮；扩 IDE / 堆角色 **不**填这个坑。

---

## 四权威（只认这张表）

| 权威 | 落点 | 谁可写 |
|------|------|--------|
| 意图 / 会话 | M1 Desktop `sessions/` | 人 + 讨论 Agent（聊） |
| 编排看板 | 2017 `apps/<id>/.ccc/board` | Hub transfer + Engine |
| **代码 SSOT** | 2017 已 register 的 `apps/<name>` | **仅** Engine 阶段执行器 |
| 远端备份 | GitHub | 人 / Cursor 同步；**不是**对话或 Engine cwd |

M1：**无**业务源码第二树；`localWorkspaceMap` 仅可选 `ccc` → 本机 CCC。

---

## 讨论 Agent 事实源

| 来源 | 用途 |
|------|------|
| Hub baseline | 开场（点时快照 + live board） |
| Hub **只读透镜** `/api/desktop/lens/{id}/…` | live 看板 / locate / 文件 / grep / git |
| Hub **项目心智** `/api/desktop/mind/{id}/digest` | L1 观察脑+决策脑短摘要（每轮） |
| 本机会话 | 已聊目标与约束（低于 digest/board） |
| 本机 Read/git | **仅** `ccc` |

CLI：`python3 scripts/ccc-hub-lens.py board|locate|tree|file|grep|git <project_id> …`  
心智写入：`python3 scripts/ccc-mind-update.py <project_id> --constraint '…'`  
禁止 sidecar `ssh mac2017` 探业务仓。问看板/文件 → **先透镜**；Hub 断 → 明说，禁止瞎编。

**扫风险 / 下一步 / 定稿**：必须定点核实真代码（`locate`/`grep` → `file`），禁止只读文档交差；禁止全仓无脑扫。路径只认 `project_id` + 透镜相对路径。对齐基线非硬门槛，但下一步/定稿前仍须 live `board`+`git`。

---

## 工程师模式

| 项目 | 规则 |
|------|------|
| 业务仓 | **拒绝** engineer |
| 平台仓 `ccc` | 可本机改 CCC |

业务改码：**定稿 → transfer → Engine**。

---

## 讨论 = Plan（规划面 · **仅 Desktop**）

> **适用范围**：只约束 **Desktop sidecar → loop-code**。  
> **不约束 Cursor**。Cursor 改本仓 = 完整 IDE 能力（见上文「双 Agent 人格独立」）。

| 维度 | 规则 |
|------|------|
| 协议 | Desktop 仍传 `tool_mode=discuss`（少动协议）；`prompt_mode` 恒 full（已取消 light） |
| 智力 | 全开：Read/Glob/Grep/Bash/Web*/Task·Agent + Hub 透镜（含 locate） |
| 执行 | **硬禁** Write/Edit/MultiEdit/NotebookEdit；子代理同样禁写 |
| 交付 | 定稿 / `plan_md` / 转任务契约，**不是**仓库 diff |
| 业务仓 | 事实只认 Hub 基线 + 透镜；禁止假装本机有第二树；禁止写死 2017 盘符 |

工程师模式 = **仅 Desktop 会话**里对 `ccc` 可写；业务仓口令无效。Desktop 代码定位 = 透镜 `locate`（业务仓不走 Cursor MCP）。

---

## 扇出角色（讨论面须知 · 勿扮演）

| 角色 | 可写 | 硬规则 |
|------|------|--------|
| product | plan/phases/扇出；不写源码 | cwd=2017 apps |
| dev | 仅 plan 白名单 | 红线 3 |
| reviewer/tester | verdict/report | Verdict 落盘才算 |
| 讨论 Agent（Plan） | 无业务写 | 透镜只读 + `ccc-transfer`；可子代理调研 |

---

## 共识如何落盘（强制应用）

以后你我达成共识，执行顺序：

1. **改本文**（或在本文增加一节并改「状态」日期）——权威。  
2. **改入口**：`STARTUP-BRIEF.md` / `CLAUDE.md` / `.cursor/rules/loop-engineer-consensus.mdc` / 必要时 `hub_voice.py`——应用。  
3. **不要**另起平行「现行真理」长文；史实类标「史」并指回本文。  
4. 讨论画布可留作评分/梳理附件，**不**替代本文。  
5. **可巡查硬卡**同步：`references/authority-patrol.jsonl`（给机器探针用，不是给人读的说明书）。

---

## 平台自动维护 + 违背才找老板（硬 · 2026-07-22）

目标是 vibe 自动化：日常维护 **不问你**；只有 **违背本文硬共识** 才用人话喊你拍板。

| 区 | 谁做 | 要不要你点头 |
|----|------|--------------|
| **绿灯（自动）** | Cursor 平台维护：对齐版本、清过时改法指引、修测试红、双机同步热更、止损清场、回填 hub_voice/L1 | **不要** |
| **红灯（决策）** | 权威巡查发现违背本文（或明确指向本文的硬卡） | **要**——桌面通知 + `~/.ccc/alerts/` 人话文件 |

硬口径：

1. **平台养仓只认 Cursor**（定时 Automation / 会话 / hook）；**禁止** Engine invent 养 CCC orch。  
2. **默认可自动**：未踩红线就直接干，禁止反复「这样行吗」。  
3. **唯一打断你**：巡查脚本 `scripts/ccc-authority-patrol.py` 发现违规 → `ccc-notify` L3（人话：发现了什么 / 为何算违背 / 建议怎么选）。  
4. **你不读长文档**：报警正文即决策界面；拍板后改本文或改实现，下次巡查变绿。  
5. **经验进配置**：authority + Cursor rule + hub_voice + 巡查卡；**禁止**另堆给你看的平行 brief。

---

## Ops 运维面（硬 · 2026-07-24 架构定稿）

> 取代「运维=迷你看板 / 只读态势拼盘」口径。后勤隐喻仍对：**Engine = 前锋；Ops = 养系统**。产品主语改为：**给人看的健康灯 + 后台自动化**。

### 三面正交（对话 / 编排 / 运维）

| 面 | 主语 | 成功标准 |
|----|------|----------|
| **对话** | 人的意图是否说清并下达 | 定稿 transfer 正确 |
| **编排** | 卡是否按权威路径跑完 | released / verdict |
| **运维** | **系统养不养得起这条环；人敢不敢开发** | 总灯绿 → 放心下达；红 → 交 Agent |

主路径仍是意图→Hub→Engine。运维是保障与闭环旁路，**不是**第四条 invent 入口，**不是**第二块派工看板，**不是**把老板变成维修工。

**invent 硬关**：`invent_hard_disabled` **保持**；日审 decision **I = 永不**。无人自造任务本阶段不开发。

| | **Engine（前锋）** | **Ops（运维面）** |
|--|-------------------|-------------------|
| 吃什么 | 板上已有可消费任务 | 旁路养系统；红灯给人看、复制包给 Agent |
| 不做 | invent / 空闲造卡 | 不抢写码主路径；不数卡当主叙事；不教人修代码 |
| 成功 | backlog→released | **全绿时人几乎无感**；红灯有一键出口；多数故障自愈不上红 |

### 红绿灯（Desktop 运维硬规则）

| 灯 | 对人意味着 | 人做什么 | 系统做什么 |
|----|------------|----------|------------|
| **绿** | 放心做项目开发、下任务 | **什么都不用做** | 旁路继续巡检 |
| **橙** | 轻度噪声/偏紧，**不挡开发** | **忽略** | 可记日志；不打断 |
| **红** | 系统/平台有问题 | **一键复制 → 交给对话 Agent** | **优先后台自愈**；自愈失败才升红 |

- 运维红灯 = **系统代码/配置/服务问题**；不懂代码的用户不需要理解细节，靠 Agent。  
- 红灯复制包 = 人话标题 + Agent 可执行字段（服务/主机/端口/探针码/建议动作）；**禁止**甩原始日志墙当唯一出口。  
- 首页验收：打开运维首先看到 **大灯 + 一句人话**；绿 → 关掉去干活；红 → 复制交 Agent；无红则告警区空。  
- 排版原则：少字、大人话、强对比灯色；详情折叠；**禁止**做成运维工程师控制台。

### 人看四域 + 后台喂灯

**人看（Desktop 可见）**

| 域 | 含什么 |
|----|--------|
| **① 总健康** | 一颗总灯 + 一句「可以开发 / 请交给 Agent」——**首页唯一主叙事** |
| **② 集群与服务** | 双机（M1 / 2017）、Hub·Engine·Board·sidecar·隧道、**端口**矩阵、launchd |
| **③ Agent 与 MCP** | 对话 Agent / 模型通道 / **MCP** / 工具模式；OpenCode·Claude 执行器是否可用 |
| **④ 告警条** | **仅红色**；每条人话 + **复制给 Agent** |

**后台（喂总灯，不抢首页）**：变更审查（日 diff/docs）、意图飞轮（regress/探针）、容量（headroom/残留）、自动止损（reap/patrol）。能自愈不上红；偏紧可橙；失败或权威红线升红。

**不是运维主业**：数各仓 backlog（归编排/右栏）；invent；代替对话定意图；平台改码（仍只认 Cursor）。

### 四类活（旁路自动化 · 用现成脚本）

| 类 | 做什么 | 实现 |
|----|--------|------|
| **供弹** | 合法 epic 进业务仓 backlog | 日 diff / 文档债 / regress；Hub adopt 仅例外 |
| **清战场** | hang 后脏、OpenCode 残留 | Engine hang/reap；板面 abnormal/僵尸归档归 Cursor/Desktop；幽灵轨清 flow/last_epic |
| **护装备** | 探活、资源、权威巡查、端口/集群 | `_ops_probe` / host-resources / `ccc-authority-patrol` |
| **回传** | 健康聚合 + 红灯 copy_payload | Hub Ops Health API（演进自 `/api/ops/summary`）+ Desktop 总灯 |

定时用 launchd 旁路（`install-ops-plist.sh` / regress plist）；**禁止**把日审/文档/patrol 塞进 Engine tick。

### 供弹铁律

1. **仅** `~/.ccc/workspaces.json` 中 `engine=true` 且非 orch 的业务仓可收 `ops-auto` / 日审卡。  
2. **禁止**往 CCC orch 建弹药卡（Engine 不消费 orch；平台修仓只认 Cursor）。  
3. 空闲优先产品 epic（`next_product_goal`）；禁止无风险时用卫生/烟测刷板。

### 日审 apply 白名单（A–J）

| 决策 | 自动 `--apply` 建卡？ |
|------|----------------------|
| A / B | 否（可推水位） |
| **C / E / F** | **可**（业务仓；去重） |
| D / G / H | **否**（升红 / 人闸经 Agent） |
| **I** | **永不**（invent 硬关） |

脚本：`ccc-daily-diff-review.py`、`ccc-daily-docs-review.py`（docs 仅 medium+）。默认 dry-run；生产机 `install-ops-plist.sh install --enable --apply-ammo`。

### 运维 UI / API（产品契约）

- Desktop OpsView / Hub `#/ops` = **人看四域**；总灯优先，不以舰队数卡为主叙事。  
- API：`GET /api/ops/summary` 顶层含 `severity`（green|amber|red）、`human_line`、`alerts[]`（仅 red + `copy_payload`）、`domains`（cluster / agent_mcp 占位 / capacity）。合成：`_ops_probe.ops_health_envelope`。M1 sidecar/MCP 由 Desktop 本机合并进总灯。  
- 采纳/apply 是例外通道，默认 workspace **不得**是 CCC。`board/roles/ops.py` 不升格为总调度。

---

## 从零测 ccc-demo

1. 对齐基线 → 空板 + live `as_of`。  
2. 定稿转任务 →「刷新看板」见在飞 work。  
3. Hub 断 → 明说不可达。  
4. 业务仓工程师模式 → 拒。

板面重置归档：`apps/ccc-demo/.ccc/archive/reset-2026-07-21/`。

---

## OpenCode 生命周期与「倒卡堵槽」（硬 · 2026-07-22）

| 事实 | 口径 |
|------|------|
| **同仓 1 路 OpenCode** | `try_acquire_opencode_slot`：同 workspace 互斥（防 `opencode.db` locked）。与跨仓 `MAX_CONCURRENT≈3` **正交**。 |
| **三任务并发 ≠ 堵死** | 三仓各一路可并行；同仓排队是设计。倒 20 张进 planned **不会**本身堵死槽——槽被占是因为**这一路不退出**。 |
| **真问题** | OpenCode CLI/node 孙子在任务结束后残留；`.ccc/pids/*.pid` 只认 runner，死 runner + 活 opencode → 同仓永久「忙」。 |
| **收尸** | `scripts/_opencode_reap.py`：runner EXIT / `.done` / hang-auto / 周期 sweep 必 reap `--dir <ws>`；死 pid 文件**不**保护孤儿。 |
| **效率埋点** | `opencode_start` / `opencode_done` → `<ws>/.ccc/stats/events.jsonl` + `~/.ccc/stats/opencode-timings.jsonl`（`duration_s`/`wall_s`/`complexity`/`duration_min`）。 |

禁止把「一次倒很多卡」当成 OpenCode 卡死的主因；排障先看残留进程与 `opencode_done.wall_min`。

**主机资源曲线（并行容量）**：Engine 每 ~60s 写 `~/.ccc/stats/host-resources.jsonl`（load_ratio=load1/ncpu、mem%、`active_dev`/`opencode_n`）。看 `python3 scripts/ccc-host-resources.py summary` 或 Hub `GET /api/ops/resources/history`：`headroom` 才考虑 `MAX_CONCURRENT+1`；`saturated` 先治挂死/残留，勿盲目加并行。同仓仍 1 路。

### 产线提效综合方案（硬记 · 2026-07-22 → 落地）

> **状态**：方案已定并落地平台代码（P0 止损 + P1–P5）。指针：[`../briefs/2026-07-22-opencode-lifecycle-stall.md`](../briefs/2026-07-22-opencode-lifecycle-stall.md) · 效率基线 [`../briefs/2026-07-22-stress-efficiency-eval.md`](../briefs/2026-07-22-stress-efficiency-eval.md)。  
> **禁止**把下列症状再误诊成「倒卡太多 / 只加 MAX_CONCURRENT」。

| # | 症状（实锤） | 根因线索 | 落地（平台） |
|---|--------------|----------|--------------|
| A | 无 `opencode run` 进程，日志仍刷「同仓已有 active opencode」 | `engine-active-tasks` / 槽位认死 runner；`.done` 已落但未出 `active_tasks` | **done→收口→释槽**；死 pid / `.done` 不挡同仓；slot 释幽灵 |
| B | `.done`+exit 0 仍卡 `in_progress` | `result.json` 被日志污染 | runner **纯 JSON** + `*.exec.log`；`_result_json` 防御解析 + `dirty_result` |
| C | 卫生卡 `executor=python` 仍进 opencode | 短路径失败后 fallback | **硬失败**不得进 opencode；`dev_path` 事件 |
| D | Engine CPU 0%、planned 全延后；**gate_wall≈200s 空等** | testing 同步堵 tick；`max_per_tick=1` + 每 60s 才审 | 限张/限时；**先 launch 再 testing**；**每 tick 抽 testing**；短路径优先；默认 `max_per_tick=4`（gate-clean 2026-07-23） |
| E | verdict FAIL+revert 冲突停仓 | 半截 `git revert` | 失败必 abort；冲突 skip + failures |
| F | 「能否加并行」无据 | 缺忙时曲线 | `host-resources`；默认 `MAX_CONCURRENT=4`，忙时≥30 点 + headroom 再试 5 |

**验收**：缩小压测后 queue_wait 降、无半截 revert、跨仓 launch 不被一仓 testing 卡死、`duration_s` 可统计、卫生卡 path≠opencode。

### 压测 KPI 闭环（硬 · 2026-07-23）

> **目的**：用**量化门禁**把「压测 → 对照 → 优化 → 再压」做成标准流程；先打通 `ccc-demo`+`qb`，再复制到已注册旧仓/新仓准入。  
> **SSOT**：[`../../references/stress-kpi-scorecard.json`](../../references/stress-kpi-scorecard.json) · 流程：[stress-kpi-loop.md](stress-kpi-loop.md) · 脚本：`ccc-stress-kpi-loop.py` / `ccc-stress-kpi-gate.py`。

| 层 | 自动化 | 说明 |
|----|--------|------|
| 量测 / 门禁 / 再投递 | 脚本 | `init` → `dispatch` →（1h）`evaluate` → `continue` |
| 定时唤醒 | Cursor loop | `arm-wake` → `AGENT_LOOP_WAKE_stress_kpi` |
| 改码 | **仅 Cursor** | 只动 scorecard `code_change_allowlist`；每轮 ≤2 个 primary_fail |

**轮次**：推荐 **4**、上限 **5**。未过核心门禁不得宣称流程打通。  
**queue 口径（R5 · 硬）**：主门 `queue_wait_p95` 只计**独立卡**（排除同 epic 串行后继 `-w2+`）；全量 p95 为观测门（≤900）。同仓 1 OpenCode 下依赖链等前驱是设计地板，禁止用加 `MAX_CONCURRENT` 刷全量 p95。  
**禁止**：加 `MAX_CONCURRENT` 当主药；无 Cursor 无人改产线；观测门 `duration_s_fill` 失败却标 PASS。

---

## 文档怎么读

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| **1** | **本文** | 路径 / 权威 / 共识 / 价值立场 |
| 2 | [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) | 过桥 |
| 3 | [`desktop-agent-handoff.md`](desktop-agent-handoff.md) | 接入 |
| 4 | [`desktop-agent-identity.md`](desktop-agent-identity.md) | 口吻 |
| 5 | [`stress-kpi-loop.md`](stress-kpi-loop.md) | 压测 KPI 准入闭环 |
| 史 | [`m1-no-second-tree-closeout.md`](m1-no-second-tree-closeout.md) | 清扫记录 |

总索引：[`../INDEX.md`](../INDEX.md)。

---

## 禁止

- M1 业务第二树当权威  
- 讨论 Agent SSH 写 2017 / 扮演 product·dev  
- 过期 baseline 否定 live 看板  
- 业务仓工程师旁路  
- 共识只留在聊天、不落本文  
- **把 Desktop Plan 门禁当成 Cursor 能力上限**；**Cursor / Desktop 人格串台** 

## API

`GET /api/desktop/lens/{id}/board|tree|file|grep|git/summary`
