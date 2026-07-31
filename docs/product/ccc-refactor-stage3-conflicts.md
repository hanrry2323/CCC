# 阶段 3：冲突文档清单

> 扫描范围：docs/ + references/（除已改造的 7 个核心文档）
> 基准：ccc-new-architecture-overview.md
> 扫描时间：2026-07-31
> 扫描方式：只读 Grep + Read 上下文核对，未修改任何被扫描文档

## 冲突判定基准（新架构 6 大变更）

1. **拆卡人变更**：Desktop Agent / 方案 Agent / 架构师 Agent / IDE Agent → Claude 后台程序（Mac 2017，无记忆，多职能复用）
2. **IDE 职责变更**：谈方案+拆卡+自动投链 → 只谈方案+写方案文件
3. **Skill 承载变更**：`executor_intent` 枚举（opencode/python/ollama/cli/auto）→ 独立 Skill/Prompt 库 + 软链接引用
4. **意图卡 schema 变更**：删除 `executor_intent`，新增 `skill_ref`/`prompt_ref`/`prompt_inline`
5. **方案入口变更**：Agent 输出 `ccc-transfer` 块 → IDE 写方案文件 → Hub API → 业务仓 `.ccc/intent-proposals/` → Claude 后台程序拆卡
6. **飞轮主体变更**：Desktop Agent 自动再投 → Claude 后台程序（多职能复用）

## 冲突文档清单

| 文档 | 冲突点（行号+摘要） | 冲突类型 | 处理建议 |
|------|---------------------|----------|----------|
| `STARTUP-BRIEF.md` | L62: 「意图链由 Agent **自动投**（已删「转意图卡」按钮）」Agent 自动投+引用已删按钮 | 旧主体+旧机制+旧流程 | 优化 |
| `STARTUP-BRIEF.md` | L124: 「转意图卡经 gate 绿后默认建 **epic**」引用已删按钮+旧流程 | 旧机制+旧流程 | 优化 |
| `STARTUP-BRIEF.md` | L179: 「老板在 Desktop（M1）点「转意图卡」（或「按 CCC 跑 X」）」引用已删按钮+旧流程 | 旧机制+旧流程 | 优化 |
| `CLAUDE.md` | L85-90: 架构概要「Hub（定稿→epic）→ Claude product 扇出 → planned(work×N)」描述旧 product 扇出流程，未提 IDE 写方案文件 + Claude 后台程序拆卡 | 旧主体+旧流程 | 优化 |
| `CHANGELOG.md` | L69: 「Desktop 自动投链永久 suppress（hp 投不进）」描述 Desktop Agent 自动投链 | 旧主体+旧流程 | 标史 |
| `CHANGELOG.md` | L198: 「transfer 对纸面/`paper_intent_probe` 强制 `executor_intent=python`」使用旧字段 | 旧字段 | 标史 |
| `CHANGELOG.md` | 多处：`executor_intent` 枚举值（opencode/python/bug 等）作为旧字段散落历史条目 | 旧字段 | 标史 |
| `docs/GETTING-STARTED.md` | L3: 「战略讨论 → Agent 自动投意图链 → 自动进代办」把 Agent 当拆卡投链主体 | 旧主体+旧流程 | 优化 |
| `docs/GETTING-STARTED.md` | L58: 「意图收敛后 Agent **自动**输出整条 `ccc-transfer` 意图链（勿等人点「转意图卡」；UI 已无该按钮）」Agent 自动出契约即投链 | 旧主体+旧机制+旧流程 | 优化 |
| `docs/GETTING-STARTED.md` | L99: 「自动投意图链」沿用旧流程描述 | 旧流程 | 优化 |
| `docs/GLOSSARY.md` | L28-31: 「转意图卡 / 意图卡 / 代办」术语段定义「转意图卡：人显式触发；Agent 写 L1 `planned`」描述已删按钮机制 | 旧机制 | 优化 |
| `docs/INDEX.md` | L43: 「**转意图卡 SOP**」（链接到 intent-card-sop.md 的显示文案）术语残留 | 旧机制 | 优化 |
| `docs/INDEX.md` | L53: 「转意图卡 → transfer_gate」术语残留 | 旧机制 | 优化 |
| `docs/briefs/2026-07-21-f4-3-proactive-triggers.md` | L56: 「行为：等价 transfer（进 backlog epic；`executor_intent="bug"`；`client_request_id` 幂等键由 `source + payload.hash` 生成）」使用旧字段 | 旧字段 | 标史 |
| `docs/briefs/2026-07-23-kpi-r4-fix.md` | L13: 「`ccc-stress-matrix.py` e04：`executor_intent=python`，走 feature_seed」使用旧字段 | 旧字段 | 标史 |
| `docs/briefs/2026-07-27-golden-path-evidence.md` | L107/L121/L157/L194: 多处 `executor_intent=opencode`（如 L121「Hub `executor_intent=opencode`（标题『文档戳记』）」） | 旧字段 | 标史 |
| `docs/briefs/2026-07-30-flowweave-vs-ccc.md` | L21: 「自动投链（删「转意图卡」按钮；Agent 出契约即 promote）」仍以 Agent 出契约作 promote 主体 | 旧主体+旧流程 | 标史 |
| `docs/briefs/2026-07-30-self-heal-inventory.md` | L43: 「L3/L3b ｜ 板红 / claim 注入 ｜ repair→optimize→**自动投链**」沿用 Agent 自动投链 | 旧主体+旧流程 | 标史 |
| `docs/ops/GO-LIVE.md` | L15: 「战略讨论 → Agent 自动投意图链（验收含可重放意图探针；勿等人点「转意图卡」）→ gate 绿自动进代办」Agent 自动投+引用已删按钮 | 旧主体+旧机制+旧流程 | 优化 |
| `docs/ops/GO-LIVE-DESKTOP.md` | L17: 「对话方案 Agent ｜ M1 本机 sidecar `:7788` + arm64 `vendor/loop-code/cli`」把对话方案 Agent 当拆卡主体 | 旧主体 | 优化 |
| `docs/ops/GO-LIVE-DESKTOP.md` | L60: 「选业务项目 → 本机对话聊定意图 → **Agent 自动投意图链**（需 Hub 投递）→ 右栏看意图卡链」Agent 自动投 | 旧主体+旧流程 | 优化 |
| `docs/ops/GO-LIVE-DESKTOP.md` | L82/L129/L131: 多处「转意图卡」按钮描述（如 L82「转意图卡 gate 绿」、L129「转意图卡成功进代办」） | 旧机制 | 优化 |
| `docs/ops/hub-boss-voice.md` | L21: 「你是 Desktop **全功能开发 Agent**（全功能开发能力）：开发 / 定任务 / 优化；Hub = 编排 API；进队后全自动」把 Desktop Agent 当拆卡+定任务主体 | 旧主体 | 优化 |
| `docs/product/desktop-agent-handoff.md` | L1/L3: 标题「Desktop Agent 交接：业务仓迁移与接入」+「给 Desktop Agent / Hub·sidecar 的短交接」以 Desktop Agent 为主语 | 旧主体 | 优化 |
| `docs/product/desktop-agent-handoff.md` | L20-28: 多处「Desktop Agent engineer 默认可改」「对话 = Desktop + sidecar（全功能 Agent）」描述 Agent 全功能职责含定任务 | 旧主体 | 优化 |
| `docs/product/desktop-agent-identity.md` | L46: 「制定开发计划 = 意图卡链（**自动投链** → gate → Engine）」Desktop Agent 自动投链 | 旧主体+旧流程 | 优化 |
| `docs/product/desktop-agent-identity.md` | L48: 「空闲继续下一站（飞轮 L1 planned；进代办由你理解后自动投；禁 invent）」Desktop Agent 当飞轮主体 | 旧主体（飞轮） | 优化 |
| `docs/product/desktop-agent-identity.md` | L72: 「意图链闭环：Agent 自动投 → L1 → gate 绿自动进代办」Agent 自动投 | 旧主体+旧流程 | 优化 |
| `docs/product/desktop-agent-identity.md` | L79: 「主路径：分析/开发/定任务 → **自动投意图链** → L1 + gate → Engine 跑」Agent 自动投 | 旧主体+旧流程 | 优化 |
| `docs/product/desktop-agent-identity.md` | L92: 「谈妥后我自动投意图链；系统跑；挂了我就修板、改卡再推——不用你点按钮」Desktop Agent 自动投+对比已删按钮 | 旧主体+旧机制+旧流程 | 优化 |
| `docs/product/desktop-flow-rail-ux.md` | L20: 「空态：「谈妥后点转意图卡」」引用已删按钮 | 旧机制 | 优化 |
| `docs/product/dialogue-orchestration-boundary.md` | L48: 「`executor_intent` / `skills_hint` / `plan_md` ｜ 供扇出参考」把旧字段列入扇出参考 | 旧字段 | 优化 |
| `docs/product/executor-plugins.md` | L54: 「转任务门禁的 `executor_intent` 仅为**软偏好**；Engine 扇出可覆盖，但应写入 work 供右栏展示」使用旧字段 | 旧字段 | 优化 |
| `docs/product/hub-api-v1.md` | L109: 「落盘标记：`executor_intent` 记为 **`bug`**（tags 含 `proactive` / `bug` / `source:<…>` / `exec:bug`）」使用旧字段 | 旧字段 | 优化 |
| `docs/product/proactive-triggers.md` | L12: 「执行标记 ｜ `executor_intent=bug`（扇出时未知 executor 归一为 opencode）」使用旧字段 | 旧字段 | 优化 |
| `docs/releases/v0.64.0.md` | L4: 「人点「转意图卡」→ Agent 写 L1 → `transfer_gate` 绿才自动进代办」引用已删按钮+Agent 写 L1 | 旧机制+旧主体 | 标史 |
| `docs/releases/v0.64.0.md` | L20: 「转意图卡 ≠ 定代办；战略讨论优先；禁 invent / 禁自转入队」引用已删按钮 | 旧机制 | 标史 |
| `docs/releases/v0.64.0.md` | L37: 「战略讨论 → 人点「转意图卡」→ L1 planned → gate 绿 → 自动进代办 → Engine」引用已删按钮 | 旧机制 | 标史 |
| `docs/releases/v0.64.1.md` | L4: 「转意图卡统一过门；僵尸 planned 可清；validate 失败不入队」引用已删按钮 | 旧机制 | 标史 |
| `docs/releases/v0.64.1.md` | L11: 「文案转意图卡；删 FlowCanvas/taskStack」引用已删按钮 | 旧机制 | 标史 |
| `docs/releases/v0.65.0.md` | L7: 「人在 Desktop 聊定意图 → Agent **自动投意图链** → Engine 跑 → 失败 **自动修板并优化再投**」Agent 自动投+飞轮 | 旧主体+旧流程 | 标史 |
| `docs/releases/v0.65.0.md` | L13: 「意图链开发 ｜ Agent 收敛后自动出多卡 `ccc-transfer`；gate 绿进代办 + wake；**无**「转意图卡」按钮」Agent 出契约+引用已删按钮 | 旧主体+旧机制 | 标史 |
| `docs/releases/v0.65.0.md` | L21: 「聊透意图 → Agent 自动投链 → gate → backlog → Engine」Agent 自动投 | 旧主体+旧流程 | 标史 |
| `docs/runbooks/app-migrate-register-desktop.md` | L4/L40/L79/L95-100/L116-118: 多处「Desktop Agent」「对齐基线 → 定稿 → 转任务」把 Desktop Agent 当拆卡主体+使用「转任务」术语 | 旧主体+旧机制 | 优化 |
| `docs/runbooks/orchestration-flow.md` | L32: 「点「转任务」→ POST /api/desktop/transfer」引用已删按钮 | 旧机制 | 优化 |
| `docs/runbooks/orchestration-flow.md` | L40: 「Agent：`../product/desktop-agent-handoff.md`」把 Desktop Agent 当交接对象 | 旧主体 | 优化 |
| `references/abnormal-solve-sop.md` | L13: 「读证据 → 按失败桶改任务拆解 → 新 `ccc-transfer` 入队 → Engine 跑绿」沿用 Agent 出 ccc-transfer 入队流程 | 旧流程 | 优化 |
| `references/abnormal-solve-sop.md` | L24: 「耗尽则 `clear_blockers` **之后必须**出优化意图链并**自动投** `ccc-transfer`」Agent 自动投 | 旧主体+旧流程 | 优化 |
| `references/align-baseline-sop.md` | L15: 「人 ｜ 听路线；要开工点「转意图卡」落成整条链 ｜ 不当技术员审 pytest」引用已删按钮 | 旧机制 | 优化 |
| `references/align-baseline-sop.md` | L48: 「「转意图卡 / 下任务卡 / 跑通」= 把**整条计划**落成多卡链」引用已删按钮 | 旧机制 | 优化 |
| `references/board-auto-repair-sop.md` | L28: 「exhausted 则 post-exhaust **优化意图链并自动投链**」沿用 Agent 自动投链 | 旧主体+旧流程 | 优化 |
| `references/commit-folder-hygiene-sop.md` | L94: 「禁止默认 `executor_intent: python` 卫生 epic 当主业」使用旧字段 | 旧字段 | 优化 |
| `references/finalize-transfer-sop.md` | L1/L3: 标题「定稿转任务 SOP → 已更名」+「转意图卡 SOP · v0.64」保留已删术语作重定向 | 旧机制 | 删除（已是单文件重定向 stub，可整合进 intent-card-sop.md 后删除） |
| `references/post-exhaust-epic-optimize-sop.md` | L28: 「acceptance 与 scope 同向；`executor_intent` 匹配」使用旧字段作验收口径 | 旧字段 | 优化 |

## 无冲突文档（确认保留）

下列文档已扫描，未发现与新架构核心要点冲突（注：仅列代表性文档，未穷举所有未命中文件）：

- `docs/briefs/2026-07-28-layer2-qb-open.md` — 仅描述 L→P→人点 S 路径，未引用旧字段/旧主体
- `docs/briefs/2026-07-28-flywheel-auto-open.md` — 飞轮 T1–T4 描述中「Desktop 人点 stable」与「Engine 自动」未把 Agent 当飞轮主体
- `references/transfer-playbook-qb.md` — 仅反模式对照，`ccc-transfer` 出现在「再 `ccc-transfer`」语境（耗尽后重投），未把 Agent 当拆卡主体
- `references/red-lines.md`、`references/board-task-schema.md` 等未命中冲突关键词的文档

> 说明：阶段 2 已改造的 7 个核心文档（loop-engineer-authority.md / transfer-gate.md / ccc-new-architecture-overview.md / ccc-refactor-stage2-plan.md / dev-channel.md / intent-card-sop.md / intent-chain-dev-sop.md / intent-proposal-sop.md / skills/ / prompts/）按任务要求跳过，不在本清单内判定。

## 处理建议汇总

- **删除**：1 个
  - `references/finalize-transfer-sop.md`（仅剩重定向 stub，可整合进 `intent-card-sop.md` 后删除）
- **标史**（文档保留但顶部标注「史径/已废弃，仅作历史决策记录」）：9 个
  - `CHANGELOG.md`（历史变更日志，按版本归档不动正文）
  - `docs/briefs/2026-07-21-f4-3-proactive-triggers.md`（决策 Brief，历史记录）
  - `docs/briefs/2026-07-23-kpi-r4-fix.md`（决策 Brief，历史记录）
  - `docs/briefs/2026-07-27-golden-path-evidence.md`（决策 Brief，历史记录）
  - `docs/briefs/2026-07-30-flowweave-vs-ccc.md`（对照决策 Brief，历史记录）
  - `docs/briefs/2026-07-30-self-heal-inventory.md`（自愈盘点 Brief，历史记录）
  - `docs/releases/v0.64.0.md`（发布说明，历史记录）
  - `docs/releases/v0.64.1.md`（发布说明，历史记录）
  - `docs/releases/v0.65.0.md`（发布说明，历史记录）
- **优化**（文档保留但需修改冲突点）：22 个
  - `STARTUP-BRIEF.md`（Agent 启动首因文件，旧流程+旧按钮）
  - `CLAUDE.md`（架构概要 L85-90 描述旧 product 扇出流程）
  - `docs/GETTING-STARTED.md`
  - `docs/GLOSSARY.md`
  - `docs/INDEX.md`（术语残留）
  - `docs/ops/GO-LIVE.md`
  - `docs/ops/GO-LIVE-DESKTOP.md`
  - `docs/ops/hub-boss-voice.md`（Desktop Agent 当拆卡+定任务主体）
  - `docs/product/desktop-agent-handoff.md`
  - `docs/product/desktop-agent-identity.md`
  - `docs/product/desktop-flow-rail-ux.md`（引用已删按钮）
  - `docs/product/dialogue-orchestration-boundary.md`
  - `docs/product/executor-plugins.md`
  - `docs/product/hub-api-v1.md`
  - `docs/product/proactive-triggers.md`
  - `docs/runbooks/app-migrate-register-desktop.md`
  - `docs/runbooks/orchestration-flow.md`
  - `references/abnormal-solve-sop.md`
  - `references/align-baseline-sop.md`
  - `references/board-auto-repair-sop.md`
  - `references/commit-folder-hygiene-sop.md`
  - `references/post-exhaust-epic-optimize-sop.md`

## 高频冲突模式（供阶段 3 改造参考）

1. **`executor_intent` 残留**：6 份 SOP/Brief 仍用旧枚举字段（`python`/`opencode`/`bug` 等）。改造模板：替换为 `skill_ref`/`prompt_ref` + 软链接到 `references/skills/`、`references/prompts/`。
2. **「转意图卡」按钮残留**：5 份用户向文档仍引用已删按钮（GO-LIVE-DESKTOP、align-baseline-sop、orchestration-flow 等）。改造模板：删除按钮描述，改为「IDE 写方案文件 → Hub API → 业务仓 `.ccc/intent-proposals/` → Claude 后台程序拆卡」。
3. **「Agent 自动投链 / Agent 出契约」残留**：8 份文档仍把 Desktop Agent / 对话方案 Agent 当拆卡+自动投链主体（desktop-agent-identity、desktop-agent-handoff、GO-LIVE 系列、releases、CHANGELOG 等）。改造模板：拆卡主体改为「Claude 后台程序（Mac 2017，无记忆，多职能复用）」；IDE 职责改为「只谈方案+写方案文件」；飞轮主体改为「Claude 后台程序（多职能复用）」。
4. **Desktop Agent 旧身份叙事**：`docs/product/desktop-agent-identity.md` + `docs/product/desktop-agent-handoff.md` 是冲突最密集的两份产品文档，需重点重写（保留对话面 Agent 身份，但删除「定任务/拆卡/自动投链/飞轮」职责描述）。
5. **SOP 类自动投链描述**：`abnormal-solve-sop.md`、`board-auto-repair-sop.md`、`post-exhaust-epic-optimize-sop.md` 在异常自愈流程末段仍写「自动投链」，需改为「写方案文件 → 提交 Hub → Claude 后台程序拆卡」。

## 改造优先级建议

| 优先级 | 文档 | 理由 |
|--------|------|------|
| P0 | `STARTUP-BRIEF.md` | Agent 启动首因文件，L62/L124/L179 含旧流程+旧按钮，影响所有 Agent 启动认知 |
| P0 | `docs/product/desktop-agent-identity.md`、`docs/product/desktop-agent-handoff.md` | Desktop Agent 身份叙事核心，冲突最密集，影响下游所有文档 |
| P0 | `references/abnormal-solve-sop.md`、`references/board-auto-repair-sop.md`、`references/post-exhaust-epic-optimize-sop.md` | 异常自愈 SOP 链，自动投链描述误导实际流程 |
| P1 | `CLAUDE.md` | 架构概要 L85-90 描述旧 product 扇出流程，平台开发席首读文件 |
| P1 | `docs/ops/GO-LIVE.md`、`docs/ops/GO-LIVE-DESKTOP.md`、`docs/GETTING-STARTED.md` | 用户上手文档，影响新用户认知 |
| P1 | `docs/ops/hub-boss-voice.md`、`docs/product/desktop-flow-rail-ux.md` | Desktop 人格/右栏 UX，把 Agent 当拆卡主体+引用已删按钮 |
| P1 | `references/align-baseline-sop.md`、`docs/runbooks/orchestration-flow.md`、`docs/runbooks/app-migrate-register-desktop.md` | 流程 SOP，影响日常使用 |
| P2 | `docs/product/dialogue-orchestration-boundary.md`、`docs/product/executor-plugins.md`、`docs/product/hub-api-v1.md`、`docs/product/proactive-triggers.md` | 产品契约文档，仅需替换 `executor_intent` 字段 |
| P2 | `docs/GLOSSARY.md`、`references/commit-folder-hygiene-sop.md` | 术语表/卫生 SOP，局部替换 |
| P2 | `docs/briefs/2026-07-30-self-heal-inventory.md` | 自愈盘点 Brief，自动投链描述（已标史） |
| P3 | `docs/INDEX.md` | 术语残留（链接显示文案），局部替换 |
| P3 | `references/finalize-transfer-sop.md` | 删除（重定向 stub） |
| 标史 | `CHANGELOG.md` + 4 份 Brief + `docs/releases/v0.64.0.md` + `v0.64.1.md` + `v0.65.0.md` | 历史文档，仅加顶部废弃标注 |
