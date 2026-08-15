# 方案 · HP 知识库底座固化与里程碑推进

> 项目：hp · 编号：hp-plan-001 · 状态：已完成 · 作者：OpenCode · 工具：ccc-plan
> 创建：2026-08-09 · 更新：2026-08-10
> 关联卡：hp001, hp002, hp003, hp004, hp005, hp006, hp007, hp008, hp010, hp011, hp012, hp013, hp014, hp015, hp016, hp017, hp018, hp019, hp020, hp021, hp022
> 关联方案: 无

## 目标

完成 HP 知识库底座评估整改、采集管道完整性修复与真数据接入，提升检索质量与前端测试覆盖率。

## 背景

HP 知识库是平台的关键基建，但此前存在短 chunk 碎片化严重、采集管道断链、真数据未打通及测试覆盖率低的问题。需要通过体系化打磨，使检索质量与管道稳定性量化达标。

## 方案内容

1. 评估整改：复活 CLI 检索、设置短 chunk 过滤闸门、建立口径映射。
2. 管道修复：恢复 ingest 和 md_parser 服务，修复解析 bug，补采文档。
3. 落地推进：存量数据落库，固化采集管道，修正 qb 归属。
4. 前端里程碑：打通真数据接入，实现后端接口及空态设计，补充单元测试与端到端测试。

## 验收标准

- [x] 存量短 chunk 占比降低到 15% 以下
- [x] 采集管道运行稳定，增量文档可自动解析落库
- [x] 前端真数据接口打通，检索评估得分达到 75+ 分
- [x] 测试覆盖率量化提升，测试评分从 4 提升到 7

## 转卡计划

- hp001-recon-baseline-roadmap: 知识库业务线路摸底与基线对齐
- hp002-monitoring-git-probe: 接入 git 与服务健康监测
- hp003-backup-alignment: 备份对齐与清理
- hp004-collector-source-expansion: 采集源扩容
- hp005-frontend-fake-data-contract: 前端 mock 数据契约
- hp006-search-quality-short-chunks: 短 chunk 评估
- hp007-cli-fulltext-and-short-chunk-gate: CLI 检索复活与短 chunk 闸门
- hp008-project-id-mapping-plan: 项目 ID 映射
- hp010-collector-multisource-fix: 采集器多源修复
- hp011-qb-docs-ownership-fix: qb 归属修正
- hp012-dashboard-search-real-data: 检索真数据接入
- hp013-library-doc-activity-notes-real-data: 活动笔记真数据
- hp014-backend-export-library-count: 后端导出数据量统计
- hp015-frontend-page-test-coverage: 前端测试覆盖补齐
- hp016-collector-pipeline-repair: 采集管道完整性修复
- hp017-chunk-hp007: 存量短 chunk 清理落库
- hp019-task: 采集任务调度
- hp020-chunk: 文本分块策略调优
- hp021-search-result-relevance-scoring-display: 检索结果相关性评分展示
- hp022-collector-network-error-retry: 采集器网络异常重试

## 备注

- 依赖于 2017 服务端的稳定性与网络挂载的持续在线。
