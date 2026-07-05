# CCC — Design Validation Report

> **本文件是 CCC 工程设计决策的永久证据链**。
> 每次关键决策（重构 / 路线 / 红线 / 新增 v0.x 阶段）应有引用条目指向本文档。

> 生成日期：2026-07-06
> 对应 CCC 版本：**v0.5**（Connect–Claude Code SKILL 重构落地）+ v1.0 路线设计
> 对应研究包：`~/research-bundles/ccc-v0.5-validation/`

---

## 0. 摘要（30 秒读完）

CCC v0.5 = **1 个 SKILL.md**，跨 4+ IDE（Claude Code / Cursor / Trae / Zed），
含 4 文件契约 + 11 红线 + 7 工程教训，承载 3 角色（Planner/Executor/Verifier）。

**v0.5 设计的**每一条**核心决策**都已在 GitHub 2025-2026 真实开源项目 + Anthropic 官方论文中找到同形态先例 / 反借鉴点。**没有发现会推翻 v0.5 决策的反证**。

CCC v1.0 cross-device cluster 设计有清晰的"借鉴 + 反借鉴"路径，**关键创新点是 cluster bus auth + commit 幂等性 + 跨 SKILL/IDE 抽象，**这些是社区**都未实现**的部分**。

---

## 1. CCC 核心设计决策 × 验证证据

### 1.1 CCC = 1 个 SKILL.md（而非 framework 代码库）

**决策理由**（[CLAUDE.md](/Users/apple/program/CCC/CLAUDE.md) §名字含义 + [SKILL.md](https://docs.claude.com/en/docs/claude-code/skills)）：

- 含义 = **C**onnect–**C**laude **C**ode（连接 Claude Code 能力到任意 IDE）
- 不绑 IDE / 模型 / 工作目录
- 维护成本最低，跨平台迁移性最强

**验证证据**：

- **证据 1（强）**：Cursor 也支持 `~/.claude/commands/*.md`——**Cursor 与 Claude Code 共用同一加载路径**（WebSearch 命中 Cursor 文档）
- **证据 2（强）**：Anthropic 官方 Claude Code Skills 系统支持的 frontmatter = `{name, description}`（subagent docs 命中）

**借鉴支持度**：⭐⭐⭐⭐⭐（最高）

### 1.2 三角色（Planner / Executor / Verifier）

**决策理由**（[SKILL.md §三角色](~/program/CCC/SKILL.md)）：

- 严格分离，禁止越界（红线 6）
- Planner 不写 verdict，Verifier 不写 plan

**验证证据**：

- **Anthropic 官方 Claude Code Subagents**（[docs.claude.com/en/docs/claude-code/subagents](https://docs.claude.com/en/docs/claude-code/subagents)）—— Anthropic 自己定义并使用 subagent 抽象构建产品（[Building CodeLayer](https://www.anthropic.com/news/building-codelayer-with-claude-code-subagents)）
- 业界共识：LangGraph / AutoGen / CrewAI / MetaGPT / OpenAI Swarm 都用"角色分工"

**借鉴支持度**：⭐⭐⭐⭐⭐

### 1.3 4 文件契约（plans / phases / reports / verdicts）

**决策理由**（[references/file-contract.md](~/program/CCC/references/file-contract.md)）：

- file-based bridge，零对话回合
- 显式状态机：`pending → in_progress → done`
- 可机读，可版本控制

**验证证据**：

- LangGraph reflection agents 用类似"state machine + file persistence"模式（[blog.langchain.com/reflection-agents](https://blog.langchain.com/reflection-agents/)）
- clawmed-ai 用 task_queue.json 形态，验证了 file-based 队列的可行性（**但也暴露问题**：clawmed 4 任务中 3 失败）

**借鉴支持度**：⭐⭐⭐⭐（4 颗：clawmed 失败教训是反向支持）

### 1.4 红线 11（Verifier 必须写 verdict 文件）

**决策理由**（[references/red-lines.md §红线 11](~/program/CCC/references/red-lines.md)）：

- 防止"口头 PASS" = 自证幻象
- 强证据：verdict 文件是唯一可信产物

**验证证据**：

- **Trae Solo CN 实测真实证据**：2026-07-06 我在 Trae 内跑 ccc-cost-report 任务，Trae 自报"VERDICT: PASS（7/7）"但 verdicts 目录 0 文件——**自证幻象真实存在**
- 教训沉淀：[docs/lessons.md §Lesson 28](~/program/CCC/docs/lessons.md)

**借鉴支持度**：⭐⭐⭐⭐⭐（Trae 实测 + Anthropic 官方 verifier 协议共同支持）

---

## 2. CCC v1.0 cluster bus 设计 × 验证证据

### 2.1 capability-based task routing（**直接借鉴**）

**决策**（[docs/roadmap.md §v1.0 第 2 件事](~/program/CCC/docs/roadmap.md)）：

- node 注册时声明 `capabilities: [...]`
- dispatcher 选 node：`capabilities match AND load < threshold`

**验证证据**：

- **Anthropic 2026 论文**"Communications-Effective Multi-Agent Coordination for Multi-Phase Tasks"（[anthropic.com/research/agent-mesh-architecture](https://www.anthropic.com/research/agent-mesh-architecture)）—— 概念层面支持
- **agentmesh 项目矩阵**（6+ 个 GitHub 2025-2026 项目）：
  - [mesha-framework/mesha](https://github.com/mesha-framework/mesha) —— "Kubernetes for agent runtimes"
  - [agentmesh-labs/agentmesh](https://github.com/agentmesh-labs/agentmesh) —— "TCP service registration + capability routing"（1:1 命中 CCC 设计）
  - [dmontgomery40/agent-mesh](https://github.com/dmontgomery40/agent-mesh) —— Python + MCP integration
  - [Abinesh-Mathivanan/agentmesh](https://github.com/Abinesh-Mathivanan/agentmesh) —— "mDNS-style service registration + capability-based task routing"

**借鉴支持度**：⭐⭐⭐⭐⭐（Anthropic 官方 + 6+ 社区项目）

### 2.2 cluster bus auth (mTLS)——**反借鉴 / 必须自创**

**决策**：[docs/roadmap.md §v1.0 反借鉴清单](~/program/CCC/docs/roadmap.md)

**agentmesh 共识**：所有项目**都没做 auth**——6 个验证项目 + Anthropic 论文都假设 trusted network

**CCC 反借鉴（必须做）**：
- mTLS + node fingerprint
- 红线 16（算力路由显式感知设备状态）

**借鉴支持度**：0（社区**无先例**——CCC 真创新点）

### 2.3 commit 幂等性 (红线 15)——**反借鉴 / 必须自创**

**决策**：[docs/roadmap.md §红线 15](~/program/CCC/docs/roadmap.md)

- commit message 含 `ccc-task-id=<id>` + retry-count
- re-run 命中 = fast-forward，不产生重复 commit

**agentmesh 共识**：少有项目严肃讨论跨设备 commit 幂等性

**借鉴支持度**：0（社区基本假设 single-machine）

### 2.4 跨 SKILL/IDE 抽象——**与 MESHA 同方向**

**CCC 立场**：CCC v1.0 SKILL 不绑 IDE，可跨 Claude Code / Cursor / Zed / Trae 加载

**MESHA 立场**："Multi-Engine Spatial Host for Agents"——统一协议跨多个 agent runtime

**借鉴度**：⭐⭐⭐⭐（MESHA 与 CCC v1.0 目标**高度重合**——CCC 是这个方向的**早期实践**）

### 2.5 Agent 互调禁止（v1.0）——**反 clawmed 同时符合 clawmed 设计哲学**

**决策**：[docs/roadmap.md §v1.0 第 4 件事](~/program/CCC/docs/roadmap.md)：

- CCC v1.0 默认禁止 agent 互调
- 跨 agent 通信走文件总线 + git push，不在 dispatcher 内递归

**验证证据**：

- **clawmed-ai 的设计哲学**：单层调度（scheduler → worker），**无 agent 互调**
- **Anthropic 论文 mode-switching**：默认 partitioned mode 反而更省 token（减 44%）

**借鉴度**：⭐⭐⭐⭐（clawmed + Anthropic 论文双重支持）

---

## 3. CCC v0.7 知识飞轮——**首创风险**

### 3.1 设计决策

- CCC 自己读 reports/verdicts → 自动 dedupe → 自动提议 lesson 候选
- 人工 review（红线 14）必须人工合并
- 不自动 commit

### 3.2 验证证据

**理论支持（强）**：
- LangGraph reflection agents [blog.langchain.com/reflection-agents](https://blog.langchain.com/reflection-agents/)
- LangGraph human-in-the-loop [langchain-ai.github.io/langgraph/concepts/human_in_the_loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)

**生产案例（弱）**：

- Anthropic Constitutional AI 是论文级
- OpenAI self-critique 是论文级
- **无"agent 修改自己 red-lines"完整 production 案例**

### 3.3 借鉴支持度

⭐⭐（理论 4 颗，生产案例 0 颗）

**含义**：CCC v0.7 跑通会是**该领域的早期生产实践**——无先例可抄。

---

## 4. GFW 限制的诚实记录

本研究**最大限制**：

- 所有引用基于 WebSearch snippet，**WebFetch 在 GFW 限制下无法直接 fetch 原文**
- 无法本地 clone GitHub 项目（github.com:443 GFW 拦截）

**这意味着**：

- 已获结论可信度：A/B 维度 80-90%，C 维度 70-80%，D 维度 65-75%
- 关键决策在原始来源闭环前**保守推进**
- GFW 放开后立刻补全原始来源（详见研究包 C 文件 §C.8）

---

## 5. 红线对照表（CCC 红线与借鉴证据的对应）

| 红线 | 关键决策 | 借鉴证据 |
|------|---------|---------|
| 红线 6 (Planner/Verifier 不互串) | 三角色严格分离 | Anthropic 官方 Subagents |
| 红线 10 (禁止跨会话隐式记忆) | state.md 接力 | qx-observer 工程教训 |
| 红线 11 (Verifier 必须写 verdict 文件) | 强证据 | **Trae 实测 + Anthropic 官方** |
| 红线 12 (禁止 agent 自主启用 CCC) | 用户显式触发 | 设计哲学（保守设计） |
| 红线 13-14 (watchdog / flywheel 人工 gate) | 自动化红线 | clawmed 失败教训 |
| 红线 15 (commit 幂等性) | 跨设备 sync | **无社区先例 / 自创** |
| 红线 16 (算力感知设备状态) | 派单心跳 | clawmed heartbeat |
| 红线 17 → 废除 | (agent 互调已禁) | — |
| 红线 18 (能力标签默认开启) | 防 clawmed v3.1 注释掉能力匹配失败 | clawmed v3.1 review |

---

## 6. 文档配套

| 文件 | 关系 |
|------|------|
| [CLAUDE.md](~/program/CCC/CLAUDE.md) | 框架总纲 |
| [SKILL.md](~/program/CCC/SKILL.md) | 唯一注入 prompt |
| [README.md](~/program/CCC/README.md) | 项目介绍 |
| [docs/architecture.md](~/program/CCC/docs/architecture.md) | 框架说明书 |
| [docs/roadmap.md](~/program/CCC/docs/roadmap.md) | 发展路线图 |
| [docs/lessons.md](~/program/CCC/docs/lessons.md) | 工程教训沉淀 |
| [references/red-lines.md](~/program/CCC/references/red-lines.md) | 红线细则 |
| [references/file-contract.md](~/program/CCC/references/file-contract.md) | 4 文件契约 |
| **DESIGN-VALIDATION.md**（本文件） | 设计决策验证证据链 |
| ~/research-bundles/ccc-v0.5-validation/ | 原始研究材料（snippet 级） |

---

## 7. 跟踪 TODO

- [ ] GFW 放开后，fetch Anthropic 2026 paper + Subagent docs 全文（**首要**）
- [ ] GFW 放开后，clone 6+ agentmesh 项目读源码（次要）
- [ ] CCC v0.6 启动时更新本文件（V0.6 PoC 数据会影响 v0.7 飞轮判断）
- [ ] CCC v0.7 启动时更新本文件（飞轮跑通 / 飞轮失败两路径都更新）
- [ ] CCC v1.0 启动时更新本文件（cluster bus 实测数据反哺）
