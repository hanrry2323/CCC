# 方案 · RSS 统计接口后端 SQL 聚合优化

> 项目：mx · 编号：mx-plan-007 · 状态：已完成 · 作者：Claude Code W1 · 工具：ccc-plan
> 批准：老板确认转卡 · 2026-08-19
> 创建：2026-08-18 · 更新：2026-08-20
> 关联卡：mx055
> 进度：1/1 (100%)
> 里程碑：M8 · 媒体库与 RSS 阅读体验优化（子项目 8.3）

## 目标

解决 `RssStatsPage.tsx` 获取未读/已读统计时因全量拉取 1000 条数据导致的严重网络带宽与内存计算性能瓶颈，重构为由后端执行高性能 `COUNT(*)` SQL 并直接返回数值。

## 背景

当前 RSS 统计前端拉取最多 1000 条数据到本地进行 `filter` 计算，不仅在条目过 1000 时导致统计数据失真，而且大体积 JSON 的拉取和频繁过滤还会导致移动端和 PC 端在媒体库增多时发生卡顿。应当在后端利用 SQLite 数据库引擎的高性能 `COUNT(*)` 机制进行轻量化统计聚合。

## 方案内容

### 1. 后端新增聚合端点
- 在 `api/routes/rss.rs` 新增专门的聚合接口 `GET /api/v1/rss/stats`。
- 由底层数据库调用 `SELECT COUNT(*) FROM rss_items WHERE unread = ?` 等 SQL 语句，组装轻量级的 JSON 返回值（例如：`{ "unread_count": N, "starred_count": M }`）。

### 2. 前端请求对齐
- 重构 `RssStatsPage.tsx`，废弃原有的 `rssApi.items({ perPage: 1000 })` 拉取全量文章流并过滤的逻辑。
- 对齐新接口，异步请求 `GET /api/v1/rss/stats` 获取预先统计好的数值并秒级渲染。

## 功能卡

### RSS 统计接口 SQL 聚合优化

目标：消除前端拉 1000 条全量数据计算统计的卡顿，改后端 COUNT(*) 聚合返回数值。

实现：①后端 `api/routes/rss.rs` 新增 `GET /api/v1/rss/stats`，SQL `SELECT COUNT(*) ... WHERE unread=?` 组装 `{unread_count, starred_count}` 轻量 JSON；②前端 `RssStatsPage.tsx` 废弃 `rssApi.items({perPage:1000})` 全量拉取+filter，改请求新接口秒级渲染。

验收：新接口数据准确不受阈值截断；前端统计页带宽<1KB；后端编译+前端打包测试全绿。

颗粒度：前后端各一处（rss.rs + RssStatsPage.tsx），1 张卡。

依赖：无（独立端点，不改既有 RSS 列表接口）。

架构位置：后端 api/routes/rss.rs 聚合层 → 前端 RssStatsPage 统计视图。

## 验收标准

- [x] 新统计接口可用，数据实时准确，不受全量拉取阈值截断。
- [x] 前端载入统计页面不再拉取 1000 条全量数据，耗用带宽降低至 1KB 以下，彻底告别卡顿。
- [x] 后端编译与前端编译打包、测试全绿。
