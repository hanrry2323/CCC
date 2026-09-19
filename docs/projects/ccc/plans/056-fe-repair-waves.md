# 方案 · 看板前端修复与体系收敛——FE-0/FE-0b 两轮探查立案执行（三波 18 卡）

> 项目：ccc · 编号：ccc-plan-056 · 状态：已确定（老板 2026-09-19 Plan 模式批准） · 作者：ZCode（环节② · FE-0/FE-0b 探查执行体） · 工具：ZCode
> 创建：2026-09-19 · 更新：2026-09-19
> 关联卡：无（转卡按「## 功能卡」段走 ccc-plan / plan-to-cards，建议卡号 fe001 起）
> 关联方案：ccc-plan-054（**视觉规格唯一权威**——本方案 W2 令牌类只做断链/一致性最小修复，视觉重构仍归 054）· ccc-plan-049（前端架构唯一权威）· ccc-plan-050（合入自动化，无交集备案）
> 取证基线：FE-0 报告 `~/program/ccc-fe0-probe-20260918/FE-0-report.md`（17 条立案）· FE-0b 报告 `~/program/ccc-fe0b-probe-20260919/FE-0b-report.md`（甲 9 条 + 乙体系 + 丙架构，含克隆回归环境与量化基线）。两轮探查全程只读+隔离克隆，零生产改动。

## 目标

把两轮探查立案的 26 条问题按「断链止血 → 体系收敛 → 性能数据层」三波 18 张窄卡全部修掉，每卡夜间可独立执行与验收，验收探针直接复用两份报告的克隆复现步骤与量化基线。

## 背景

FE-0（2026-09-18 夜）与 FE-0b（2026-09-19 夜）对立面做了两轮只读探查：FE-0 走查 7 路由×双宽度×双主题+失败态，立案 17 条（高 4：看板 SSE 无限 401、接口失败渲染成「🎉 健康空态」、控制台窄屏右列不可达、暗色主题白斑；中 3；低 10）；FE-0b 在隔离克隆（220 卡造数）补扫写链路/性能/可达性：写接口延迟 8.7–52.2s 且 push 失败时「报错但已落盘」、方案 prompt 编辑整篇替换（25 行→11 行实锤）、转方案失败路径非原子、`/cards` 冷合成 6.0s 致看板 TTI 15.3s、30 分钟长挂无泄漏（正面基线）。外脑出修复方案所需证据已齐（老板 2026-09-19 指令按方案执行）。

## 方案内容

三波推进，波内可并行，波间硬依赖（W2 踩 W1 组件、W3 踩 W1 落盘一致性）。范围红线：视觉重构不动（归 054）、全局态势页与 5 入口重组不执行（FE-D 拍板项，见备注）。

### W1 断链止血（P0 · 8 卡）

| # | 主题 | 一句话 | 对应立案 |
|---|---|---|---|
| W1-1 | SSE 持 token | 看板执行中/机审卡日志流加 `?token=`，api.js 收口 sseUrl() 唯一出口 | FE-1 |
| W1-2 | 错误态组件 | 区块级「失败+重试」组件；ops/console/plans 的 `.catch(()=>null)` 传错误标记 | FE-2、FE0b 甲 |
| W1-3 | 方案编辑弹层 | window.prompt → textarea 弹层，杜绝整篇替换 | FE-5、FE0b-4 |
| W1-4 | 写失败一致性 | push 失败回滚文件与 commit（或如实「已落盘未同步」语义） | FE0b-2 |
| W1-5 | 转方案原子化 | 先建方案成功再删草案 | FE0b-5 |
| W1-6 | apiDelete 抛错 | 非 2xx 必抛，调用点 catch+失败提示 | FE-6 |
| W1-7 | 复制兜底 | 共享 copyTextToClipboard（execCommand 兜底）替换裸 clipboard | FE-8 |
| W1-8 | 转卡 fail-fast | card_gate 前置，错误聚合瘦身（111KB→摘要+明细文件） | FE0b-3 |

### W2 体系收敛（P1 · 6 卡）

| # | 主题 | 一句话 | 对应立案 |
|---|---|---|---|
| W2-1 | 弹窗组件 cc-dialog | ESC+遮罩+focus trap+焦点归还，替换 6 套弹层 | FE-9、FE0b-8 |
| W2-2 | 暗色令牌清理 | #fafafa/#333/#fff 硬编码→语义令牌（规格遵 054 §1） | FE-4 |
| W2-3 | console 窄屏 | `.console-grid` ≤768px 单列 | FE-3 |
| W2-4 | 尺寸/层级令牌迁移 | z-index 19 种→5 档、红系 9 种→语义色、check 脚本防回潮 | 乙 1–3 |
| W2-5 | 渲染器/工具去重 | markdown.js 死代码清理、esc/setHtmlStable/agoText/_loadAdopted 归一 | 乙 4 |
| W2-6 | 低级别批量 | FE-10～FE-17 + 触控目标 + aria 符号钮 + 陈旧详情标记 | FE-0 低 10 条 |

### W3 性能+数据层（P2 · 4 卡）

| # | 主题 | 一句话 | 对应立案 |
|---|---|---|---|
| W3-1 | /cards 富化分层 | 运行时富化按 mtime 增量缓存，冷合成 6.0s→<1.5s @231 卡 | FE0b-7 |
| W3-2 | 写路径异步化 | transition/convert 受理即返+回报，按钮「受理中」态 | FE0b-1 |
| W3-3 | 缓存 TTL 对齐 | api.js TTL 10s 对齐各页轮询 30s | 丙 3 |
| W3-4 | 错误模型信封 | `{ok, data\|error{code,message}}` 渐进迁移（新端点强制） | 丙 3、FE-6 |

## 验收标准

- [ ] W1：克隆实例（重启命令见 FE-0b 报告末尾）逐卡复现探针通过——SSE 无 401 循环、断网下 ops 无「🎉」、方案编辑行数不塌缩、无 origin 写失败后文件与响应一致、promote 失败草案保留、apiDelete 500 显示失败、HTTP 活体复制成功、转卡 400 响应 <5KB
- [ ] W2：dark 截图无白斑且 overview-line 对比度 ≥4.5:1；390px console 右列可达；FE-9 弹窗 ESC/遮罩可关且 settings 不回退；全站字面量 grep 归零（variables/themes 除外）且 check 脚本入 CI；wall/plans 渲染快照对照一致
- [ ] W3：231 卡冷缓存 `/cards` <1.5s、看板 TTI <6s；transition 响应 <3s 且 UI 有进度态；同接口 30s 内网络请求 ≤1 次
- [ ] 回归：FE-0b 量化基线不回退（30min 长挂 heap 1–3MB 平稳、断网自愈 <5s、写链路 15 项行为表）
- [ ] 全程：生产仓不直推 main，走环节②审核合入；每卡合入前机审+人审

## 功能卡

### W1-1 · 看板 SSE 持 token（断链修复）

目标：看板执行中/机审卡的实时日志流在开鉴权环境下恢复连通。现状 EventSource 无法自带 Authorization 头且未带 `?token=`，服务端读闸（server.py:4207）无限 401，卡面永久「连接中断，重连中…」。
实现：api.js 新增 `sseUrl(path)`（自动附 localStorage token 查询参数，唯一 SSE 出口）；boardPage.js:330 改用；wallPage.js:500 迁移到同一出口。
验收：克隆实例执行中卡日志流显示中文行；Network 面板 `/tasks/stream` 无 401 循环。
颗粒度：2 文件 ~20 行，一卡。
依赖：无。
架构位置：legacy-chat/js/api.js → pages/boardPage.js、pages/wallPage.js（前端数据层出口）。

### W1-2 · 页面错误态组件与 catch 收口

目标：接口失败不再渲染成「🎉 健康空态」。ops/console/plans 所有 `.catch(() => null)` 改传错误标记，区块级渲染「加载失败+重试」组件；空态与失败态视觉分离。
实现：新增轻量错误区块渲染函数（对齐 app.js 既有「页面加载失败：重试」文案风格）；opsPage.js:479-486 六源、consolePage.js:470-483 十二源、plansPage.js:144-150 首载失败路径收口。
验收：请求中止模拟下 ops 四闸门不出现「🎉」、console 不显示「未配置集群节点」、plans 显示错误条；恢复后点重试即自愈。
颗粒度：3 页 +1 组件，约 120 行，一卡。
依赖：无。
架构位置：legacy-chat/js/pages/{ops,console,plans}Page.js + components/（展示层）。

### W1-3 · 方案编辑 textarea 弹层

目标：方案「编辑」不再经 window.prompt 整篇替换多行 Markdown（FE0b-4 文件级实锤 25 行→11 行）。
实现：plansPage.js:572 改 plans-form-overlay 样式 textarea 弹层（标题+正文+保存/取消），保存前展示首尾预览各 3 行；服务端 /plans/update 不动。
验收：克隆编辑后文件仅追加/修改所编辑段落，行数不塌缩；取消不写盘。
颗粒度：1 文件 ~80 行，一卡。
依赖：无。
架构位置：legacy-chat/js/pages/plansPage.js（前端交互层）。

### W1-4 · 卡写路径 push 失败一致性

目标：消除「API 报 500 但卡已流转」的分歧。push 失败（网络/远端锁）时回滚工作树与本地 commit，或响应如实改为「已落盘未同步」并让看板提示。
实现：card_state_store.py transition/commit_push 失败分支补 `git reset --hard`+`git rebase --abort` 类清理（保留 history 记录 failed）；二选一以最小改动为准，响应语义与 UI 提示对齐。
验收：无 origin 克隆上 transition：文件状态与响应语义一致，无「报错但已落盘」残留 commit。
颗粒度：1 模块 ~40 行 + 测试，一卡。
依赖：无。
架构位置：server/engine/card_state_store.py（写路径存储层）。

### W1-5 · 草案转方案原子化

目标：promote-to-plan 失败时不再留下「草案已删+半成品方案文件」（FE0b-5 实证）。
实现：server.py 草案转方案链路改序——先 `create_plan` 全部成功（含前缀校验），成功后再从 roadmap.md 移除草案；任一步失败即抛错且不删草案。
验收：注入未注册前缀：400、草案保留、无残留方案文件；干净环境 201 行为不回退。
颗粒度：1 处时序调整 + 测试，一卡。
依赖：无。
架构位置：server/web/server.py roadmap promote 链路（服务端写路径）。

### W1-6 · apiDelete 抛错收口

目标：DELETE 失败不再假成功（FE-6：草案取消失败也弹「已取消 ✓」）。
实现：api.js:238-243 补 `if (!resp.ok) throw new Error(...)`（对齐 apiPut 语义，401 文案同款）；roadmapPage.js:475 调用点已有 catch 即可生效，其余 apiDelete 调用点逐一核对补 catch。
验收：注入 500：UI toast 显示失败；成功路径行为不变。
颗粒度：1 文件 + 调用点核对，~15 行，一卡。
依赖：无。
架构位置：legacy-chat/js/api.js（前端数据层）。

### W1-7 · 复制工具统一兜底

目标：ops/dsh「转卡」复制按钮在 HTTP 局域网（非安全上下文）可用。活体实测 `navigator.clipboard` 为 undefined，现必显「复制失败」。
实现：boardPage.js:53-78 copyTextToClipboard（clipboard+execCommand 双路）抽到 utils.js；opsPage.js:369、dshPage.js:230 改用。
验收：HTTP 活体 192.168.3.116:7788 点「转卡」显示「已复制 ✓」；localhost 行为不回退。
颗粒度：3 文件 ~30 行，一卡。
依赖：无。
架构位置：legacy-chat/js/utils.js + pages/{ops,dsh}Page.js（前端工具层）。

### W1-8 · 转卡门禁 fail-fast 与错误瘦身

目标：转卡失败不再返回 111KB/737 条错误串，也不再「先写生成卡再校验后删除」。
实现：server.py /plans/convert 链路把 card_gate 校验提前到生成卡之前（dry-run 门禁）；失败响应聚合为摘要（计数+前 5 条）+ 明细落日志文件引用路径。
验收：非法数据转卡：400 响应 <5KB、无「已删除生成卡」日志；合法转卡 200 行为与生成物不变。
颗粒度：1 链路重排 + 错误聚合，~60 行，一卡。
依赖：无。
架构位置：server/web/server.py convert 链路 + card_gate（服务端写路径）。

### W2-1 · 弹窗组件 cc-dialog 归一

目标：六套弹层（board-modal/settings-sheet/plans-form-overlay×3/toast 外的 dialog 类/cell-input/hub-login 中前三类）关闭行为、焦点管理统一；FE-9（看板弹窗 ESC/遮罩不可关）与 FE0b-8（无 focus trap、焦点不归还）一并闭环。
实现：新增 components/dialog.js（ESC+遮罩点击+Tab trap+关闭后焦点归还+暗色令牌）；boardPage/settings/plans/roadmap 三处迁移；hub-login 与 cell-input 保持独立（形态不同），toast 不动。
验收：ESC/遮罩可关、Tab 不逃出弹窗、关闭后焦点回触发钮；settings 行为不回退；无回归 console 报错。
颗粒度：1 新组件 + 4 处迁移，~200 行，一卡。
依赖：无（与 W1 并行亦可）。
架构位置：legacy-chat/js/components/dialog.js + pages 迁移（前端组件层）。

### W2-2 · 暗色主题硬编码清理

目标：暗色主题无白斑、无不可读文本（FE-4 四处实锤）。
实现：shell.css:3326/3434（#fafafa）→ `var(--ccc-bg-surface)`、3311（#333）→ `var(--ccc-text-secondary)`、3062-3066（stream 白底）→ 层级令牌、boardPage.js:106（搜索框内联 #fff）→ 令牌、boardPage.js:118（banner 硬编码红）→ `--ccc-danger` 系。视觉规格遵 ccc-plan-054 §1，本卡只做等价替换不做视觉重设计。
验收：dark 截图 board/console 无白斑；`console-overview-line` 对比度 ≥4.5:1（实测口径同 FE0b）。
颗粒度：2 文件 6 处，一卡。
依赖：无。
架构位置：legacy-chat/css/shell.css + pages/boardPage.js（样式层）。

### W2-3 · console 窄屏单列

目标：控制台 390px 不再右列裁切不可达（FE-3：`1fr 360px` 无断点）。
实现：shell.css `.console-grid` 补 ≤768px `grid-template-columns: 1fr`（对齐 plans 断点做法）；顺带核查 `.console-overview-row` 窄屏换行。
验收：390px 截图右列完整可达、无横向裁切。
颗粒度：1 文件 ~10 行，一卡。
依赖：无。
架构位置：legacy-chat/css/shell.css（样式层）。

### W2-4 · 尺寸/层级令牌迁移 + 防回潮 check

目标：乙节统计的体系违背不再增长：z-index 19 种→5 档令牌（nav50/dropdown100/modal200/toast400/loading500）、语义色 9 种红→`--ccc-danger` 等九色、字号 21 种→7 档；新增 check 脚本禁止组件 CSS/JS 新增字面量（variables/themes 两文件豁免）。
实现：scripts/check-entry-docs.py 同款门禁风格新增 check-fe-tokens.py（正则扫描+白名单）；存量迁移按乙节清单分批，toast 100/board-modal 100 同层冲突优先解。
验收：`check-fe-tokens.py` 全绿并入 CI；z-index/语义色 grep 归零（豁免文件除外）。
颗粒度：CSS/JS 存量迁移 + 1 脚本，分批较大但机械，一卡（超 400 行可拆二）。
依赖：W2-2（暗色令牌先清，避免双重改写）。
架构位置：legacy-chat/css+js 全局 + scripts/（体系层）。

### W2-5 · 渲染器/工具去重

目标：收敛乙4 重复组：markdown 渲染器 ×3（markdown.js 333 行疑似零消费死代码先核实再删）、esc ×3、setHtmlStable ×3、agoText ×2、_loadAdopted ×2。
实现：核实 markdown.js 零消费后删除；esc/工具统一 import utils/ui；行为等价以 wall/plans 渲染快照对照验收。
验收：全站单一定义；渲染快照对照一致；零新增 console 报错。
颗粒度：~200 行删除+改 import，一卡。
依赖：无。
架构位置：legacy-chat/js/{utils,ui}.js + pages（前端工具层）。

### W2-6 · 低级别缺陷批量收编

目标：一次收编 FE-0 全部低级别与可达性项，避免碎卡。
实现：FE-10 空列文案分列语义化；FE-11 状态流转文案去「已关闭」；FE-12 dsh 错误区复位；FE-13 plans 深链 `?plan=` 刷新保留；FE-14 看板 `?state=` 深链+console KPI 带参；FE-15 黑话文案；hub-nav 触控目标 ≥44px；符号钮（☀/☾/↓/×）补 aria-label；FE0b-9 详情弹窗数据随轮询刷新或「已过期」标记。
验收：FE-0 报告对应条目逐条复核通过；触控目标抽样 ≥44px；读屏标签抽查通过。
颗粒度：9 项小改跨 7 文件，一卡（每项独立 commit 便于回退）。
依赖：W2-1（弹窗相关项踩 cc-dialog）。
架构位置：legacy-chat/js+css 多点（展示与交互层）。

### W3-1 · /cards 运行时富化分层缓存

目标：`/cards` 冷合成 6.0s→<1.5s @231 卡，看板 TTI 15.3s→<6s（FE0b-7 量化基线）。
实现：每卡 git/worktree 富化结果按文件 mtime+commit 增量缓存（对齐 server 既有 TTL/mtime 缓存风格），仅变更卡重算；预热线程复用。
验收：克隆重跑 FE0b-7 口径：冷 `/cards` <1.5s、看板 TTI <6s；数据与全量重算一致（抽样对照）。
颗粒度：1 合成链路，~150 行+测试，一卡。
依赖：W1-4（写失败一致性先行，避免缓存与回滚交织）。
架构位置：server/web/server.py _compose/_enriched 链路（服务端读路径）。

### W3-2 · 写路径异步化

目标：transition/convert 不再同步阻塞 UI 8.7–52.2s（FE0b-1）。
实现：受理即返 `{ok, accepted: true, pending: true}`，落盘+push 在后台线程完成后经既有 10s 轮询/SSE 回报；看板按钮改「受理中…」态（复用机审按钮既有文字切换模式）。
验收：231 卡 transition 响应 <3s；完成后看板 10s 内反映新状态；失败经 toast 报告且落盘一致（W1-4 语义）。
颗粒度：服务端 2 端点 + 前端 2 按钮，~120 行，一卡。
依赖：W1-4。
架构位置：server/web/server.py 写端点 + boardPage.js 动作按钮（前后端写链路）。

### W3-3 · 缓存 TTL 对齐轮询周期

目标：api.js CACHE_TTL 10s 与各页 30s 轮询失配（代码注释自认）导致双拉。
实现：apiGet 支持按路径族 TTL（summaries/plans/roadmap 30s、状态类保持不缓存），消除 30s 页的无效重复请求。
验收：Network 面板同接口 30s 内 ≤1 次；各页数据新鲜度不回退（写后失效路径 invalidateCache 不变）。
颗粒度：1 文件 ~20 行，一卡。
依赖：无。
架构位置：legacy-chat/js/api.js（前端数据层）。

### W3-4 · 错误模型信封渐进迁移

目标：数据层错误模型统一（apiGet/apiPost/apiDelete 三态不齐、88 处 `{"error"}` 与 `ok:true/false` 双形）。
实现：前端 api.js 统一非 2xx 必抛+错误对象 `{code,message}`；后端新端点强制 `{ok, data|error{code,message}}` 信封，存量端点仅在触及时渐进迁移。
验收：api.js 类型注释与单测齐全；新端点 check 入 validate；存量端点行为不变。
颗粒度：1 文件+规约文档，一卡。
依赖：W1-6。
架构位置：legacy-chat/js/api.js + server.py（前后端契约层）。

## 转卡计划

按波次顺序转卡：W1-1…W1-8（可并行）→ W2-1…W2-6（W2-4 依赖 W2-2、W2-6 依赖 W2-1）→ W3-1…W3-4（W3-2 依赖 W1-4、W3-4 依赖 W1-6）。建议卡号 fe001–fe018，走 ccc-plan / plan-to-cards.sh；夜间执行体每卡独立提交，环节②按上方各卡验收口径合入。

## 备注

- **FE-D 决策项（本方案不执行）**：全局态势页 + 5 入口重组（态势/执行/规划/巡检/运营，导航 7→5）、wall/dsh 与 ops/console 归并——蓝图与三档技术路线对比见 FE-0b 报告丙节，拍板在老板+外脑。
- **与 054/049 边界**：视觉规格/组件美学归 054（待排期，拍板后其 B2 批可复用本方案 W2 的令牌地基）；架构与数据层机制归 049。本方案只做「修复+收敛」，不做视觉重设计、不做框架迁移（三档对比结论：①现状+收敛 推荐执行，③全量重写现阶段否定）。
- **回归环境**：克隆 `/tmp/ccc-fe0b` + 裸仓 origin 保留；重启命令 `cd /tmp/ccc-fe0b && EXECUTOR_LOG_DIR=/tmp/ccc-fe0b-logs CCC_WEB_AUTH_REQUIRED=1 python3 -m server.web.server --port 7791`；量化基线与写链路行为表见 FE-0b 报告。
- **风险**：W2-4 存量令牌迁移面大（669 处间距为 054 范畴，本卡只收 z-index/语义色/字号），若超 400 行按卡内说明拆二；W3-2 异步化改变写交互语义（同步等待→受理回报），需老板知悉。
