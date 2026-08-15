# 方案 · HP 稳控与可恢复（M2）

> 项目：hp · 编号：hp-plan-004 · 状态：作废 · 作者：Claude（中枢） · 工具：Claude Code
> ⚠️ **2026-08-15 流程改造收回**：里程碑→看板流转粒度修正（里程碑→子项目→计划逐步投入→开发卡三要素）。本方案原按「里程碑级一次投入」立项，作废收回；M2 子项目内容（2.1-2.7）待新模型下重新按子项目立项。
> 创建：2026-08-15 · 更新：2026-08-15
> 关联卡：待老板节点②确认功能卡清单后转卡（本方案暂不出卡）
> 关联方案：hp-plan-001（底座固化，已完成）
> 里程碑：M2 · 稳控与可恢复

## 目标

让 HP 知识库**可恢复、可重建**：核心源码全部回灌 SSOT，开发（mac2017）与部署（hp 节点）彻底隔离，双仓归一，凭据治理，验证从 SSOT 能全新重建整套服务。

## 背景

2026-08-15 三路调查（本地文档/远端代码/调用方生态）发现 HP 处于「部分可用」状态，其中两个 P0：
1. **源码丢失**：pipeline（ingest/chunker/embedder/search）核心源码只存在于 hp 节点（部署机），mac2017 SSOT 仓没有——违反 README 自身「服务源码必须进 git」规则。hp 节点一旦损坏，整套入库能力不可恢复。
2. **SSOT 名不副实**：mac2017 仓与 hp 节点仓**无共同 git 祖先**（双仓漂移），互相有对方缺失的源码；运行时 mcp_server（含 kb_status）比 SSOT 还新。

此外待治理：`.credentials-backup/` 敏感材料未跟踪、`.env` 含 DB 口令明文、`rss-to-hp-kb.py` 硬编码 M1 旧路径。

架构定论配套：HP 升级为「全文知识底座」（存全文 chunk），ccc-kb 降为离线降级副本——主备分层（见 M2-2.4/2.5）。

## 方案内容

分 7 个子节点执行：

**2.1 pipeline 源码回灌 SSOT**：把 hp 节点 `/data/knowledge/pipeline/`（chunker/db/embedder/ingest/search/config/parsers）全部源码迁入 mac2017 `docs/..`（业务仓 `/Users/fan/program/apps/hp`），与 mcp-server/memory-store 同级，纳入 git。

**2.2 双仓 git 归一**：mac2017 与 hp 节点两套独立 git 历史合并为单一线性真值（如 hp 节点历史 rebase/graft 到 mac2017 main，保留 mtime 语义）；明确唯一 SSOT = mac2017 仓，hp 节点为部署产物。

**2.3 运行时↔SSOT 对齐**：运行时 mcp_server（125 行含 kb_status）回灌 SSOT；SSOT 领先的 memory-store 等回灌运行时；跑 diff 确认两端一致。

**2.4 全文摄入改造**：ingest 存全文 chunk（标题+摘要+全文+指针），knowledge_search 返回全文片段，命中即得全文、不再跳原仓。

**2.5 双库改主备**：HP 为主（全量语义底座），ccc-kb 降为离线降级副本（本地 BM25，只存 CCC 决策/教训，敏感内容隔离不进 HP）；HP 不可用时 ccc-kb 兜底。

**2.6 凭据治理**：`.credentials-backup/` 移出运行时目录并评估是否入库；`.env` DB 口令轮换；gitignore 规则清理，禁止敏感材料进 git。

**2.7 可重建验证**：从 SSOT 全新 clone → 安装依赖 → 初始化 PG/pgvector → 跑 pipeline 重建 → 起 mcp/memory-store → 端到端检索验证，产出灾备演练记录。

## 验收标准

- [ ] pipeline 全部源码在 mac2017 SSOT 仓，git 跟踪，hp 节点无「独有源码」
- [ ] mac2017 与 hp 节点收敛为单一 SSOT（无分叉历史）
- [ ] 运行时与 SSOT diff 为空（两端源码一致）
- [ ] HP 检索直接返回全文片段（不再只回索引/指针）
- [ ] ccc-kb 降级副本可用：HP 停止时检索兜底不中断
- [ ] 敏感凭据已治理（.credentials-backup 处理、.env 口令轮换、无敏感材料进 git）
- [ ] 灾备演练通过：空机从 SSOT 全新重建整套服务可端到端检索
- [ ] 既有功能回归：5267 docs 检索、memory_*、多端 MCP 调用不破坏

## 功能卡

> 一个功能一张卡（一子节点一卡）。节点② 老板确认清单后一次转卡，当前阶段不出卡。

### pipeline 源码回灌 SSOT
目标：把 hp 节点上的 ingest/chunker/embedder/search 等全部源码迁入 mac2017 业务仓并纳入 git，消灭「部署机独有源码」。
验收：pipeline 源码全部在 SSOT 仓、可构建、hp 节点无独有源码。

### 双仓 git 归一
目标：mac2017 与 hp 节点两套分叉 git 历史合并为单一线性真值，明确唯一 SSOT。
验收：两仓收敛统一历史，无共同祖先问题消除。

### 运行时与 SSOT 对齐
目标：运行时 mcp_server（含 kb_status）回灌 SSOT，SSOT 领先部分回灌运行时，两端一致。
验收：运行时与 SSOT diff 为空。

### 全文摄入改造
目标：HP 存全文 chunk，检索直接返回全文片段，命中即得全文。
验收：knowledge_search 返回全文片段，不回仅索引。

### 双库改主备
目标：HP 为主知识底座，ccc-kb 降为离线降级副本（敏感隔离 + HP 挂兜底）。
验收：HP 停止时 ccc-kb 本地检索兜底不中断。

### 凭据治理
目标：处理 .credentials-backup、轮换 .env 口令、清理 gitignore，杜绝敏感材料进 git。
验收：无敏感材料入仓，凭据已轮换/隔离。

### 可重建验证（灾备演练）
目标：从 SSOT 全新部署到空机，验证整套服务可恢复、可端到端检索。
验收：空机重建 + 端到端检索通过，演练记录归档。

## 转卡计划

本方案为「已确认」状态（规划已定，暂不出卡）。功能卡清单经老板节点②确认后，用 `plan-to-cards.sh` 一次转卡执行。

## 备注

- **开发/部署分离红线**：开发只在 mac2017 SSOT，部署产物才上 hp 节点；禁止直接在 hp 节点改源码
- **红线**：不破坏既有 5267 docs 检索与多端 MCP 调用；凭据轮换后旧凭据作废
- **范围外**：告警推送（M3）、数据重灌（M4）、生态消费（M5）分别立项
