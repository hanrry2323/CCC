# Loop Engineer — 事实权威与人机共识（SSOT）

> **状态**：现行 · 2026-07-28（**四席工具定死** + **双轨业务 qb∥QuantHive** + **Relay 付费-only Go 单活跃钥** + 三层/loop-code + Hub 隧道 `:17777`；M1=对话 / 2017=编排）
> **谁读**：老板 / Desktop Agent / Hub·sidecar / Cursor 改平台。  
> **冲突时以本文为准。** 边界流程：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> **规则**：你我共识 → **写入本文（或明确指向本文的一节）** → 再改代码/人格；禁止只留在聊天里。

---

## 一句话（开发路径）

**人定意图 → Hub 下达 → Engine 编排扇出 → 权威仓写码 → 验收纠错 → 回流飞轮；全程只认一个权威仓。**

（叙事：[`../VISION.md`](../VISION.md)。）

---

## 四席工具定位（硬 · 2026-07-28）

同模型（Relay `flash`）**不**改变分工——靠角色约束，不靠比智力。通道：[`dev-channel.md`](dev-channel.md)。

| 席位 | 职责（定死） | 禁止 |
|------|--------------|------|
| **Cursor** | **CCC** 合入权威；**QuantHive** 主力开发合入；平台/双轨对照改文档 | 不当运维主入口；不当知识库主入口 |
| **Claude Code**（个人 CLI） | **①** 本机 CCC/relay/launchd 养机；**② QuantHive 日常维护**（交易侧运维，非合入大功能） | 不当 CCC/QuantHive 合入 IDE；不扛新功能主路径；不冒充 Desktop；**不**用 CCC 产线改 QuantHive |
| **OpenCode** | **仅** Engine 写码执行器（2017 `--dir`；**qb** 等走 CCC 的仓） | 不当个人主力 IDE；不改 CCC 合入；不做人设聊天；**不**当 QuantHive 开发 IDE |
| **Codex**（ChatGPT.app） | **知识管理 + 闲聊**（双轨分域记，禁止混成一个项目） | **尽量不开发**：不改 CCC / qb / QuantHive 权威仓 |
| **CCC Desktop** | 意图门 / 看板 / 下达 / 态势（**qb 与其它挂 CCC 的仓**） | 不当第三套 IDE；不当知识库主入口；**不**管 QuantHive 开发主路径 |

**串台禁令**：

1. CCC / QuantHive **开发合入** → **Cursor**。  
2. 本机养机 **或** QuantHive 日常维护 → **Claude Code**。  
3. 知识整理 / 闲聊 → **Codex**（qb 与 QuantHive **分路径**落盘）。  
4. **qb**（及挂 CCC 的仓）产线意图 / 定稿下达 → **Desktop**。  
5. **qb** 等业务仓批量写码 → **Hub→Engine→OpenCode**（不是个人 OpenCode IDE）。  
6. **禁止** Claude Code / Codex / 个人 OpenCode 当 CCC 合入工具。  
7. **禁止**把 qb 与 QuantHive 当同一系统或互为别名；**禁止**用 CCC 编排「接管」QuantHive。

主机指令落盘：`~/.claude/CLAUDE.md` · `~/.codex/AGENTS.md` · `~/.config/opencode/AGENTS.md`（M1 与 2017 同文）。

---

## 双轨业务：qb ∥ QuantHive（硬 · 2026-07-28）

> 两套都是量化，**完全独立**。同步跑，是为了对照「CCC 自动化产线」vs「Cursor 开发 + Claude 维护」两种方式。禁止合并仓库、禁止知识库混成一个项目、禁止用一套流程替代另一套。

| 项目 | 定位 | 开发 | 日常维护 | 与 CCC |
|------|------|------|----------|--------|
| **qb** | CCC 产线养大的**单机 VIP 套利引擎**；开发收口后走**自动化维护**对照 | **CCC**：Desktop 定意图 → Engine → OpenCode；平台本身用 Cursor | 收口后：飞轮 regress + 板务 + bugfix epic | **绑死**：权威仓在 2017，只经产线改码 |
| **QuantHive** | **更单纯**的交易达成路径 | **Cursor** 把功能开发出来 | **Claude Code** 日常维护即可跑日常交易 | **独立**：不依赖 CCC 也能跑；**禁止**强行灌进 Hub/Engine 主路径 |

| 项 | 口径 |
|----|------|
| **给谁** | **仅个人**（不做多用户卖点 / 不做对外产品化主路径） |
| **对照实验** | qb = 测 CCC 叠加自动化的代价与收益；QuantHive = 测薄工具链能否稳定交易 |
| **CCC 侧成功（开发收口前）** | qb 硬意图走完 LPSN；**且**域门 **B4.2 实盘人确认** + **B5 回测可视化** 绿 → **开发阶段结束 → 维护态**。**禁止**用 `released`/VERSION/开源星数冒充业务完成或能盈利 |
| **维护态（收口后默认）** | 只认：regress 回归 epic、生产 bugfix（人确认下达）、板务 `hub_repair`。**默认拒**新功能/扩所/跨机/开源公开；须人 `supersede_goals` + 新 L1 goal |
| **QuantHive 侧成功** | Cursor 交付 + Claude 可维护 → **日常交易可用**（证据链自管；不套 CCC `intent_stable` 冒充） |
| **停做** | Ops/SPA 抛光主路径；多厂商通道花样；invent；自动 `intent_stable`；把两轨揉成「一个量化大脑」；用 GitHub 星评 qb |
| **下一开程（CCC）** | qb **开发收口**：B4.2 实盘人确认 + B5 回测可视化 → 进入维护态（非 Ops 抛光；非开源排行榜） |
| **知识脑（Codex）** | HP 分域：`domain=qb` / `domain=quanthive`；memory `/codex/topics/qb/` 与 `/codex/topics/quant-hive/` **分树**；交叉对照只写 `/codex/cross-ref/` 且标明「对照非合并」 |
| **心智入口** | 路径五句 + **双轨独立** + qb 收口合同 + Go 单活跃付费。其余 brief 当附录 |
| **域门 SSOT** | [`../briefs/2026-07-27-qb-domain-ship-gate.md`](../briefs/2026-07-27-qb-domain-ship-gate.md)（B1–B5） |

---

## 模型通道简规（硬 · 2026-07-28 · 付费-only）

| 项 | 口径 |
|----|------|
| **Relay 角色** | **薄垫片**：Anthropic↔上游翻译 + `thinking` 关 + 固定打当前启用的 Go 付费钥。**不是**多厂商调度站 |
| **上游** | **仅** OpenCode Go · `https://opencode.ai/zen/go/v1` · `deepseek-v4-flash` |
| **免费钥** | **全部禁用/不进启用池**（Zen free / GLM / big-pickle 等）；**MiniMax 等已退役，禁止复活** |
| **付费钥** | 配置可留 **2** 把备份；**运行时 `enabled=true` 恰好 1 把**；禁止同会话双付费自动 RR |
| **换钥** | 额度/费用用尽 → **人通知后手动**改 `enabled` + kickstart；不做自动切备份 |
| **KPI** | `upstream_cache_token_ratio=cached/prompt`（活跃付费会话目标 **≥0.9**） |
| **手册** | [`../relay/KEY-POOL.md`](../relay/KEY-POOL.md) · 钥只在 2017 `~/.ccc/relay/` |

---

## 双 Agent 人格独立（硬 · 2026-07-22）

| | **Cursor（平台开发）** | **Desktop Agent（对话面）** |
|--|------------------------|------------------------------|
| 在哪 | Cursor IDE · 本仓 `/Users/apple/program/CCC` | M1 App · sidecar → loop-code |
| 职责 | **改 CCC 平台**：读/写/跑测/提交/排障，完整 IDE 能力 | **定意图**：对齐事实、定稿 epic、转任务；默认 Plan（硬禁写业务仓） |
| 人格 SSOT | 本仓 Cursor 规则 + [`dev-channel.md`](dev-channel.md) | [`desktop-agent-identity.md`](desktop-agent-identity.md) + `hub_voice.py` |
| 工具门禁 | **无** Desktop discuss allowlist；不受 Plan「不写码」约束 | **默认 engineer**（可写本机 CCC + 全套 Hub 含板务）；显式 discuss=只读；业务改码仍 transfer→Engine |

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
| 战略讨论 / 点**转意图卡** / 切看板 | Hub 连通、投递、重试、卡死恢复 |
| 立刻关 sheet、徽章 `queued`、可继续聊 | 入本机 outbox；**sidecar 常驻 flush** → Hub；成功写 `transfer-receipts.json` |
| 看板始终画列（可空） | 拉板失败保留快照 + 短超时，不整页死白 |

**意图卡供给闭环（硬 · 2026-07-29 · v0.64）**：

> 人只确认「要做成什么」；Agent 起草意图卡；**系统 `transfer_gate` 不过绝不进代办**。  
> **转意图卡 ≠ 定代办**；自动进代办 = 放行，不是跳过质控。代办卡 = Engine 开工令（OpenCode→审测）；**卡错则全错**。

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **人** | 战略收敛后**显式**点「转意图卡」；只审白话意图/验收 | 不审路径/pytest；不手写代办；未谈妥不乱点 |
| **Agent** | 人触发后按 [`../../references/intent-card-sop.md`](../../references/intent-card-sop.md) 起草 L1；可查 HP/社区；读 lessons | 禁未触发自转；禁 invent；禁 gate 红仍推进代办；禁开场运维说教 |
| **系统** | 契约过 `transfer_gate` **仅绿**才 auto transfer→backlog+wake | 禁见结构化块就入队；override 须显式+`human_note` |

流程：战略讨论 → 人点转意图卡 → Agent 写 L1 `planned` → gate → 绿则自动进代办；红则卡留意图层 + `fix_hint` 改卡（改「要做成什么」须再问人）。

**Agent 定方案（硬）**：**战略规划优先**（方案/路线/风险白话；可查 HP 知识库与社区资料）；板务仅在挡讨论/挡下达时静默自清。按用户意图给**最佳方案**并默认推进；**禁止**每轮甩拍板选择题、**禁止转意图卡后再问要不要入队**。仅当真缺不可逆信息才最多 1 问。白话给人看；契约折叠进块，不把 tid/路径当结论。**板面残卡清场**归 **当前 Desktop App Agent**（`hub_repair`），**禁止**默认逼卫生 epic，**禁止**甩锅「请打开编排运维」。偶发卫生卡：`executor_intent=python`；`pipeline=ops` 仍扇出。abnormal / 未核账在飞残卡禁止重复下达同目标（须先清板或人 override）。

**Desktop App Agent 全功能（硬 · 2026-07-24 · 1A/2A）**：

| 项 | 口径 |
|----|------|
| **单一人格** | 每个 Desktop 项目卡（含 `ccc`）同一套全功能 Agent；**取消**「业务只讨论 / 板务唯一交 ccc」分轨 |
| **默认权限** | **engineer**：本机可改 CCC 平台仓；全套 Hub（透镜 / mind / **跨仓 hub_repair**） |
| **业务改码** | 仍只经 **定稿 → transfer → Engine**（1A）；禁 M1 业务第二树；禁 sidecar `ssh` 写业务仓 |
| **`ccc` 卡** | **平台仓入口**（UI 可称「CCC 平台」）；能力与业务卡同级，**非唯一运维人格** |
| **板务** | **当前会话自己清**；禁止「请打开编排运维」当主路径 |

**对用户（硬 · Cursor 级语感）**：短人话先结论；自己跑透镜/心智/**板务**；**禁止**把 `transfer-outbox` / Terminal / Hub CLI / 执行器黑话教给老板；平台词只进 `ccc-transfer` 块内。板堵 → **本会话 `hub_repair`**，不甩锅。

**Desktop 对老板（硬 · 方案与路线）**：老板不懂技术；正文只聊要做成什么 / 取舍 / 风险 / 白话验收；**禁止**把对话变成技术问答或甩 `src/`、类名、`pytest`、hub 工具名。定方案前静默 `hub_modules`→`hub_locate`/`hub_grep`→`hub_file`（未核实禁断言有无）；核实过程不进正文。`plan_md` 须与 `goal` 同向——`transfer_gate` 拒收 `plan_goal_conflict`（如 goal 要 CLOSE、plan 写「交给上层」）。**对标/评分**：禁止以 GitHub 星/社区当主轴；禁止默认「开源公开」当收口；谈 qb 成熟度对齐 **B4.2 实盘人确认 + B5 回测可视化**；Redis/plist/Grafana 等禁进正文。

**意图卡人话 + 审查回流（硬 · 2026-07-29）**：点意图卡 /「讨论方案」→ Desktop 自动发「先人话翻译」提示；Agent **首轮** 2～4 句白话（禁路径/`ccc-transfer`）。谈妥 → 人点**转意图卡** → Agent 起草 L1 → gate 绿自动进代办（`title`/`goal` 对齐卡原文）→ L1 **`dispatched`**，右栏意图卡链更新。CCC 全绿 → `probed` **收口在运维页**；人点标记稳定 → `stable`。人偶发粘贴审查报告 → Agent 白话归纳 → **优化意图卡**（可 `supersede_goals`）。人格：`hub_voice`「意图卡 · 首轮翻译」「审查报告回流」。

#### Desktop 主路径（硬 · 2026-07-29 · 意图卡两段）

```text
战略讨论（自由聊；可查 HP/社区；对齐基线=可选）
  → 人点「转意图卡」（认白话意图）
  → Agent 按 intent-card-sop 起草 → 写 L1 planned
  → transfer_gate 绿 → 自动进代办（outbox→Hub epic→wake Engine）
  → 红 → 意图卡停留 + fix_hint 改卡（零 OpenCode）
```

| 环节 | 人 | Agent / 系统 |
|------|-----|----------------|
| 战略讨论 | 自由聊 | **方案优先**；可查知识库/社区；可选「对齐基线」；**禁止**开场运维说教 |
| 对齐基线 | 可点；**非硬门槛** | Hub baseline + live lens；残卡 → 本会话 `hub_repair` |
| 看仓况 | 可选芯片 | lens；**不是**下达必经 |
| **转意图卡** | 显式一点 | 收敛门：未谈妥拒转；出契约；写 L1；**不是**直接定代办 |
| **gate→代办** | 不审技术字段 | 仅绿 auto transfer；红停意图层 |
| 入队后 | 继续聊 | `task_dispatch`+wake；看板计数看状态；右栏**不**堆 work 拆解卡 |

- **不用对齐基线、直接聊 → 转意图卡：放行**（gate 不查 baseline；仍查探针/scope）。
- **「下一步」不是必经阶段**。
- 禁 `ssh`；能力靠透镜 + **本会话** `board-repair`。
- **凡进 backlog 的 epic 须 wake Engine**；超时无 fanout → 自动自愈。

#### 编排自愈硬指标 + 业务仓 main 提交（硬 · 2026-07-29）

> 大卡经人确认进入看板后，扇出→写码→审测→失败收尸/有限重试必须自动；**卡死/失败无人介入可恢复是 CCC 基础指标**。禁止以「请用户复制给对话」为修板主路径。业务仓提交在 **main（当前分支）**，Cursor 不做逐卡合入闸。

| 项 | 口径 |
|----|------|
| **提交** | Engine/DoD 在业务仓**当前分支（默认 main）**提交；`task_id`/`phase` 进 message；**不做** feature 旁支合入门禁；Cursor **事后总验**不挡产线 |
| **进板后** | 人只确认下达；之后扇出/写码/审测/hang 收尸/有限 reopen **全自动** |
| **自愈分层** | **L1** Engine：`pending_no_fanout` 有限重扇出 + hang 收尸 + 瞬态 abnormal 有限 reopen（不抬预算）+ wake；**L2** Hub/`board_repair`：`clear_blockers` 先 reopen 可恢复再归档 permanent/failed/孤儿；**L3** Desktop/sidecar 清板 SOP 钩子；**L3b** 耗尽后 Agent **改大卡再开**（读证据→按失败桶优化 `ccc-transfer`，意图不变；见 [`../../references/post-exhaust-epic-optimize-sop.md`](../../references/post-exhaust-epic-optimize-sop.md)）；**L4** 人仅红灯/改意图。**总闸**：[`../../references/abnormal-solve-sop.md`](../../references/abnormal-solve-sop.md)——**清障 ≠ 解决问题**；结案=根因消除且意图可再验收（已绿则结算，勿空投） |
| **Agent 定卡培养闭环（硬 · 2026-07-29）** | 培养 Desktop Agent 定**意图卡**/纠板，**禁止**靠 Cursor 反复救火。① **入学考试**：`transfer_gate` 拒弱探针/假绿/`plan` 无 `## 验收`/过宽 scope/**验收>3 条**/**unit+paper混装**，返回 `fix_hint`；② **失败记忆**：`decided.transfer_lessons[]` + digest；③ **处方改卡**：`failure_pack.optimize_hint`；④ **qb 反模式** + **[`../../references/intent-card-sop.md`](../../references/intent-card-sop.md)**（快捷「转意图卡」注入；旧名 `finalize-transfer-sop.md` 重定向）。禁 invent / 禁抬重试 / 禁自动 stable；**耗尽回流新意图卡**（须人再点转） |
| **禁止** | 新修板 UI 当主路径；invent；自动 `intent_stable`；无限重试同一烂卡；**耗尽后只藏卡不改大卡**；**先 `ui_hidden` 还可重试的 abnormal**；用 Cursor/Zed 当业务仓合入通道；**用「已归档/已 reopen」当向老板的完成话术** |
| **SOP** | 总闸 [`../../references/abnormal-solve-sop.md`](../../references/abnormal-solve-sop.md) · 清板 [`../../references/board-auto-repair-sop.md`](../../references/board-auto-repair-sop.md) · 耗尽改大卡 [`../../references/post-exhaust-epic-optimize-sop.md`](../../references/post-exhaust-epic-optimize-sop.md) · **Commit/文件夹卫生** [`../../references/commit-folder-hygiene-sop.md`](../../references/commit-folder-hygiene-sop.md)（脏树三分法；噪音不挡；禁 `git add -A`；禁卫生 epic 主业） · **垃圾卡硬清** `scripts/_board_garbage.py`（探针/戳记/`regression-*` 移出看板；regress **无意图探针不建回归卡**；禁脏树 alone 炸板） |

#### Desktop 板务 · App Agent 本职（硬 · 2026-07-24 · 全功能）

**看板维护是当前 Desktop App Agent 的本职**（任意项目卡，含业务与 `ccc`）。Engine 跑挂/退出留下的 `abnormal`/残卡/幽灵轨/**孤儿 running** → 经 Hub **`POST /api/desktop/board-repair`**（`hub_repair`，**可跨 project_id**）清场，**绝不**写业务源码。平台小改可对本机 CCC 走 engineer（Write/Edit）；深改仍认 Cursor。

**编排异常**（右栏 stopLoss / failed / abnormal）：系统**自动**注入 SOP 交 Agent（或 Engine 先确定性清），**禁止**把「复制给对话」当必经人机步骤。

死循环禁区：板堵 → ready=false → 下不了新产品 → Agent 甩锅「请打开编排运维」或甩卫生 epic / Terminal outbox → 老板又当运维。**破法**：**自动自愈 + 本会话 `clear_blockers`**，报告板面数字。

| 允许 | 禁止 |
|------|------|
| 归档/隐藏：`abnormal`、failed epic、已 `done` 僵尸、**孤儿 running**（子卡缺失/无在途） | 写业务仓文件 / plan 白名单外改码 |
| 剪幽灵轨：`last_epic` / `epic_history` / flow-events | invent / ops-auto 自造产品卡 |
| 瞬态 abnormal 有限 reopen（对齐 failure-learning） | 对 CCC orch 投**业务** epic（R-15） |
| 审计日志；本机改 CCC 运维脚本/配置 | Engine 卫生 epic / 教用户手写 outbox 当清场主路径 |
| | 「请打开编排运维清板」当默认主路径 |

**清 abnormal / 沉底孤儿 running 不等人审**。人审只在定稿确认 / inbox 采纳。

未 ready：仅业务脏 / 真在飞冲突时拦新产品 epic（人可 override，记 `human_note`）。

运维红灯「复制/交给 Agent」→ **打开当前选中项目会话（或 `ccc` 平台入口）**并带入告警摘要；**不**暗示只有 ccc 能修。

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
| **项目脑包** | CLAUDE 定位/铁律 + 规划文 + profile + decided 摘要 | **权威仓文件 + Hub 编译注入** | 见下 · qb 样板 |

- API：`GET/PUT /api/desktop/mind/{project_id}/…`（digest 含 `brain`）；sidecar **每轮**注入，与 live board **并行拉取**，本机短缓存（约 20s）降隧道往返。
- 新鲜度：`live board / lens git` > L1 digest/brain > 聊天 resume。
- 不复活 invent；心智沉淀 ≠ 自动投 backlog。
- Hub 断 / 隧道断：明说 L1 不可达，**禁止**用聊天 resume 编造在飞；转任务仍可 outbox。

### 项目脑包 · qb 样板（舰队标准 · 硬 · 2026-07-24）

按项目隔离 Agent 知识 = L0 通用壳 + **按 `project_id` 注入权威仓脑包**。SSOT 清单：[`project-agent-brain.md`](project-agent-brain.md)。

| 角色 | 认领落点（不新造） | 说明 |
|------|-------------------|------|
| 定位 / 铁律 | 根 `CLAUDE.md` | 必含「项目脑索引」三行 |
| 规划 / 未来待办 | 规划文（qb=`docs/DEV_PLAN_v1.1.md`；其它仓可等价名，CLAUDE 声明） | **禁止**平行根级 `TODO.md` 主路径 |
| 当前产品意图 | `.ccc/agent-mind/decided.json` `goals[]`（须 `exit_condition`） | LPSN · `next_product_goal` |
| 共识 / 约束 | `decided.constraints` + CLAUDE 铁律 | |
| 档案 / 双机 | `.ccc/profile.md` | |
| 开发过程 | `.ccc/board/*` | **看板≠未来目标清单** |

`AGENTS.md` / 薄 `STATUS.md` **不升 SSOT**。`ccc` 平台入口会话不灌业务规划文当产品搭档。其它仓改造只许映射等价路径，抄 [`project-agent-brain.md`](project-agent-brain.md) Rollout 表。

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
- **审测按卡型适型（硬 · 2026-07-23 → 2026-07-29）**：先认 `dev_path`（script_seed / feature_seed / **util_probe** / board_ops / doc_only / opencode），再认 diff 行数。短路径 = py_compile + 验收重放 → 写 verdict，**不进 600s LLM**；真代码 medium/large 仍 LLM。**`util_probe`**：单文件 `scripts/*_probe.py`（含 open-intent）+ 白名单验收 → 确定性审测，**不受** `complexity=medium` floor 抬成 LLM（R8 空 verdict）。禁止 plan-only PASS；lock skip 写 TIMEOUT。tester 缺 PASS verdict 不得 verified；短路径不强制 cov；plan 已有验收探针时 tester **不得**再追加全仓 `--cov`（R7）。
- **验收强度（硬 · 2026-07-29）**：业务卡禁止 **existence-only**（仅 `test -f`/`test -d`）当真绿；须 ≥1 条 behavioral（`python3 -c` assert / DRY_RUN / scope pytest / `grep -q`）或 compile。模块 `_acceptance_strength`；plan_lint / `check_acceptance` / engine「acceptance_ok 跳全仓 pytest」均认强度。ops/卫生/doc_only 豁免。`released` ≠ 盘上真绿。FAIL→revert 是设计止损，假红先修门禁。
- **L0 / L1 分拆（硬 · 2026-07-23）**：**L0** = 可重放验收 / 短路径确定性（总闸，不过不进 L1）；**L1** = opencode 真代码语义审（Claude 副闸）。禁止把 Claude 当 testing 默认总闸。
- **失败学习 R1/R2/R3（硬 · 2026-07-23）**：FAIL 打回前写 `.ccc/pids/{tid}.review_fail.md`；revert 后 phases 对齐；dev prompt 注入失败摘要。`review_fail_loops≥2` 或 plan_gap → **R2 修订该 work 的 plan**（禁止盲重试原指令；禁止 epic 子卡 product regen）。≥3 → R3 quarantine。**enabled 下**：瞬态 abnormal（非 permanent / 非 loops 耗尽）可有限次自动 reopen→planned（每卡 ≤2；须 work 卡 + 业务仓；禁止 invent/orch）；永久类仍停 abnormal 等人/Cursor。本轮**不做** Ollama / 新 coding CLI。
- **hang 归类（硬 · 2026-07-24）**：验收探针 exit **124** / wall `TimeoutExpired` / 输出含 `HANG_DETECTED` → acceptance reason 与 quarantine `reason.txt` **必须**含关键词 `hang_detected`（禁止只写 `acceptance_cmd_failed` 污染 abnormal 统计）；hang auto-restart 耗尽同理。failures ledger `related_stats_event=hang_detected`。跨顶层目录（≥2 roots，如 src+dashboard+tests）phase fan-out **强制串行**，禁止并行写码。
- **hang 收尸让下一卡（硬 · 2026-07-24 · 方案 A → 2026-07-29）**：无进展默认 **300s**（`CCC_PHASE_NO_PROGRESS_SEC`）；CPU hang 检查间隔 **120s**；同卡 hang 重试 ≤**1**。kill 优先 **killpg(session)**（`engine/process.py`）。`no_progress` **先 salvage 再 kill**；kill+reap 后 opencode 仍在 → **禁止 relaunch**、释槽；有 `.hung` 时 orphan reap `max_age_sec=0`。stash/kill/relaunch 失败也必 orphan-reap + 释槽；耗尽 quarantine 后再 reap。释槽后**同 tick**优先 `_try_launch_planned`。仍同仓 1 路 OpenCode，不加 `MAX_CONCURRENT`。
- **seed 扇出快路径（硬 · 2026-07-24 → 2026-07-29）**：定稿已挂 plan+phases 时 `fanout_from_seeded_epic` 跳过 Claude；child `## 验收` **禁止散文**，须白名单可重放探针（且业务禁 existence-only）。`plan_lint` 失败 → **`apply_fanout` 本地修验收一次**（seed 与 Claude 同路径），仍失败才回退 Claude。已拆 work 全 planned 且同仓有 in_progress → flow `queue_hint=same_ws_opencode`（排队 ≠ 扇出卡住）。
- **hollow 适型**：仅 OpenCode；优先扫本 phase stdout，避免历史 report 误伤文档 phase；script_seed/board_ops 不跑 hollow。
- **complexity=small** 仅表规模提示，**不** stub 跳过 reviewer/tester。默认 **medium**。多步回归/三件套（acceptance 可执行条 ≥3 或模块标记 ≥3）禁止 small——Hub `resolve_complexity` 会抬升；扇出对真回归不因 small 强制单卡。
- **运行时冒烟验收**：`.venv/bin/python` / `python3` + 显式 `DRY_RUN=true`；禁止裸 `python`。
- **VERSION**：kb 默认 **不** bump；仅 transfer/epic 显式 `bump_version=true`（或 tag `bump-version`）才升版+changelog+tag。
- **看板卫生归属（硬 · 2026-07-24 · 全功能）**：**板面残卡/僵尸 backlog/幽灵轨/孤儿 running 清场归当前 Desktop App Agent 或 Cursor**（Hub `board-repair`），**禁止**靠压测/日批投「看板卫生」Engine epic 当主路径；**禁止**甩锅「请打开编排运维」。`efficiency_six` **不含 e05**。若偶发仍有 scope∈`.ccc/board/**` 且 executor∈{python,auto,cli} 的卡，Engine 仍可走 board_ops 短路径（兼容），但**不得**用它替代平台清场 / board-repair。
- **卫生卡 seed（硬）**：验收白名单里出现的历史 `.ccc/plans/*.plan.md` **不是** adopt 引用；仅「见/参照/已写入 …plan.md」才收养。Transfer 写 `plan_md` 时须同步合成 phases（保留 `.ccc/` scope）。ops / `.ccc`-only **禁止**强制全仓 pytest（否则卫生卡必挂）。
- **止损清场**（Agent/平台排障）：failed epic + abnormal work 经 board-repair 归档/隐藏后，还必须清 `last_epic` / `epic_history` 与 `~/.ccc/flow-events.jsonl` 中该 epic（API `purge_flow` / `clear_blockers` 一体做），否则右栏 `bound_hint` 幽灵复活。**清板不删** `.ccc/stats/failures.jsonl`；隐藏前把 report/verdict/`review_fail` 等快照到 `.ccc/quarantines/<tid>/board-repair/`。short_path 耗尽进 abnormal 必须 `record_failure`。
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
| 平台生产三层出门 + 金路径 | [`../briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md) · Layer0/1/2；**Layer1 已出门（2026-07-28）**；证据 [`../briefs/2026-07-27-golden-path-evidence.md`](../briefs/2026-07-27-golden-path-evidence.md) |
| 业务域 KPI（qb 样板 · 非 CCC 冒充盈利） | [`../briefs/2026-07-27-qb-domain-ship-gate.md`](../briefs/2026-07-27-qb-domain-ship-gate.md) |
| 飞轮自动化（已实现 · 2026-07-28） | [`../briefs/2026-07-28-flywheel-auto-open.md`](../briefs/2026-07-28-flywheel-auto-open.md) · T1 seed / T2 probed / T3 人点 stable / T4 next_goal；规划 [`../briefs/2026-07-24-lpsn-flywheel-auto.md`](../briefs/2026-07-24-lpsn-flywheel-auto.md) |

平台只认这一条飞轮；扩 IDE / 堆角色 **不**填这个坑。  
**硬边界**：平台 Layer1 出门 ≠ 业务 Layer2 出门；`intent_stable` 只证明「意图探针稳定」，不证明实盘盈利或风控达标。qb **开发收口**另须域门 **B4.2 + B5**（见 qb-domain-ship-gate）。

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

## 三层架构与 loop-code 槽位化（硬 · 2026-07-25）

**分层（产品级定义）**：

```
① 前端层     Desktop App · :7788 页面 · （未来手机 App）
② 编排层     CCC 自研：sidecar(session_manager) · Hub · Engine · board.roles
③ 运行时层   可插拔 CLI 槽位（对话槽 / 写码槽）
```

**核心共识：`loop-code` 是槽位名（逻辑名），不是具体工具。**

| 项 | 口径 |
|----|------|
| 双槽定义 | **对话槽**（M1 sidecar 驱动）契约 = **claude-agent-sdk 兼容**（SDK `cli_path`；`-p`/`stream-json`/`--resume`/env）。**写码槽**（Engine 扇出）契约 = [`executor-plugins.md`](executor-plugins.md)（OpenCode 为默认件）。两槽契约独立，勿混用 |
| 对话槽候选 | 钉版 vendor 构建（现默认 · 已验证）· 原版 claude（同源 · 已验证）· 其他 Claude Code 兼容 CLI（如 Qoder CLI，**须先过 SDK 兼容验证**）· 未来 SDK 自建 runtime |
| CCC 专注 | **编排层 + 前端层**。能力增强（supervisor / 工人可视化 / 多 agent）一律做在②，**不下沉**到③ |
| ③ 保持哑运行时 | 只经文档化接口驱动；零槽位实现独有依赖（2026-07-25 已核实：sidecar 无任何 loop-code 独有调用，换 `cli_path` 即换实现） |
| 填槽门禁 | 契约兼容验证 + 钉版 + SHA256 + 配置家隔离（`~/.ccc/loop-code`）+ 凭证隔离（不碰个人 keychain） |
| 定位修正 | **勿再**把 loop-code 说成「能力增强 fork / 打通原版封闭功能」；vendor 构建价值 = 供应链稳定件。源码级定制须先过「可复现构建」门禁，且仅当②做不到时才考虑（取代 [`loop-code-ownership-cut.md`](loop-code-ownership-cut.md) 的「深度开发 loop-code」提法） |

**同仓多 agent 纪律（硬 · 2026-07-25 · 实战教训）**：同一工作树跑多个 agent 会话（Cursor / claude / loop-code / 工人）时——① 并行改码必须 **worktree 隔离**，否则只允许串行提交；② **禁止 `git add -A` / `git add .` 全量提交**，只 add 本任务明确改动的文件（2026-07-25 实例：except 清理会话全量 add 把并行会话的 7 个共识文档卷进 `356318e` observability 提交）；③ 提交前 `git status` 核对无他人改动混入。

## CCC Relay（硬 · 2026-07-25 · 中转站回归 + 深度整合）

推翻 v0.52「不恢复 ai-loop-router」口径。恢复中转站并入 CCC 仓为 **CCC Relay** 子系统。

| 项 | 口径 |
|----|------|
| **三档 tier = 全局契约** | `flash` / `Pro` / `code` 三逻辑名仍保留；**现行主对接仅 `flash`**。`Pro`/`code` **轮空**（无启用上游；`pro`→回落 flash） |
| **协议转换范围** | `:4000`(Anthropic) / `:4002`(OpenAI chat + **`/v1/responses`**) **都打同一 flash 池**；空 Pro 时客户端选 `pro` → relay 回落 `flash`。`/v1/responses` **仅**服务个人 Codex（知识/聊天席），**非** CCC 产线主路径 |
| **代码归属** | 已并入 CCC 仓 `relay/`(原 `~/program/ai-loop-router`);`dist/` gitignore,2017 本地 `npm ci && npm run build` |
| **M1 / 2017 双实例** | M1 `com.ccc.relay.m1`(同 sidecar 生命周期,服务桌面端);2017 `com.ccc.relay.2017`(同 Engine 生命周期,服务编排面);两实例独立 plist,各自 `~/.ccc/relay/upstreams.json` |
| **Flash 单通道 · 付费-only（硬 · 2026-07-28）** | Claude Code + OpenCode **一律** `flash` / `loop/flash`。启用池**仅** Go 付费 `zen/go/v1`+`deepseek-v4-flash`；配置可留 2 把，**`enabled=true` 恰好 1**（备份钥人切）。**禁止**免费 Zen/GLM/MiniMax 进启用池。**IP/HK `proxy` 退役**。详见上文「模型通道简规」 |
| **M1 对话路径** | sidecar / 个人 Claude Code → **2017 编排面 relay**(`http://192.168.3.116:4000`,共享 flash 池);可用 `CCC_ANTHROPIC_BASE_URL` 改回本机 `relay.m1`;默认模型 **`flash`** |
| **2017 编排路径** | Engine claude → 本机 relay(`AGENT_PLANNER_BASE_URL=http://127.0.0.1:4000`,flash);OpenCode dev → `:4002`（`OPENCODE_MODEL=loop/flash`） |
| **Go thinking 关（硬 · 2026-07-27）** | 所有 Go/`deepseek-v4-*` 上游须 `request_overrides: { "thinking": { "type": "disabled" } }`（主机 `upstreams.json`，不进 git）。默认 thinking 会令 OpenAI 兼容口 `content=""`、只填 `reasoning_content` → OpenCode 空转 hang。手册：`docs/relay/KEY-POOL.md`。 |
| **付费-only（硬 · 2026-07-28）** | **唯一启用上游**=`billing=opencode-go` · `https://opencode.ai/zen/go/v1` · `deepseek-v4-flash`。Go 钥误打 `zen/v1` 会假 401。免费/`zen-free`/智谱/MiniMax **不得** `enabled=true`。钥 SSOT=2017 `~/.ccc/relay/upstreams.json` + `KEY-INVENTORY.md`；手册=`docs/relay/KEY-POOL.md` |
| **单活跃钥 + 缓存（取代 PaidGuarantee/free-first · 2026-07-28）** | 无免费池、无付费自动 RR。单活跃钥即天然会话钉；亲和仍可用 `x-session-id` / system+首条 user。主 KPI=`upstream_cache_token_ratio`（目标 **≥0.9**；勿把 L1/`cache_hit_ratio` 当账单）。额度用尽 → **人通知后**启用备份钥、关掉旧钥 |
| **三目标（硬 · 2026-07-28）** | **快**（sole 跳 peek、不 short-cool 空转）· **缓存**（始终 Go prompt cache）· **稳定**（薄垫片+直连）；多钥 peek 仅 `LOOP_STREAM_PEEK=1`。手册=`docs/relay/KEY-POOL.md` |
| **冷却 / 限流（硬 · 2026-07-27）** | 429 + `Retry-After` >120s 一律按**日配额**冷却（采纳完整 RA，禁封顶 120s 反复撞钥）。`POST /admin/cooldowns/clear` **默认保留**剩余 >300s 的冷却；急救全清用 `?force=1`。列表：`GET /admin/cooldowns` |
| **OpenCode 默认（硬 · 2026-07-28）** | Engine/`ccc-engine.sh` 默认 `OPENCODE_MODEL=loop/flash`（本机 `:4002` → relay **flash** 同池）；`~/.config/opencode/opencode.json` 只留 `loop` provider；直连兜底 `opencode.direct.json`（禁 `$comment` 键） |
| **fail-open 红线(不可协商)** | relay 探活失败时客户端降级**真直连**:`CCC_RELAY_DIRECT_URL` 或 `~/.ccc/relay-direct.url`;**禁止**硬编码厂商 URL、**禁止**默认指回本机 `:4000`。**MiniMax-M3 已退役**(2026-07-26),未配置直连文件则只打日志、不假装成功 |
| **日常主路径** | Desktop / Claude Code / OpenCode **一律 flash**；`Pro`/`code` 轮空勿当主业 |
| **对话口鉴权（硬 · 2026-07-27）** | M1 sidecar `:7788` **默认 `CCC_AGENT_AUTH=0`**（内网网页 `#/chat` 不弹 Token）；需要时再 `CCC_AGENT_AUTH=1`。Hub Basic Auth 不动 |
| **双机拓扑(硬)** | M1 **不**跑 Hub/Board/Engine；Hub 仅 Mac2017；M1 Desktop/sidecar 默认 `http://127.0.0.1:17777` 隧道；**禁止** M1 业务第二树 / 伪 `engine=true` 登记 |
| **Ops Relay 用量** | Hub envelope `domains.relay` = **2017 编排面**用量；M1 对话面用量不在本表合并 |
| **门禁②(已补)** | `relay/src/protocols/{messages,chat}.ts` 非流式 `AbortSignal.timeout(30_000)` 改可配 `LOOP_NONSTREAM_TIMEOUT_MS`(默认 600s);`server.ts` 显式 `Agent(bodyTimeout/headersTimeout/keepAliveTimeout)`,根除 Lesson 24 长任务断连 |
| **观测回流** | `_ops_probe.fetch_router_usage` 真实现(GET `:4000/admin/usage`);`PORT_GROUPS` 加 4000/4002;ops summary `domains.relay`;Desktop 卡片 + Titlebar 复显 |
| **Desktop 模型快选** | sidecar `/health` 动态拉 relay 真实三档,不再硬编码 4 个假选项;**真三档**取代「伪四档」 |
| **密钥收拢** | 编排面上游 key 收至 `~/.ccc/relay/upstreams.json` 单点(0600);`opencode.json` 明文由 relay 兜底,Phase 5 收敛 |
| **旧文件废弃** | `templates/ccc-config.sh` `AGENT_PLANNER_BASE_URL=:4000` 由「退役残留」复活为「现行」;`docs/executors/overview.md` 等口径同步翻转 |

---

## 讨论 Agent 事实源

| 来源 | 用途 |
|------|------|
| Hub baseline | 开场（点时快照 + live board） |
| Hub **只读透镜** `/api/desktop/lens/{id}/…` | live 看板 / **modules** / locate / 文件 / grep / git |
| Hub **项目心智** `/api/desktop/mind/{id}/digest` | L1 观察脑+决策脑短摘要（每轮） |
| 本机会话 | 已聊目标与约束（低于 digest/board） |
| 本机 Read/Write/git | **CCC 平台仓**（engineer 默认；业务树仍禁第二树） |

CLI：`python3 scripts/ccc-hub-lens.py board|locate|tree|file|grep|git <project_id> …`  
心智写入：`python3 scripts/ccc-mind-update.py <project_id> --constraint '…'`  
禁止 sidecar `ssh mac2017` 探业务仓。问看板/文件 → **先透镜**；Hub 断 → 明说，禁止瞎编。

**扫风险 / 下一步 / 定稿**：必须定点核实真代码（`modules` → `locate`/`grep` → `file`），禁止只读文档交差；禁止全仓无脑扫；**未核实禁止断言模块有无**。路径只认 `project_id` + 透镜相对路径（**禁进用户正文**）。对齐基线非硬门槛，但下一步/定稿前仍须 live `board`+`git`。

---

## 工程师模式

| 项目 | 规则 |
|------|------|
| 任意 Desktop 项目卡 | **默认 engineer**：可本机改 CCC；全套 Hub（含跨仓 `hub_repair`） |
| 显式 discuss | 只读（禁 Write/Edit）；仍可用透镜/板务只读 status |
| 业务仓源码 | **禁止**本机/Hub 直写；只经 **定稿 → transfer → Engine** |

平台深改仍认 Cursor；App 内平台小改与板务由 **当前会话 Agent** 直接做。`ccc` 卡 = 平台仓入口，非唯一运维。

---

## 讨论 = Plan（规划面 · **仅 Desktop · 可选**）

> **适用范围**：只约束 **Desktop sidecar → loop-code** 在显式 `discuss` 时。  
> **默认是 engineer，不是 discuss。**  
> **不约束 Cursor**。Cursor 改本仓 = 完整 IDE 能力（见上文「双 Agent 人格独立」）。

| 维度 | 规则 |
|------|------|
| 协议 | Desktop 可传 `tool_mode=engineer`（默认）或显式 `discuss`；`prompt_mode` 恒 full |
| 智力 | 全开：Read/Glob/Grep/Bash/Web*/Task·Agent + Hub 透镜（含 locate）+ board-repair |
| 执行（discuss） | **硬禁** Write/Edit/MultiEdit/NotebookEdit；子代理同样禁写 |
| 执行（engineer） | 允许对本机 CCC 写；业务改码仍走 transfer |
| 交付 | 定稿 / `plan_md` / 转任务契约 + 板务数字结果 |
| 业务仓 | 事实只认 Hub 基线 + 透镜；禁止假装本机有第二树；禁止写死 2017 盘符 |

Desktop 代码定位 = 透镜 `locate`（业务仓不走 Cursor MCP）。

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
| **运维** | **系统养不养得起这条环；人敢不敢开发** | 总灯绿 → 放心下达；红 → **交给对话 Agent**（当前项目或 `ccc` 平台入口） |

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
- 首页验收：打开运维首先看到 **大灯 + 一句人话**；绿 → 关掉去干活；红 → **交给对话 Agent**（填入当前/平台会话）；无红则告警区空。  
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
- API：`GET /api/ops/summary` 顶层含 `severity`（green|amber|red）、`human_line`、`alerts[]`（仅 red + `copy_payload`）、`domains`（cluster / agent_mcp / capacity）。合成：`_ops_probe.ops_health_envelope`。`agent_mcp`：Hub 探本机 OpenCode/Cursor MCP 清单（`mcp_probed`+list/ok；未配置非红；断连/失败红+`copy_payload`）。M1 sidecar 仍由 Desktop 本机合并进总灯。  
- 采纳/apply 是例外通道，默认 workspace **不得**是 CCC。`board/roles/ops.py` 不升格为总调度。

### Desktop Ops 重构拆卡（硬 · 2026-07-27 · 下程实现）

详卡：[`docs/briefs/2026-07-27-desktop-ops-refactor.md`](../briefs/2026-07-27-desktop-ops-refactor.md)。**本条只定优先级，不在本轮改 Swift。**

| 程 | 做什么 |
|----|--------|
| **P0** | **已合入**（2026-07-27）：四域壳、schema、MCP 红灯、侧栏红点 |
| **P1** | 域 chip 绿/橙/红（relay fail-open=橙）；折叠模型通道接 upstream-daily；显式 `:17777` 隧道行；告警「仅复制」vs「交给 Agent」——指令包 `docs/dev-packets/` |
| **P2** | 权威巡查 alerts 进红条；agent_minds 折叠；网页 `#/ops` 降级；重建 App 二进制发布三档 picker+运维 UI |

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


## 三档契约 + 上游解耦（硬 · 2026-07-25）

| 项 | 口径 |
|----|------|
| **下游只对接三档** | `flash` / `Pro` / `code` 三个逻辑名(由 relay 路由表定义);桌面端、Engine、OpenCode 等下游**绝不直接 import 上游服务商 URL 或 API key** |
| **上游可换** | 上游细节由 `~/.ccc/relay/upstreams.json` 热替换。**现行**：flash=**仅 1 把启用的 Go 付费**（另 1 把备份 `enabled=false`）；免费/MiniMax **不进启用池**；**Pro/code 轮空** |
| **变更边界** | 换上游 = 改 upstreams.json + 重启 relay,无需改下游任何代码。下游契约(`flash`/`Pro`/`code`)**稳定,基本不变** |
| **禁止反模式** | 客户端代码出现 `api.minimaxi.com` / `api.anthropic.com` / `opencode.ai/zen/v1` 等具体 URL 或 `sk-...` 硬编码 key(仅 `upstreams.json` / `~/.ccc/relay/*` / `~/.ccc/*.key` 持有) |
| **运行时降级** | 上游挂 / 限流 / 跑路:relay `EWMA 评分 + 配额账本` 触发自动切换同 tier 下游;客户端通过 `relay_is_up()` 探活 + `relay_direct_fallback()` 切直连(双层 fail-open) |
| **可观测** | 三档实时用量 + 健康 + 命中率进 `_ops_probe.domains.relay` 子域;Hub `/api/ops/summary` 透传;Desktop 卡片显示 |

> 设计意图:**下游稳、上游活**。客户端代码稳定保护开发效率;上游灵活保护供应链与抗封禁。

## M1 Desktop Claude Code 双身份隔离（硬 · 2026-07-25）

| 项 | 口径 |
|----|------|
| **产品大脑** | M1 Desktop Claude Code **仅做产品大脑**:接用户意图、拆大卡、接 Hub transfer、回答板面问题、定稿/采纳 inbox |
| **平台开发禁** | M1 Desktop Claude Code **不再修改 CCC 仓**;不论用户如何措辞请求,只要目标是改 `~/program/CCC` 下的文件,必须**明确转交 Cursor**,不直接改 |
| **Cursor 独立** | CCC 平台开发 / 仓内**合入权威** 100% 走 Cursor(平台开发工具只认 Cursor 已是 v0.39 共识,本条仅**强制执行**);Cursor 走完整 IDE 能力(读/写/Bash/测/git),与 Desktop Agent **人格完全独立** |
| **识别边界** | 看对话 cwd + 文件路径:任何 `~/program/CCC` 路径下的写操作请求 → 转 Cursor;其他(用户日常对话 / 业务仓 / docs) → 照常 |
| **失败回环不属本条** | 产品大脑拆的大卡经 Hub transfer → 2017 Engine → product 角色(2017 Claude Code)扇出小任务 → dev 角色(OpenCode)写代码 → reviewer/tester 验收。失败由 2017 Engine 调度层(纯 Python,无 LLM)决定重试/重派,不属于双身份隔离范围 |

> 边界来源:CLAUDE.md 头部「人格独立」节 v0.39 已写"平台开发只认 Cursor";但未强制 M1 Desktop Claude Code 行为边界。本条把**共识变成执行规则**,由 sidecar / Cursor 规则双端 enforce(sidecar 检测 CCC 仓 cwd 写操作时拒 + Cursor 仍保留全 IDE 能力)。

## 个人 Claude Code（硬 · 2026-07-28 · 运维席；草稿旁路）

> **主职（定死）**：**日常维护运维**——本机 `~/.ccc`、launchd、relay 探活/kickstart、日志、板务辅助。见上文「四席工具定位」。  
> **非主职**：功能开发 / 合入权威（→ Cursor）；产线意图（→ Desktop）；知识闲聊（→ Codex）。  
> **草稿旁路**：Layer1 已出门后**停用放大**；**仅**接金路径打回的白名单 `dev-packets` 缺陷。详：[`../briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md) · [`../dev-packets/README.md`](../dev-packets/README.md)

| 项 | 口径 |
|----|------|
| **合入 SSOT 仍只认 Cursor** | **禁止**把个人 Claude Code / Desktop Agent / Codex / 个人 OpenCode 当合入权威 |
| **运维允许** | 读改本机配置与日志；relay/sidecar/hub-tunnel 探活与 kickstart；协助板务诊断（不替代 Desktop `hub_repair` 主路径） |
| **运维禁止** | 上 main；改 `loop-engineer-authority` / 红线当「顺手」；功能开发主路径；冒充 Desktop |
| **草稿旁路允许** | 指定 feature branch / worktree 内按 **dev-packet** 白名单改文件；跑 packet 验收 |
| **草稿旁路禁止** | 改权威/控制面；动生产密钥；`git add -A`；强推 main；跨 packet 重构；Ops/SPA 抛光大包 |
| **与四席关系** | 个人 CLI ≠ Desktop；≠ Cursor；≠ Codex；≠ Engine OpenCode |
| **Layer1 / 盈利边界** | 同前：`released` ≠ 业务完成；Ops 抛光不计入金路径 |

> 巡查口径：仓内**禁止**「用 Claude Code / Codex / OpenCode 当平台合入 IDE」现行教法；允许「运维席 + 草稿旁路 + Cursor 合入」说明。

## Claude --bg 长任务（已交付 · v0.63.0 · 仅 Mac2017）

| 项 | 口径 |
|----|------|
| **范围** | `claude --bg` 与 Engine reviewer 长 session；Hub `/api/ops/bg-sessions`；Desktop 运维卡只读展示；**nudge 真注入** |
| **运行时主机** | **仅 Mac2017**（`ccc-reviewer-bg.sh` + `LongLivedSession` + `~/.ccc/bg-sessions/`）；M1 Desktop 只消费 Hub 透出，不在本机起 --bg |
| **已交付(v0.62.0)** | reviewer 包装启 bg session；register/verify/list；fleet stop 清真进程；Hub envelope `domains.bg_sessions`；Desktop `bgSessionCard` |
| **已交付(v0.63.0)** | `nudge_bg_session`：写 `.nudge` + `claude --resume` 异步注入（`CCC_BG_NUDGE_DRY_RUN` / `CCC_CLAUDE_BIN`）；E2E `tests/scripts/test_nudge_bg_session.sh` |
| **禁止** | M1 上跑 Engine/--bg；把 dry_run 当生产注入；sidecar 改 spawn 模式冒充长任务 |

> 旧「预留 / 禁止提前试水」与「v0.63 占位」口径已废止（nudge 真通道随 v0.63.0 上线）。
