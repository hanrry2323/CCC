# 任务卡 T36 · M4-1 知识源更新：种子重生成 + 索引重建（Trae GLM5.2 执行）

> 关联：INT-120（M4 知识移植/独立移交 · P5）· 依据：Codex 2026-08-03 评估——knowledge/ 种子为 T9 快照（2026-08-02 上午），缺 08-02 中转站双轨决议、08-03 重构收口重评/T31–T35/M2 生产验证；索引未按新种子重建
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：待分派 · 日期：2026-08-03

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

**执行体**：Trae（GLM5.2）· 日期：
