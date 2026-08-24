# 存量卡关联字段治理：旧->新方案关联映射对照表 (2026-08-09)

> 关联：ccc-plan-011 卡4 · 治理详情审计参考

| # | 任务卡 ID | 任务卡名称 | 项目 | 治理前关联字段 (旧) | 治理后关联字段 (新) |
|---|-----------|------------|------|--------------------|--------------------|
| 1 | `T40-shell-base-3col-ui` | 壳基座修复 + 三栏 UI（HTTP + 桌面）（Trae GLM5.2 执行） | `ccc` | 新阶段「双壳可用 + 心智升级」（老板 2026-08-03 指示） | `ccc-plan-001` |
| 2 | `T41-brain-mind-streaming` | 大脑心智升级 + 流式输出体验（OpenCode 执行） | `ccc` | 新阶段「双壳可用 + 心智升级」 | `ccc-plan-001` |
| 3 | `T42-dual-shell-e2e-acceptance` | 双壳全链路联调 + 心智验收（OpenCode 执行） | `ccc` | 新阶段「双壳可用 + 心智升级」收口 | `ccc-plan-001` |
| 4 | `T43-conversation-long-poll` | 对话历史 HTTP 长轮询增量同步（OpenCode 执行） | `ccc` | 新阶段「对话壳感知 + 增量同步」 | `ccc-plan-001` |
| 5 | `T44-shell-ux-optimization` | 双壳体验优化：10 项问题修复（OpenCode 执行） | `ccc` | 老板实测反馈「问题太多」 | `ccc-plan-001` |
| 6 | `T45-user-centric-ux-overhaul` | 以人为本体验整改：10 项（Claude Code 执行） | `ccc` | 老板实测强烈反馈（2026-08-04）——「登录脱裤子放屁」「发一次就断」「无流式无工具卡」「界面一堆 bug」；Codex 真机取证逐项定位根因 | `ccc-plan-001` |
| 7 | `T46-conversation-stability-sse` | 对话稳定性 + SSE 展示体验（Claude Code 执行） | `ccc` | 老板实测反馈（2026-08-04）「对话过程中切换界面就中断」「思考过程/思考文字没展示」 | `ccc-plan-001` |
| 8 | `T47-project-thread-sidebar` | 项目+会话模型重构 + 左栏（借鉴 Codex/Cursor）（Claude Code 执行） | `ccc` | 老板指出「左侧栏展示逻辑错误——应该项目+对话，用项目区分，不是任务分组；展示逻辑借鉴 Codex/Cursor 成熟工具」 | `ccc-plan-001` |
| 9 | `T48-shell-problem-audit` | 双壳全量问题排查（Claude Code 执行） | `ccc` | 老板反馈「桌面端和 HTTP 页面小问题非常多」+「展示逻辑借鉴 Codex/Cursor 成熟工具」 | `ccc-plan-001` |
| 10 | `T49-conversation-as-workflow` | 业务流程打通：对话即工作闭环（Claude Code 执行） | `ccc` | 老板指示「站在业务流程梳理高度，前端界面与后端功能业务打通」 | `ccc-plan-001` |
| 11 | `T50-dual-shell-e2e-acceptance` | 双壳全链路联调 + 老板实测验收（Claude Code 执行） | `ccc` | 业务流程打通收口 | `ccc-plan-001` |
| 12 | `T51-knowledge-mcp-optimize` | 知识库 MCP 优化（Claude Code 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 13 | `T52-automation-base` | 自动化基建：出卡模板 + 一键放行 + 验收自动化（Claude Code 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 14 | `T54-auto-naming-migration` | T-A1 命名与目录迁移（Claude Code 执行） | `ccc` | 阶段 3（T-A1 命名规则落地，Codex 决策 2026-08-04） | `ccc-plan-005` |
| 15 | `T55-index-layer` | T-A2 派生索引层（Claude Code 执行） | `ccc` | 阶段 3（T-A2 索引层，过夜任务后端链 1/3） | `ccc-plan-005` |
| 16 | `T56-card-components` | T-B1 统一卡片组件层（Claude Code 执行） | `ccc` | 阶段 3（T-B1 统一卡片组件，过夜任务前端链 1/2） | `ccc-plan-005` |
| 17 | `T57-big-small-cards` | T-A4 大卡/小卡 + 项目级执行体隔离（Claude Code 执行） | `ccc` | 阶段 3（T-A4，过夜任务后端链 2/3） | `ccc-plan-005` |
| 18 | `T58-board-refactor` | T-B2 看板重构（列表默认 + 视图切换）（Claude Code 执行） | `ccc` | 阶段 3（T-B2，过夜任务前端链 2/2） | `ccc-plan-005` |
| 19 | `T59-engine-parallel-relay-guard` | Engine 异步派发 + 中继稳定性兜底（Claude Code 执行） | `ccc` | 过夜任务发现——① Engine 串行派发（同步等执行体完成才派下一张）；② 上游中继多次波动导致执行卡死/超时 | `ccc-plan-001` |
| 20 | `T60-console-cockpit` | T-B3 控制台驾驶舱对齐统一组件（Claude Code 执行） | `ccc` | 前端四板块架构（T-B3） | `ccc-plan-001` |
| 21 | `T61-task-flow-linked` | T-B4 右栏关联卡流 + task_status 联动（Claude Code 执行） | `ccc` | 前端四板块架构（T-B4）+ T49 对话即工作 | `ccc-plan-001` |
| 22 | `T62-archive-review` | T-A5 历史归档与回顾 + /cards 兜底（Claude Code 执行） | `ccc` | 阶段 3（T-A5）+ T50 联调发现（/cards 缺索引返回空，需兜底） | `ccc-plan-005` |
| 23 | `T63-nginx-entry` | Nginx 统一入口（Claude Code 执行） | `ccc` | 阶段 3（Nginx 统一入口） | `ccc-plan-005` |
| 24 | `T64-engine-auto-worktree` | Engine 自动按卡建 worktree（并行派发完善）（Claude Code 执行） | `ccc` | T59 并行派发发现——每卡需独立 worktree，当前靠卡内续作指令手动建 | `ccc-plan-001` |
| 25 | `T65-dual-shell-align` | T-B5 双壳对齐（桌面端补齐 HTTP 新能力）（Claude Code 执行） | `ccc` | 前端四板块架构（T-B5 双壳对齐） | `ccc-plan-001` |
| 26 | `T67-deploy-race-guard` | 部署窗口误派防线（卡头纪律 + Engine/放行双保险）（Claude Code 执行） | `ccc` | T60 误派复盘（2026-08-05 部署窗口：已验收卡因卡头未同步被 Engine 重新拉起） | `ccc-plan-001` |
| 27 | `T68-http-resource-resilience` | HTTP 壳静态资源加载韧性（Cursor 测试卡 · M1 前端开发） | `ccc` | T48 审计 P0（M1→2017 静态资源并发 ERR_CONNECTION_RESET 41%，SPA 白屏根因，前端侧） | `ccc-plan-001` |
| 28 | `T69-release-engine-plist-rebuild` | release.sh Engine plist 自愈（T68 部署事故修复） | `ccc` | T68 部署事故（2026-08-05：start_engine 遇 plist 缺失仅 WARN，Engine 掉线未恢复，Codex 现场重建恢复） | `ccc-plan-001` |
| 29 | `T70-code-audit` | 全项目代码 bug 检查（Cursor 测试卡 2 · M1 只读审计） | `ccc` | 老板 2026-08-06 指示「Cursor 做一次全部 CCC 项目检查，主要做代码 bug 检查」 | `ccc-plan-001` |
| 30 | `T71-fix-server-p0` | server P0 修复（F01/F02/F11 · T70 审计） | `ccc` | T70 审计 P0（F01 卡头替换误改正文 / F02 非 UTF-8 卡拖垮扫描 / F11 SSE 断流不 settle） | `ccc-plan-001` |
| 31 | `T72-fix-desktop-p0` | desktop P0 修复（F18/F19/F20 · T70 审计） | `ccc` | T70 审计 P0（F18 workspace 传路径 / F19 Kanban 英文旧列 / F20 流式缺 thread_id/model） | `ccc-plan-001` |
| 32 | `T76-conversation-base-hardening` | 对话大底座加固与 50 轮稳定性极限压测 | `ccc` | 对话大底座加固（F16） | `ccc-plan-001` |
| 33 | `ccc001-e2e-smoke-engine-dirty` | E2E smoke: Engine dispatch + worktree + board dirty（Claude Code 执行） | `ccc` | E2E联调 2026-08-06 | `ccc-plan-007` |
| 34 | `ccc002-e2e-smoke-opencode` | E2E smoke: OpenCode channel + worktree（OpenCode 执行） | `ccc` | E2E联调 OpenCode 2026-08-06 | `ccc-plan-007` |
| 35 | `ccc003-engine-anti-fake-success-and-template-align` | E2E 派发收单防假成功与技术债收口（Claude Code 执行） | `ccc` | E2E联调技术债 2026-08-06 | `ccc-plan-007` |
| 36 | `ccc004-register-ccc-demo-prefix` | register ccc-demo prefix cd（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 37 | `ccc005-registry-single-source` | 项目注册表单源接线（PREFIXES /projects /taskable + 校验） | `ccc` | 文档与项目注册统一治理 | `ccc-plan-001` |
| 38 | `ccc006-engine-audit-auto-backfill` | engine机审通过自动落盘机审区（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 39 | `ccc007-m5-audit-dogfood-rebase-hint` | M5 audit dogfood rebase hint（OpenCode 执行） | `ccc` | M5 真机审狗粮 | `ccc-plan-001` |
| 40 | `ccc008-ready-probe-script` | ready-probe 脚本（OpenCode 执行） | `ccc` | ccc-plan: M7 ready-probe dogfood | `ccc-plan-003` |
| 41 | `ccc009-stale-docs-archive-cleanup` | 文档卫生：过时/过期文档清理归档（OpenCode 执行） | `ccc` | ccc-plan: 文档卫生与业务总线路图 | `ccc-plan-002` |
| 42 | `ccc010-roadmap-business-track-xy` | 总线路图：roadmap 增业务线路（xy）总览段（OpenCode 执行） | `ccc` | ccc-plan: 文档卫生与业务总线路图 | `ccc-plan-002` |
| 43 | `ccc012-48-codex` | 48 分叉 codex 分支人工核验清理（Claude Code 执行） | `ccc` | 升级批次 3 生命周期 | `ccc-plan-001` |
| 44 | `ccc013-flow-verify-pipeline` | 新流程全链路验证（OpenCode 执行） | `ccc` | CCC 系统化升级 | `ccc-plan-004` |
| 45 | `ccc014-converge-stale-remote-branches` | 收敛历史已关闭卡的远端 codex 分支（OpenCode 执行） | `ccc` | CCC 治理 | `ccc-plan-004` |
| 46 | `ccc015-gate-audit-separation` | 机械门禁与机审职责分离：编译/测试/lint/范围由门禁裁决，机审定位优化就地闭环（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 47 | `ccc017-prompt` | 引擎 prompt 注入审计日志（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 48 | `ccc018-task` | 知识库条目自动同步脚本（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 49 | `ccc019-engine-gate-skip-metrics` | engine gate skip metrics（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 50 | `ccc020-prompt-injection-dashboard` | prompt injection dashboard（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 51 | `ccc021-s8` | S8 转卡验收样例 — 转卡验收样例卡（OpenCode 执行） | `ccc` | 阶段 3 P1 | `ccc-plan-005` |
| 52 | `clw007-resume-cwd-fix` | resume 携带工作目录 + git 路径解码修复 + kill 非阻塞（OpenCode 执行） | `clw` | ccc-plan: clw007 会话恢复工作目录 + 小缺陷修复 | `clw-plan-001` |
| 53 | `hp001-recon-baseline-roadmap` | 首次摸底：recon baseline 与业务线路图梳理（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 54 | `hp002-monitoring-git-probe` | 监控盲区：cluster-health 增强 hp git 状态探针与统一探活（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 55 | `hp003-backup-alignment` | 备份对齐：pg 备份链路摸底与冷热备份机制规范化（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 56 | `hp004-collector-source-expansion` | 采集管道验证与数据源扩展（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 57 | `hp005-frontend-fake-data-contract` | 前端治理：假数据边界与API契约三方对齐（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 58 | `hp006-search-quality-short-chunks` | 搜索质量：短chunk清理与检索相关性调优（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 59 | `hp007-cli-fulltext-and-short-chunk-gate` | 旧 CLI 全库检索复活 + 管道短 chunk 闸门 + bak 恢复 + 文档回填（OpenCode 执行） | `hp` | ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填） | `hp-plan-001` |
| 60 | `hp008-project-id-mapping-plan` | documents.project_id 与 chunks.project 映射规则方案（OpenCode 执行） | `hp` | ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填） | `hp-plan-001` |
| 61 | `hp010-collector-multisource-fix` | 采集管道多源固化与补采（ccc-docs 剩余 + qb 源恢复）（OpenCode 执行） | `hp` | ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正） | `hp-plan-001` |
| 62 | `hp011-qb-docs-ownership-fix` | qb 文档错归属存量修正（OpenCode 执行） | `hp` | ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正） | `hp-plan-001` |
| 63 | `hp012-dashboard-search-real-data` | Dashboard 与 Search 页面真实数据接入（清假数据）（OpenCode 执行） | `hp` | ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） | `hp-plan-001` |
| 64 | `hp013-library-doc-activity-notes-real-data` | Library/Document/Activity/Notes 页面真实数据接入与空态统一（OpenCode 执行） | `hp` | ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） | `hp-plan-001` |
| 65 | `hp014-backend-export-library-count` | 后端接口补齐（export 导出 + library 计数）（OpenCode 执行） | `hp` | ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） | `hp-plan-001` |
| 66 | `hp015-frontend-page-test-coverage` | 前端页面测试覆盖（React Testing Library）（OpenCode 执行） | `hp` | ccc-plan: HP 前端测试覆盖补齐（页面渲染 + 关键交互，目标测试评分 4→7） | `hp-plan-001` |
| 67 | `hp016-collector-pipeline-repair` | 采集管道完整性恢复与 md_parser 解析修复（OpenCode 执行） | `hp` | ccc-plan: HP 采集管道完整性修复（ingest/md_parser 恢复 + 解析 bug + ccc-docs 补采） | `hp-plan-001` |
| 68 | `hp017-chunk-hp007` | 存量短 chunk 清理落库（hp007 遗留）（OpenCode 执行） | `hp` | hp007 遗留：存量 445 短 chunk 处理方案落库 | `hp-plan-001` |
| 69 | `hp019-task` | 采集器日志结构化（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 70 | `hp020-chunk` | 短 chunk 门禁自动化脚本（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 71 | `hp021-search-result-relevance-scoring-display` | search result relevance scoring display（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 72 | `hp022-collector-network-error-retry` | collector network error retry（OpenCode 执行） | `hp` | 阶段 3 P1 | `hp-plan-001` |
| 73 | `mx001-recon-and-baseline` | recon and baseline（OpenCode 执行） | `mx` | 阶段 3 P1 | `mx-plan-001` |
| 74 | `mx002-add-server-health-api-and-python-smoke-test` | add server health api and python smoke test（OpenCode 执行） | `mx` | 阶段 3 P1 | `mx-plan-001` |
| 75 | `mx003-recon-business-tracks` | recon business tracks for in-flight branches（OpenCode 执行） | `mx` | mx 业务线路摸底 | `mx-plan-001` |
| 76 | `mx004-service-health-probe` | service health probe integration（OpenCode 执行） | `mx` | ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点 | `mx-plan-001` |
| 77 | `mx005-polish-inventory` | polish inventory for code and UI（OpenCode 执行） | `mx` | ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点 | `mx-plan-001` |
| 78 | `mx006-cargo-fmt-ci-gate` | CI 补后端 Rust 格式门禁（OpenCode 执行） | `mx` | ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验 | `mx-plan-001` |
| 79 | `mx007-settings-path-frontend-validation` | 设置页路径输入前端校验（OpenCode 执行） | `mx` | ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验 | `mx-plan-001` |
| 80 | `mx008-http-page-ux-audit` | HTTP 页面体验巡检（RSS 优先）（OpenCode 执行） | `mx` | ccc-plan: HTTP 页面体验巡检：RSS 优先 + 全页面代码/显示/双端适配 | `mx-plan-001` |
| 81 | `mx009-atom-parser-library` | Atom 解析器换标准库（OpenCode 执行） | `mx` | ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项 | `mx-plan-001` |
| 82 | `mx010-opml-export-bearer-auth` | OPML 导出支持 Bearer 鉴权（OpenCode 执行） | `mx` | ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项 | `mx-plan-001` |
| 83 | `mx011-tablet-breakpoint-layout-fix` | 768px 平板断点布局修复（OpenCode 执行） | `mx` | ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项 | `mx-plan-001` |
| 84 | `mx012-rss-stats-backend-aggregation` | RSS 统计改后端聚合接口（OpenCode 执行） | `mx` | ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项 | `mx-plan-001` |
| 85 | `mx013-architecture-doc-dev-guide` | 整体架构文档与开发指南（OpenCode 执行） | `mx` | ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐 | `mx-plan-001` |
| 86 | `mx014-crawl-all-image-localization` | crawl_all 图片本地化缓存补齐（OpenCode 执行） | `mx` | ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐 | `mx-plan-001` |
| 87 | `mx015-crawl-all-error-writeback` | crawl_all 错误状态写回数据库（OpenCode 执行） | `mx` | ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐 | `mx-plan-001` |
| 88 | `mx016-pc-keyboard-shortcuts` | PC 端 RSS 键盘快捷键（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进 | `mx-plan-001` |
| 89 | `mx017-rss-image-proxy` | RSS 图片防盗链代理端点（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进 | `mx-plan-001` |
| 90 | `mx018-rss-reader-css-class` | RSS 阅读器 CSS 类绑定修复（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进 | `mx-plan-001` |
| 91 | `mx019-backend-coverage-core-tests` | 后端覆盖率收窄与核心服务单测（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进 | `mx-plan-001` |
| 92 | `mx020-rss-save-transaction` | RSS 保存事务化（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复 | `mx-plan-001` |
| 93 | `mx021-scheduled-health-probe` | 定时巡检接线（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复 | `mx-plan-001` |
| 94 | `mx022-opml-import-attribute-order` | OPML 导入属性顺序修复（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复 | `mx-plan-001` |
| 95 | `mx023-frontend-coverage-ci-gate` | 前端覆盖率 CI 门禁（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露 | `mx-plan-001` |
| 96 | `mx024-quick-xml-security-upgrade` | quick-xml 安全债升级（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露 | `mx-plan-001` |
| 97 | `mx025-core-module-coupling-audit` | core 模块耦合梳理（OpenCode 执行） | `mx` | ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露 | `mx-plan-001` |
| 98 | `mx026-rssservice-websub-p0` | RssService WebSub 联动断链修复（P0）（OpenCode 执行） | `mx` | mx025 架构问题清单 #1 P0 | `mx-plan-001` |
| 99 | `mx027-core-60` | 后端 core 模块测试覆盖率提升到 60%（OpenCode 执行） | `mx` | 阶段 3 P1 | `mx-plan-001` |
| 100 | `mx028-rss-feed-validation-before-add` | RSS feed validation before add（OpenCode 执行） | `mx` | 阶段 3 P1 | `mx-plan-001` |
| 101 | `mx029-media-library-sort-persistence` | media library sort persistence（OpenCode 执行） | `mx` | 阶段 3 P1 | `mx-plan-001` |
| 102 | `qb002-task` | 添加基础测试套件（OpenCode 执行） | `qb` | 阶段 3 P1 | `qb-plan-001` |
| 103 | `qb003-lint` | 代码规范与 lint 自动化（OpenCode 执行） | `qb` | 阶段 3 P1 | `qb-plan-001` |
| 104 | `qb004-api-response-time-logging` | API response time logging（OpenCode 执行） | `qb` | 阶段 3 P1 | `qb-plan-001` |
| 105 | `qb005-script-argument-parsing-fix` | script argument parsing fix（OpenCode 执行） | `qb` | 阶段 3 P1 | `qb-plan-001` |
| 106 | `xy001-write-video-script-command` | 一键生成短视频脚本命令与产出流程（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 107 | `xy002-bug-scan-and-fix` | xy代码bug全量扫描与修复（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 108 | `xy003-wire-2pass-encoding` | 接入2pass VBR编码到生产链路（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 109 | `xy004-fix-audio-voice-ducking` | 音频处理：修复语音闪避(ducking)功能异常（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 110 | `xy005-fix-audio-bgm-and-level-norm` | 音频处理：重构BGM自动混音与音量标准化（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 111 | `xy006-platform-kuaishou-channels-bridge` | 平台适配：接入快手与微信视频号发布通道（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 112 | `xy007-bilibili-toutiao-cookie-collector` | 登录流程：实现B站与头条自存Cookie扫码抓取工具（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 113 | `xy008-auto-build-openclaw-plugin` | 系统集成：自动构建openclaw-plugin与依赖补齐（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 114 | `xy009-video-pexels-clip-downloader` | 内容生产：接入Pexels/Pixabay API检索下载短视频素材（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 115 | `xy010-video-high-bitrate-crf-encoding` | 画面加固：全链路视频高码率高质量CRF编码升级（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 116 | `xy011-subtitle-karaoke-style-ass-rendering` | 字幕重构：引入双色卡拉OK高亮与高表现力ASS滤镜渲染（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 117 | `xy012-tts-multi-voice-emotion-selector` | 配音加固：爆款TTS情绪人声分流与配音轨道声学增强（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 118 | `xy013-render-hyperframes-glass-template` | 画面渲染：激活并打通Hyperframes网页组件渲染引擎（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 119 | `xy014-eng-baseline-video-pipeline-alignment` | 工程化：video-pipeline 与旁路对齐 + 退役决策落盘（OpenCode 执行） | `xy` | ccc-plan: xianyu 工程化底座补齐 | `xy-plan-001` |
| 120 | `xy015-eng-profile-renewal-2026-08` | 工程化：.ccc 档案续期到 08-07 现状（OpenCode 执行） | `xy` | ccc-plan: xianyu 工程化底座补齐 | `xy-plan-001` |
| 121 | `xy016-video-pipeline-recon-html-report` | 视频出片链路全摸底与架构图 HTML 产出（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 122 | `xy017-storage-layout-normalize` | 存储路径统一规划与硬编码消除（OpenCode 执行） | `xy` | ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 | `xy-plan-001` |
| 123 | `xy018-config-drift-fix` | 配置漂移修复与文档对齐（OpenCode 执行） | `xy` | ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 | `xy-plan-001` |
| 124 | `xy019-prod-gap-fix` | 生产补漏：Pexels Key 部署与 BGM 校验与调度核实（OpenCode 执行） | `xy` | ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 | `xy-plan-001` |
| 125 | `xy020-round2-legacy-inventory` | 第二轮历史遗留全仓排查与遗留清单产出（OpenCode 执行） | `xy` | ccc-plan: xy 第二轮历史遗留排查（根基立稳） | `xy-plan-001` |
| 126 | `xy021-purge-hardcode-old-rules` | 硬编码/旧 OpenCode 规则/人名消灭（P0-PATH）（OpenCode 执行） | `xy` | ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 | `xy-plan-001` |
| 127 | `xy022-dynamic-path-derivation` | 遗留治理①：硬编码路径动态推导（P0-PATH 深化）（OpenCode 执行） | `xy` | ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 | `xy-plan-001` |
| 128 | `xy023-env-credential-alignment` | 遗留治理②：凭据补全与 .env.example 对齐（P0-CRED）（OpenCode 执行） | `xy` | ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 | `xy-plan-001` |
| 129 | `xy025-media-quality-acceptance` | 成片质量验收联测（P0-MEDIA）（OpenCode 执行） | `xy` | ccc-plan: xy PRM 批3：成片质量验收联测 + 关卡自动验证脚本 | `xy-plan-001` |
| 130 | `xy026-p0-flow` | 测试门禁修复与文档除债（P0-FLOW 前置）（OpenCode 执行） | `xy` | xy PRM P0-FLOW 前置（xy024 意图重建） | `xy-plan-001` |
| 131 | `xy028-pytest-3` | 修复 pytest 3 个失败用例（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 132 | `xy029-task` | 清理文档中过期工具引用（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 133 | `xy030-video-encoding-progress-log` | video encoding progress log（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
| 134 | `xy031-config-path-resolution-fix` | config path resolution fix（OpenCode 执行） | `xy` | 阶段 3 P1 | `xy-plan-001` |
