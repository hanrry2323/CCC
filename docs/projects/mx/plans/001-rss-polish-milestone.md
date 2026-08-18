# 方案 · RSS 打磨与服务端里程碑推进

> 项目：mx · 编号：mx-plan-001 · 状态：已完成 · 作者：OpenCode · 工具：ccc-plan
> 创建：2026-08-09 · 更新：2026-08-10
> 关联卡：mx001, mx002, mx003, mx004, mx005, mx006, mx007, mx008, mx009, mx010, mx011, mx012, mx013, mx014, mx015, mx016, mx017, mx018, mx019, mx020, mx021, mx022, mx023, mx024, mx025, mx026, mx027, mx028, mx029
> 关联方案: 无
> 进度：29/29 (100%)

## 目标

对 RSS 核心逻辑、HTTP 服务、数据库模型与前端展示进行系统化打磨，提升性能、安全与用户体验，建立完善的质量门禁。

## 背景

medio-0 是独立业务仓，此前缺乏系统化规范，代码格式未强制规范，部分 RSS 解析和 WebSub 联动存在稳定性隐患，移动端与平板端显示不适配。需要进行一系列的打磨和重构工作，确保其作为生产服务的健壮性。

## 方案内容

1. 框架与地基：确立文档底基，梳理业务线路，补齐 RSS 巡检与监控。
2. 基础打磨：启动服务巡检，加入 Cargo Fmt 后端格式门禁，实现设置页路径前端校验。
3. RSS 解析与体验：修复 HTTP 页面，实现 OPML 导出 Bearer Auth 鉴权，支持 RSS 状态后端聚合。
4. 交互与安全推进：支持 PC 键盘快捷键，新增 RSS 图片代理以提升安全性，规范 RSS Reader CSS 样式。
5. 深度打磨：支持事务化保存，提供定时巡检并修复 OPML 导入，合并核心耦合模块，实现前端测试覆盖率 CI 门禁。

## 验收标准

- [x] 后端 Cargo Fmt 与前端 oxlint CI 门禁全绿
- [x] 服务巡检机制与 WebSub 联动运行正常
- [x] RSS 相关改动在 axum HTTP 服务端工作稳定
- [x] 页面在移动端、平板端自适应良好
- [x] 后端测试覆盖率达标

## 转卡计划

- mx001-recon-and-baseline: medio-0 业务摸底与环境对齐
- mx002-add-server-health-api-and-python-smoke-test: 添加服务端健康接口与 Python 冒烟测试
- mx003-recon-business-tracks: 梳理业务板块与独立性校验
- mx004-service-health-probe: 服务健康巡检
- mx005-polish-inventory: 打磨盘点与基准对齐
- mx006-cargo-fmt-ci-gate: CI 后端格式化门禁
- mx007-settings-path-frontend-validation: 设置页路径前端校验
- mx008-http-page-ux-audit: HTTP 页面体验巡检与自适应
- mx009-atom-parser-library: Atom 解析器
- mx010-opml-export-bearer-auth: OPML 导出 Bearer Auth
- mx011-tablet-breakpoint-layout-fix: 平板断点布局修复
- mx012-rss-stats-backend-aggregation: RSS 数据状态后端聚合
- mx013-architecture-doc-dev-guide: 编写架构文档与开发指南
- mx014-crawl-all-image-localization: 爬虫图片本地化
- mx015-crawl-all-error-writeback: 爬虫错误回写与巡检
- mx016-pc-keyboard-shortcuts: PC 键鼠快捷键
- mx017-rss-image-proxy: RSS 图片安全代理
- mx018-rss-reader-css-class: RSS Reader 样式优化
- mx019-backend-coverage-core-tests: 核心测试覆盖率
- mx020-rss-save-transaction: RSS 事务性保存
- mx021-scheduled-health-probe: 定时健康巡检
- mx022-opml-import-attribute-order: OPML 导入属性顺序兼容
- mx023-frontend-coverage-ci-gate: 前端测试覆盖率门禁
- mx024-quick-xml-security-upgrade: quick-xml 安全升级
- mx025-core-module-coupling-audit: 核心模块耦合度审计
- mx026-rssservice-websub-p0: WebSub 断流 P0 修复
- mx027-core-60: 核心模块迁移 60% 重构
- mx028-rss-feed-validation-before-add: 订阅源添加前合法性校验
- mx029-media-library-sort-persistence: 媒体库排序规则持久化

## 备注

- 各任务涉及 medio-core、medio-server 及前端，需保持多模块联动。
