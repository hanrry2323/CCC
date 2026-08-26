# 方案 · CCC 前端架构重构研究——与 DSH 深度绑定的目标架构、隔离层与迁移路径

> 项目：ccc · 编号：ccc-plan-049 · 状态：已确定 · 作者：DSH（ox-alpha · 总调度） · 工具：DSH
> 创建：2026-08-26 · 更新：2026-08-26
> 关联卡：无（老板直派研究课题 · 指令模式 · 全程只读研究，除本报告外零代码零配置改动；报告提交受老板临时授权）
> 关联方案：045（墙迁移 DSH 融合，P1/P1.5/P3 已落地）· 046（UI 一期皮层，M1/M2/M3 已落地、M4 回滚）· 047（二期实时通道收敛，已确定——P1 分支已实现未合入，P2-P4 未动）· 048（看板墙职责分离，P1 已合入 ccc079、P2/P3 未落地）
> 性质：研究报告。六项内容：现状盘点 / DSH 能力面盘点 / 目标架构 / DSH 隔离层 / 迁移路径 / 风险清单。

## 目标

回答一个问题：legacy-chat 单壳（15858 行）如何一次重构到位，成为「DSH 集群的操作面」，且 **DSH 升级时 CCC 前端不崩、最多适配层小改**。产出可直接拆功能卡的完整方案。

## 背景

老板立项定调（2026-08-26）：前端与 DSH 深度绑定——不是调 API 的浅集成，而是让 CCC 看板成为 DSH 集群的操作面（数据同源、操作直达）。硬边界：**绑定不得把 CCC 锁死在 DSH 的某个版本上**（DSH 当前 `0.1.1-rc.2`，rc 快速迭代期）。本报告全部结论基于只读实测，证据格式为 `文件路径:行号` 或命令输出。

---

## 0. 结论速览

1. **现状**：33 文件 15858 行中，可安全清除的死码约 **5200-5600 行（33-35%）**——CSS 约 4500-4890 行对话残留/多代死样式 + JS 层约 713 行（整文件 477 + 文件内死块 236）；七页面 js 共 4510 行是真实资产。047-P1 去轮询化已在 `feat/047-unification` 分支实现但**未合入 main**（main 上数据轮询 8 处仍在；分支有一处已声明偏差：plans 徽章用 60s 微探针替代 tasks/stream 订阅），P2-P4 未动。
2. **DSH 面**：真实稳定边界 = 一条 `/api` wire 协议（约 52 个一元方法，无版本段、无认证层）+ 一套磁盘格式（`sessions/**/*.jsonl.zstd`，append-only，有正式 README）+ 一个组合格式（profile/bundle）。稳定性排序：**磁盘只读 ≥ `/api` 只读子集 > `/api` 写操作 > 插件注入**。
3. **目标架构**：保持 vanilla ES modules 零构建（换框架是最大风险源且与存量资产冲突），重构收益来自数据层收拢 + 组件收编 + 隔离层，不来自 UI 框架。信息墙视图写成宿主无关 render 函数，为将来进 DSH GUI Slot 留 React 适配位。
4. **隔离层**（核心）：CCC 后端侧新建 `server/web/dsh_compat/` 为**唯一**允许了解 DSH 的模块——能力探测器 + 三通道传输（磁盘只读/`/api` 读/`/api` 写白名单）+ 双源互备 + 四级降级状态机；前端只消费 CCC 自有「视图协议」与能力位，永远不知道 DSH 细节。
5. **迁移路径**：五阶段绞杀式迁移（P0 清残留 → P1 数据层收拢 → P2 组件+实时通道+降级接线 → P3 信息架构重组 → P4 清理退役），每阶段独立可部署可回滚，合计 14 张功能卡；047-P1 已实现分支直接合入不重做。
6. **最大风险**：不是技术选型，是「高频变更区上动刀」（legacy-chat 近 30 天 176 次提交）与「DSH rc 期接口漂移」的叠加。对策：短周期特性分支逐期合入（047 模式）+ 契约测试门禁把「文档说了算」变成机器校验。

---

## 1. 现状盘点：legacy-chat 实际结构

### 1.1 代码量清单（wc -l 实测，2026-08-26）

总量：33 文件 **15858 行**（复现：`find server/web/legacy-chat -type f \( -name '*.js' -o -name '*.html' -o -name '*.css' \) -exec wc -l {} + | tail -1`）。

| 分组 | 行数 | 说明 |
|---|---|---|
| 七页面 js（js/pages/） | 4510 | wall/board/plans/roadmap/console/ops/dsh |
| 组件层 js（js/components/ + ui.js 等） | 691 | taskCard 族/toast/settings |
| 壳层基础设施 js（app/router/api/state/theme 等） | 754 | 含 index.html 46 行 |
| CSS（css/ 8 文件） | 9521 | **其中约 4500-4890 行为对话残留/多代死样式** |
| 其余散件（markdown.js/shell-ui.js/roadmapTimeline.js 等） | ≈383 | 见 1.5 可扔清单 |

### 1.2 七页面画像与后端接口依赖矩阵

（每页：职责 / 行数 / 消费接口 / 刷新方式）

#### 壳层结构（index.html 实测 46 行）

`hub-nav` 七链接（信息墙首项）+ ⚙设置按钮；`#hub-views` 下七个 `view-*` 空容器；**无任何对话期 DOM 残留**（侧栏/composer/titlebar/login-view 已随 045 P1.5 拆除）；脚本仅 theme-init.js（阻塞式防闪主题）、shell-ui.js、app.js 三个。路由为 hash router，默认 `#/wall`（router.js:7-9）。壳本身很薄——债务在页面层与 CSS 层。

| 页面 | 职责 | 行数 | 消费的后端接口（方法+路径，括号内为调用点行号） | 刷新方式 |
|---|---|---|---|---|
| **wallPage.js** 信息墙 | SSE 实时展示 DSH 会话格子流 + 格内回写 | 736 | `GET /wall/api/stream`(SSE, :483)；`POST /session` 换 token(:524)；`POST /wall/api/dsh/prompt`(:533) | 纯 SSE 推送；断线 3s 重连 setTimeout(:497)；标题闪烁定时器 1.5s(:448)；**唯一无数据轮询的页** |
| **boardPage.js** 看板 | 五态看板列 + 卡详情 + 人审动作 + 运行日志流 | 818 | `GET /cards`(:553)、`/tasks/running`(:554)、`/board/ready_for_merge`(:555)、`/board/summaries`(:441,:484)、`/projects`(:485)、`/tasks/{id}`(:574)；`POST /tasks/{id}/transition`(:669,:701)、`/false-positive`(:720)、`/audit`(:745)；SSE `/tasks/stream`(:320) | 10s 轮询兜底(:781,:796，注释自述「SSE 已覆盖实时」) + SSE 日志流 + 手动刷新 |
| **consolePage.js** 控制台 | 系统健康 + 配置中心（节点/端口/KB/PG/服务开关/门户） | 547 | pollSystem :470-483 共 12 个 GET：`/ops/summary`、`/ops/ports`、`/ops/relay-stats`、`/ops/hp-health`、`/ops/kb-health`、`/board/states`、`/board/ready_for_merge`、`/config`、`/ops/concurrency`、`/ops/pg-health`、`/ops/services`、`/ops/portals`；pollRunning :509-512；`POST /ops/service/start\|stop\|restart`(:427) | 双频轮询 15s(:532)+8s(:533)；手动刷新 |
| **dshPage.js** 巡检 | DSH 巡检报告结论优先展示 + 留档采纳 | 317 | `GET /ops/dsh-findings`(:267)；报告原文直 fetch `{latest.path}`(:284)；`POST /loop/adopt`(:250) | 30s 轮询(:310) + 手动刷新 |
| **opsPage.js** 运维 | 项目健康 + 人审闸门四池 + diff 审查 + 失败聚合 | 545 | `_pollInner` :479-486：`/board/roadmap`、`/loop/findings`、`/board/ready_for_merge`、`/cards?page_size=500`、`/plans/list?status=待排期`、`/ops/failures`；`/roadmap/{project}` N+1 并行(:496)；`POST /loop/adopt`(:385) | 30s 轮询(:533) + 重入守卫(:464) |
| **plansPage.js** 计划 | 方案六态流水线看板 + 详情/转卡/拍板/编辑 | 875 | `GET /projects`(:102,:127)、`/cards?page_size=500`(:113,:128)、`/plans/list`(:129)、`/plans/card-states`(:130)、`/plans/detail?path=`(:452,:569,:624)；`POST /plans/update`(:433,:575,:611)、`/plans/accept`(:551)、`/plans/convert`(:703)。注释里的 `POST /plans/create`(:11) 已无调用方（新建表单按老板指令移除，:721 自证） | 30s 轮询(:858)，壳静态+列签名增量刷新 |
| **roadmapPage.js** 线路图 | 项目总览 + 里程碑 rail/子任务 master-detail + 草案池人审① | 672 | `GET /board/roadmap`(:606)、`/roadmap/{project}`(:414)；`POST /roadmap/{p}/draft/promote-to-plan`(:203,:441)、`PUT /roadmap/{p}/draft/{index}`(:459)、`DELETE` 同径(:475)、`POST /subproject/activate`(:385)、`POST /milestone`(:560)、`PUT /milestone/{title}`(:557) | 仅一级页 30s 轮询(:656)；二级页手动刷新 |

**矩阵读法**：(a) 看板/控制台/运维三页对 `/board/ready_for_merge` 重复消费三次；(b) `/cards` 被 plans/ops 以不同 page_size 各自拉全量；(c) 只有墙页是纯推送架构，其余六页全是轮询——这正是 047 要收敛的形态。

#### 后端接口面速览（server.py 4740 行，66 条路由 + 静态托管）

- **鉴权模型**：`CCC_WEB_AUTH_REQUIRED` 默认 0（免登录），写请求默认强制 Bearer（`CCC_WEB_WRITE_AUTH` 默认 1，server.py:1994-2002）；两条 SSE 在鉴权门前分发——因为 EventSource 无法带 Authorization 头（server.py:3988-3989 注释）。
- **孤儿路由**（仓内无任何消费者）：`GET /board/arch`、`GET /board/realtime`、`/board/recent`、`/board/by_project`（仅冒烟脚本消费）、`GET /roadmap/projects`、`DELETE /roadmap/{p}/milestone/{title}`、`POST /roadmap/{p}/draft`、`POST /plans/create`、`GET /wall/api/active`（SPA 首帧走 SSE 不调它）、`POST /wall/api/dsh/archive`（UI 已停用，端点保留）。
- **对话遗留路由**（SPA 零调用、服务端暂保留，045:93-97 声明待确认外部消费）：`GET/POST /conversation`（含 SSE 流形态 ：2103 起）、`GET /projects/{p}/threads` 三件套、`GET /dsh/workspaces`、`GET /dsh/sessions/{id}`、独立桥服务 `POST /chat :7799`（chat_bridge.py:409-418）。

### 1.3 组件复用对照表

#### 组件 × 使用者矩阵（import 实测）

| 模块 | 使用者（import 位置） | 备注 |
|---|---|---|
| utils.js escapeHtml | ui.js:10、taskCard.js:5、markdown.js:1（死文件） | 其余 7 个导出全仓零调用 |
| ui.js esc/STATE_TONES/setHtml | taskCard.js:1、boardPage.js:17、dshPage.js:14、plansPage.js:17、opsPage.js:16、consolePage.js:19、roadmapPage 经 roadmapTimeline.js:13 二次转发 | — |
| theme.js | app.js:8、settings.js:13、wallPage.js:13 | theme-init.js 独立 IIFE（index.html:18） |
| components/toast.js | app.js:98 动态 import；各页经 window.showToast?. | — |
| components/taskCard 族 | 仅 boardPage.js:14-16 一家消费 | 「组件」实为单页私有件 |
| js/markdown.js | **零 importer** | 死文件 |
| js/state.js / ports.js | **零 importer** | 死文件 |
| js/shell-ui.js | index.html:43 script 标签；window.copyCode 唯一触发源=markdown.js:161 生成的 HTML ⇒ 连坐死 | — |

**结构性发现**：components/ 目录五个文件中三个只服务于看板一页——所谓组件层实际不存在跨页复用，这是各页重复造轮子的直接原因。

#### 重复实现对照（12 组，均有双处行号证据）

| # | 语义 | 对照证据 | 差异一句话 |
|---|---|---|---|
| 1 | HTML 转义 esc ×3 | utils.js:1-5 ↔ wallPage.js:61-64 ↔ taskCardList.js:257-261 | taskCardList 版不转义引号（在死代码块内，复活即属性注入风险） |
| 2 | Markdown 渲染器 ×3 | markdown.js:126-333（死）↔ plansPage.js:725-825 ↔ wallPage.js:67-140 | plans 版表格+checkbox 无高亮；wall 迷你版无 checkbox |
| 3 | agoText 时间文案 ×2 | opsPage.js:22-28 ↔ dshPage.js:20-26 | 逐字相同；utils.js relativeTime 重叠但无人用 |
| 4 | 时长格式化 ×2 | taskCard.js:38-49 ↔ wallPage.js:142-147 | 同语义不同输出细节（60s 边界） |
| 5 | debounce ×3 | utils.js:83-89 ↔ plansPage.js:83-89（逐字相同副本）↔ boardPage.js:635-641 裸 setTimeout 第三份 | — |
| 6 | 幂等 innerHTML ×3 | ui.js:17-19 ↔ consolePage.js:23-29 ↔ dshPage.js:130-135 | 比较机制两派（innerHTML vs __lastHtml 属性） |
| 7 | 剪贴板降级 ×3 派 | shell-ui.js:6-34 ↔ boardPage.js:50-75 ↔ dshPage.js:230-240 / opsPage.js:365-375 | 有 execCommand 降级派 vs 直用 clipboard 无降级派 |
| 8 | 状态色板 ×3 | ui.js:22-28 STATE_TONES ↔ taskCard.js:7-21,23-33 ↔ plansPage.js:22-29 | 五态色/卡色映射/计划六态各自为政 |
| 9 | sessionStorage 留档 ×2 | opsPage.js:312-318 ↔ dshPage.js:70-76 | 逻辑相同仅键名不同 |
| 10 | 弹层/模态 ×4 | settings.js:20-26 ↔ boardPage.js:120-139 ↔ plansPage.js:255,650-681 ↔ roadmapPage.js:166-171,498-504 | 无共享模态原语，四套各写各的 |
| 11 | 加载/空态类名 ×6 | board-loading(boardPage:115)/console-empty(consolePage:52)/ops-empty(opsPage:43)/dsh-empty(dshPage:51)/pcol-empty(plansPage:308)/board-empty 复用(roadmapPage:38) | ui-kit.css:158-170 统一的 .k-empty/.k-loading **零引用** |
| 12 | 分页双机制 | taskCardList.js:98-204（分页器零调用⇒totalPages 恒 1 永不出现）↔ boardPage.js:270-288 load-more 自实现 | 组件侧分页 API 是死代码 |

### 1.4 对话残留考古

**JS 层（已拆净 + 死码清单见 1.5）**：045 P1.5 删除了 24 个对话前端文件，app.js 从 613 行瘦到 113 行；现存对话痕迹全部是「零引用死物」而非活逻辑——state.js（streaming/dualPane/sessions 等纯对话状态）、ports.js（stub）、markdown.js（对话渲染器）、utils.js 的 scrollToBottom/desktopThreadId 等 7 个导出、api.js 缓存前缀里的 `/claude/projects`、`/claude/sessions`（api.js:28，前端对 /claude/* 零调用方）。

**仍活的对话基因（不可当死码删）**：

1. **格内对话全链**：cell-input DOM（wallPage.js:189-199）→ sendPrompt（:507-559）：无 token 时现场 `POST /session` 换取并缓存 localStorage(:520-532)，`POST /wall/api/dsh/prompt`(:533)，401 清 token(:539)；服务端对应写门禁拦截（server.py:4207）。这是「操作直达 DSH」的现有雏形，重构方向是下沉到隔离层客户端而非删除；
2. fmtTaskCopy「复制任务块可粘贴到对话」（taskCard.js:185-203 + boardPage.js:219-227,386-395）——链路完全可用，仅语义是对话残留，改文案/下架属产品决策；
3. matchFilter 旧筛选值兼容（wallPage.js:320 default 分支注释「兼容旧 localStorage 残留」）——有意的老用户迁移兼容，删除会使老用户筛选失效；
4. api.js `_fetchWithAuth` 名不符实（:105,:122,:172,:186——LAN 免登录后并不附加凭据），但与墙写 token 错误路径共享代码，低收益高误伤，P1 数据层收拢时顺带正名。

**服务端对话遗留**（前端零调用，本课题范围外但本方案 P4 必须处理）：§1.2 所列 `/conversation` 族 + threads 族 + `/dsh/workspaces|sessions` + chat_bridge :7799。下线前置条件：确认 ai-loop-router/Desktop 无外部消费（045:94 声明）。

### 1.5 「能直接扔」清单

三级分类（子代理逐项零引用实证，区间边界核到行号）：

**A. 整文件零引用（≈477 行，高置信）**

| 对象 | 行数 | 证据 |
|---|---|---|
| js/state.js | 49 | 静态 import 全查为 0；streaming/dualPane/sessions 等字段仓内无消费 |
| js/ports.js | 44 | 零 importer，全 stub 恒值；仅 settings.js:5 注释提及 |
| js/markdown.js | 333 | 静态+动态 import 全查为 0（renderMarkdown 无人调） |
| js/shell-ui.js + index.html:43 script 标签 | 37 | window.copyCode 唯一触发源=死文件 markdown.js:161 生成的 HTML |
| js/roadmapTimeline.js | 14 | 仅剩 re-export shim，roadmapPage.js:13 改从 ui.js 导入即可 |

**B. 文件内死块（≈236 行，高置信）**

| 对象 | 证据 | 行数 |
|---|---|---|
| utils.js 除 escapeHtml 外全部导出（ts/scrollToBottom/generateId/desktopThreadId/resolveProjectPath/relativeTime/debounce） | 逐个 grep 仅定义处命中；settings.js:7 注释自证「全仓无调用方」 | ~84 |
| api.js loadProjects/getBoardTask/searchCards | api.js:202-236 零调用方（plans/board 各自本地实现） | ~35 |
| taskCardList.js:230-281 __PENDING_DETAIL_ID__ 兜底块 | 只有读/清无 setter（setter 属已拆的对话任务对话框）；块内藏不转义引号的 esc(:257-261) | ~52 |
| taskCardList.js 死 API（showLoading/showError/setupPagination/renderPagination） | 外部零调用，totalPages 恒 1 分页 UI 永不出现 | ~65 |
| app.js:9 未用的 navigate 导入 + api.js:28 `/claude/*` 缓存前缀 | grep 实证 | ~3 |

**C. CSS 死区（≈4500-4890 行，中置信——区间实证、总量估算）**

| 文件 | 死区概要 | 预估减少 |
|---|---|---|
| components.css | 对话期区块：Titlebar/relay-stats(1-193)、#layout(195-204)、Sidebar(205-676)、Messages(677-741)、Bubble(742-883)、ToolCall/thinking(884-1197)、Composer/qa-dock(1198-1581)、ScrollFAB/chat-panel(1582-1626)、Empty-state(1816-1899)、MessageEdit(1900-1946)、对话 Mobile(1947-2057，内嵌 ~10 行 settings 存活需摘出)、ClaudeUI v2.1(2058-2438)、runtime-status/git-diff/engine-control(2939-3062)、dispatch-card(3063-3225)、conn-banner 等(3226-3306)。判定依据：#titlebar/#sidebar/#messages/.bubble/#composer 等 js/html grep 零命中。**必留**：Settings sheet(1627-1748)、Toast(1749-1815)、T40 五态徽章段(2439-2938，含 badge-audit-\${cls} 动态类) | ≈2600/4596 |
| shell.css | epic 族(348-638)、旧一代 console(831-980)、旧一代 ops(981-1342)、SVG 时间线+旧线路图(1260-1531)、dialogue-mode(1674-1772)、login-view(1870-1964)、旧 Roadmap 五视图(1965-2184)、二代 SVG 残段与重复 rm-*/ops 族（多处区间）。勿误切示例：.rm2-miles(3431-3438 死)紧邻 .rm2-mile-card(3440 起活)；.dsh-review-item(shell.css:3720) 是活类（插值致初筛误报） | ≈2100/3854 |
| ui-kit.css | 仅 k-topbar 三件套被六页用；k-page/k-card 四件套/k-chip/k-badge/k-dot/k-btn/k-empty/k-loading **全部零引用**（046-M1 落了地基但 M2 收编未做） | ≈160/182 |
| base.css | typing-dot/skeleton/streaming-cursor 对话期动画 | ≈30 |

**合计 ≈5200-5600 行（占全壳 33-35%）**。

⚠️ 删除纪律（前科教训）：046-M4 曾做自动清死样式后**整体回滚**（git 1373c4fa4，「语料判定假阴性误杀存活规则」）。动态拼接类名（`state-${tone}`、`badge-audit-${cls}`、`toast-${type}`）静态扫描判不死，必须列入人工白名单保留。清理只能人工白名单制，禁批量自动删除。

仍活的功能耦合点（不可当死码删）：

- **格内对话**：wallPage 格内输入框 cell-input/ci-send → `POST /wall/api/dsh/prompt` + `POST /session` 换 Bearer token（wallPage.js:507-559）——这是活功能，是「操作直达 DSH」的现有雏形；
- fmtTaskCopy「复制任务块可粘贴到对话」按钮仍活，是否保留属产品决策项。

### 1.6 与对话残留耦合过深、需如实说明的问题

1. **CSS 层耦合远深于 JS 层**：JS 对话栈 045 P1.5 已拆净（app.js 现 113 行），但 CSS 里对话期样式约 4700+ 行仍在，且 shell.css 内新旧两代样式叠压（旧代约 2100 行），没有测试网兜住视觉回归——这是全项目最大的隐性债务，也是 047 P4「清理重做（人工白名单制）」被排到最后的原因。
2. **wallPage 是唯一「既承载新职能又带对话基因」的页面**：格内对话、Bearer token 换取逻辑直接写在页面组件里（wallPage.js:507-559），而非数据层模块——重构时必须先抽到隔离层客户端，否则墙页无法瘦身。
3. 服务端 `/conversation`、`/claude/*`、brain bridge 心跳等**后端**对话遗留暂保留（045 已声明：需先确认 ai-loop-router/Desktop 无外部消费才能下线）——前端重构不阻塞于此，但 P5 退役阶段必须处理。

---

## 2. DSH 能力面盘点：对外接口形态与稳定性评估

> 方法：只读源码核查 DSH 安装检出 `/Users/fan/.npm-global/lib/node_modules/@deepseek-ai/dsh/`（下缩 `…/dsh/`，子包在 `…/dsh/node_modules/@deepseek-ai/<pkg>/`），并以本会话运行时的 Inspect Provider 活体目录交叉验证。所有行号为实读所得。

### 2.1 包身份与迭代形态

| 事实 | 证据 |
|---|---|
| 包名 `@deepseek-ai/dsh`，版本 **0.1.1-rc.2** | `…/dsh/package.json:2,4`；本机 `node -e require(...).version` 实测同值 |
| **单列车锁版**：CLI 只是启动器，实现拆为约 60 个 `@deepseek-ai/dsh-*` 子包，dependencies 全部 `^0.1.1-rc.2` 同进退 | 各子包 package.json 抽查（dsh-base/dsh-web-app/dsh-client-connection/dsh-host-webserver/dsh-host-apiproxy/dsh-session-persistence-jsonl/dsh-tools 均 rc.2） |
| 框架底座 `@deepseek-ai/cordis` 为 **^4.0.1 稳定 semver**——全套唯一有独立稳定版本线的锚 | 主包 dependencies；cordis 包自带 README/Quick Start |
| **无 CHANGELOG**；主包 lib/ 无 deprecated/experimental 标记；全 dsh 子包唯一 `@deprecated` 是 CUID v1 说明 | `find -iname 'CHANGELOG*'`；`<dsh-client-connection>/lib/client.js:1105` 等四处 |

**解读**：`0.x + -rc.N` 双重信号 = 正式发布前候选期，按 semver 惯例 0.x 本身不作兼容承诺。无 CHANGELOG + 无弃用管理意味着破坏性变更频率无法从制品量化、也不会提前公告——**「不锁死版本」只能靠 CCC 自己的隔离层保证，不能指望 DSH 的兼容承诺**。

### 2.2 接口形态全集（四类）

#### A. Web 服务面 :3080 —— HTTP API / RPC / SSE / WS

组合链：profile `web` = `dsh-base` bundle + `dsh-web-app` bundle + 用户 `~/.dsh/profiles/web/cordis.patch.yml`（bundle 清单见 `<dsh-web-app>/cordis.patch.yml:105-183`）。

| 类别 | 形态 | 关键事实 | 证据 |
|---|---|---|---|
| RPC | `POST /api/<method>`，信封 `{type:"client-request", rpcId, method, payload}` → `{type:"server-response", rpcId, result:{ok,…}}` | 一元路由表 UNARY_ROUTES 约 52 个方法：session.*(12)、subagent.*(4)、workspace.*(7)、agentPreset.*(6)、settings.*(5)、credentials.*(3)、host.*(5)、llm.*(3)、goal.*(6)、skill.list | `<dsh-host-apiproxy>/lib/index.js:4576 起`；信封校验 `<dsh-client-connection>/lib/index.js:275-301` |
| 会话导出 | `GET/HEAD /api/session.export?sessionId=…` | 会话日志下载 | `<dsh-host-apiproxy>/lib/index.js:4903-4913` |
| 下行事件流 | WS `/api/events.mux`、`/api/events.host`（仅下行，客户端消息一律 close(1008)）；同端点 GET 即 SSE 形态 | 帧：session/event、approval/requested、question/requested、host/session-added 等（开放判别联合，注定增变体） | `<dsh-client-connection>/lib/index.js:369-373,566-585`；`<dsh-host-apiproxy>/lib/index.js:4895-4902,5012 起` |
| 静态 SPA + 注入 | fallback 座位页；每个 index 响应经注入渲染拼入 `window.__DSH_BOOT__` 启动图 | 插件经 `webserver/index-inject` 事件推行注入行 | `<dsh-host-frontend-static>/lib/index.js:46-91`；`<dsh-host-webserver>/lib/index.js:59-77,286-310`；`<dsh-client-modules>/lib/index.js:209-250` |
| 鉴权 | **没有认证层**，只有信任栅栏：Host 头须 loopback/trustedHosts、拒 `sec-fetch-site: cross-site`、Origin 同源 | 源码自述 *"this fence is not an auth layer"*、*"until a real authentication layer exists"*；特权方法（settings/credentials 写等）钉死 loopback | `<dsh-client-connection>/lib/index.js:106-198,504-520` |

**对 CCC 的含义**：(1) 浏览器跨站直连 ：3080 会被栅栏拒绝，且即便放行也无认证——**CCC 前端永远不应直连 ：3080，一切访问经 CCC 后端代理**；(2) RPC 面无 URL 版本段、方法表开放式增长——依赖哪个方法必须在适配层登记并可探测。

#### B. Cordis 插件机制

- 框架核心 API（ctx.on/effect/provide/plugin、Service、inject）属 cordis 4.x 文档化公开面（`<cordis>/README.md`；`cordis/lib/index.js:371,799,1168,1618`）。
- 能力 API：model Tool 注册 `ctx.tools.register`；浏览器 Slot（SlotCore/SlotRegistry，root 槽明确禁注册、应去 `shell.overlay`）；主题 token；插件私有 RPC 通道 `ctx.connection.rpc.handle`（公共 `/api` 由网关独占一个拦截器席位）。
- 动态插件沙箱把可用 ctx 面收敛并明示 framework internals 被扣留（"Available: ctx.tools.register / ctx.on / ctx.provide…"写进了护栏文案本身，`<dsh-cordis-host-runner>/lib/index.js:593-659`）。
- 本会话活体验证：Inspect Provider 目录可枚举 Host Services（sessionQuery/sessionPersistence/webServer/apiProxy 等 40+ 键）与 Events（session/event、agent/status 等 47 种）——**这是 agent 侧的检查面，不是给外部前端的业务 API**，但其存在证明「运行时能力发现」在框架层是一等公民。

**对 CCC 的含义**：插件注入是「深度」最高、稳定性最低的通道（整族骑在 0.1.1-rc 上）。终局形态（045 规划的 P2+：DSH Tool 化、事件订阅）方向正确，但 rc 期内 CCC 的生存不应依赖它。

#### C. 会话数据磁盘布局（$DSH_HOME 默认 `~/.dsh`）

```
~/.dsh/
├── sessions/<归一化cwd>/<sessionId>/session.jsonl.zstd   # 追加式会话日志（首帧 SessionHeader 含 version/id/cwd/createdAt…）
├── profiles/<name>/{package.json, cordis.yml, cordis.patch.yml, node_modules}
├── .agent-presets/<presetId>/…
├── skills/<skillName>/
├── storages/{workspace.json, session_projcache.json}      # 工作区登记 v2 / 投影缓存 v3
├── settings.yaml                                          # 用户设置
└── .credentials.yaml                                      # 凭据（0600）
```

- 格式有正式 README（on-disk layout、崩溃恢复、**无迁移策略**明示）：`<dsh-session-persistence-jsonl>/README.md`——三类表面中文档投入最重、最像长期承诺的一个。append-only 设计天然向后兼容读取。
- 默认部署无持久 SQLite（全文检索索引以 `path: ':memory:'` opt-in 挂载，`<dsh-base>/cordis.patch.yml:117-125`）。
- 本机实证：`~/.dsh/sessions/--Users-fan-program-CCC--/0047a5b7-…/session.jsonl.zstd`（411KB）；工作区按 cwd 归一化目录名分桶（50 个桶）。

**对 CCC 的含义**：磁盘只读是**最稳**的数据通道（格式文档化 + append-only + 自带 version 字段可校验），代价是自己处理 zstd/chunk 行/seq 连续性——wall.py 已经在做这件事。

#### D. CLI 入口

bin 仅三种模式：`profile`（启动）、`plugin`（转发 pnpm）、`dump-config`（打印组合树）。**不存在读写既有会话的任何 CLI 子命令**（`…/dsh/lib/bin.js` 尾部 switch 实证）。

### 2.3 CCC 当前实际消费面（截至本报告）

| 消费点 | 通道 | 内容 | 位置 |
|---|---|---|---|
| 墙 reader | **磁盘只读** | 扫 `~/.dsh/sessions/**`，zstd 解压，事件折叠为会话状态机（classify_source/_apply_events/_recompute_status/snapshot） | `server/web/wall.py:110-477` |
| 格内对话 | **`/api` 写** | `dsh_rpc("session.prompt", …)` | `wall.py:569-577`；转发器 `wall.py:542-564`（POST `127.0.0.1:3080/api/<method>`，rpcId 信封） |
| 归档联动 | **`/api` 写** | `workspace.archiveSession` | `wall.py:579-582` |
| 架构红线 | —— | 零碰 DSH 核心、纯本地文件只读解析 + 官方 RPC 回写、禁破解 WS（审批帧已实证不可行：不落盘、不在 Web 暴露） | HANDOVER §4.3，固化于 045 方案 §二 |

### 2.4 稳定性分级表（隔离层的依据）

| 级别 | 表面 | 依据 |
|---|---|---|
| **S 稳** | cordis 框架核心 API（4.x 独立版本线 + 公开 README）；会话磁盘格式与 persistence seam（专用 README + append-only + version 字段）；launcher 语法（--profile/--patch/web/plugin，README 明文承诺旗标边界）；HTTP 信任栅栏语义（威胁模型长篇论证 + fail-loud 输入规范化） | `<cordis>/README.md`；`<dsh-session-persistence-jsonl>/README.md`；`…/dsh/README.md`；`<dsh-client-connection>/lib/index.js:106-198` |
| **A 半稳** | `/api` RPC 方法面（52 个一元方法 + 信封 schema 有 zod 校验与个别 wire contract 标注，但路由表开放增长、无版本段）；插件能力 API（tools/slots/theme/connection.rpc，逐包 README 是架构文档非兼容承诺）；profile/bundle 组合格式 | `<dsh-host-apiproxy>/lib/index.js:4576 起,4793-4795`；`<dsh-cordis-host-runner>/lib/index.js:593-659` |
| **B 易变** | cordis `internal/*` 事件族与 reflect/symbols；`__DSH_BOOT__` wire 图（仅代码内定义）；WS/SSE MuxFrame/HostFrame 判别联合（开放联合注定增变体）；鉴权模型（源码两处注释暗示 1.0 前会变） | `<dsh-api-gateway>/lib/index.js:72-85`；`<dsh-client-modules>/lib/client.js:65-104`；`<dsh-host-apiproxy>/lib/index.js:5012 起,493-498` |

**集成优先级结论**：磁盘只读 ≥ `/api` 只读子集 > `/api` 写操作 > 插件注入。CCC 隔离层按此顺序组织依赖，并把每一项依赖做成可探测、可降级的能力位（见第 4 章）。

明示不确定项：npm dist-tag 无法本地核验；破坏性变更频率无 CHANGELOG 不可量化；鉴权演进方向无代码线索。三项均按「高不确定性」处理，不做侥幸假设。

---

## 3. 目标架构设计

### 3.1 总体分层

```
┌─ 浏览器 ─────────────────────────────────────────────────┐
│ CCC 前端壳（vanilla ES modules · 零构建 · hash 路由）        │
│  视图层：角色视图（墙/板/规划/运维台）× k-* 组件库            │
│  视图协议客户端：js/data/* 五域模块 + degrade.js 能力位消费   │
└────┬─────────────────────────────────────────────────┘
     │ HTTP JSON + SSE —— CCC 自有视图协议 ccc-view-v1
     │ （含能力位 flags；协议中不出现任何 DSH 概念）
┌────▼─────────────────────────────────────────────────┐
│ CCC 后端 server.py（:7788 stdlib；鉴权门 + 写 Bearer 门） │
│  路由层：/wall/api/* /tasks/* /plans/* /roadmap/* …      │
│  ┌─────────────────────────────────────────────────┐  │
│  │ dsh_compat/ —— 全仓唯一允许了解 DSH 的模块          │  │
│  │   probe.py 能力探测器 · degrade.py 四级降级状态机    │  │
│  │   T1 磁盘只读 reader（sessions/*.jsonl.zstd）       │  │
│  │   T2 /api 只读子集客户端（session.list/history…）   │  │
│  │   T3 /api 写白名单客户端（prompt/archive 两方法）    │  │
│  └─────────────────────────────────────────────────┘  │
│  非 DSH 数据面：dispatch 卡文件 / plans / roadmap / ops  │
└────┬───────────────────────────────────────────────┘
     │ 文件系统只读 + POST 127.0.0.1:3080/api/<method>（白名单）
┌────▼───────────────────────────────────────────────┐
│ DSH 0.1.1-rc.x（可整体升级更换；破坏性变更被隔离层吸收）  │
└────────────────────────────────────────────────────┘
```

**依赖方向铁律**：前端 → CCC 视图协议 → dsh_compat → DSH，单向；反向禁止，跨层禁止。配套机器门禁见 §4.7。

### 3.2 技术选型对比与推荐

| 方案 | 存量资产复用 | 构建链 | 组件约束力 | 与 DSH GUI 生态亲和 | 判定 |
|---|---|---|---|---|---|
| **vanilla ES modules（现状强化）** | 全量保留 | 零构建保持（git 提交号版本戳 scripts/bump-frontend-stamp.sh 现制不变） | 弱——靠纪律补：组件=纯函数模块 + 统一数据层 + 统一刷新器 | 需薄适配层 | **推荐** |
| Preact + htm（vendor 单文件 ESM） | 高 | 可零构建（vendor/ 目录已有先例位） | 强 | 中 | 备选，触发条件见下 |
| Lit（Web Components） | 中 | 可零构建但加运行时心智 | 中 | 中 | 不取：双范式并存 |
| Svelte / Vue / React | 低——15.8k 行交互重写 | 必引入 node 构建链 + launchd 部署链改造 | 强 | React 高（DSH client 插件官方模式即 React.createElement 纯 JS） | 不取 |

推荐理由（全部有实证支撑）：

1. 重构痛点是「各页自造轮子」（§1.3 十二组重复实现、六页八处数据轮询），不是框架缺失——框架救不了没组件纪律的代码；
2. 046-M1 已落地 ui-kit.css 原语层、047 已定稿结构复刻期——换框架等于推翻两个已验收方案的前置投入；
3. 零构建是现行部署特性（launchd + git pull + 版本戳脚本），引入 node 构建改变部署面，违反「每步可部署」迁移纪律；
4. 老板要的深度绑定绑定点在接口层（数据同源、操作直达），不在 UI 框架；
5. 为将来留门：信息墙格内卡片等候选「进 DSH GUI Slot」的视图写成宿主无关 `render(container, data, ctx)` 纯函数——DSH client 插件无 JSX、官方模式即 `React.createElement`，届时以百行级适配器挂入即可。

**Preact 触发条件**（写明何时重新评估，避免教条）：P2 完成后若同构 UI 出现第 4 次手写复制，或手写刷新调度复杂度失控，再引 Preact+htm vendor 单文件。「组件=纯函数」约束已把届时迁移成本压到最低。

### 3.3 组件库设计

基座现状：variables.css 令牌 + ui-kit.css 182 行原语（k-page/k-topbar 三件套/k-card 四件套/k-chip/k-badge/k-dot/k-btn/k-empty/k-loading）。⚠️ 实测除 k-topbar 三件套外**全部零引用**——046 只落了地基，收编（047-P2/P3）还没发生。原则沿用 046：「ui-kit 只加不改」+ 注释契约块。

本期新增统一基础组件（全部「数据进→DOM 出」纯函数，组件文件禁止自行发请求）：

| 组件 | 职责 | 收编对象（§1.3 证据） |
|---|---|---|
| k-status-badge | 任务五态/会话态/计划六态统一徽标，单一映射表注入 | 三套色板（对照#8） |
| k-timeline | 时间线（卡流转史/会话事件史共用） | SVG 时间线死样式对应已退役渲染器的教训上重建轻量版 |
| k-logstream | 日志/事件流容器：追加行+滚动锚定+心跳指示+断线态 | boardPage 流渲染与 wallPage 会话流各自手写逻辑 |
| k-session-card / k-task-card | 两类一等公民卡：会话卡=墙原子、任务卡=板原子，内部互不嵌套（048 显示面红线） | taskCard 族三件 + wallPage 格内自绘 |
| k-degraded | 降级态容器：能力位 flag → 陈旧时间戳/重试按钮/降级说明 | 新能力（第 4 章配套），也是全站唯一允许出现的「坏数据」呈现方式 |
| k-refresh | 手动刷新按钮 + 最后更新时间戳（去轮询化标准件） | 五页各自为政的刷新按钮 |
| modal 原语 | 共享弹层 | 四套各写各的模态（对照#10） |
| fmt.js | 唯一的时间/字节/时长格式化模块 | agoText×2/fmtElapsed×2 等（对照#3#4） |

组件纪律三条：(1) 组件不发请求；(2) 组件不读全局单例（theme 除外）；(3) 每个 k-* 在 ui-kit.css 有注释契约块（046 先例）。

### 3.4 页面按角色视图重组

048 显示面独立红线是宪法，不动：墙=会话沟通面（原子=session）、板=任务状态机+全链追溯面（原子=卡）。重组对象是**导航信息架构**：

```
一级导航（hub-nav 分组，hash 二段式路由）
├─ 执行面  #/wall              老板视角的墙：多会话同屏实时纠偏、格内对话直达 DSH
├─ 任务面  #/board             开发视角的板：全量任务卡 + origin 徽章(048-P2 数据)
│                              + 「轨迹」按钮直达墙内对应会话卡(048-P3 索引)
├─ 规划面  #/plans  #/roadmap  方案池 + 线路图（三层金字塔中上层；两页保留，导航归组）
└─ 运维面  #/ops-hub           运维视角仪表盘：三 tab 聚合壳
      ├─ 系统 tab（ports/services/进程 ← consolePage）
      ├─ 引擎 tab（失败聚合/审查队列 ← opsPage）
      └─ 巡检 tab（DSH 巡检报告 ← dshPage）
```

要点：(a) 物理页面不合并——console/ops/dsh 保持独立模块，聚合壳只做 tab 编排与共用刷新节流，把物理合并的高回归风险换成低风险编排；(b) 默认路由仍 wall（045 定局：打开即墙）；(c) 各角色首屏定义——墙=活跃会话网格+停滞告警行；板=五态计数条+在途卡列+待合入区；运维台=健康四格（web/engine/board-scheduler/**DSH 连通性**）+ 异常流水；(d) 移动端按组折叠（046 断点基线）。

### 3.5 与 engine/看板 SSE 实时通道的关系（047 成果保全）

两条既有 SSE 是全站仅有的服务端推送通道，**保留且是唯一扩线方向**：

| 通道 | 服务端机制 | 前端消费 |
|---|---|---|
| `/tasks/stream`（看板任务流） | 连接即推 snapshot（每卡最近日志行）；此后 5s 轮询日志增量推 log 事件；≥15s 心跳（server.py:3838-3915） | boardPage.js:309-358；ids 签名未变复用连接；onerror 靠浏览器原生自动重连 |
| `/wall/api/stream`（墙会话流） | 首帧立即推全量 state；Condition 挂起、快照 diff 有变才推；15s 心跳（server.py:3917-3951）。底层 0.6s mtime 快检线程扫 `~/.dsh/sessions/**`（wall.py:42,487-496） | wallPage.js:481-500；显式 onerror→close→3s 重连+离线横幅；visibilitychange 回前台恢复(:710-715) |

鉴权事实：两条流分发位于鉴权门前（server.py:3983-3995）——因为 EventSource 无法带 Authorization 头（:3988-3989 注释）。隔离层新增任何 SSE 必须沿用此前提设计。

047 衔接现状（实测修正）：P1 已在 `feat/047-unification` 分支提交 `4de1da854` 实现（六页 setInterval 拆除），**未合入 main**；其中一处方案偏差已由执行体注明——plans 更新提示改用 60s 微探针 `fetch('/plans/list?page_size=1')` 替代 tasks/stream 订阅（该流按卡 ID 定投不适合全局变更探测）。本方案处置：**合入而非重做**，偏差在合入卡里显式裁决（微探针可接受，但须挂可见性门控）。P2-P4 结构复刻与清理按原案并入本方案 P2/P4。承诺不变：不新建第三条服务端推送通道。

---

## 4. DSH 隔离层设计（核心章节）

> 硬边界回答：**绑定不锁死版本**靠四个机制——单点知识（全仓只有 dsh_compat 了解 DSH）+ 能力位（一切依赖可探测可缺失）+ 双源互备（磁盘读/RPC 读互为备份）+ 四级降级（数据不可得=局部降级态，绝不白屏）。DSH 升级的最坏情形 = dsh_compat 小改 + 墙视图进降级态，其余页面零感知。

### 4.1 设计原则

1. **单点知识**：全仓只有 `server/web/dsh_compat/` 允许出现 DSH 概念（zstd/jsonl/RPC 方法名/:3080/SessionHeader）。前端与 server.py 其余部分只见 CCC 自有协议。
2. **单向依赖**：前端→CCC 视图协议→dsh_compat→DSH；反向与跨层引用禁止，grep 门禁机器化（§4.7）。
3. **能力位而非假设**：一切 DSH 依赖表达为 capability flag 下发前端；前端按 flag 渲染，永不假设可用。
4. **双源互备**：会话读以磁盘 reader 为主源（稳定性 S 级）、`/api` 读为备源（A 级），任一失效自动切换并在 payload 标注 `read_source`。
5. **降级是局部态不是全局故障**：DSH 不可得只影响 DSH 依赖视图（墙/轨迹/巡检连通性格）；看板/计划/线路图等自有数据视图永不受牵连。

### 4.2 模块与职责

```
server/web/dsh_compat/
├── __init__.py        # 对外唯一出口：get_capabilities()/read_sessions()/send_prompt()/archive_session()
├── probe.py           # 三层探测（§4.4）；结果缓存 TTL 60s；快照持久化 data/dsh_compat/capabilities.json
├── degrade.py         # L0-L3 四级降级状态机；线程安全；半开试探自动复位
├── reader_disk.py     # T1 磁盘只读（现 wall.py reader 逻辑迁入：mtime 快检/增量解析/状态机折叠）
├── client_rpc.py      # T2/T3 /api 客户端（现 dsh_rpc 迁入）；T3 白名单={session.prompt, workspace.archiveSession}
└── CONTRACT.md        # 人读契约登记表（§4.5 表的仓内镜像；pytest 校验与代码一致）
```

现有资产迁入路径：wall.py 585 行中 reader 状态机（:110-477）与 dsh_rpc/dsh_prompt（:542-585）正是雏形，逻辑零改动搬移 + 包一层 source 标注与降级挂钩；wall.py 本身退化为薄壳转发保持 `/wall/api/*` 形状不变。

对外 API 形状（ccc-view-v1 示例）：

```json
GET /wall/api/capabilities
{ "v": 1,
  "dsh": { "present": true, "version": "0.1.1-rc.2", "level": "L0",
           "read": "ok", "read_source": "disk", "write": "ok" },
  "checkedAt": "2026-08-26T15:00:00+08:00" }
```

所有 `/wall/api/*` 响应带 `X-CCC-Degrade-Level` 头；SSE 心跳帧携带 level 变更事件；前端 degrade.js 订阅两者驱动 k-degraded 渲染。

### 4.3 接口契约：哪份文档说了算

三层真值，冲突时以编号小者为准：

1. **机器真值**：probe.py 运行产物 capabilities 快照（持久化+时间戳）——运行时行为以此为准；
2. **人读权威文档 = `dsh_compat/CONTRACT.md`**（本方案 §4.5 是其初版）。其他任何文档（含本方案、卡文件）引用 DSH 接口一律以 CONTRACT.md 为准；
3. **上游参考**（只读、不维护副本、靠探测对齐）：DSH 会话磁盘格式权威 = `<dsh-session-persistence-jsonl>/README.md`（正式 README：布局/崩溃恢复/无迁移策略）；RPC 面权威 = `<dsh-host-apiproxy>` UNARY_ROUTES 源码。

变更流程：新增/修改任一 DSH 依赖必须同时改「client_rpc 白名单 + CONTRACT.md 登记 + contract 测试期望」三元组，缺一 pytest 红。**DSH 侧没有通知义务，CCC 以探测+门禁自保**——这是 rc 期上游不给兼容承诺时的唯一可靠姿势。

### 4.4 版本探测（cheap-first 三层）

| 层 | 手段 | 时机 | 失效含义 |
|---|---|---|---|
| 静态 | 读 DSH 安装 package.json version（同机部署可行；路径经 settings/env 可配，默认探测 npm 全局/profile 目录列表——**生产 2017 与中枢 M1 双机现实，禁硬编码路径**，topology.md 实证） | 进程启动 | 读不到=present:false，墙直接 L3 冻结态起步 |
| 动态 | T3 写方法调用失败（信封 method_not_found/拒连）→ degrade.py 置 lost + 记录原始错误码 | 懒触发（首次真实调用），不做启动全量 ping | L1 写损 |
| 格式 | reader_disk 解析 SessionHeader.version，未知主版本告警 | 随每次读取 | L2/L3 |

lost 能力每 300s 半开试探一次（成功复位），避免雪崩重试；探测缓存 TTL 60s。

### 4.5 接口契约登记表（CONTRACT.md 初版）

| # | 依赖接口 | 形态 | 稳定性(§2.4) | 用途 | 失效表现 | 降级行为 |
|---|---|---|---|---|---|---|
| C1 | `sessions/**/*.jsonl.zstd` 布局+SessionHeader | 磁盘 | S | 墙会话流主源 | 扫描空/解析错 | L2→切 T2 RPC 读 |
| C2 | zstd 多帧格式 | 磁盘 | S | 同上 | 解压错 | 同上 |
| C3 | `POST /api/session.prompt` | RPC 写 | A | 格内对话 | method_not_found/拒连 | L1 墙输入框禁用+横幅 |
| C4 | `POST /api/workspace.archiveSession` | RPC 写 | A | 归档联动 | 同上 | L1 按钮 disabled 态 |
| C5 | `POST /api/session.list` / session.history | RPC 读 | A | T2 备源；历史抽屉(P2 备选) | 同上 | 主源健在则无感 |
| C6 | `GET /api/session.export?sessionId=` | HTTP | A | 轨迹导出（P4 候选） | 404 | 入口隐藏 |
| C7 | `storages/workspace.json` archivedSessionIds | 磁盘 | A | 归档过滤 | 文件缺 | 不过滤（宁多勿漏） |

**禁入清单**（明确永不依赖）：WS/SSE 下行帧判别联合（开放联合，B 级易变）；`window.__DSH_BOOT__` wire 图；cordis `internal/*` 事件族与 reflect/symbols；审批/提问 pending 帧（045 实证不可行：不落盘、不在 Web 暴露，且禁破解 WS）；settings/credentials 特权方法（钉死 loopback 且鉴权模型 1.0 前必变）。

### 4.6 破坏性升级降级策略（四级状态机）

| 级别 | 触发场景 | 用户所见 | 自动恢复 |
|---|---|---|---|
| **L0 全绿** | 全部能力 ok | 正常渲染 | — |
| **L1 写损** | C3/C4 失效（如 prompt 改名） | 墙浏览正常；输入框变灰+横幅「对话发送暂不可用（DSH 接口变更）」；其余页面零变化 | 半开试探复位 |
| **L2 读损·有备** | C1/C2 失效（磁盘格式变）但 C5 可用 | 墙自动切 RPC 源，角标「备用源」 | reader 修复后回落主源 |
| **L3 冻结** | C1+C2+C5 全失效（DSH 大版本破坏性升级/进程不在） | 墙显示最后成功快照 + 全幅降级条「DSH 数据暂不可达 · 快照截至 HH:MM · [重试]」。**绝不白屏、绝不静默假活** | 300s 试探 + 人工重试即时 |

硬规则三条：(a) 任何级别下页面骨架照常挂载；(b) 非 DSH 依赖视图零影响；(c) 降级必须有可见标识——禁静默陈旧数据冒充实时（防幻觉纪律的前端化）。

验收方式：pytest 故障注入矩阵（七类失效 × 四级断言 payload/DOM 态）+ CDP 冒烟截图；DSH 升级 SOP 增加一步「升前必跑 dsh_compat 测试组，升后跑真机降级演练」。

### 4.7 契约测试门禁（把「文档说了算」变成机器校验）

- `test_dsh_compat_contract.py`：扫描 dsh_compat 源码中的 RPC 方法名/磁盘路径常量 ⊆ CONTRACT.md 登记集，多余即红；
- `test_dsh_compat_degrade.py`：故障注入矩阵逐级断言；
- `test_frontend_no_dsh_concepts.py`：grep 前端目录禁词表（session.prompt / zstd / .dsh / api/<method> / 3080 / SessionHeader），命中即红——保证前端永远不知道 DSH 存在，这是「不锁死版本」在前端侧的执行体。

---

## 5. 迁移路径

总原则：绞杀式迁移，**每阶段结束系统完整可部署、可独立回滚**，不存在新旧断裂的全站不可用窗口。分支策略沿用 047 已定稿模式：特性分支、每卡独立 commit、逐卡验收 fast-forward 合入 main、合入观察一个使用时段再进下一卡；main 与 :7788 生产全程不受影响。

| 阶段 | 内容 | 出口验收（摘要） | 卡数 |
|---|---|---|---|
| **P0 清残留** | §1.5 A/B 类 JS 死码全删（纯删除零行为变化） | grep 断言符号消失；七视图 CDP 冒烟零控制台错误；pytest 绿 | 1 |
| **P1 数据层收拢** | dsh_compat 骨架（probe/degrade/capabilities 下发）；reader/rpc 迁入+双源互备；前端 api.js 拆五域模块+degrade.js；wallPage 对话/token 逻辑下沉后端消费 | 契约/降级测试绿；前端禁词门禁绿；墙功能等价回归（快照形状 diff 为空） | 3 |
| **P2 组件与实时通道** | 合入 feat/047-unification（裁决 plans 徽章偏差）；047-P2/P3 结构复刻并入；k-status-badge/k-timeline/k-logstream/k-refresh/fmt.js/modal 原语；k-degraded+degrade.js 接线并演练 L1/L3 | setInterval 数据轮询归零；像素矩阵子集对照；降级演练截图入库 | 5 |
| **P3 信息架构重组** | 导航四分组+二段 hash 路由；#/ops-hub 聚合壳；看板「轨迹」按钮接 048-P3 心跳索引（索引数据先行，属 048 范畴） | 全路由可达断言；移动端折叠回归；任取一卡一条命令返回轨迹（048-P3 原验收） | 3 |
| **P4 清理退役** | CSS 人工白名单清理 ≈4500 行（C 类）；目录更名 legacy-chat→webapp（白名单/版本戳脚本/文档路径联动）；服务端对话遗留路由经外部消费确认后下线 | 像素矩阵全绿分批删；更名后全路由冒烟+版本戳生效；退役后 grep 断言+pytest 绿 | 2 |
| **合计** | | | **14** |

工作量口径：registry.yaml 中 ccc 前缀 `taskable: false, forbidden: true`（平台自研直接开发模式，「卡数」是粒度/顺序/依赖的计量单位；若届时流程允许可经 plan-to-cards 转 ccc 卡或作为工单编号使用）。

关键顺序约束：(a) 048-P2（origin 字段）/P3（心跳索引）是本方案 ccc049-c12 的数据前置，建议先行或并行；(b) P1 完成后立即做一次 **DSH 升级演练**（模拟 rc.3 发布：临时改 probe 目标版本+篡改一个 RPC 方法名），验证降级链路后再进 P2；(c) CSS 清理（c13）永远排在结构复刻之后，避免给将死的样式做对照。

---

## 6. 风险清单 Top 5

| # | 风险 | 实测依据 | 规避 |
|---|---|---|---|
| **R1 DSH rc 期接口漂移击穿集成** | 无 CHANGELOG、无弃用管理、52 个 RPC 方法开放增长无版本段、鉴权模型源码自注 1.0 前必变 | §2.1/§2.4 源码证据 | 第 4 章全套机制；升级演练纳入 SOP（R1 的检验标准：模拟 rc.3 演练中墙进 L1/L3 而非崩溃） |
| **R2 高频变更区动刀冲突** | legacy-chat 近 30 天 176 次提交（git log 实测）；重构期业务修复不停 | §0 | 每卡短周期特性分支逐卡合入；重构卡与业务修复卡物理隔离（重构卡纯搬移不动行为，单独标注）；冲突时业务优先、重构卡 rebase |
| **R3 并存期烂尾拉长** | 既有先例：feat/047-unification 分支已实现 P1 却滞留未合入；legacy-chat 目录名债与服务端对话遗留自 045 拖至今日；roadmap.md 未回写墙融合一波方案（计划池与线路图脱节） | 子报告 §1.4/§1.6 实测 | 每阶段强制「删旧」出口条件；分支滞留超一个使用时段即升级为待办裁决项；本方案批准时同步回写 docs/projects/ccc/roadmap.md 里程碑 |
| **R4 样式回归事故重演** | 046-M4 自动清死样式已整体回滚一次（git 1373c4fa4 假阴性误杀）；动态拼接类名静态判不死；ui-kit 大量原语至今零引用证明「收编」比「新建」容易拖延 | §1.5/§3.3 | CSS 清理只许人工白名单制+像素矩阵全程对照（047-P4/M4 复盘纪律原样执行）；清理卡与功能卡永不混编；每批删除独立 commit 可单点 revert |
| **R5 「深度绑定」滑向「深耦合」** | 诱惑具体存在：:3080 无认证层直连最省事；wallPage 已有前端持 token 先例；审批帧破解曾有冲动（045 已禁） | §2.2/§1.4 | 前端禁词门禁机器化（§4.7 第三条）；架构红线（零碰核心/文件只读/官方 RPC 白名单/禁破解 WS）写入 CONTRACT.md 首节并列为每张卡的审查项；「操作直达」的新需求一律走 T3 白名单扩编流程而非绕行 |

---

## 验收标准（本研究报告）

- [x] 六项研究内容齐备，每项结论带 文件:行号 或命令输出证据（复现命令散布各节；子代理盘点原始数据已核入正文）
- [x] 隔离层章节正面回答硬边界：DSH 升级不锁死（单点知识+能力位+双源互备+四级降级+契约门禁五机制）
- [x] 迁移路径五阶段每步可部署、出口验收可执行、14 张功能卡粒度可直接转卡
- [x] validate-plans.sh 通过（提交前机械校验，2026-08-26 实测 OK）
- [ ] 老板拍板：技术选型（维持 vanilla）与运维台聚合方案认可后转「已确认」

## 功能卡

> 一个功能一张卡。颗粒度/依赖/架构位置三要素齐备；转卡由人触发（ccc 平台现行直接开发模式下亦可作工单编号）。

### 删除零引用 JS 与死导出（P0）

目标：执行 §1.5 A/B 类清单——删 state.js/ports.js/markdown.js/shell-ui.js+script 标签/roadmapTimeline shim、utils 死导出、api.js 死导出与 /claude 缓存前缀、taskCardList 死块。纯删除零行为变化。
实现：逐对象确认零 importer 后删除；grep 断言符号消失；CDP 七视图冒烟。
验收：上述对象不在仓内；冒烟零控制台错误；pytest 绿。
颗粒度：纯删除约 713 行、12 个对象，不触碰任何存活逻辑。
依赖：无
架构位置：legacy-chat/js 壳层与组件层死码

### dsh_compat 骨架与能力探测（P1）

目标：新建 server/web/dsh_compat/{__init__,probe,degrade}.py，实现三层探测与四级降级状态机，暴露 GET /wall/api/capabilities；SSE 心跳携 level 变更。
实现：按 §4.2/§4.4 落地；capabilities 快照持久化 data/dsh_compat/；server.py 挂线 ≤10 行。
验收：probe/degrade 单测绿；故障注入矩阵逐级断言通过。
颗粒度：新 Python 包 ≤400 行 + 最小挂线；不含 reader/rpc 迁移。
依赖：无
架构位置：server/web/dsh_compat → server.py 路由层

### reader 与 rpc 客户端迁入 dsh_compat（P1）

目标：wall.py reader 状态机迁 reader_disk.py（T1 主源），dsh_rpc 迁 client_rpc.py（T2/T3 白名单两方法），实现 L2 双源互备；wall.py 退化薄壳保持 /wall/api/* 形状。
实现：逻辑零改动搬移 + source 标注 + 切换开关接 degrade 状态机。
验收：墙快照形状 diff 为空等价回归；注入磁盘故障自动切 T2 并角标显示；pytest 绿。
颗粒度：搬移 ~450 行 + 互备 ~80 行。
依赖：dsh_compat 骨架与能力探测（P1）
架构位置：dsh_compat.reader_disk/client_rpc ← wall.py

### 前端数据层拆域与对话逻辑下沉（P1）

目标：api.js 按 domain 拆 wall/board/plans/roadmap/system 五模块（保留 TTL 缓存/pageScopeAbort 机制）；wallPage 格内对话的 token 换取与发送改为纯消费后端路由（token 缓存逻辑下沉服务端会话），新增 js/degrade.js 消费 capabilities+SSE level。
实现：机械拆分不改语义；_fetchWithAuth 正名。
验收：前端禁词门禁绿（无 session.prompt/token 换取/3080 字样）；七页数据加载回归。
颗粒度：api.js 拆分 + degrade.js ~120 行 + wallPage 删减 ~60 行。
依赖：dsh_compat 骨架与能力探测（P1）
架构位置：js/api.js+pages/wallPage.js → js/data/*+degrade.js

### 合入 047-P1 去轮询化分支（P2）

目标：fast-forward 合入 feat/047-unification（4de1da854 六页 setInterval 拆除），显式裁决 plans 徽章偏差（微探针方案接受与否）并补可见性门控。
实现：分支 rebase main 后合入；偏差决策写入合入 commit。
验收：main 上数据轮询 setInterval 归零；七视图回归；plans 徽章实测。
颗粒度：分支合入 + 单点补丁，无新功能开发。
依赖：前端数据层拆域与对话逻辑下沉（P1）
架构位置：js/pages/* 定时器装配段

### 新原语组件族（P2）

目标：ui-kit.css 增 k-status-badge/k-timeline/k-logstream/k-degraded/k-refresh/modal + fmt.js 唯一格式化模块；只加不改。
实现：纯函数组件+注释契约块；fmt 收编 agoText/fmtElapsed 散件。
验收：原语注释契约齐全；现有页面零视觉变化（截图对照）；后续卡可消费。
颗粒度：css/js 新增 ~500 行，不改存量。
依赖：无（可与 P1 并行）
架构位置：css/ui-kit.css + js/components/

### 结构复刻·运维面板族（P2，并入 047-P2）

目标：dsh→console→ops 三页私有卡片类替换为 k-card 族+k-topbar，内联色改令牌。
实现：按 047 §2.2 顺序逐页独立 commit。
验收：逐页像素对照；三页无私有卡片类残留。
颗粒度：三页模板字符串与类名替换，无逻辑改动。
依赖：新原语组件族（P2）
架构位置：js/pages/{dsh,console,ops}Page.js + css/

### 结构复刻·数据面板族（P2，并入 047-P3）

目标：roadmap→plans→board 同上；board 压轴单独分支预演。
实现：同上；board 预演通过再动。
验收：同上；42 张像素矩阵终验入库。
颗粒度：三页皮层替换。
依赖：结构复刻·运维面板族（P2）
架构位置：js/pages/{roadmap,plans,board}Page.js + css/

### 降级态渲染接线与演练（P2）

目标：k-degraded 驱动的 L1/L3 前端呈现（横幅/冻结快照+时间戳/重试/备用源角标）接入墙与看板轨迹区；完成首次 DSH 升级演练。
实现：degrade.js 事件 → 视图 render 分支；演练脚本模拟 rc.3（改版本+篡改方法名）。
验收：L3 下墙不白屏且有快照时间戳；演练截图入库；恢复自动复位实测。
颗粒度：渲染分支+演练脚本，无数据层改动。
依赖：reader 与 rpc 客户端迁入 dsh_compat（P1）；新原语组件族（P2）
架构位置：js/degrade.js + pages/{wall,board}Page.js

### 导航分组与二段路由（P3）

目标：hub-nav 四分组（执行/任务/规划/运维）+ 二段式 hash（#/ops-hub/system 等），默认仍 wall。
实现：router.js 支持 section/view；nav 分组渲染；移动端折叠。
验收：全路由可达断言；未知路由折叠回 wall；046 移动端基线回归。
颗粒度：router/nav/index.html 改造，页面本身不动。
依赖：无
架构位置：js/router.js + index.html hub-nav

### 运维台聚合壳（P3）

目标：#/ops-hub 三 tab（系统/引擎/巡检）编排 console/ops/dsh mount/unmount，共用刷新节流与健康四格条（含 DSH 连通性，来自 capabilities）。
实现：聚合壳纯编排；三物理页零改动。
验收：tab 循环切换 unmount 断言无泄漏；健康四格含 DSH 态。
颗粒度：新聚合壳 ~150 行。
依赖：导航分组与二段路由（P3）；合入 047-P1 去轮询化分支（P2）
架构位置：js/pages/opsHub.js ← {console,ops,dsh}Page.js

### 看板全链追溯接线（P3）

目标：卡详情「轨迹」按钮读 data/trace/card-sessions.json（048-P3 索引）直达墙内对应会话卡；索引缺失走 k-degraded 降级态。
实现：board 详情扩展轨迹区；点击 navigate 至 wall 并聚焦 session。
验收：任取一卡一条命令返回轨迹路径与当前阶段（048-P3 原验收）；按钮降级态实测。
颗粒度：board 详情扩展 ~80 行；索引数据属 048-P3 范畴须先行。
依赖：降级态渲染接线与演练（P2）；外部前置：048-P2/P3 数据层
架构位置：js/pages/boardPage.js 详情区 ← data/trace/card-sessions.json

### CSS 人工白名单清理（P4）

目标：删 components.css 对话期区块与 shell.css 多代旧样式共 ≈4500 行；动态拼接类名永久白名单。
实现：M4 复盘纪律——人工逐段白名单+42 张像素矩阵全程对照，分 ≥4 批各带截图，禁批量自动删除。
验收：矩阵全绿后逐批 commit；css 总量下降 ≥4000 行且零视觉 diff。
颗粒度：纯 CSS 删除，四批次独立可 revert。
依赖：结构复刻·数据面板族（P2）
架构位置：css/components.css + css/shell.css

### 目录更名与对话遗留下线（P4）

目标：legacy-chat/ → webapp/（_STATIC_WHITELIST/bump-frontend-stamp.sh/test_http_api 断言联动更新）；/conversation 族、threads 族、/dsh/workspaces|sessions、chat_bridge :7799 经外部消费确认后下线。
实现：更名独立 commit 承认全量路径 churn；下线先出消费方确认清单（ai-loop-router/Desktop）。
验收：更名后全路由 CDP 冒烟+版本戳生效；下线后 grep 断言路由消失且 pytest 绿。
颗粒度：机械更名 + 后端路由删除（后者以前者确认为前提，可拆两卡执行）。
依赖：CSS 人工白名单清理（P4）
架构位置：server/web/{legacy-chat→webapp} + server.py 旧对话路由

---

## 备注

1. **性质声明**：本报告为老板直派只读研究课题（指令模式），除本文件外未改任何代码/配置/文档；报告的 commit+push 受老板临时授权。
2. **与前置方案的关系**：不推翻 045/046/047/048 任何一个——047-P1 分支直接合入、P2-P4 原案并入本方案 P2/P4；048-P1（ccc079）已完成合入，P2/P3 是本方案追溯接线的数据前置；046 的 ui-kit 地基直接续用。
3. **明示不确定项**（不装懂）：npm dist-tag、DSH 破坏性变更频率、鉴权演进形态三项无法从本地制品核验，均按高不确定性处理；生产 :7788 运行态、:3081 是否已下线、/cards 实际项目覆盖为运行态未核实项；046 验收中「hex 84→3」口径与现行 components.css 不符（M4 回滚残留状态），不影响本方案结论。
4. 若老板认可本方案：下一步 = ① ccc049-c01（清残留）与 dsh_compat 骨架可立即开工，二者无依赖；② 048-P2/P3 与本方案 P3 追溯卡的衔接需老板排期裁决先后；③ roadmap.md 补记本方案里程碑（R3 整改动作）。
