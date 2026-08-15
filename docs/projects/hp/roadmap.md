# HP 知识库 线路图

> 项目：hp · 更新：2026-08-15

## 草案池

- M6 演进方向（多模态知识图谱 / 高维向量微调 / 高可用多副本）——已列里程碑，具体内容待老板定夺后再排期
- 悬空项：hp009 幽灵卡分支（`codex/hp009-stock-short-chunk-and-rss-backfill`）未合入 hp main、教训库仍引用——待裁决（归 M2 治理或单独处理）

## 里程碑

### M1 · 知识库底座固化
- 状态：已完成
- 关联方案：hp-plan-001、hp-plan-002
- 描述：从零搭建集群知识库底座——数据结构（PG18+pgvector）、MCP 服务六工具、语义检索、种子入库全链路；22 卡 + 20 分支合入，5267 docs 在线。
- 子节点：数据模型（documents/chunks/memory_store）｜MCP 服务（knowledge_search/kb_status/memory_*，双入口）｜语义检索（向量化+ivfflat）｜种子入库
- 遗留：hp009 分支未合入 → 转 M2 治理

### M2 · 稳控与可恢复
- 状态：待启动
- 关联方案：hp-plan-004
- 描述：让 HP **可恢复、可重建**——pipeline 源码回灌 SSOT、双仓 git 归一、运行时与 SSOT 对齐、全文摄入改造（主备分层基础）、凭据治理、可重建灾备验证。开发（mac2017）与部署（hp 节点）彻底隔离。
- 子节点：
  - 2.1 pipeline 源码回灌 SSOT（ingest/chunker/embedder/search 进 mac2017 仓）
  - 2.2 双仓归一（mac2017 与 hp 节点无共同祖先 → 统一 git 历史）
  - 2.3 运行时↔SSOT 对齐（运行时 mcp_server 含 kb_status 回灌；SSOT 领先部分回灌运行时）
  - 2.4 全文摄入改造（HP 存全文 chunk，检索直接出全文）
  - 2.5 双库改主备（ccc-kb 降为离线降级副本：敏感隔离 + HP 挂兜底）
  - 2.6 凭据治理（.credentials-backup 处理、.env 口令轮换、gitignore 清理）
  - 2.7 可重建验证（从 SSOT 全新部署到空机，验证可恢复）

### M3 · 可观测与告警
- 状态：待启动
- 关联方案：hp-plan-005
- 描述：HP 健康三态探针 + 故障自动发现——PG 僵尸事故（端口通连接全挂，20h 无人发现）后补齐可观测与告警，不再靠人巡检。
- 子节点：
  - 3.1 健康三态探针（postgres/ollama/memory-store/mcp-server/graph server 探活）
  - 3.2 pg-health 前端渲染（后端已合入 1bbabfe5，前端 renderPg 待办）
  - 3.3 告警推送通道（PG 僵尸/服务宕机 → 主动推送）
  - 3.4 悬空 cron 清理（HP 节点遗留 cron 排查）
  - 3.5 health 报告自动化（daily 报告 + 异常标记）

### M4 · 数据保鲜与质量
- 状态：待启动
- 关联方案：hp-plan-006
- 描述：数据不过期、检索质量稳——collector 加固、旧数据重灌（多个大项目 last_ingest 停在 6 月）、短 chunk 治理、相关性优化。
- 子节点：
  - 4.1 collector 加固（多源采集恢复/加固）
  - 4.2 旧数据重灌（claude-code/ai-instruction/boss/research 重 ingest）
  - 4.3 短 chunk 治理（拦截/合并，目标 <15%）
  - 4.4 相关性优化（knowledge_search 评分/排序改进）
  - 4.5 定时入库监控（collector 每日跑 + 监控）

### M5 · 生态消费
- 状态：待启动
- 关联方案：hp-plan-007
- 描述：业务项目真正用起来——mx/qb/xy 接入知识库，CCC 出卡/验收流程与 KB 检索、教训回流联动。
- 子节点：
  - 5.1 mx 接入（方案/教训/决策回流 HP）
  - 5.2 qb 深化（103 docs 基础上深化消费）
  - 5.3 xy 接入（建立 xy 域，现 0 docs）
  - 5.4 流程集成（出卡/验收时 KB 检索 + 教训回流自动触发）
  - 5.5 质量回检（消费方反馈 → 质量闭环）

### M6 · 演进（远期待定）
- 状态：待启动（内容待定）
- 关联方案：无（内容确定后再立项）
- 描述：能力升级方向——多模态知识图谱（graph server v3.1 → V2/V3：ELK/edges/社区检测）、高维向量微调、高可用多副本。全局 roadmap 已挂账「多模态知识图谱 K12」意向。
