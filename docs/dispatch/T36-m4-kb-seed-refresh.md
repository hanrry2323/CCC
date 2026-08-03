# 任务卡 T36 · M4-1 知识源更新：种子重生成 + 索引重建（Trae GLM5.2 执行）

> 关联：INT-120（M4 知识移植/独立移交 · P5）· 依据：Codex 2026-08-03 评估——knowledge/ 种子为 T9 快照（2026-08-02 上午），缺 08-02 中转站双轨决议、08-03 重构收口重评/T31–T35/M2 生产验证；索引未按新种子重建
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：已回写 · 日期：2026-08-03

## 目标

CCC 自建知识库（knowledge/）四类知识（节点/路径、项目元数据、决策、教训）更新到 2026-08-03 最新权威状态，索引重建后检索可命中。

## 红线（先看）

1. 只读权威源提炼，禁止编造：节点/路径以 CCC 仓 `docs/architecture.md` + 重构决策 + 2026-08-03 生产验证为准；决策以 qx-map `__archive__/decisions/` 对应主档为准；不写密钥/密码/运行面敏感信息。
2. 只改 `knowledge/`（seed + domains + 索引产物）；不动 server/ 运行代码（大脑接库是 T37）。
3. 保留四类 schema 与安全声明；更新后标注 updated_at=2026-08-03 与来源。
4. 真实提交；验收标准不可自行解释。

## 范围

knowledge/seed/（01-nodes-paths.json、02-project-metadata.json、03-key-decisions.json、04-lessons.json、00-README.md）、knowledge/domains/（四域 seed.md）、knowledge/README.md（如需）、server/kb/indexer.py 的 CLI 用法（只读确认，不实现新功能）、server/tests/（索引/检索单测）。

## 步骤

1. 通读权威源：qx-map `__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md`、`ccc-refactor-收口重评-2026-08-03.md`、`ccc-refactor-M2-生产验证-2026-08-03.md`、`ccc-relay-双轨决议-2026-08-02.md`；CCC 仓 `docs/architecture.md` + T31–T35 卡 + INT-120 记录。
2. 重生成四类种子（保持现有 schema 结构）：
   - 决策：补 ≥6 条新增（重构定稿 v2、中转站双轨决议、收口重评、T31–T35 收口完成、M2 生产验证通过、D10 硬编码纪律），保留既有历史决策。
   - 节点/路径：按 2017 单端终态更新（2017 :7788 三服务、M1 壳、6100/6102 CCC 中转站、M1 4100/4102 保留、HP 知识库服务），移除已退役端口（7777/7775/17777/7778）。
   - 项目元数据：qb（Mac2017 真身路径）、medio-0、QuantHive（独立轨道，禁合并表述）、CCC 自身；与 `docs/architecture.md` 一致。
   - 教训：补 ≥4 条（文档口径分裂导致执行漂移 / 验收判定放宽导致 Engine 壳层 / 生产配置与代码 schema 脱节 / 挂载死功能残留），保留既有教训。
3. domains/*.md 与 seed JSON 同步；更新 updated_at/source/note。
4. 重建索引（按 server/kb/indexer.py 的既有入口，产物到 knowledge/.index/）；验证检索：至少 5 个查询词各命中对应文档。
5. 补/改单测：种子 schema 完整性、索引重建后检索命中、无敏感字段（密钥模式扫描）。
6. 提交（message 含 T36）。

## 验收标准

1. 四类种子 updated_at=2026-08-03；新增决策 ≥6、教训 ≥4，来源可追溯（指向主档路径）；无密钥/密码/敏感信息（扫描零命中）。
2. 索引重建成功，5 个查询词实测命中对应域文档；`pytest server/tests -q` 全绿。
3. 已退役端口/旧架构表述在 knowledge/ 现行文档零残留（history 可留 seed 包注释）。
4. 工作树仅剩许可预存项；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：四类种子更新清单（新增条目逐条）、索引重建命令与检索实测、pytest 结果、commit hash。

## 回写区

**执行体**：Trae（GLM5.2）· 日期：2026-08-03

### 四类种子更新清单

#### 01-nodes-paths.json（节点/路径）

- updated_at: 2026-08-03
- source: qx-map `cluster/path-authority.md` (2026-08-01) + `docs/architecture.md` v0.70.0 + `ccc-relay-双轨决议-2026-08-02.md` + `ccc-refactor-M2-生产验证-2026-08-03.md`
- 新增字段：`ccc_topology_2017`（2017 单端终态：端点表 / 三服务 launchd / 鉴权）、`relay_dual_track`（D11 双轨：M1 4100/4102 保留 + Mac2017 6100/6102 CCC 专用）、`retired_ports_authoritative`（7 条退役端口权威清单）、`path_hallucination_checks`（6 条路径幻觉检查规则）
- 修订：M1 services 列表移除 7777/7788 现行口径，归入 `retired_services`；Mac2017 services 加入 `com.ccc.web-server/engine/board-scheduler/ai-loop-router` 四个 launchd 常驻服务

#### 02-project-metadata.json（项目元数据）

- updated_at: 2026-08-03
- source: qx-map `cluster/path-authority.md` + `docs/architecture.md` v0.70.0 + `ccc-refactor-方案-定稿-2026-08-02.md`
- CCC 项目新增 `version: v0.70.0`、`access` 区分开发期/运行期；qx-map 标注「M4 移交后 CCC 独立运行，不再读写」；ai-loop-router role 改为「M1 4100/4102 + Mac2017 6100/6102」；ccc-relay-runtime `last_activity: retired`

#### 03-key-decisions.json（决策 · 补 6 条新增）

- updated_at: 2026-08-03
- source: qx-map `__archive__/decisions/` + hp-kb `/codex/topics/` + CCC `docs/dispatch/T31–T35`
- 新增 6 条决策（逐条）：
  1. **D1-D10**: CCC 重构方案 v2（升级为 v2，加 D10 + 终态拓扑 + 契约清单）
  2. **D11-Relay-Dual-Track**: CCC 中转站双轨终态决议（M1 4100/4102 保留 + Mac2017 6100/6102 CCC 专用，永久生效）
  3. **Closeout-Reeval-2026-08-03**: CCC 重构收口重评 + T31–T35 指令（含 5 条取证发现）
  4. **T31-T35-Closeout-Done**: T31–T35 重构收口五卡全部完成（每卡一句话摘要 + pytest 数）
  5. **M2-Production-Verified**: M2 里程碑生产验证通过（Engine 接单→真实执行→收单回写→看板派生四阶段全链路 + 里程碑状态表）
  6. **D10-Hardcode-Discipline**: D10 杜绝硬编码永久纪律细则（5 条细则 + T33 执行结果）

#### 04-lessons.json（教训 · 补 4 条新增）

- updated_at: 2026-08-03
- source: qx-map `__archive__/lessons/` + CCC `docs/lessons.md` + hp-kb `/codex/topics/` + `ccc-refactor-收口重评-2026-08-03.md`
- 新增 4 条收口期教训（逐条）：
  1. **LC1**: 文档口径分裂导致执行漂移（T28 越界证据 + T31 修复 + 应用规则）
  2. **LC2**: 验收判定放宽导致 Engine 壳层（M2 判定标准收紧 + T32 修复 + 应用规则）
  3. **LC3**: 生产配置与代码 schema 脱节（T32/T33 example 改了但生产配置未同步 + M2 实测前补齐 + 应用规则）
  4. **LC4**: 挂载死功能残留（双壳/孤儿页面/旧 Hub 文案/跨项目遗留物四类 + T34 修复 + 应用规则）

### domains/*.md 同步

- `nodes-paths/seed.md`：加 CCC 拓扑（2017 单端终态）+ 2017 :7788 端点表 + 三服务 launchd + 中转站双轨表 + 已退役端口权威清单表
- `projects/seed.md`：CCC 主仓与 qb 分独立小节 + 关键独立性纪律节（QuantHive 独立轨道 + D2/D3 红线）
- `decisions/seed.md`：补 6 条新增决策（每条含日期/状态/来源文件/摘要/要点/影响或里程碑）
- `lessons/seed.md`：补 4 条 LC1-LC4 收口期新教训（每条含日期/来源/现象/根因/修复/应用）

### 00-README.md / knowledge/README.md 更新

- 移除「T9」字样；标「M4 刷新：2026-08-03」+ 关联 T36；加 M4 刷新记录节（四类变更摘要）；来源节区分初始种子与 M4 刷新两段

### 索引重建命令与检索实测

```
$ python3 -m server.kb.mcp_server --reindex
索引重建完成：80 文档
```

5 查询词实测命中对应域：

| 查询词 | 期望域 | 实测命中（top-1） | score |
|--------|--------|------------------|-------|
| 2017 单端 | nodes-paths | `domains::nodes-paths::CCC_拓扑_2017_单端终态_` | 4.2547 |
| 中转站 双轨 | decisions | `03-key-decisions::D11-Relay-Dual-Track` | 13.2764 |
| CCC 重构方案 v2 | decisions | `03-key-decisions::D1-D10` | 12.8948 |
| 文档口径分裂 | lessons | `04-lessons::note`（含 LC1 摘要） | 14.0262 |
| QuantHive 独立轨道 | projects | `02-project-metadata::QuantHive` | 14.8395 |

MCP selftest：

```
$ python3 -m server.kb.mcp_server --selftest
[selftest] 索引重建完成：80 文档
[selftest] kb_search('CCC') → 20 结果
[selftest] kb_list('nodes-paths') → 8 条目
[selftest] kb_read('domains::nodes-paths::section_0') → 93 字符
[selftest] kb_search 空结果正确
[selftest] ALL PASSED
```

### pytest 结果

```
$ python3 -m pytest server/tests/
280 passed in 4.57s
```

新增用例（34 个，`server/tests/test_kb_seed_integrity.py`）：
- `TestSeedSchema`：4 文件 × 3 用例 = 12（schema/section/updated_at/source/note 必填 + updated_at=2026-08-03 + schema=ccc-kb-seed-v1）
- `TestNewEntries`：2 用例（决策 6 条 ID 全在 + 教训 4 条 LC1-LC4 全在）
- `TestRetrievalHits`：5 用例（5 查询词 × 域命中校验）
- `TestNoSensitiveFields`：8 用例（4 seed JSON + 4 domains MD × 7 敏感模式扫描零命中）
- `TestNoRetiredPortResidue`：7 用例（非 nodes-paths 种子 3 文件 + 非 nodes-paths 域 MD 3 文件 + nodes-paths 退役端口归档标注校验）

### 三扫描自检

- **密钥扫描**：`rg 'sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}' knowledge/` → 零命中
- **密码/token 扫描**：`rg '(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*[a-zA-Z0-9]{20,}' knowledge/` → 零命中
- **退役端口现行文档零残留**：17777/7775/7778/11434 命中 14 行，全部位于 `retired_ports_authoritative` / `retired_services` / `已退役端口` / M4 刷新记录等显式归档清单上下文；非 nodes-paths 域零命中
- **旧架构表述扫描**（Hub :7777/scripts/ccc-engine/能力包/角色分层/三档契约）：8 行命中，全部位于「已取消/已修复/已归档」上下文（v2 摘要的「取消重型机制」+ 收口重评的「取证发现」+ LC1 教训的「现象」描述）

### commit hash

`a466f32` — docs(kb): T36 M4 知识种子刷新 + 索引重建——补 6 决策/4 教训 + 2017 单端终态对齐（11 files changed, 815 insertions(+), 107 deletions(-)）

### 工作树预存项

无（工作树干净，无许可预存项外内容）。
