# CCC 新架构总览（意图链解耦与多入口 · 草案）

> **状态**：草案 · 2026-07-31 · **批准后并入 `loop-engineer-authority.md` 为准**
> **谁读**：老板 / 架构决策 / 后续文档修改与组件拼装
> **冲突时以本文为准**（批准前与现有文档冲突的，本文为准；批准后回写 `loop-engineer-authority`）
> **本次范围**：仅定义架构基准，不动代码

---

## 一句话

**人 + IDE 谈方案 → Claude 后台固定程序拆意图链（从 Skill/Prompt 库组装软链接）→ Engine 标准化 + 驱动闭环 → 任意职能经 Skill/Prompt 库无限扩展接入。**

---

## 旧方案漏洞（本次要解决的）

| # | 漏洞 | 后果 |
|---|------|------|
| 1 | IDE 端 Agent 自己拆意图卡 | 每个 IDE 性格/记忆不同 → 记忆错乱、性格漂移（Trae 已踩坑） |
| 2 | Engine 直接吃"大目标方案" | Engine 无 LLM 拆分能力 → 拆不动、扇出错位 |
| 3 | 意图卡写死职能（`executor_intent` 枚举） | 只能开发向，新增职能要改代码 → 有限流程 |
| 4 | IDE 既谈方案又拆卡 | 职责混淆，IDE 端能力参差导致产出不稳 |

---

## 四层分工（硬 · 不可协商）

| 层 | 承担者 | 职责 | 硬边界 |
|----|--------|------|--------|
| **① 谈方案** | **人 + 任一 IDE 工具** | 大目标 → 详细行动/项目方案（不拆卡） | **不拆意图卡**；只产出方案文档 |
| **② 拆意图链** | **Claude 后台固定程序**（独立、无个人记忆） | 方案 → 标准意图卡链；从 Skill/Prompt 库查找组装软链接 | **无对话上下文**；只按固定 SOP 拆；不创造新 Skill |
| **③ 标准化** | **Engine（NG）** | `transfer_gate` 校验 + 入 backlog + wake | **不拆卡**；只做契约校验和入队 |
| **④ 闭环驱动** | **Engine 流水线**（fanout → 写码 → 验收 → released） | 推进链条、跑探针、刷状态 | **不解析 Skill 内容**；交给执行器加载 |

**关键边界**：
- ① 谈方案 ≠ 拆卡（IDE 只管方案，不碰意图卡）
- ② 拆卡 ≠ 写码（Claude 后台程序只拆卡+组装引用，不写业务码）
- ③ 标准化 ≠ 拆分（Engine 只校验入队，不二次拆）
- ④ 驱动 ≠ 解析（Engine 推进链条，Skill 内容由执行器加载）

---

## Skill/Prompt 解耦（核心设计 · 无限扩展）

### 设计哲学
- **Skill 库**和 **Prompt 库**独立存在，无限扩展
- 意图卡只**引用**（软链接），不**内联**Skill/Prompt 内容
- 新增职能 = 库里加文件 + 意图卡引用，**不改意图卡格式、不改 Engine、不改 Claude 拆卡逻辑**

### 物理形态
```
references/
├── skills/                    # Skill 库（无限扩展）
│   ├── code-review/
│   │   └── skill.md           # 职能定义（结构由 Skill 自治，不强制）
│   ├── video-edit/
│   │   └── skill.md
│   ├── write-article/
│   │   └── skill.md
│   └── ...                    # 新增职能 = 加目录
└── prompts/                   # Prompt 库（无限扩展）
    ├── code-review-prompt.md
    ├── debug-fix-prompt.md
    └── ...                    # 新增 Prompt = 加文件
```

### 软链接引用（不内联）
- 意图卡存 `skill_ref`/`prompt_ref` 路径引用
- 执行时由执行器解析软链接 → 加载 Skill/Prompt 内容
- 库可热更新，已生成意图卡自动吃到最新版（解耦优势）

---

## 意图卡引用契约（新增字段）

在现有 `ccc-transfer` JSON schema 基础上新增：

```jsonc
{
  // 现有字段（不变）
  "title": "...",
  "goal": "...",
  "acceptance": ["..."],
  "pipeline": "dev",
  "executor_intent": "opencode",
  "project_id": "qb",
  "feasibility": "ok",
  "plan_md": "...",

  // 新增引用字段（软链接）
  "skill_ref": "skills/code-review",        // Skill 库路径引用
  "prompt_ref": "prompts/code-review-prompt", // Prompt 库路径引用
  "prompt_inline": "..."                     // 可选：Claude 组装时内联补充本卡特定上下文
}
```

**规则**：
- `skill_ref`/`prompt_ref` 是相对 `references/` 的路径
- 引用缺失 = gate 拒绝（`missing_skill_ref`）
- `prompt_inline` 可选，用于本卡特定上下文（不替代库引用）
- `executor_intent` 保留（Skill 可自带默认 executor，意图卡可覆盖）

---

## Claude 后台程序（② 层 · 固定 SOP · 多职能复用）

### 定义
- **独立后台程序**（非 IDE 会话、非对话面 Agent）
- **运行位置**：Mac 2017（与 Engine 同机，无对话上下文）
- **无个人记忆**（不继承任何 IDE 的会话上下文/性格，每次按 SOP 干活）
- **多职能复用**：同一个 Claude 后台程序，按阶段切换职能：
  - **拆卡阶段**：方案 → 标准意图卡链（从 Skill/Prompt 库组装软链接）
  - **飞轮阶段**：regress 重放、verdict 副闸、LPSN 推进等 Claude 职能
  - 职能切换 = 加载不同 Skill/Prompt（与 Skill 库设计天然契合）

### 拆卡职能 SOP（固定）
1. 读方案（来自 `docs/intent-proposals/` 的方案文件）
2. 识别方案中的职能单元（"这段是代码审查"、"这段是写码"、"这段是写文档"）
3. 去 `references/skills/` + `references/prompts/` 查找匹配的 Skill/Prompt
4. 按标准意图卡格式生成多卡链（含 `skill_ref`/`prompt_ref` 软链接）
5. 设置卡间依赖（`depends_on_tasks`）
6. 输出意图链 → 写入 backlog → Engine 自动消费

**不创造新 Skill**：库里找不到 → 拆卡失败 + 报告缺失职能（人去库里补）

---

## Engine 驱动角色（不变 · 仅强化边界）

Engine 在新架构下**只做驱动，不解析 Skill**：

| Engine 做 | Engine 不做 |
|-----------|-------------|
| transfer_gate 契约校验 | 解析 Skill 内容 |
| 入 backlog + wake | 解释 Prompt |
| fanout（epic → work 链式） | 判断 Skill 是否合适 |
| 调度执行器（OpenCode 等） | 修改 Skill/Prompt 库 |
| 跑验收探针 | 创造新职能 |
| 刷状态、释槽、自愈 | 二次拆分意图卡 |

**执行器加载 Skill**：执行器（如 OpenCode）拿到意图卡的 `skill_ref` → 解析软链接 → 加载 Skill/Prompt 内容 → 按 Skill 方式干活。Engine 只看到"执行器跑完了 + 探针绿"。

---

## 多入口接入（"任意 IDE 接入"的实现 · 方案 C）

### 机制：文件 + 一条激活命令

新架构下，IDE 接入 CCC 的标准路径：

| 步骤 | IDE 做 | CCC 做 |
|------|--------|--------|
| 1 | 加载 CCC 项目文件夹 | — |
| 2 | 读 `references/intent-proposal-sop.md` 了解方案标准格式 | — |
| 3 | 人 + IDE 谈方案 | — |
| 4 | 把方案写成 `.md` 到 `docs/intent-proposals/` | — |
| 5 | 跑 `ccc-submit-proposal <file>` 激活 Claude | — |
| 6 | — | Claude 后台程序拆意图链 → 写 backlog |
| 7 | — | Engine 自动消费（tick 拾取）→ 闭环驱动 |
| 8 | — | 产出（代码/文档/视频/...） |

### 为什么选方案 C（文件 + 激活命令）

| 候选 | 评估 | 结论 |
|------|------|------|
| A. 纯文件 + watcher | 要跑常驻 watcher 进程（多一个故障点） | 否决 |
| B. 纯 API | IDE 要会发 HTTP（部分 IDE 不便） | 否决 |
| **C. 文件 + 激活命令** | 任意 IDE 会写文件+会跑 shell 即可；无常驻进程 | **采用** |

### IDE 侧能力门槛（极低）
- **会写文件**（写到 `docs/intent-proposals/`）
- **会跑命令**（`ccc-submit-proposal <file>`）
- **会读 SOP**（`references/intent-proposal-sop.md`，项目内自带）

不需要：懂意图卡格式 / 会拆卡 / 固定人格 / 发 HTTP / 装插件。

### 标准方案文件格式
见 `references/intent-proposal-sop.md`（阶段 2 产出）。摘要：方案 `.md` 须含「目标 / 范围 / 步骤概要 / 验收意图」四节，Claude 拆卡程序按此识别职能单元。

---

## 新旧方案对比

| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| **拆卡人** | Desktop Agent / IDE Agent | Claude 后台固定程序（无个人记忆） |
| **IDE 职责** | 谈方案 + 拆卡 | 只谈方案 |
| **Skill 承载** | `executor_intent` 枚举（写死） | 独立 Skill 库 + 软链接引用 |
| **新增职能** | 改代码 + 改 schema | 库里加文件 |
| **职能扩展性** | 有限（开发向） | 无限（任意职能） |
| **Engine 角色** | 闭环执行 | 闭环执行（不变，强化不解析 Skill） |
| **记忆稳定性** | 依赖 IDE Agent（易漂移） | Claude 后台固定程序（无漂移） |
| **IDE 接入门槛** | 需要会拆卡 + 固定人格 | 只会谈方案即可 |

---

## 不变的核（保留）

新架构不推翻以下既有硬共识：
- 权威仓单写（2017 `apps/<id>/`）
- 探针验收（`## 验收` 可重放白名单命令）
- LPSN 飞轮（code_landed → intent_probed → intent_stable → next_intent）
- 双机拓扑（M1 对话面 / 2017 编排面）
- invent 硬关
- transfer_gate 质检（仅扩 schema，不弱化）
- Engine 自愈（hang 收尸、有限 reopen、耗尽回流）

---

## 并发控制与版本管理（补 · 2026-07-31）

### 并发控制（多方案同时提交）

**场景**：两个 IDE 同时提交方案；同一项目同时拆多个方案卡。

**决策**：
- **Claude 后台程序 = 单实例 + 串行队列**（不并发拆卡），避免 backlog 写竞争、卡 ID 冲突、依赖链交叉
- 实现方式：Hub `/api/desktop/proposal` 端点收到方案 → 写入 `.ccc/intent-proposals/` → 入串行队列 `proposal_queue.jsonl` → Claude 后台程序单实例逐个消费
- 同一项目同时多方案：按提交顺序串行拆卡，后到的等待前一个完成
- 不同项目：仍串行（Claude 单实例），但可优先级队列（`priority` 字段，默认 5，紧急 1）
- **不引入分布式锁**：单实例 + 队列即足够，与现有 Engine 串行模型一致

### Skill 版本管理（reconcile 热更新 vs 可重放）

**冲突**：Skill 库热更新（"已生成意图卡自动吃到最新版"）vs 探针验收可重放（"不变的核"硬共识）。

**决策**：**意图卡锁定 Skill 版本 = git commit hash**
- 意图卡引用字段 `skill_ref` = `skills/code-review@<short-hash>`（如 `skills/code-review@a1b2c3d`）
- Claude 后台程序拆卡时，从 Skill 库当前 HEAD 读取，写入意图卡时附 7 位 commit hash
- 验收重放时，Engine 按 hash 从 git 历史读取对应版本 Skill，不读当前 HEAD
- **Skill 库热更新只影响新拆的卡**，已生成卡的验收行为锁定不变
- 实现：`references/skills/` 是 git 管理目录，`git show <hash>:skills/code-review/skill.md` 读取历史版本
- 无 hash 时（向后兼容）：默认读 HEAD，但记 warning 到 `.ccc/intent-proposals/<id>.result.jsonl`

### 错误处理（拆卡失败流程）

**决策**：
- 拆卡失败 → 方案文件状态改 `failed` → 写 `.ccc/intent-proposals/<id>.result.jsonl`（含失败原因）
- Hub 返回失败给 M1 → Desktop 展示失败原因 → 用户改方案重新提交
- **部分拆卡成功**（3 张成功第 4 张失败）：成功的 3 张正常入 backlog，失败的第 4 张记 `result.jsonl`，方案状态 `partial`
- **格式异常/依赖循环/超时**：统一记 `failed`，附 `error_type`（format/circular/timeout/unknown）
- **重试**：不自动重试（Claude 无记忆，重试结果可能不同）；用户改方案后重新提交
- **超时**：单方案拆卡 120s 上限，超时杀进程，记 `failed: timeout`

### 灾难恢复（Hub 挂了怎么办）

**决策**：
- **Hub 挂时**：IDE 写方案到 M1 本地 outbox `~/.ccc/proposal-outbox/` → Hub 恢复后 `ccc-submit-proposal --flush-outbox` 批量提交
- outbox 文件命名：`<timestamp>-<proposal-id>.md`（幂等键 = 方案内容 hash）
- flush 机制：CLI 每 60s 检测 Hub 可达性，可达则批量 POST + 删除本地 outbox 文件
- **重复 flush 幂等**：Hub 端按方案内容 hash 去重，已存在的方案返回已有 `proposal_id`
- **Claude 拆卡进程崩溃**：Hub 检测子进程退出码 ≠ 0 → 标记方案 `failed: splitter_crash` → 不自动重启（用户重新提交）
- **Hub 重启后**：串行队列从 `proposal_queue.jsonl` 恢复，状态 `pending` 的继续拆

### 审计日志（拆卡记录 schema）

**决策**：`.ccc/intent-proposals/<id>.result.jsonl` 每行一个 JSON：
```jsonc
{
  "proposal_id": "<id>",
  "submitted_at": "2026-07-31T...",
  "submitted_from": "M1|CLI|external",
  "status": "ok|partial|failed",
  "cards_produced": [{"epic_id":"...","skill_ref":"...","prompt_ref":"..."}],
  "error": {"type":"format|circular|timeout|splitter_crash|unknown", "message":"..."},
  "splitter_version": "<claude-commit-hash>",
  "duration_s": 45
}
```
- 保留策略：永久（与 backlog 历史一致）
- 与 `events.jsonl` 关系：result.jsonl 是拆卡专属审计；events.jsonl 是 Engine 执行日志，不混
- 查看权限：同 backlog（项目内可见）

---

## 落地边界（本文档不做）

- **不改代码**（本文档仅定义架构基准）
- **不删现有文档**（批准后阶段 2-3 统一处理冲突）
- **不盘组件**（批准后阶段 4 做）
- **不写 Skill/Prompt 内容**（库里具体内容由后续职能需求驱动）

---

## 落地路径（批准后的阶段）

| 阶段 | 产物 | 谁确认 |
|------|------|--------|
| **1（本文）** | 新架构总览 | 老板批准 |
| 2 | 修改核心文档 + 新增 SOP：① `loop-engineer-authority.md`（新增「Skill/Prompt 解耦」「Claude 后台程序多职能」节）② `transfer-gate.md`（schema 加 skill_ref/prompt_ref）③ `intent-chain-dev-sop.md`（拆卡人改为 Claude 后台程序）④ `intent-card-sop.md`（卡片格式加引用字段）⑤ `dev-channel.md`（IDE 边界：只谈方案不拆卡）⑥ **新增** `references/intent-proposal-sop.md`（方案文件标准格式）⑦ **新增** `references/skills/` + `references/prompts/` 库目录 + 2-3 个测试 Skill/Prompt | 老板审 |
| 3 | 冲突文档清单（删除/标史/优化） | 老板审 |
| 4 | 组件盘点表（冗余/保留/改造） | 老板审 |
| 5 | 拼装 + 最小闭环验证 | 老板验收 |

---

## 已确认决策（2026-07-31）

1. **Claude 后台程序载体** = **独立后台程序**，运行在 **Mac 2017**，无记忆。多职能复用：拆卡阶段 + 飞轮阶段（regress/verdict 等）都是它，按阶段加载不同 Skill/Prompt 切换职能。
2. **Skill/Prompt 库初始内容** = **先建库，装 2-3 个测试 Skill/Prompt**（从电脑里现有 Skill 选取），跑通流程后再扩展。
3. **IDE 交方案入口** = **方案 C：文件 + 激活命令**。两阶段路径：
   - **阶段一（IDE 临时工作文件）**：IDE 写方案 `.md` 到任意可访问位置（建议项目内 `docs/intent-proposals/` 作为约定俗成，但不强制）
   - **阶段二（Hub 权威落盘）**：`ccc-submit-proposal <file>` 读文件 → `POST /api/desktop/proposal` → Hub 在 2017 落盘到业务仓 `.ccc/intent-proposals/<proposal_id>.md`（权威存储）
   - 常驻 watcher：无；适配任意 IDE；M1 临时文件用完即删

---

## 核心工程问题（双机架构地基 · 必须在阶段 2 前定）

> 以下问题源于双机架构调研，是新架构落地必须解决的工程地基。
> 每个问题给出【现状】【新架构冲击】【建议决策】，老板确认后写入阶段 2。

### 问题 1：方案文件跨机传输（最关键）

**现状**：M1 不保留业务第二树；意图卡走 Hub API（`/api/desktop/transfer`）；产物留在 2017，M1 看摘要。

**新架构冲击**：
- IDE 在 M1 写方案 `.md` 到 `docs/intent-proposals/`
- Claude 后台程序在 2017 要读这个方案
- **问题：方案文件在哪台机器？怎么跨机？**

**决策**：**方案文件走 Hub API，不落 M1 磁盘**。
- IDE 写方案到 M1 临时文件 → `ccc-submit-proposal <file>` 读文件 → `POST /api/desktop/proposal`（Hub 新端点，SSH 隧道）→ Hub 在 2017 落盘到业务仓 `.ccc/intent-proposals/<proposal_id>.md` → 激活 Claude 拆卡
- 理由：复用现有 SSH 隧道 + Hub 通道，不引入新传输机制；方案文件落业务仓（2017 权威），与 backlog/plan 同仓同树
- **不落 M1**：避免第二树问题；IDE 临时文件用完即删

---

### 问题 2：数据库

**现状**：CCC 编排面**无数据库**，纯文件 + JSONL + fcntl.flock。HP 业务仓有 PG 存根但未连接。

**新架构冲击**：
- Skill/Prompt 库是新增的无限扩展资源
- 方案文件 + 意图卡 + 拆卡记录持续累积
- 跨机查询（M1 看 2017 卡）靠 Hub HTTP 枚举目录

**决策**：**不引入数据库，保持文件 + JSONL**。
- Skill/Prompt 库 = 目录 + Markdown 文件（git 可追踪、可 diff、可热更新）
- 方案文件 = `.ccc/intent-proposals/<id>.md`（同 backlog 同仓）
- 拆卡记录 = `.ccc/intent-proposals/<id>.result.jsonl`（拆卡结果日志）
- 理由：文件型存储与现有 `.ccc/` 体系一致；git 原生追踪；跨机靠 Hub API；无 DB 运维负担
- **唯一例外**：若未来 events.jsonl 超万条，考虑 SQLite 索引（但不引入 PG/MySQL）

---

### 问题 3：git tree（方案文件归属哪个仓）

**现状**：业务仓权威在 2017 `~/program/apps/<name>/`；M1 不 clone 业务仓；平台仓 CCC 在 M1+2017 双份同步。

**新架构冲击**：
- `docs/intent-proposals/` 这个路径在哪个仓？
  - 选项 A：平台仓 CCC（M1+2017 双份，git 同步）
  - 选项 B：业务仓 `apps/<name>/.ccc/intent-proposals/`（2017 权威，M1 不存在）
- **问题：方案文件归平台仓还是业务仓？**

**决策**：**方案文件归业务仓 `.ccc/intent-proposals/`**。
- 理由 1：方案是业务意图，应与业务 backlog/plan 同仓同树
- 理由 2：避免污染平台仓 CCC（CCC 是编排工具，不是业务意图仓库）
- 理由 3：Claude 后台程序在 2017 直接读业务仓文件，零跨机
- **IDE 侧**：IDE 写临时文件 → Hub API → 2017 业务仓落盘（IDE 不需要知道业务仓路径）

---

### 问题 4：项目隔离

**现状**：每项目 = 2017 `~/program/apps/<name>/`（独立 .git + `.ccc/`）；三层注册（Hub 发现 / Agent cwd / Engine 消费名单）。

**新架构冲击**：
- 方案文件需按项目隔离（qb 的方案不能进 hp 的仓）
- Claude 后台程序拆卡时要知道"这个方案属于哪个项目"

**决策**：**方案文件按项目隔离到业务仓 `.ccc/intent-proposals/`**。
- `POST /api/desktop/proposal` 必带 `project_id` → Hub 路由到对应业务仓
- 落盘路径：`~/program/apps/<name>/.ccc/intent-proposals/<proposal_id>.md`
- Claude 后台程序拆卡时 `cwd = 业务仓路径`，读该仓 `.ccc/intent-proposals/`
- **平台仓 CCC 不存业务方案**（CCC 只存 Skill/Prompt 库 + 平台文档）

---

### 问题 5：Skill/Prompt 库位置与跨机同步

**现状**：角色 skill 在 `skills/ccc-<role>/SKILL.md`（平台仓 CCC，M1+2017 双份 git 同步）。

**新架构冲击**：
- 新增 `references/skills/` + `references/prompts/` 无限扩展库
- Claude 后台程序在 2017 要读这个库
- IDE 在 M1 也可能想浏览库（了解有哪些职能可用）

**决策**：**Skill/Prompt 库归平台仓 CCC，M1+2017 双份 git 同步**。
- 路径：`/Users/apple/program/CCC/references/skills/` + `references/prompts/`
- 同步机制：复用现有 `ccc-sync-after-push.sh`（M1 push → 2017 pull --ff-only）
- Claude 后台程序在 2017 读 `/Users/apple/program/CCC/references/skills/`（本机磁盘）
- IDE 在 M1 读同路径（本机磁盘，git 同步后一致）
- **不通过 Hub API 传 Skill**（库是平台资源，不是业务数据；git 同步足够）

---

### 问题 6：会话隔离（Claude 后台程序多职能）

**现状**：product-session 每 task 独立子进程，跨 task 不复用 SDK 会话（无长记忆）。

**新架构冲击**：
- Claude 后台程序多职能复用（拆卡 + 飞轮）
- 拆卡职能不能被飞轮职能污染（无记忆 = 无串扰）

**决策**：**每职能独立子进程，跨职能不复用会话**。
- 拆卡 = 独立子进程 `ccc-intent-splitter.py --proposal <id>`（`start_new_session=True`）
- 飞轮 = 现有 product-session / reviewer（不变）
- 每子进程独立 `CLAUDE_CONFIG_DIR`（拆卡用 `~/.ccc/intent-splitter`，与 engine-claude 隔离）
- **无记忆保证**：子进程退出即销毁会话；下次拆卡是新进程 + 新会话
- 拆卡进程配置家注入「拆卡 SOP」+ 「Skill/Prompt 库索引」，不注入任何对话历史

---

### 问题 7：IDE 激活命令的运行位置

**现状**：`ccc-submit-proposal` 命令在阶段 1 设想，但没定在哪台机器跑。

**新架构冲击**：
- IDE 在 M1，Claude 在 2017
- 命令在 M1 跑 → 要跨机激活 2017 的 Claude（走 SSH / Hub API）
- 命令在 2017 跑 → IDE 要 SSH 到 2017 执行（部分 IDE 不便）

**决策**：**命令在 M1 跑，走 Hub API 激活**。
- `ccc-submit-proposal <file>` 是 M1 本地 CLI 脚本
- 脚本读方案文件 → `POST http://127.0.0.1:17777/api/desktop/proposal`（SSH 隧道）→ Hub 在 2017 激活 Claude 拆卡
- IDE 只需在 M1 跑 shell 命令（任意 IDE 都能做）
- **不要求 IDE 会 SSH**（SSH 隧道由 launchd 保活，IDE 无感知）

---

### 问题 8：Hub 单点加重

**现状**：Hub 是唯一跨机通道（transfer / flow / lens / baseline / files）；Hub 挂 → Desktop 转任务进 outbox。

**新架构冲击**：
- 新增 `POST /api/desktop/proposal` 端点 → Hub 承担方案接收 + 激活 Claude
- Hub 单点依赖加重

**决策**：**复用 Hub，但拆卡异步化 + outbox 兜底**。
- `POST /api/desktop/proposal` 同步返回 `proposal_id` + `accepted: true`（Hub 落盘方案文件即返回）
- Claude 拆卡异步进行（Hub 起 `ccc-intent-splitter.py` 子进程）
- 拆卡结果写 `.ccc/intent-proposals/<id>.result.jsonl` + 生成的意图卡写 backlog
- Hub 挂时：IDE 写方案到 M1 本地 outbox（同 transfer-outbox 机制）→ Hub 恢复后 flush
- **不引入新服务**（复用 Hub + outbox 兜底）

---

### 问题 9：产物回传（M1 看拆卡结果 + 产出）

**现状**：verdict/report 留 2017，M1 看 Hub 摘要；代码 diff 走 GitHub。

**新架构冲击**：
- 拆卡结果（意图链）需要回传 M1 给用户确认
- 后续产出（代码/文档/视频）也需要回传

**决策**：**渐进式自动化（拆卡结果走 Hub API，产出走现有机制）**。
- 拆卡完成 → Hub 写 `.ccc/intent-proposals/<id>.result.jsonl`（含生成的意图卡列表）
- M1 通过 `GET /api/desktop/proposal/<id>/result` 拉取拆卡结果
- 产出回传不变（代码走 GitHub，verdict 走 Hub 摘要）
- **Phase A（上线初期，默认）**：Desktop 展示拆卡结果（意图链卡片）→ 用户确认 → 入 backlog
  - 理由：新流程上线，拆卡质量未验证，需人工把关
- **Phase B（跑稳后）**：拆卡完成 → 直接入 backlog → 看板可见
  - 切换条件：`~/.ccc/control.json` 加 `intent_splitter_auto_commit` 字段，默认 `false`
  - 释放条件：连续 10 次拆卡零修正 → 可手动切 `true`
  - 这是渐进式自动化最佳实践：先人工把关，稳定后释放

---

### 问题 10：CCC 仓角色变化（平台仓 → 平台仓 + Skill 库）

**现状**：CCC 仓是编排工具仓（scripts/docs/references），`role=orch` + `engine=false`，不可下达。

**新架构冲击**：
- Skill/Prompt 库归 CCC 仓 → CCC 仓承担"平台资源仓"新角色
- CCC 仓内容变化：新增 `references/skills/` + `references/prompts/` + `references/intent-proposal-sop.md`

**决策**：**CCC 仓角色不变，仅扩内容**。
- `role=orch` + `engine=false` 不变（CCC 仓本身不可下达为业务 epic）
- 新增 `references/skills/` + `references/prompts/` + `references/intent-proposal-sop.md`
- 这些是平台资源，被 Claude 后台程序 + 执行器读取，不是业务意图
- **CCC 仓的 `.ccc/board/` 仍仅平台自研**（不消费业务 epic）

---

## 核心工程问题决策汇总（已定 · 2026-07-31）

| # | 问题 | 决策 |
|---|------|----------|
| 1 | 方案文件跨机 | 走 Hub API，不落 M1 |
| 2 | 数据库 | 不引入，保持文件 + JSONL |
| 3 | git tree 归属 | 方案文件归业务仓 `.ccc/intent-proposals/` |
| 4 | 项目隔离 | 按项目隔离到业务仓 |
| 5 | Skill/Prompt 库位置 | 归平台仓 CCC，git 同步 |
| 6 | 会话隔离 | 拆卡 = 独立子进程 + 独立配置家 |
| 7 | 激活命令运行位置 | 在 M1 跑，走 Hub API 激活 |
| 8 | Hub 单点 | 复用 Hub + outbox 兜底 |
| 9 | 产物回传 | 渐进式：初期需确认，跑稳后自动入（`intent_splitter_auto_commit`） |
| 10 | CCC 仓角色 | 不变，仅扩内容 |

**状态**：已定，进入阶段 2。
