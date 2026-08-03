# CCC 知识种子包

> 用途：CCC 自建知识库的种子数据源，由 `server/kb/indexer.py` 解析后生成 BM25 检索索引。
> 来源：外脑权威源（qx-map）一次性移植 + CCC 仓内权威文档（`docs/architecture.md` / `docs/dispatch/` / 重构决策）持续提炼，只读不修改原档。
> 移植后 CCC 独立运行，零外脑依赖（D3 契约）。
> 初始化日期：2026-08-02 · M4 刷新：2026-08-03 · 关联：INT-120（CCC 重构）· 任务卡：T36

## 结构

| 文件 | 内容 | 权威源 |
|------|------|--------|
| `01-nodes-paths.json` | 机器节点、IP、SSH、路径、服务（2017 单端终态） | `cluster/path-authority.md` + `docs/architecture.md` v0.70.0 + `ccc-relay-双轨决议-2026-08-02.md` + `ccc-refactor-M2-生产验证-2026-08-03.md` |
| `02-project-metadata.json` | 项目元数据（位置、性质、访问方式） | `cluster/path-authority.md` + `docs/architecture.md` v0.70.0 + `ccc-refactor-方案-定稿-2026-08-02.md` |
| `03-key-decisions.json` | 关键决策摘要（含重构 v2 / 双轨 / 收口 / M2 / D10） | qx-map `__archive__/decisions/` + hp-kb `/codex/topics/` + CCC `docs/dispatch/T31–T35` |
| `04-lessons.json` | 教训清单（含 LC1–LC4 收口期新教训） | qx-map `__archive__/lessons/` + CCC `docs/lessons.md` + hp-kb `/codex/topics/` + `ccc-refactor-收口重评-2026-08-03.md` |

## M4 刷新记录（2026-08-03）

- 节点/路径：移除已退役端口（7777/7775/17777/7778/11434/4000）；2017 :7788 三服务常驻；6100/6102 CCC 专用中转站；M1 4100/4102 保留。
- 项目元数据：CCC 主仓在 M1（v0.70.0）；qb 真身在 Mac2017；QuantHive 独立轨道禁止合并表述。
- 决策：补 6 条新增（D1-D10 v2 / D11 双轨 / 收口重评 / T31–T35 完成 / M2 生产验证 / D10 细则）。
- 教训：补 4 条收口期新教训（LC1 文档口径分裂 / LC2 验收放宽 / LC3 配置 schema 脱节 / LC4 死功能残留）。

## 来源追溯

- 初始种子（2026-08-02）：外脑权威源 qx-map 一次性导入。
- M4 刷新（2026-08-03）：qx-map `__archive__/decisions/` + CCC 仓内 `docs/architecture.md` v0.70.0 + T31–T35 任务卡 + M2 生产验证记录。
- 之后独立维护，新决策/教训只写本库（D3 红线）。

## 安全声明

本种子包不含：
- 密钥 / API token / 密码
- 运行面敏感信息（端口仅含服务名，不含实时状态）
- 运行面配置（env / .env 内容）
