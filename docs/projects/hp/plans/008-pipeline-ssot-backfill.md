# 方案 · pipeline 源码回灌 SSOT（M2）

> 项目：hp · 编号：hp-plan-008 · 状态：已完成 · 作者：Claude（中枢） · 工具：Claude Code
> 批准：老板验收拍板 · 2026-08-16
> 创建：2026-08-16 · 更新：2026-08-16
> 关联卡：hp023
> 关联方案：无
> 进度：1/1 (100%)
> 里程碑：M2 · 稳控与可恢复
> 子项目：2.1 pipeline 源码回灌 SSOT
> 环境准备：mac2017 hp 业务仓可写；hp 节点 /data/knowledge/pipeline 只读访问

## 目标

把 hp 节点 pipeline 核心源码全部迁入 mac2017 SSOT 仓并纳入 git，消除源码丢失 P0。

## 背景

pipeline（ingest/chunker/embedder/search/config/parsers）源码只存在于 hp 部署机，mac2017 SSOT 仓没有——违反 README「服务源码必须进 git」规则。

## 功能卡

### 实施「pipeline 源码回灌 SSOT」
目标：完成子项目 2.1 pipeline 源码回灌 SSOT，交付可验收产物。
颗粒度：子项目级（1-2 卡）。
依赖：无
架构位置：pipeline 全链路（ingest→chunker→embedder→search）

## 验收标准

- [x] pipeline 源码回灌 SSOT完成，验收点可复核（命令/可观察结果）

## 备注

前置子项目（依赖）：无——按依赖顺序逐步转卡，前置卡完成后本子项目才能独立验收。
