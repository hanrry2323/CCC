# 方案 · CCC 软件质量评分体系（S3 · 指标库 + 双轨评分 + 健康看板 + 质量回环）

> 项目：ccc · 编号：ccc-plan-044 · 状态：已确定 · 作者：S116-01 · 工具：Claude Code
> 创建：2026-08-23 · 更新：2026-08-23
> 关联卡：无（平台自研红线：ccc 前缀禁出卡，2017 本机 Claude Code 会话直接开发 + 异席机审，不走 engine）
> 关联方案：ccc-plan-042（质量机械验证）、043（DSH 执行模型）、033（人审两环节修订）
> 依据：老板 2026-08-23 定调（成熟标准锚定 + 双轨评分 + 指标库 + 健康看板 + 任务质量回环）；量化侧 M1 案例（`QuantHive/docs/plans/2026-08-23-quant-system-quality-system.md`）方法论参照
> 里程碑：度量（S3 · 2026-08-07 foundation anti-drift）

## 目标

把量化侧已验证的「**指标库 + 双轨评分 + 健康看板 + 任务质量回环**」四件套，系统化落到 CCC 软件开发侧：建立**锚定成熟软件质量工程标准（ISO/IEC 25010 等）的指标库**、**DSH 执行侧与本席验收侧双轨打分**、**0-100 健康看板**、**低分/大 gap → 打回 → 修复 → 反哺**的任务质量回环，让 CCC 自身软件质量可度量、可追踪、可改善。

## 背景

量化侧已验证三件套有效（M1 仓质量体系：指标库 60+ 基本面 × 双轨评分 × 健康看板 × 任务回环）。CCC 是软件工程侧，本计划把同一方法论落到软件开发质量上。老板定调两条硬约束：

1. **不许臆想指标**——每个指标必须锚定成熟标准（软件侧核心 = **ISO/IEC 25010 软件质量模型**；辅以 25023 度量、29119 测试、15504/33020 SPICE 或 CMMI 过程、IEEE 1061/McCabe 可维护性、DORA 交付、ISO 31000 风控）。无标准锚定的进「自定义待论证」队列，**不参与评分**。
2. **不许敷衍**——要成体系：指标库（正交分解可扩展，非手写）、双轨评分（DSH 执行侧 vs 本席验收侧，gap=校准度）、健康看板（0-100 一屏见红黄绿）、任务质量回环（低分/大 gap → 打回 → 修复 → 复验 → 反哺模板/preset）。

**CCC 现状盘点（已探索确认）**：
- L1 机械质量分已存在（`scripts/quality-score.py`：圈复杂度/mypy 错误密度/断言密度三维增量分），但基线硬编码在脚本、软告警不阻断；
- 机审真值单源已落地（`data/audit/ledger.jsonl` + `server/board/audit_ledger.py` 原子写）；
- 健康看板骨架已存在（`server/web/server.py` `/ops/summary` severity 红黄绿 + `server/engine/observer.py` 每日 5 组观测含假关闭红旗）；
- 假关闭红旗、维护区四问、机审命中率、越权提交检测俱在。

**本计划 = 在现有骨架上长肉，不是另起炉灶。**

## 方案内容

### 一、继承什么 / 重造什么

| 层面 | 量化侧（M1 案例） | CCC 软件侧（本计划） |
|------|------|------|
| 指标锚定标准 | De Prado 回测 / DAMA 数据 / SRE / ISO 31000 | **ISO 25010 软件质量 8 特征** + 25023 度量 + 29119 测试 + SPICE/CMMI 过程 + DORA 交付 + ISO 31000 |
| 指标库结构 | 域 × 组件 × 标准属性 × 检查点（正交，万级可扩展） | 同结构；**种子锚定现有扫描脚本**（quality-score/radon/mypy/validate/docgate/observer） |
| 双轨评分 | exec（DSH）vs accept（调度） | exec（DSH 执行体，回写区）vs accept（**本席环节② 终审**，验收区）；机审（DSH auditor）= 二进制门禁不参与打分 |
| 健康看板 | quality_board.py 渲染 0-100 | **quality-board.py（CCC 版）** + 台账派生，接现有看板风格 |
| 质量回环 | 低分 → 修复 → 复验 | 低分/大 gap → 打回 DSH → 修复 → 复验 → **反哺机审提示/出卡模板/preset** |

**为什么 accept 侧是本席**：老板定调「你这边还需要填一个验收侧的打分」= 环节② 终审（Claude Code）。与审核红线自洽——**accept_score 正是独立核验后的人审判断**，绝不信 DSH 自述。

### 二、指标体系设计

**正交分解（可扩展，非手写）**：

```
域(8) × 组件(6) × 标准属性(每域 3-6 条) × 检查点(每属性 1-N 条) → 指标
```

**域（锚定 ISO/IEC 25010:2023 产品质质量模型 8 特征，2011 版 Usability 于 2023 更名 Interaction capability）**：

| # | 域 | ISO 25010 特征 | 组件 |
|---|----|---------------|------|
| 1 | 功能适用性 | Functional Suitability | server/board（卡/方案/机审契约）|
| 2 | 性能效率 | Performance Efficiency | server/web、server/engine |
| 3 | 兼容性/可移植性 | Compatibility / Portability | server/config、跨平台脚本 |
| 4 | 交互能力 | Interaction capability（原 Usability）| 看板/API 响应、对账联动词 |
| 5 | 可靠性 | Reliability | server/engine（机审池/调度）、部署链路 |
| 6 | 安全性 | Security | 密钥扫描、执行边界、越权 |
| 7 | **可维护性** | Maintainability | 全 server/（CCC 最大短板）|
| 8 | **过程/治理** | ISO 15504/33020 SPICE + CMMI + DORA（非 25010）| 卡流程/机审命中率/返工率/部署频率 |

组件 = `server/engine` `server/web` `server/board` `server/kb` `server/config` `scripts` `docs`。
标准属性取 ISO 25010 各特征子特征（如 Maintainability → analyzability/modifiability/reusability/testability）；检查点 = 一条可执行测量。

**指标 schema（JSON，与量化侧 `system-quality-indicators.json` 同构）**：

```json
{
  "id": "ccc-maint-001",
  "domain": "maintainability",
  "component": "server/*",
  "attribute": "analyzability",
  "standard": "ISO/IEC 25010:2023 Maintainability.analyzability + IEEE 1061/McCabe",
  "measure": "radon cc 平均圈复杂度",
  "source_script": "scripts/quality-score.py (complexity_of)",
  "baseline": 4.96,
  "threshold": "增量 ≤ baseline（不可劣化）",
  "weight": 0.12,
  "owner": "DSH-exec + S116-01-accept"
}
```

- **standard 字段非空且通过白名单校验** = 参与评分；否则进「自定义待论证」队列。
- 白名单：`ISO 25010 / 25023 / 29119 / 15504 / 33020 / CMMI / IEEE 1061 / McCabe / DORA / SRE / ISO 31000 / OWASP`。

**种子指标库（首批 15 条，全部可复现、全部锚定现有脚本）**：

> 从 `docs/notes/2026-08-22-code-quality-baseline.md` + 现有门禁直接抽取，**不新增臆想指标**。
> 落点：`data/quality/indicators.json` + `indicator-schema.json`（运行时数据，同 `data/audit/` 不进版本库；若需纳入版本管理按 DOC-PROTOCOL 单独立项）。

| ID | 域 | 指标 | 锚定标准 | 测量来源 | 现有基线 |
|----|----|------|---------|---------|---------|
| maint-001 | 可维护性 | 平均圈复杂度 | ISO 25010 + McCabe | `quality-score.py` | 4.96（A）|
| maint-002 | 可维护性 | 高复杂度函数数（≥C）| McCabe | `radon cc` | 11 个，server.py F 级 |
| maint-003 | 可维护性 | 模块行数（上帝对象）| ISO 25010 Maintainability.modifiability | `wc -l server/web/server.py` | 4714 行 P0 |
| maint-004 | 可维护性 | mypy 错误密度/文件 | ISO 25010 + 类型工程 | `mypy --follow-imports=skip` | 273 错 / 25 文件 |
| maint-005 | 可维护性 | 重复代码块 | ISO 25010 reusability | 指纹法（基线扫描）| 266 组 |
| test-001 | 可靠性 | 测试通过率 | ISO 29119 | `pytest server/tests/` | 16 失败（基线）|
| test-002 | 可靠性 | 断言密度/测试 | ISO 29119 | `assert`/`def test_` | 2.3（低断言高危文件 22 个）|
| test-003 | 可靠性 | 覆盖率门禁 | ISO 29119 | CI `--cov-fail-under=80` | 83% |
| test-004 | 可靠性 | 高 mock 测试数 | ISO 29119 + 防空转 | 断言/mock 密度 | test_infra_resilience 10.5 |
| proc-001 | 过程 | 机审命中率/返工率 | CMMI/SPICE process performance | `audit_ledger.hit_rate` | 台账已有 |
| proc-002 | 过程 | 维护区四问通过率 | SPICE + 治理 | `docgate.verify_maintenance` | 门禁已硬 |
| proc-003 | 过程 | 假关闭红旗计数 | SPICE + 数据一致性 | `observer.closed_without_audit` | 单列已存在 |
| proc-004 | 过程 | 越权提交次数 | 治理红线（禁 DSH commit/push）| ledger 检 `approve_merge` | 任务卡模板已禁 |
| proc-005 | 过程 | 维护区覆盖率 | SPICE + 治理 | observer `gather_maintenance_metrics` | 观测已跑（每日 markdown）|
| deliv-001 | 交付 | 合入→部署周期 / 变更失败率 | DORA 4 keys | `approve_merge` 台账派生 | 需派生（新）|

> 口径统一：基线文档「1165 测试/55 文件」与实测「1128/60」漂移——**测量脚本化、口径固定**（探子 agent 发现，纳入指标实现要求）。

### 三、双轨评分模型

**三席分工（异席、互不可见后填，与机审同一防合谋纪律）**：

| 席 | 动作 | 落点 | 内容 |
|----|------|------|------|
| DSH 执行体 | 回写时填 **self_score** | 卡 `## 回写区` 新增「质量自评」节 | 0-100 + 自评依据（证据）|
| DSH 机审 | 机审（**二进制门禁**，不改分）| `## 机审区` | 通过/不通过（现有契约不变）|
| **本席 环节②** | 验收/合入时填 **accept_score** | `## 验收区` / ledger | 0-100 + verdict + 依据（独立核验）|

**gap = 校准度信号（不合并、不平均）**：

- `gap = |accept_score − self_score|` → 独立落台账 `audit_ledger` `record_action("quality_score", card, detail={exec, accept, gap, verdict})`。
- **gap 只作校准度/改善依据**，不作合入硬门禁（合入门禁 = 现有机械门禁 + 老板人审）。
- 聚合：`accept_score` 全指标加权 → **系统健康分 0-100**：≥95 绿 / 80-95 黄 / <80 红。
- 校准：全指标平均 gap → DSH 校准度（大 gap 集中 → 反哺 DSH preset / 自评指导）。

**与现有 L1 的关系（分层）**：

- **L1**（现有 `quality-score.py`）：合入后增量不可劣化，**保留软告警**（不阻断；先采集校准数据，稳定后再评估是否转硬）。
- **L2**（本计划新增）：双轨评分 + 单卡质量回环。
- **L3**（本计划新增）：系统健康审计（按周期跑全指标库，出 0-100 + 分域/分组件分解 + 趋势）。

### 四、健康看板

- **不另起炉灶**：现有 `/ops/summary` 已是健康看板雏形（severity 红黄绿）；`observer.py` 已每日跑 5 组观测（含假关闭红旗）并出 `data/observer/observation-YYYY-MM-DD.md`。
- **动作**：在 observer/`/ops/summary` 骨架上扩展——新增 `scripts/quality-board.py` 读指标库 JSON + 跑测量脚本 + 读台账 → 渲染健康看板；总分 + 红黄绿徽章 + 每域/每组件分 + 每卡双轨分与 gap + 校准度 + 趋势（按周期存档）。
- **接入**：端到端只读（渲染产物 `data/quality/health-board.md` + API 端点 `/quality/health`）；审核只看实时 API（不认陈旧快照，沿用纪律）。
- **落点合规**：指标库数据/渲染产物落 `data/quality/`（运行时数据，同 `data/audit/` `data/observer/`，不碰 DOC-PROTOCOL 落点表）；仅设计文档走 `docs/projects/ccc/plans/`。
- **状态机对齐**：新看板一律吃 `models.py` 六态 + `task.py` 转移表 + `board_column` 派生「机审」列，**不另建状态枚举**。
- 假关闭红旗/机审命中率/维护区覆盖**直接并作指标测量源**，不重复造。

### 五、任务质量回环

```
低 accept_score 或 大 gap
  → 打回 DSH（回环原因带「问题 → 文件:行号 + 唯一最佳动作」，沿用机审可执行打回纪律）
  → DSH 修复 → 复验 → 若反哺点成立 →
      反哺① 机审提示（prompt_inject KB review/lesson）
      反哺② 出卡模板 / 卡八节要求
      反哺③ DSH preset（防乐观/防幻觉指导）
```

- 回环触发阈值（初版）：`accept_score < 60` 或 `gap ≥ 20` → 必须打回/重点复验；`60 ≤ accept < 80` → 标记改进项。
- 每张卡质量回环结果全部进台账，沉淀为「可复用教训」供 Q2 维护区引用。

### 六、与现有体系接线

| 落点 | 现有资产 | 本计划动作 |
|------|---------|-----------|
| 机械增量分 | `scripts/quality-score.py`（L1）| 保留；基线从硬编码抽到 `data/quality/baseline.json` |
| 台账 | `server/board/audit_ledger.py`（JSONL + fcntl 原子写）| 复用 `record_action`；新增 quality_score/health 两种 action |
| 维护区 | `server/board/docgate.py` `verify_maintenance` | 新增「质量自评」节校验（self_score 0-100 + 证据非空）|
| 机审提示 | `server/board/prompt_inject.py` `build_audit_prompt` | 检查项追加「核对 self_score 与证据一致性」|
| 看板视图 | `server/board/queries.py` + `server/web/server.py` | 新增 `/quality/health`（复用 items→派生模式）|
| 假关闭红旗 | `server/engine/observer.py` `closed_without_audit` | 直接作为 proc-003 测量源 |
| 健康看板骨架 | `/ops/summary`（severity 红黄绿）+ observer 5 组观测 | L3 健康审计在 observer/`/ops` 骨架上扩展，不另建平行系统 |
| 合入门禁 | `scripts/approve-merge.sh` | 合入后 quality-score 保持软告警；验收时 `--accept-score` 落台账 |
| 状态机/校验 | `server/board/models.py` / `validate.py` | 验收区 accept_score 可选字段（兼容旧卡）|
| 巡检骨架 | `docs/CCC-PRIME-DIRECTIVE.md` §6.2 运维五级 | 架构漂移/技术债两级的既有巡检并入指标库测量 |

**不动的**：机审区格式契约（`> 结论：通过/不通过` 唯一判定）、机械门禁顺序、角色白名单、产线红线（禁 commit/push、禁直推 main）。

## 验收标准

- [ ] 指标库 15 条种子全部可复现（各附复现命令输出），`quality-schema-check.py` 绿
- [ ] 一张真卡走通 self_score → 机审 → accept_score → gap 全链，台账有 quality_score 记录
- [ ] 健康看板渲染 0-100 + 红黄绿 + 分域分解 + 趋势；`/quality/health` 返回 JSON；六态/转移表对齐，无平行状态枚举
- [ ] 首轮系统健康审计出 CCC 当前健康分 + 分域最弱项
- [ ] 低分/大 gap 卡走通打回 → 修复 → 复验 → 反哺（prompt_inject/template/preset 至少一处落库）
- [ ] 回归：全量 `pytest server/tests/` 绿；`approve-merge.sh` 机械门禁不劣化；机审区契约/产线红线不变

## 功能卡

> 本计划为平台自研（ccc 前缀禁出卡），不转 dispatch 卡；以下各阶段为 2017 本机 Claude Code 会话内直接开发+测试 的**工作切片**，每阶段经异席机审 + 老板确认里程碑后推进。

### 阶段 1 · 指标库种子 + 测量脚本接线

目标：15 条种子指标全部落 `data/quality/indicators.json`，schema 校验脚本可跑，baseline 从 quality-score.py 硬编码抽到 `data/quality/baseline.json`，每条测量复跑命令固化。

实现：建 `scripts/quality-schema-check.py`（读 schema JSON 校验 indicators.json：standard 白名单、id 唯一、字段完备）；抽 baseline 常量到 JSON；固化 15 条 measure 复跑命令（含口径固定，杜绝 1165/1128 漂移）。

验收：schema 校验绿；15 条各自复跑命令输出可复现（附命令）。

颗粒度：新增 2 脚本 + 1 数据目录 + quality-score.py 常量抽取（不动行为）

依赖：阶段 0 设计文档 + 指标库骨架（本方案）

架构位置：scripts/ → data/quality/（测量与数据层）

### 阶段 2 · 双轨评分接线

目标：DSH 回写区「质量自评」节（self_score）+ docgate 校验；验收区 accept_score + approve-merge `--accept-score` 落台账；gap/校准度计算。

实现：改 `server/board/docgate.py`（自评节校验）、`server/board/prompt_inject.py`（核对项）、`server/board/audit_ledger.py`（新 action：quality_score）、`scripts/approve-merge.sh`（--accept-score）、`server/board/models.py`（验收区 accept_score 可选字段）。

验收：一张真卡走通 self→机审→accept→gap 全链，台账有 quality_score 记录。

颗粒度：server/board 四文件 + approve-merge.sh 一处参数 + models.py 一个可选字段（兼容旧卡）

依赖：阶段 1（指标库就绪）

架构位置：server/board/（评分链路）+ server/web（展示）

### 阶段 3 · 健康看板

目标：在 observer/`/ops/summary` 骨架扩展 `scripts/quality-board.py` + `/quality/health` 端点 + `data/quality/health-board.md` 渲染。

实现：`quality-board.py` 读指标库 JSON + 跑测量 + 读台账 → 0-100 + 红黄绿 + 分域/分组件分解 + 趋势；`server/web/server.py` 加只读端点 `/quality/health`（对齐 `/ops/summary` severity 语义）；状态机一律吃 `models.py` 六态 + `task.py` 转移表，不另建枚举。

验收：看板可渲染 0-100 + 红黄绿 + 分域分解 + 趋势；`curl :7788/quality/health` 返回 JSON。

颗粒度：新增 1 脚本 + server/web 1 端点 + 渲染产物目录

依赖：阶段 2（台账有 quality_score）

架构位置：server/web/（端点）→ data/quality/（渲染产物，运行时数据）

### 阶段 4 · 首轮系统健康审计

目标：全指标库首跑，出 CCC 当前健康分 + 分域最弱项 + 返工/越权/假关闭治理项。

实现：跑全 15 条测量 → 加权聚合健康分 → 分域/分组件分解 → 最弱项清单（预期可维护性域）→ 治理建议进健康看板。

验收：首轮健康分 + 分域最弱项成文（附复现命令输出）。

颗粒度：纯测量跑批 + 报告产出（无代码改动）

依赖：阶段 3（看板渲染就绪）

架构位置：data/quality/（报告产物）

### 阶段 5 · 质量回环反哺（首轮闭环）

目标：首轮低分项（预期：可维护性/server.py 上帝对象、mypy、重复代码、低断言测试）分批修复 + 反哺 prompt_inject/template/preset。

实现：低分项分批修复卡 → 复验回升；反哺点成立 → 机审提示/KB lesson/出卡模板/DSH preset 至少一处落库。

验收：复验后低分项回升；反哺项入库（docs/notes 或 KB）。

颗粒度：分批修复（每批独立可验）+ 反哺落库

依赖：阶段 4（健康分定优先级）

架构位置：server/ + docs/（修复与反哺）

## 转卡计划

本方案为**平台自研**，按 registry 红线 **ccc 前缀禁止出 dispatch 卡**（`FORBIDDEN_CARD_PREFIXES`，registry.yaml ccc 行 notes）。实现方式：

- **2017 本机 Claude Code 会话直接开发 + 测试**（阶段 1-5 工作切片）；
- 每阶段 **异席机审**（DSH auditor 机器审核）→ **老板确认里程碑** 后推进；
- 不委派 engine 自动流程、不走 docs/dispatch/ccc/ 卡（043 同款红线口径）。
- 阶段 0（本方案 = 设计文档 + 指标库骨架）已完成，送老板确认「标准白名单 + 种子库」。

## 备注

- **风险 1 不臆想**：所有指标必须过 standard 白名单；无锚定 → 待论证队列不评分。红线不回退。
- **风险 2 双轨是校准信号不是追责工具**：先积累校准数据再谈淘汰；gap 大先查「自评指导/证据规范」而非直接定责。
- **风险 3 打分 ≠ 门禁**：分数驱动改善；机械门禁（机审/维护区/密钥/范围）仍是硬门槛，不因高分放宽。
- **风险 4 权重不可自解释**：初始权重 = 域平均 + 可调，改动须带论证（沿用「验收标准不可自解释」纪律）。
- **风险 5 口径漂移**：测量脚本化、口径固定，杜绝 1165/1128 式漂移。
- **PRIME-DIRECTIVE 对齐**：本计划与三层架构/两环节模型兼容；最高准则文档「3 人审节点」口径与两环节模型的精确对齐单独立项（不动门禁语义）。
