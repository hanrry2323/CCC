# 交付报告 · 知识库底座固化（M1）

> 项目：hp · 编号：hp-delivery-001 · 方案：hp-plan-001、hp-plan-002 · 作者：CCC 中枢 · 交付日期：2026-08-19 · 软件版本：v0.1.2 · 对应 Git Tag：v0.1.1

## 1. 交付目标与背景

HP 知识库底座固化：从零搭建集群知识库底座——数据结构（PG18+pgvector）、MCP 服务六工具、语义检索、种子入库全链路。M1 是 HP 项目的第一个里程碑，22 张卡（hp001-022）全部关闭，5267 docs 在线。为 M2-M5（稳控/可观测/数据保鲜/生态消费）奠定基础。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本报告归档 `docs/projects/hp/deliveries/hp-delivery-001.md`
- [x] **CHANGELOG**：业务仓 CHANGELOG.md（v0.1.2 阶段，最新 2026-08-03；M2-M5 后续工作待补 CHANGELOG）
- [x] **RELEASE**：业务仓版本记录（v0.1.2）
- [x] **Git Tag**：v0.1.1 已打 push（注：tag v0.1.1 落后 VERSION v0.1.2，待补 v0.1.2 tag）
- [x] **可复跑安装验证**：业务仓 `scripts/qa/dr_drill_test.sh`（灾备演练）+ `scripts/qa/verify-k23.sh`（短 chunk 门控）+ `hp-health.py`（健康探针）均可复跑；`docs/knowledgebase/REBUILD_VERIFY_REPORT.md` 可重建验证报告

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：hp-plan-001、hp-plan-002 状态=已完成
- [x] **方案验收标准全勾**：hp-plan-001 4 条验收（短 chunk<15% / 采集管道稳定 / 前端真数据检索 75+ / 测试评分 4→7）全 `[x]`
- [x] **关联任务卡全关闭**：hp001-022 全部已关闭
- [x] **项目档案近况同步**：README 线路/近况已含 M1
- [x] **全局线路图挂账同步**：docs/projects/hp/roadmap.md M1 标已完成

## 4. 版本与发布信息

- 软件版本：`v0.1.2`
- 部署：Mac2017 `/Users/fan/program/apps/hp`（编排 SSOT）+ HP 节点 `/data/knowledge`（双 clone 同 github 仓，SSOT=mac2017）
- 关联卡：hp001-022（22 张）
- 运行态：mcp-server(:8083) + memory-store(:8082) + postgres(:5432) + ollama(:11434) + graph(:8000) 五服务在线

## 5. 运维要点

- PG18 + pgvector 向量索引（ivfflat），数据分区 `/data` 167G/458G
- embedding 走 HP 本机 ollama（11434），2026-08-02 修复（旧规则 mac2017 已 RETRACTED）
- 冷备份：HP 文本权威区 → Mac2017 冷存储（每日快照保留 7 份）

## 6. 回滚

- 数据层：PG 物理备份 + 文本权威区冷存储双保险
- 代码层：v0.1.1 tag 可 `git reset --hard v0.1.1` 回退
- 服务层：launchd 五服务可逐个 kickstart 重启

## 7. 后续（M2-M5 交付物）

M2（稳控）/M3（可观测）/M4（数据保鲜）/M5（生态消费）方案均已验收"已完成"，交付物（CHANGELOG/tag/scripts）在业务仓但未 CCC 侧登记。建议后续合并补 hp-delivery-002（M2-M5 综合），因 HP 是单仓多里程碑，业务仓 CHANGELOG 连续记录，不强行按里程碑切分 delivery。
