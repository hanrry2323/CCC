# CCC 新架构重构 · 阶段 2 详细 Plan

> **基准**：`docs/product/ccc-new-architecture-overview.md`（已定）
> **范围**：7 个文档改造（5 改 + 2 新增），不动代码
> **原则**：区分新旧方案 · 每个文档列具体改动点 · 按冲突密度排序执行

---

## 新旧方案对比总览

| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| 拆卡人 | Desktop Agent / 架构师 Agent | Claude 后台程序（Mac 2017，无记忆） |
| IDE 职责 | 谈方案 + 拆卡 + 自动投链 | 只谈方案 + 写方案文件 |
| Skill 承载 | `executor_intent` 枚举（写死） | 独立 Skill/Prompt 库 + 软链接引用 |
| 意图卡 schema | 含 `executor_intent` | 新增 `skill_ref`/`prompt_ref`/`prompt_inline` |
| 方案入口 | Agent 输出 `ccc-transfer` 块 | IDE 写方案文件 → Hub API → 业务仓 `.ccc/intent-proposals/` |
| 飞轮主体 | Desktop Agent 自动再投 | Claude 后台程序（多职能复用） |

---

## 执行顺序（按冲突密度）

| 序 | 文档 | 操作 | 冲突密度 |
|----|------|------|----------|
| ① | `docs/product/loop-engineer-authority.md` | 改 7 处 + 删 3 处 | 最高（SSOT 母文档） |
| ② | `docs/product/transfer-gate.md` | 改 4 处 + 删 4 处 | 高（schema 契约） |
| ③ | `references/intent-card-sop.md` | 改 5 处 + 删 2 处 | 高（卡片格式） |
| ④ | `references/intent-chain-dev-sop.md` | 改 4 处 + 删 3 处 | 中（流程 SOP） |
| ⑤ | `docs/product/dev-channel.md` | 改 3 处 + 删 1 处 | 中（席位表） |
| ⑥ | `references/intent-proposal-sop.md` | 新增 | 新文件 |
| ⑦ | `references/skills/` + `references/prompts/` | 新增 | 新目录 |

---

## ① loop-engineer-authority.md 改造 Plan

**路径**：`docs/product/loop-engineer-authority.md`（879 行）

| 行号 | 旧内容（摘要） | 新内容（摘要） | 操作 |
|------|---------------|---------------|------|
| 128–145 | 双 Agent 人格独立：Desktop Agent 全功能（开发、定任务、优化…） | Desktop/IDE 只保留"谈方案"；"定任务（拆卡）"剥离给 Claude 后台程序 | 改 |
| 24–42 | 最小可跑通 v1 双槽：Claude 对话槽=聊透+产出 epic+plan+verify | 对话槽只留"聊透意图"；新增"Claude 后台程序"槽=拆卡+飞轮 | 改 |
| 232–265 | 意图卡供给闭环：Agent 自动出多卡链 + 自动投链 | IDE 写方案文件 → Claude 后台程序消费方案 → 拆卡 → gate | 改+删 |
| 267–292 | Desktop 主路径：Agent 自动出 ccc-transfer | 方案文件入口 → 后台程序拆卡 → gate（重画流程） | 改 |
| 250–261 | App Agent 全功能表：可开发、定任务、优化 | 删"定任务"，改为"只谈方案" | 改 |
| 276–277 | 飞轮：Agent 理解后自动再投 | 飞轮归 Claude 后台程序（多职能复用） | 改 |
| 148–158 | 闭环七词"意图/下达" | 补充方案文件入口环节；"意图"收窄为 IDE 只谈 | 改 |
| 582–608 | 讨论=Plan：可输出 ccc-transfer | 删 ccc-transfer 输出权，改为只写方案文件 | 改+删 |
| 869–879 | Claude --bg 长任务（Mac2017） | 交叉引用：此基础设施可复用为后台程序载体 | 保留+标注 |

**保留不动**：席位工具定位(64–87)、双轨业务(90–112)、模型通道(114–125)、价值立场(180–204)、三层架构(497–518)、CCC Relay(520–548)、四权威(484–494)、验收关门(417–435)、LPSN(437–481)、Ops(643–735)、OpenCode 生命周期(750–793)

---

## ② transfer-gate.md 改造 Plan

**路径**：`docs/product/transfer-gate.md`（130 行）

| 行号 | 旧内容（摘要） | 新内容（摘要） | 操作 |
|------|---------------|---------------|------|
| 10–19 | 流程：聊透→Agent 出 ccc-transfer→validate | 流程：IDE 写方案→Hub API→后台程序拆卡→gate（重画） | 改 |
| 21–40 | 定稿协议：方案 Agent 输出 ccc-transfer 块 | 定稿主体=方案文件；ccc-transfer 由后台程序产出 | 改 |
| 53–72 | 必填字段表含 `executor_intent`(63行) | 删 `executor_intent`；新增 `skill_ref`/`prompt_ref`/`prompt_inline` | 改+删 |
| 42–49 | 二级卡可改边界含 `executor_intent`(46行) | 删 `executor_intent` 行；新增 skill_ref 等可改性规则 | 改+删 |
| 98 | 错误码 `invalid_executor_intent` | 删除；新增 `missing_skill_ref`/`invalid_skill_ref` | 删+新增 |

**保留不动**：标题(1–8)、验收写作(76–84)、错误码主体(88–109 除 executor_intent)、失败回流(111–117)、成功响应(119–130)、其他字段(title/goal/acceptance/pipeline/feasibility 等)

---

## ③ intent-card-sop.md 改造 Plan

**路径**：`references/intent-card-sop.md`（151 行）

| 行号 | 旧内容（摘要） | 新内容（摘要） | 操作 |
|------|---------------|---------------|------|
| 1–8 | 谁用：Desktop App Agent 自动出 ccc-transfer | 谁用：IDE（谈方案）+ Claude 后台程序（拆卡） | 改 |
| 12–28 | 三角色：Agent 自动落成意图卡链 | 拆为：IDE 写方案 + 后台程序拆卡 + 系统 gate | 改 |
| 53–63 | 契约硬预算表 | 新增 skill_ref/prompt_ref/prompt_inline 三行 | 改 |
| 111–123 | 两段落盘：Agent 出 ccc-transfer→gate→backlog | IDE 写方案→后台程序拆卡→gate→backlog | 改 |
| 126–131 | 对用户输出：ccc-transfer 块 | IDE 输出方案文件路径/摘要（非 ccc-transfer） | 改 |
| 17,21 | "自动落成意图卡链""发起权=Agent 自动投链" | 删"自动落成""自动投链"，改为后台程序 | 删 |

**保留不动**：收敛门(31–39)、起草前核验(43–50)、文/码分轨(65–72)、acceptance 白/黑名单(74–90)、plan_md 正形(92–107)、失败回流(134–143)、qb 案例(146–151)

---

## ④ intent-chain-dev-sop.md 改造 Plan

**路径**：`references/intent-chain-dev-sop.md`（87 行）

| 行号 | 旧内容（摘要） | 新内容（摘要） | 操作 |
|------|---------------|---------------|------|
| 1–7 | 谁用：Desktop App Agent | 谁用：IDE（只谈方案）+ Claude 后台程序（拆卡） | 改 |
| 10–15 | 一句话：你理解后自动落成多卡链 | IDE 写方案；后台程序消费后拆卡 | 改 |
| 18–31 | 怎么写任务：你自动出 ccc-transfer | IDE 写方案文件→后台程序出 ccc-transfer | 改 |
| 73–80 | Desktop 快捷：投链由你自动 | 投链由后台程序自动 | 改 |
| 12,24,80 | "你自动落成""你自动出""投链由你" | 删"你"，改为后台程序 | 删 |

**保留不动**：怎么监控(34–44)、怎么失败修复(47–61)、怎么验收关门(64–70)、完成定义(84–87)

---

## ⑤ dev-channel.md 改造 Plan

**路径**：`docs/product/dev-channel.md`（61 行）

| 行号 | 旧内容（摘要） | 新内容（摘要） | 操作 |
|------|---------------|---------------|------|
| 10–29 | 席位表（缺后台程序席位） | 新增"Claude 后台程序"席位行 | 改 |
| 18 | CCC Desktop：意图/看板/下达 | CCC Desktop：意图讨论/看板/方案文件起草（删"下达"拆卡义） | 改 |
| 54–61 | 禁止混淆 | 新增：四个 Claude 角色不可串台（后台程序≠Engine Claude≠Desktop Agent≠个人 CLI） | 改 |

**保留不动**：草稿旁路(32–41)、Desktop/模型(44–50)、其他席位行(14–17,19–25)

---

## ⑥ 新增 intent-proposal-sop.md

**路径**：`references/intent-proposal-sop.md`（新文件）

**内容大纲**：
1. 谁用：任意 IDE 工具（会谈方案 + 会跑命令）
2. 方案文件标准格式（4 节）：
   - 目标（做什么）
   - 范围（涉及哪些文件/模块）
   - 步骤概要（怎么做的思路，不拆卡）
   - 验收意图（成功长什么样）
3. 文件命名：`<方案名>.md`，放 `docs/intent-proposals/`（IDE 临时目录）
4. 激活命令：`ccc-submit-proposal <file>`
5. 流程：IDE 写方案 → 跑命令 → Hub API 落盘业务仓 → Claude 后台程序拆卡 → gate → backlog
6. 禁止：方案文件里直接写意图卡 JSON（那是后台程序的活）

---

## ⑦ 新增 skills/ + prompts/ 库

**路径**：
- `references/skills/`（新目录）
- `references/prompts/`（新目录）

**初始 2-3 个测试 Skill/Prompt**（从现有角色 skill 迁移）：
1. `references/skills/code-review/skill.md` — 代码审查职能
2. `references/skills/write-code/skill.md` — 写码职能
3. `references/prompts/code-review-prompt.md` — 代码审查 prompt

**Skill 文件格式**：自由结构（不强制 schema），Markdown 文件，内容自自治。目录名 = 职能名。

---

## 验收标准

- [ ] 5 个文档全部改造完成，无"Desktop Agent 拆卡"残留表述
- [ ] `executor_intent` 枚举在所有文档删除，替换为 skill_ref/prompt_ref/prompt_inline
- [ ] 新增 intent-proposal-sop.md + skills/ + prompts/ 库
- [ ] 跨文档一致性：拆卡人统一为"Claude 后台程序"，IDE 统一为"只谈方案"
- [ ] 保留章节未被误改（验收关门/LPSN/Relay 等）
