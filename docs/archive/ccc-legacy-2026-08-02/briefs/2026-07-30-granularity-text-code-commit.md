# 评估：意图颗粒度 · 文/码分轨 · Commit 职责（2026-07-30）

> 证据：舰队 failures（hang / empty_acceptance / oversplit / product timeout）+ OpenCode 低质量长卡。  
> 结论进权威「意图卡供给 / 编排自愈」；实现：`transfer_gate` · `_product_fanout` · SOP · `hub_voice`。

## 1. 颗粒度（失败主因）

| 层 | 正确模型 | 错误现状 |
|----|----------|----------|
| **意图** | 人/对话 Agent 定的**大任务**（可多卡链） | 一轮糊一张大卡塞给 OpenCode |
| **扇出** | epic → **小而硬**的 work（1 phase、≤5 文件、1～2 强探针） | Step1–6 / 跨目录 / 文码混装 |
| **OpenCode** | **只**接小、明确、低难度**代码**任务 | 吃文档/VERSION/规划 → hang / 假绿 |

**硬规则**：大意图可以、也应当拆成多张意图卡；**每张进产线的 work 必须小而硬**。  
`complexity=small` = 规模提示，不跳审测；真回归禁 small 抬 medium（既有）。

## 2. 文 / 码分轨

| 轨 | 谁做 | 进 Engine/OpenCode？ |
|----|------|----------------------|
| **文本**（规划叙述、脑包 decided、SOP 文案、changelog 叙述、对齐文档） | **对话 Agent**（Hub mind / 本机 CCC 写；业务脑经 Hub） | **否**（gate 拒 `text_task_agent_track`） |
| **代码**（实现、单测、可执行验收脚本） | **产线** Engine → OpenCode（或 script_seed/util_probe 短路径） | **是** |
| **板务/卫生** | Agent `hub_repair`；偶发 `pipeline=ops` | 禁卫生 epic 主业 |

纯 `docs/` · `CHANGELOG` · `VERSION`  alone · `CLAUDE.md` · `.ccc/agent-mind` · `GOAL.md` / `dev-plan` 叙述 → **文本轨**。  
scope 含 `.py`/`.rs`/`.ts`/测试路径 → **代码轨**（可附带极少文档，但验收须代码探针）。

## 3. Commit / 脏树职责（最佳方案 = 分责，非二选一）

| 对象 | 谁 commit | 说明 |
|------|-----------|------|
| **业务源码 + 本卡测试** | OpenCode 优先；**Engine DoD** `ensure_task_commit` 兜底 | 只 stage scope；message 含 `task_id`；禁 `git add -A` |
| **文本/脑包** | **不经 OpenCode**；Agent→Hub `decided`/digest；平台仓文档可由 Cursor/Agent 本机提交 | 业务仓禁止 Agent SSH 直写 |
| **`.ccc/` / lessons 噪音** | **不提交业务仓**；`ccc_hygiene` **不挡** ready | 禁卫生 epic 清脏；禁把脏文件数当业务失败 |

**为何不选「全给 Agent」**：业务权威仓在 2017，Agent 无直写；DoD 已能安全兜底代码 commit。  
**为何不选「全给 Engine」**：Engine/OpenCode 做文案又慢又 hang，且污染 scope。

SSOT 实现：`references/commit-folder-hygiene-sop.md`（本节同步）+ `_task_commit` + `_project_baseline` dirty_kind。

## 4. 预期降失败率

1. Gate 提前拦过大 work / 纯文卡 → **零 OpenCode** 空转 hang。  
2. 扇出二次门禁 oversized child → 少 `phase_unresolvable` / acceptance 空子弹。  
3. Commit 分责清晰 → 少 dirty_block 假红、少卫生 epic。  
4. Agent 心智注入文码分轨 → 定卡即小而硬，repair-queue 优化卡同规则。

## 5. 非目标

- 不放开 invent；不对 orch 写业务 epic。  
- 不把 FlowWeave 式画布当写码主控。  
- 不自动 `stable`；不抬 OpenCode 并发代替修闸门。
