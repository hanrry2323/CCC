# 方案 · 后端核心模块测试覆盖率除债与单测补齐

> 项目：mx · 编号：mx-plan-008 · 状态：待验收 · 作者：Claude Code W1 · 工具：ccc-plan
> 批准：老板确认转卡 · 2026-08-19
> 创建：2026-08-18 · 更新：2026-08-20
> 关联卡：mx053
> 进度：1/1 (100%)
> 里程碑：M8 · 媒体库与 RSS 阅读体验优化（子项目 8.4）

## 目标

收窄 `tarpaulin` 工具对核心代码的广泛过滤，补齐 `websub_service`、`scan_scheduler`、`rss_service` 等核心后端逻辑的真实单元测试，将后端核心 core 模块真实覆盖率推升至 80% 以上。

## 背景

当前 `tarpaulin` 针对 `medio-core` 的测试覆盖率报告屏蔽了大量核心功能文件的真实检验。为了对公开化和多端 CI 交付提供坚实的技术底座支持，必须对这些关键服务实施单元测试与覆盖率除债。

## 方案内容

### 1. 覆盖率屏蔽层收缩
- 修改 `Cargo.toml` 或 `tarpaulin.toml` 配置文件，移除对 `service/rss/*` 以及核心扫描器 `scan_scheduler` 等文件的排除项。

### 2. SQLite 内存单测补齐
- 为 `rss_service` 和 `scan_scheduler` 设计轻量级、无状态的 SQLite 内存（`:memory:`）数据库测试套件。
- 测试覆盖订阅状态转换、扫描重试次数递增、错误日志状态写回等核心边界逻辑。

## 功能卡

### 后端核心模块测试覆盖率补齐

目标：收窄 tarpaulin 覆盖率屏蔽，补 websub_service/scan_scheduler/rss_service 等核心后端单测，行覆盖率≥80%。

实现：①`Cargo.toml`/`tarpaulin.toml` 移除对 `service/rss/*`、`scan_scheduler` 等的排除项（覆盖率屏蔽收缩）；②为 rss_service、scan_scheduler 设计 SQLite `:memory:` 无状态单测套件，覆盖订阅状态转换、扫描重试递增、错误日志写回等边界逻辑。

验收：覆盖率排除配置缩减后单测全绿；后端核心模块实际行覆盖率≥80%。

颗粒度：配置改动 + 多个单测文件（service/rss、scan_scheduler），1-2 张卡（建议 1 张，配置+单测同批）。

依赖：无（纯增量测试，不改业务逻辑）。

架构位置：后端 core 服务层（rss_service/scan_scheduler/websub_service）+ Cargo/tarpaulin 覆盖率配置。

## 验收标准

- [ ] 后端 core 模块在覆盖率排除配置缩减后，单元测试执行全绿通过。
- [ ] 后端实际测试行覆盖率（Line Coverage）不低于 80%。
