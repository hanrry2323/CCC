# 方案 · CCC 计划页面（#/plans）实施方案

> 项目：ccc · 编号：ccc-plan-009 · 状态：已完成 · 作者：老板 + Claude Code · 工具：Claude Code
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无
> 审核：Codex（审查意见 `docs/notes/2026-08-09-plans-page-review-codex.md`）
> 迁移自：docs/notes/2026-08-09-plans-page-implementation.md（自举收口）
> 审查意见：`docs/notes/2026-08-09-plans-page-review-codex.md`
>
> **执行前提（硬）**：本次实施不走 CCC 自动流程。由 Claude Code 亲自开发执行；不建卡文件、不进看板、不走 Engine 派发、不机审合入。8 个阶段每阶段完成由 Codex 审核，通过后再进下一阶段。

---

## 0. 一句话目标

在 CCC 看板和线路图之间增加「计划」页面（`#/plans`），作为**方案池**——统一管理所有项目的开发方案、版本计划、架构提案，形成「线路图 → 计划 → 看板」三层金字塔。

---

## 1. 路径规范（硬 · 定死）

### 1.1 方案文件路径

```text
docs/projects/<prefix>/plans/<编号>-<slug>.md
```

| 段 | 规则 | 例 | 非法例 |
|----|------|----|--------|
| **prefix** | 与 `registry.yaml` 前缀一致，2–4 位小写字母 | `ccc` `xy` `hp` `mx` `qb` | `CCC` `qh` |
| **编号** | 3 位数字，同前缀内自增，独立于任务卡编号 | `001` `002` | `1` `0001` |
| **slug** | 小写字母/数字/连字符，从标题派生 | `arch-upgrade-v2` | `架构升级` |
| **扩展名** | 固定 `.md` | — | `.MD` |

**与任务卡编号的关系**：方案编号和卡编号**分区独立**。方案用 `plans/` 下的编号，转卡时由 `new-card.sh` 生成卡编号。防止方案编号与卡编号冲突。

### 1.2 目录结构

```
docs/projects/<prefix>/
├── README.md          ← 项目档案（现有，不变）
└── plans/             ← 🆕 方案池
    ├── 001-<slug>.md
    ├── 002-<slug>.md
    └── ...
```

### 1.3 禁止

- 禁止方案文件放在 `docs/projects/<prefix>/` 根目录（不进 plans/ 子目录）
- 禁止用任务卡编号（如 `xy021`）给方案编号
- 禁止在 `docs/dispatch/` 下放方案文件——那是任务卡目录
- 禁止在 `docs/notes/` 新建方案文件——notes 是临时笔记，7 天内清退

---

## 2. 方案模板（硬 · 统一）

每个方案文件必须包含以下字段。模板文件放在 `docs/projects/_template/plan-template.md`。

```markdown
# 方案 · <人读标题>

> 项目：<prefix> · 编号：<prefix>-plan-<NNN> · 状态：<状态> · 作者：<作者> · 工具：<工具名>
> 创建：YYYY-MM-DD · 更新：YYYY-MM-DD
> 关联卡：无 | <card-id>, <card-id>
> 关联方案：无 | <plan-id>, <plan-id>

## 目标

<一句话说清要达成什么>

## 背景

<为什么需要这个方案，解决什么问题>

## 方案内容

<具体怎么做，分步骤写>

## 验收标准

- [ ] <可验证的完成条件 1>
- [ ] <可验证的完成条件 2>

## 转卡计划

<预计拆成几张卡、每张卡做什么。转卡时脚本读取此段生成任务卡>

## 备注

<风险、依赖、排期考虑等>
```

**状态机**（五态定死）：

```text
草案 → 已确认 → 部分执行 → 已完成 → 作废
```

| 状态 | 含义 |
|------|------|
| **草案** | 方案初稿，待讨论确认 |
| **已确认** | 方案已定，等待排期进入看板 |
| **部分执行** | 已拆分部分任务卡进入看板 |
| **已完成** | 全部关联任务卡已关闭 |
| **作废** | 方案不再执行（保留历史，不删除） |

---

## 3. 前端页面设计

### 3.1 路由与导航

- 路由：`#/plans`
- 导航栏位置：看板 和 线路图 之间

```html
<a class="hub-nav-link" data-route="board" href="#/board">看板</a>
<a class="hub-nav-link" data-route="plans" href="#/plans">计划</a>   <!-- 🆕 -->
<a class="hub-nav-link" data-route="roadmap" href="#/roadmap">线路图</a>
```

### 3.2 页面布局

```
┌──────────────────────────────────────────────┐
│ 计划                                [+ 新建方案] │
├──────────────────────────────────────────────┤
│ 筛选：[全部项目 ▾] [全部状态 ▾]   🔍 搜索...   │
├──────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐  │
│ │ xy · 已确认  #001  视频质量 v3 升级方案   │  │
│ │ 作者：老板 · Claude Code · 2026-08-05    │  │
│ │ 关联卡：xy021, xy022                     │  │
│ │ 验收：3/4 项完成                          │  │
│ ├─────────────────────────────────────────┤  │
│ │ ccc · 草案   #003  计划页面实现方案       │  │
│ │ 作者：老板 · Claude Code · 2026-08-09    │  │
│ │ [转为任务卡]                              │  │
│ └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### 3.3 核心功能

| 功能 | 描述 |
|------|------|
| **方案列表** | 按项目分组、按状态筛选、按关键词搜索 |
| **方案详情** | 点击展开/跳转，Markdown 渲染 |
| **新建方案** | 表单填写（标题/项目/内容），自动生成编号、落盘到标准路径 |
| **转为任务卡** | 人触发，读取方案的「转卡计划」段，调 `new-card.sh` 生成任务卡，自动更新方案状态和关联卡字段 |
| **状态流转** | 手动改状态：草案→已确认→部分执行→已完成/作废 |

### 3.4 API 设计

在 `server/web/server.py` 新增：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/plans/list` | 方案列表（支持 `?project=&status=&q=` 筛选） |
| GET | `/plans/detail?path=...` | 单方案详情（Markdown 渲染） |
| POST | `/plans/create` | 新建方案（写盘 + 校验） |
| POST | `/plans/update` | 更新方案状态/内容 |
| POST | `/plans/convert` | 转为任务卡（调 `new-card.sh`） |

---

## 4. 存量文档处置

侦查结果：散落方案集中在 4 个位置，分类处置如下。

### 4.1 处置分类

| 类别 | 标记 | 动作 |
|------|------|------|
| **🟢 活跃方案** | 仍在计划中、未执行完 | 迁移到标准路径 `docs/projects/<prefix>/plans/` |
| **🟡 历史参考** | 已执行完、但有关键决策记录 | 保留原地，头部加「史」标记 |
| **🔴 作废/过期** | 已无参考价值 | 迁入 `docs/archive/` 或原地标「作废」 |
| **⚪ 不动** | 已在 archive 目录、或非方案类文档 | 不处理 |

### 4.2 逐位置处置清单

#### 位置 A：CCC `docs/notes/`（13 个文件）

| 文件 | 性质 | 处置 |
|------|------|------|
| `m7-ccc-plan-dogfood.md` | ccc-plan 狗粮记录 | 🟡 原地标「史 · 2026-08-07」 |
| `m7-next-plan.md` | M7 方案（已执行） | 🟡 原地标「史 · 2026-08-07」 |
| `m8-loop-baseline-plan.md` | M8 方案（已定稿执行中） | 🟢 迁入 `docs/projects/ccc/plans/001-loop-baseline-100.md` |
| `m9-arch-roadmap-plan.md` | M9 线路图升级方案（活跃） | 🟢 迁入 `docs/projects/ccc/plans/002-arch-roadmap-upgrade.md` |
| `2026-08-09-fix-plan.md` | 流程问题修复计划（活跃） | 🟢 迁入 `docs/projects/ccc/plans/003-flow-fix-plan.md` |
| `2026-08-09-batch-monitor.md` | 批量出卡监控记录 | 🟡 原地标「史 · 2026-08-09」 |
| `2026-08-09-pipeline-runthrough.md` | 重构后首次跑通记录 | 🟡 原地标「史 · 2026-08-09」 |
| `2026-08-09-round2-monitor.md` | 第二轮跑动监控 | 🟡 原地标「史 · 2026-08-09」 |
| `2026-08-08-investigation-claude-code.md` | 排查指令 | 🟡 原地标「史 · 2026-08-08」 |
| `2026-08-08-hp-env/` | HP 环境目录 | 🔴 迁入 `docs/archive/2026-08-08-hp-env/` |
| `2026-08-08-upgrade/` | 升级目录 | 🔴 迁入 `docs/archive/2026-08-08-upgrade/` |

> 迁移后，旧位置留一跳转 stub：`> ⚠️ 已迁移至 [docs/projects/ccc/plans/NNN-slug.md](...)`。

#### 位置 B：CCC `docs/briefs/`（4 个文件 + 1 模板）

| 文件 | 性质 | 处置 |
|------|------|------|
| `_TEMPLATE.md` | 执行 brief 模板 | 🔴 作废——被新方案模板取代。标「作废 · 2026-08-09，由 plan-template.md 取代」 |
| `2026-07-27-ccc-production-readiness.md` | 生产就绪 brief | 🟡 标「史 · 2026-07-27」 |
| `2026-07-27-golden-path-evidence.md` | 黄金路径证据 | 🟡 标「史 · 2026-07-27」 |
| `2026-07-27-qb-domain-ship-gate.md` | QB 领域发布门 | 🟡 标「史 · 2026-07-27」 |
| `PASTE-OPS.md` | 粘贴操作 | 🟡 标「史 · 2026-07-21」 |

> briefs/ 目录整体降级为历史参考，顶部 README 加说明。

#### 位置 C：CCC `.ccc/archive/plans/`（102 个 plan 文件）

| 判定 | 处置 |
|------|------|
| 全部为旧 cockpit 时期计划（2026-07），已在 archive 目录内 | ⚪ **不动**。README 已注明归档。 |

#### 位置 D：qx-map `__archive__/decisions/`（~60 个决策文档）

**活跃方案 → 迁入 CCC**：

| 文件 | 性质 | 处置 |
|------|------|------|
| `ccc-系统化升级方案-2026-08-08.md` | 活跃方案 | 🟢 CCC 迁入 `docs/projects/ccc/plans/004-systematic-upgrade.md` |
| `ccc-阶段3-自动化开发流程-规划草案-2026-08-04.md` | 活跃方案 | 🟢 CCC 迁入 `docs/projects/ccc/plans/005-auto-dev-flow-phase3.md` |
| `ccc-开发与业务分离-架构基线-2026-08-09.md` | 活跃方案（昨天刚落） | 🟢 CCC 迁入 `docs/projects/ccc/plans/006-dev-business-separation.md`，保留原文继续演进 |
| `xianyu-视频里程碑-方案-2026-08-03.md` | 活跃方案 | 🟢 CCC 迁入 `docs/projects/xy/plans/001-video-milestone.md` |
| `qb-refactor-方案-2026-08-03.md` | 活跃方案 | 🟢 CCC 迁入 `docs/projects/qb/plans/001-refactor.md` |
| `线路图升级为集群全景架构图-2026-08-08.md` | 活跃方案（与 m9 重叠） | 🟢 与 `ccc/plans/002` 合并，先保留原文再合并，不丢内容；原文件标「已迁移至 CCC」 |
| `ccc-loop-engineering-评估与100卡基线计划-2026-08-08.md` | 活跃方案（08-08 定稿 v2） | 🟢 CCC 迁入 `docs/projects/ccc/plans/007-loop-engineering-100-cards.md` |
| `claude-code-心智分层-方案-2026-08-03.md` | 活跃方案（待老板确认文案后执行） | 🟢 CCC 迁入 `docs/projects/ccc/plans/008-claude-mind-tiering.md`；备注「待核：是否已被 2026-08-06 双脑架构替代」 |

**不迁但需显式归类**：

| 文件 | 归类 | 动作 |
|------|------|------|
| `hp-qxmap-整合-执行方案-2026-08-03.md` | 🔴 作废 | 补废弃标记（与 INT-040「Trae 停用，定位收敛暂停」口径一致） |
| `quanthive-退出链路加固-方案-2026-08-03.md` | 🟡 历史 | 标史（INT-041 已关闭，QuantHive 独立轨道不迁） |
| `ccc-refactor-方案-定稿-2026-08-02.md` | 🟡 永久基线 | 留 qx-map（永久基线例外，不衰减不迁移） |
| `中转站单点化评估与2017优化-方案-2026-08-04.md`、`loop-router-dashboard-卡片化双机改造-方案-2026-08-04.md`、`ccc-execution-roadmap-2026-08-03.md` | 🟡 历史 | 标史（均已落地/被替代） |

**决策定稿类 → 保留在 qx-map**：

| 文件 | 处置 |
|------|------|
| `ccc-开发方案总览与执行模式评估-2026-08-04.md` | 🟡 保留（决策定稿） |
| `ccc-下一步开发决策-2026-08-04.md` | 🟡 保留（决策定稿） |
| `ccc-任务卡体系-规则定稿-2026-08-04.md` | 🟡 保留（规则定稿） |
| `quanthive-工程开发计划-2026-08-04.md` | 🟡 保留（QuantHive 独立轨道，CCC 只建索引指针） |
| 其余 ~50 个文件（重构/事故/技术决策/验收） | ⚪ **不动**（决策类文档，非方案类） |

> qx-map decisions 目录定位：**决策定稿归档**。活跃方案迁出后，q-map 不再存放待执行方案。

#### 位置 E：qx-map `command-post/`（INT 体系）

| 文件 | 性质 | 处置 |
|------|------|------|
| `intents.md` | INT 意图总表（INT-001~119） | 🔴 **退役**。头部加退役标记。活跃意图转入 CCC 计划页面 |
| `PLAN.md` | 决策中枢实施计划（已执行） | 🟡 标「已执行 · 2026-08-01」 |
| `check-intents.py` | INT 编号校验脚本 | 🔴 降级为只读（保留文件，不再作为门禁） |
| `sop-plan-write.md` | 旧方案编写 SOP | 🔴 标「作废 · 被 CCC DOC-PROTOCOL 取代」 |
| `sop-plan-review.md` | 旧方案审核 SOP | 🔴 标「作废 · 被 CCC 计划页面取代」 |
| `workers.md` | 工人画像 | 🟡 保留（角色定义，非方案类） |

#### 位置 F：CCC `references/intent-*.md`（3 个 INT SOP）

| 文件 | 处置 |
|------|------|
| `intent-card-sop.md` | 🔴 标「作废 · 2026-08-09，意图管理体系已退役，由计划页面取代」 |
| `intent-chain-dev-sop.md` | 🔴 同上 |
| `intent-proposal-sop.md` | 🔴 同上 |

#### 位置 G：CCC `docs/roadmap.md`「下一程挂账」

| 处置 |
|------|
| 保留 roadmap.md 的产品北星部分。**「下一程挂账」中的意向条目不再在 roadmap.md 新增**——新意向统一进计划页面。已有挂账条目逐步转为计划文档或直接出卡。在 roadmap.md 顶部加一行说明指向计划页面。 |

### 4.3 处置汇总

| 类别 | 数量 | 动作 |
|------|------|------|
| 🟢 活跃方案 → 迁入 plans/ | 12 个 | 迁移 + 旧位留指针 |
| 🟡 历史参考 → 标「史」 | ~25 个 | 原地加标记 |
| 🔴 作废/退役 | ~12 个 | 标作废/降级/迁 archive |
| ⚪ 不动 | ~150+ 个 | 已在 archive/或非方案类 |

---

## 5. INT 体系退役方案

### 5.1 退役原因

INT 意图总表（`command-post/intents.md`）和三个 intent SOP 是旧意图管理体系的核心。当前问题：
- INT 编号与任务卡编号（`<prefix><NNN>`）是两套体系，维护负担重
- INT 总表状态更新依赖人工回写，实际已停更（最后更新 2026-08-02）
- 计划页面接替了 INT 的「方案管理」职能，看板接替了「执行追踪」职能

### 5.2 退役步骤

1. `command-post/intents.md` 头部加退役标记，说明「计划页面 + 看板已接替」
2. `check-intents.py` 从 `daily-sync.sh` 调用链中移除（不再校验 INT 编号）
3. `references/intent-*.md` 三个文件标作废
4. `AGENTS.md` / `CLAUDE.md` 中移除 INT 相关引用，改为指向计划页面

### 5.3 不退役的部分

- qx-map `command-post/` 目录本身保留（作为决策中枢历史归档）
- `workers.md` 保留（角色定义仍有参考价值）
- `__archive__/decisions/` 保留（决策定稿归档）

---

## 6. 入口文档更新

### 6.1 CCC 需更新的文件

| 文件 | 更新内容 |
|------|----------|
| `CLAUDE.md` | 新增「计划页面」段，说明方案池路径和模板 |
| `AGENTS.md` | 同上 |
| `CURSOR.md` | 同上 |
| `docs/INDEX.md` | §0 新增计划页面入口 + 方案模板指针 |
| `docs/DOC-PROTOCOL.md` | §1 落点表新增「方案/计划」行；§2 新增方案编号规则 |
| `docs/product/card-hub-manual.md` | 新增「计划→转卡」流程 |
| `docs/product/hub-context-sop.md` | 出卡前了解步骤新增「读计划页面」 |

### 6.2 qx-map 需更新的文件（含 M1 双主档红线修订）

> **M1 问题**：qx-map 有 7 个文件写了「方案/决策唯一主档 = `__archive__/decisions/`」。
> 本次方案把活跃方案主档迁到 CCC，不修订这条红线会形成双主档冲突——三个 CLI 读到两处"唯一主档"。
> **修订**：qx-map 降为「决策定稿归档」；活跃方案主档归 CCC。

| 文件 | 现行内容 | 修订为 |
|------|----------|--------|
| `AGENTS.md` L166–171 | 「方案/决策单一主档」段：所有方案/决策全文只写 `__archive__/decisions/` | **决策定稿归档 = `__archive__/decisions/`**；活跃方案主档 = CCC `docs/projects/<prefix>/plans/`；hp-kb 索引指针指向 CCC 权威源路径 |
| `CLAUDE.md` L18,29,46 | 「方案/决策唯一落点 = `__archive__/decisions/`」三处 | 同上修订 |
| `REASONIX.md` L30 | 「方案主档：`__archive__/decisions/`（唯一实时端口）」 | 同上修订 |
| `ide/mcp-manifest.md` L13 | 「方案/决策全文唯一主档 = qx-map `__archive__/decisions/`」 | 同上修订 |
| `.reasonix/skills/code-map/SKILL.md` L14 | 「方案主档：`__archive__/decisions/`」 | 同上修订 |
| `command-post/sop-plan-write.md` | 「方案/决策唯一写点 = `__archive__/decisions/`」 | 标「作废 · 被 CCC 计划页面取代」 |
| `command-post/sop-plan-review.md` L16 | 「唯一源：`__archive__/decisions/`」 | 标「作废 · 被 CCC 计划页面取代」 |
| `command-post/intents.md` | 头部加退役标记 | 不变 |
| `command-post/README.md` | 更新说明 | 不变 |

---

## 7. HP 知识库向量化（第二阶段）

> ⚠️ 第一阶段先搭页面+路径口径。HP 向量化是第二阶段。

### 7.1 原则

- 权威源只在 CCC 仓 `docs/projects/<prefix>/plans/`
- HP 只做**只读向量索引**，不存第二份副本
- Agent 通过 HP 向量检索按需加载方案片段，再从 CCC 权威源拉完整内容

### 7.2 实现要点

1. 索引管道：CCC `docs/projects/*/plans/*.md` → 分块 → 向量化 → 写入 HP KB
2. 索引更新：方案文件变更时触发增量更新（通过 git hook 或定时扫描）
3. 检索接口：Agent 调用 `mcp__hp-kb__knowledge_search` 时，方案池内容可被检索
4. 元数据标注：每个向量块标注来源文件路径，Agent 可回源读取全文

---

## 8. 实施阶段（8 阶段，不走 CCC 自动流程）

> **不建卡、不进看板、不走 Engine。** 每阶段完成由 Codex 审核，通过后进下一阶段。
> Claude Code 亲自写码执行。编号仅用于排序，不产生任务卡。

| 阶段 | 内容 | 审核人 |
|------|------|--------|
| S1 | 方案模板 + 路径规范落地 | Codex |
| S2 | 存量文档处置（迁移清单须老板先确认） | Codex |
| S3 | 入口文档更新（含 qx-map 双主档红线修订） | Codex |
| S4 | INT 体系退役 | Codex |
| S5 | 后端 API（5 端点 + 方案读写校验） | Codex |
| S6 | 前端计划页面（路由 + 列表/详情/筛选/新建/转卡 + 单测） | Codex |
| S7 | 导航栏 + 路由更新 | Codex |
| S8 | 端到端验收（新建方案 → 转卡 → 看板 → 闭环） | Codex（总验收） |

### 8.1 各阶段验收标准

**S1**（模板+路径）：
- [ ] `docs/projects/_template/plan-template.md` 存在，包含全部必填字段
- [ ] `DOC-PROTOCOL.md` §1 落点表新增方案行，§2 新增方案编号规则
- [ ] `scripts/validate-plans.sh` 可校验方案文件格式

**S2**（存量处置）：
- [ ] 老板已确认迁移清单（§4.2 全量）
- [ ] 所有 🟢 文件已迁移到标准路径，旧位置留跳转 stub
- [ ] 🟡 文件已标「史」
- [ ] 🔴 文件已标「作废」或迁入 archive
- [ ] `docs/notes/` 清理后只剩 7 天内临时文件
- [ ] 合并类迁移保留原文不丢内容（审查建议 3）

**S3**（入口文档）：
- [ ] CCC §6.1 全部 7 个文件已更新
- [ ] qx-map §6.2 全部文件已更新，**含双主档红线修订**（M1）
- [ ] `scripts/check-entry-docs.py` 通过

**S4**（INT 退役）：
- [ ] `intents.md` 头部有退役标记
- [ ] `check-intents.py` 从 daily-sync 调用链移除
- [ ] 3 个 intent SOP 标作废
- [ ] qx-map `AGENTS.md` 移除 INT 分派章节

**S5**（后端 API）：
- [ ] 5 个端点全部实现，测试通过
- [ ] 方案编号自动生成、不冲突
- [ ] 方案文件落盘路径校验（必须进 `plans/` 子目录）
- [ ] `/plans/convert` 成功后自动推进方案状态为「部分执行」+ 写入关联卡字段（审查建议 1）

**S6**（前端页面）：
- [ ] `#/plans` 路由可访问
- [ ] 方案列表按项目分组、按状态筛选、搜索
- [ ] 方案详情 Markdown 渲染
- [ ] 新建方案表单 + 自动落盘
- [ ] 「转为任务卡」按钮 + 脚本调用
- [ ] 列表渲染/筛选/转卡按钮触发均有单测（审查建议 2）

**S7**（导航）：
- [ ] 导航栏「计划」在看板和线路图之间
- [ ] 侧栏「计划」入口
- [ ] 移动端适配

**S8**（端到端）：
- [ ] 新建一个方案 → 确认 → 转卡 → 看板出现任务卡 → 全链路通过

---

## 9. 红线

- 不双写：方案权威源只认 CCC `docs/projects/<prefix>/plans/`
- 不自动转卡：转卡必须人触发
- 不破坏现有看板/线路图功能
- 方案编号不与任务卡编号混用
- qx-map 不再存放待执行方案（只保留决策定稿）
- `docs/notes/` 不新建方案文件

---

## 10. 风险

| 风险 | 缓解 |
|------|------|
| 迁移期旧指针丢失 → 历史断链 | 每个迁移文件旧位置留 stub 跳转 |
| 新方案不按模板写 → 又散一次 | 模板 + `validate-plans.sh` 门禁 + 入口文档声明 |
| 方案编号与卡编号冲突 | 分区独立编号 + 转卡时由脚本生成卡编号 |
| INT 退役后历史意图不可追溯 | `intents.md` 保留为只读历史，不删除 |

---

*本文为实施方案正文。定稿后按 §8 拆卡执行。*