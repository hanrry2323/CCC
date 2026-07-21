# 角色生成机制（SSOT）

> **状态**：架构定稿（2026-07-21）  
> **冲突裁决**：[`VISION.md`](../VISION.md) §「无穷角色机制」> 本文 > 任何残留「7 角色」字面表述  
> **一句话**：CCC **不依赖任何固定 skill / prompt**；角色 = **任务 → 工具路由 → 注入 Skill + Prompt** 的即时产物。`skills/ccc-*` 是流水线阶段的**默认 seed**，不是用户菜单。

---

## 1. 核心命题

| 命题 | 说明 |
|------|------|
| 角色不是预定义列表 | 早期文档的「7 角色」（product/dev/reviewer/tester/ops/kb/regress）是 **v0.16 默认 seed**，不是产品形态 |
| 角色由任务即时生成 | 每次任务实例：意图 → 选执行器 → 注入 Skill + Prompt = 本次角色 |
| 用户不选角色、不背 Skill | 用户只面对意图；Skill/Prompt 是编排面的事 |
| 可覆盖任意行业 | 行业差异落在 **Skill / Prompt / 工具路由**，不落在「再造一个角色产品」 |
| 红线 6「角色不互串」仍成立 | 指的是**同一次任务实例内**阶段职责边界（拆解包不写业务码），**不是**「用户必须先选角色」 |

## 2. 生成公式

```text
任务意图
  → 路由工具（谁执行：Claude / OpenCode / …）
  → 注入 Skill + Prompt（这次怎么干）
  = 本次「角色」
```

- 同一个「dev 阶段」可因 task 不同注入不同 Skill（前端 / 后端 / 数据 / …）
- 同一个 Skill 可被不同阶段复用
- 新增角色 = 新增 Skill + Prompt 文件，**不改产品形态**

## 3. 默认 seed（v0.16 起，可扩）

| 阶段 | 默认 Skill | 触发 |
|------|-----------|------|
| product | `skills/ccc-product/` | backlog pending epic |
| dev | `skills/ccc-dev/` | planned work |
| reviewer | `skills/ccc-reviewer/` | testing 门禁 |
| tester | `skills/ccc-tester/` | testing 门禁 |
| ops | `skills/ccc-ops/` | 手动 / 可选 |
| kb | `skills/ccc-kb/` | verified 非空 |
| regress | `skills/ccc-regress/` | 23:30 / 手动 |

**这 7 个是 seed，不是上限。** 业务可在 `skills/` 下加 `ccc-<custom>/SKILL.md`，由 Engine 按阶段名加载。

## 4. 文档口径（强制）

| 残留表述 | 改为 |
|---------|------|
| 「7 角色」当产品形态 | **阶段能力包（默认 seed 7，可扩）** |
| 「完整 7 角色 pipeline」 | **完整阶段能力包 pipeline** |
| 「用户先选 7 个角色」 | **禁止**（见 [`../STARTUP-BRIEF.md`](../../STARTUP-BRIEF.md) 勿再说） |
| 「7 角色看板流水线」（红线 12） | **CCC 流水线**（与角色数无关） |

历史文档（`CHANGELOG.md` / `docs/roadmap.md` / `docs/archive/`）保留「7 角色」**作为史实**，不回改；现网 SSOT 以本文件口径为准。

## 5. 与 Loop Engineering 的对照

| Loop Engineering 概念 | CCC 落点 | 备注 |
|----------------------|---------|------|
| Skill（一类任务做法手册） | `skills/ccc-<role>/SKILL.md` | seed 7，可扩 |
| Agent（执行者） | 执行面 + Engine roles | 角色由 Skill+Prompt 即时生成 |
| Sub-agent | `scripts/board/roles/` | Engine 调度，非主 Agent 派出 |
| Workflow | Engine 阶段串行 | 阶段 = 默认 Skill 包，非角色菜单 |

详见 [`four-role-fluency-charter.md`](four-role-fluency-charter.md) §架构评估。

## 6. 关联

- 叙事 SSOT：[`../VISION.md`](../VISION.md) §「无穷角色机制」  
- 战略地图：[`../STRATEGY-MAP.md`](../STRATEGY-MAP.md) §0 翻译口径  
- 启动简报：[`../../STARTUP-BRIEF.md`](../../STARTUP-BRIEF.md)  
- 红线：[`../../references/red-lines.md`](../../references/red-lines.md) R-6 / R-12  
- 看板契约：[`../../references/board-task-schema.md`](../../references/board-task-schema.md) §复杂度分流
