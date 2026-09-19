# CCC 前端盘查报告（只读·严格版）

- **日期**：2026-08-29（盘查窗口 03:00–03:50 本机时间前后）
- **对象**：CCC web 前端（http://127.0.0.1:7788 ，Mac2017 本机回环）+ 仓内 `server/web/` 源码
- **性质**：只读盘查。零写仓、零配置变更、零服务操作、未跑 pytest、未重启/杀进程。
- **用途**：结论直接决定前端优化重构+功能打通方案。

---

## §0 零写自证

**开工 git status（03:0x）：**

```text
（空输出，exit 0）
```

**收工 git status（03:47）：**

```text
M  .pre-commit-config.yaml
 M requirements-hub.txt
M  server/engine/scheduler.py
```

**终核（报告落盘后补跑）：**

```text
（空输出，exit 0）
```

→ 开工与终核两次输出**一致且为空**，零写达成。

**过程差异说明（如实陈述）**：本仓是多会话共用的活仓，盘查期间有产线执行体会话并发工作：

- 盘查中段（03:29–03:33）脏文件为 `scripts/approve-merge.sh`、`server/engine/phase2.py`、`server/tests/test_phase2.py`（mtime 实测 03:29:29 / 03:32:55 / 03:33:34）；
- 随后这些文件被**他人提交**：`git log` 显示 `652c316f3`（approve-merge.sh）、`0e7363c7b`（phase2 测试）均为盘查窗口内新落库提交；
- 收工时的 3 个脏文件是执行体**下一轮工作**的新改动，与本盘查无关；
- 期间 HEAD 由 `1726b0180` 前进到 `f885fcd26`→`0e7363c7b`，其中 `server/web/` **零提交**（`git log 1726b0180..f885fcd26 -- server/web/` 输出为空），故本报告全部代码结论对当前 HEAD 仍有效。

**本盘查全部命令清单（均可复核，全部只读）**：`git status/log/rev-parse`、`ls/find/wc/cat/grep`、`ps/lsof -p`（只读进程信息）、`curl GET/POST 探测`（POST 仅打向**不存在的卡 ID `__NONEXIST__`** 与空体 `/plans/update`，均 401，无任何数据变更；`/session` 探测 500，未签发任何 token）、浏览器操作（只读走查+截图，未点击任何提交/确认类按钮）。

---

## §1 结构盘点

### 1.1 前端定位与目录

前端 = `server/web/`（服务端 + 静态资源同仓同进程），页面源码在 **`server/web/legacy-chat/`**（目录名为历史遗留，实际是当前唯一前端）：

```text
server/web/
├── server.py                 # 4740 行：HTTP 服务 + 全部 API 路由（Python stdlib 零依赖）
├── wall.py / dsh_reader.py / exec_metrics.py / session_store.py / chat_bridge.py /
│   audit_evidence.py / worktree_dirty.py      # API 的数据后端
├── data/
│   ├── board.js              # 静态导出产物（window.BOARD_DATA，board/export.py 生成）
│   └── arch/*.json           # 架构全景数据（/board/arch 用）
├── legacy-chat/              # ★ 前端本体
│   ├── index.html            # 唯一入口页（壳：导航 + 7 个空视图容器）
│   ├── css/ 8 个文件（9521 行，全站全局加载）
│   └── js/ 24 个文件（6291 行）：app/router/api/theme/utils/ui + pages/×7 + components/×5
└── favicon.svg
```

另有 `desktop/`（Swift 桌面端，消费同一批 HTTP API）——非本次 web 盘查范围，仅备注存在。

### 1.2 技术栈与版本

| 层 | 选型 | 证据 |
|---|---|---|
| 框架 | **无框架**，原生 ES Module + hash 路由 SPA | `index.html` 无任何框架 script；`js/app.js` 动态 `import('./pages/*.js')` |
| 构建 | **无构建**：源码即产物，无 package.json/打包器 | `legacy-chat/` 下无任何构建配置文件 |
| 服务端 | Python stdlib `http.server`（零依赖），进程 `python -m server.web.server --host 127.0.0.1 --port 7788` | `ps` 86493 号进程实测；`server/web/README.md` |
| 版本戳 | 服务端运行时把 HTML 内魔法串 `v=20260809t12` 替换为 git 短号 | `server.py:1952`；实测首页资源 `?v=f885fcd26`（=当时 HEAD） |
| 依赖清单 | 前端**零 npm 依赖**；无 package.json（`desktop/package.json` 属 Swift 桌面端） | 目录盘点 |

### 1.3 构建与部署（页面如何送到 :7788）

1. 源码就在仓内 `server/web/legacy-chat/`，**没有构建步骤**；改完即生效（靠版本戳破缓存）。
2. 服务进程把 `GET /` `/wall` `/app` 映射到 `legacy-chat/index.html`，`/js/*` `/css/*` 落到 `legacy-chat/` 目录（白名单 + 目录前缀，防穿越），见 `server.py:289-339`。
3. 带参缓存策略：`?v=` 命中 → `Cache-Control: immutable` 一年；无参 HTML → `no-cache`（`server.py:1954-1959`）。
4. 部署 = 仓 pull 后重启进程（launchd label `com.ccc.web-server` 登记，实测当前进程为手动拉起——见 §4 控制台 M2 矛盾证据）。
5. 白名单里的 `/data/cluster.js` 指向**不存在的文件**（实测 HTTP 404），属遗留映射（`server.py:302`）。

### 1.4 路由表（每条路由 → 页面文件 → 功能）

路由为 hash 路由，注册表 `js/router.js:7`，加载器 `js/app.js:17-53`：

| 路由 | 页面文件 | 功能 | 状态 |
|---|---|---|---|
| `#/wall`（**默认**） | `js/pages/wallPage.js` | DSH 监控墙：活跃会话格子墙，SSE 实时流，格内发消息/归档 | 在用 |
| `#/board`（支持 `?ws=<project>`） | `js/pages/boardPage.js` | 五列看板（待分派/打回/执行中/机审/已回写）+ 卡详情弹窗 + 状态流转/机审/误报/作废 + 卡内实时日志 SSE | 在用 |
| `#/plans`（支持 `?plan=<id>` 深链） | `js/pages/plansPage.js` | 六态方案池（已确定/待排期/部分执行/待验收/已完成/作废）+ 方案详情 + 转卡/验收拍板/改状态/编辑 | 在用 |
| `#/roadmap` | `js/pages/roadmapPage.js` | 项目线路总览 → 单项目：里程碑 rail + 子任务卡 + 草案池（确认转方案/编辑/取消）+ 新建/编辑里程碑 | 在用 |
| `#/ops` | `js/pages/opsPage.js` | 项目健康 + 四大人审闸门 + diff 审查/代码健康 + 螺旋循环 + 失败原因 | 在用 |
| `#/dsh` | `js/pages/dshPage.js` | DSH 巡检报告结论页（红旗/黄旗/蓝旗 + 发现清单 + 原文折叠） | 在用 |
| `#/console` | `js/pages/consolePage.js` | 系统总览/集群节点/端口探索/中转站/知识库/后台进程/**服务开关**/已开发成果/只读设置 | 在用 |
| 未知路由 | `router.js:14-19` | 折叠到 `#/wall` 并纠正地址栏 | — |
| 隐藏入口 | `components/settings.js` | ⚙ 设置面板（仅主题三态 + 版本关于；方案创建表单 2026-08-24 已按老板指令移除，`plansPage.js:721` 注释） | 在用（轻） |
| 隐藏深链 | `boardPage.js` 「去收卡」横幅 | `#/board` 积压告警条 → 跳 `#/console` | 在用（数据驱动） |

**半成品/废弃**：页面级无半成品；**死文件**见 §6.2（state.js / ports.js / markdown.js）。

### 1.5 页面/视图全量清单与状态标注

| 页面/入口 | 状态 | 说明 |
|---|---|---|
| 信息墙 wall | 在用 | 默认首屏；SSE 正常推送（实测） |
| 看板 board | 在用 | 主动线核心；已关闭卡不可见（见 M5） |
| 计划 plans | 在用 | 主动线核心；创建入口已删（收敛到线路图激活/转卡） |
| 线路图 roadmap | 在用 | qb 数据源有重复里程碑（见 M4） |
| 运维 ops | 在用 | 纯聚合视图，无写操作（除 loop/adopt 留档） |
| 巡检 dsh | 在用（带 2 缺陷） | 原文拉取断链 M1、空 findings 文案矛盾 M7 |
| 控制台 console | 在用 | 服务开关真值错位 M2、portals 探活失真 M3 |
| 设置面板 | 在用 | 仅主题/版本 |
| 对话栈（消息流/composer/侧栏会话/登录门/分屏） | **已拆除** | `app.js:4-6` 注释明示；后端 `/conversation`、`/projects/*/threads`、`/dsh/workspaces`、`/dsh/sessions/*` 仍存活但前端零调用（见 §2.2 缺口②） |

---

## §2 页面↔接口对照

### 2.1 逐页面 API 清单（代码定位 + 浏览器 Network 实测双重验证）

**全局（api.js 数据层，`js/api.js`）**：所有请求同源相对路径；GET 统一 15s 超时 + 瞬时错误静默重试 1 次 + 10s TTL 内存缓存（白名单前缀）+ 在途去重；写后 `invalidateCache('/')` 全清。**不带任何 Authorization 头**（`api.js:105-118`）。

| 页面 | 方法+路径 | 用途 | 实测 |
|---|---|---|---|
| wall | GET `/wall/api/stream` (SSE) | 会话状态全量+diff 推送，15s 心跳 | 200·首帧✓ |
| wall | POST `/wall/api/dsh/prompt` | 格内给 DSH 会话发消息（**唯一带 Bearer 的调用**，token 现场换，`wallPage.js:518-537`） | 未实测写（401 已由 curl 证实） |
| wall | POST `/wall/api/dsh/archive` | 归档会话（**前端无入口调用**，代码保留） | — |
| wall | POST `/session` | 现场换 token（账号硬编码 `ccc`） | 500（auth 未配置） |
| board | GET `/board/summaries` | 工作区按钮组（按项目计数） | 200 |
| board | GET `/projects` | prefix→显示名映射 | 200 |
| board | GET `/cards?project=&page_size=1000` | 全量卡拉取（前端过滤分列） | 200 |
| board | GET `/tasks/running` | 运行时指标合并（dirty/耗时/调用数） | 200 |
| board | GET `/board/ready_for_merge` | 待合入计数 + 积压告警横幅 | 200 |
| board | GET `/board/summaries?workspaces=a,b` | 各项目徽标状态（alert/running） | 200 |
| board | GET `/tasks/{id}` | 卡详情弹窗 | 200（tst997） |
| board | GET `/tasks/stream?ids=…` (SSE) | 执行中/机审卡内 5 行日志瀑布 | 200·snapshot✓ |
| board | POST `/tasks/{id}/transition` | 重新分派（打回→待分派）/ 作废 | **401** |
| board | POST `/tasks/{id}/audit` | 手动机审（轻/中/重） | **401** |
| board | POST `/tasks/{id}/false-positive` | 机审误报回填 | **401** |
| plans | GET `/plans/list`（缓存） | 方案池六列 | 200（72 方案） |
| plans | GET `/plans/card-states` | 关联卡六列流程条 | 200 |
| plans | GET `/cards?page_size=500` | 关联卡状态徽标（警示标签） | 200 |
| plans | GET `/projects` | 项目筛选按钮组 | 200 |
| plans | GET `/plans/detail?path=` | 方案详情（含 `## 功能卡` 解析） | 200（mx-plan-004） |
| plans | POST `/plans/update` | 拖拽改状态/编辑内容/改状态下拉 | **401** |
| plans | POST `/plans/convert` | 节点②确认转卡（支持 `slices` 子集） | **401**（弹层可开，提交被闸） |
| plans | POST `/plans/accept` | 验收拍板（待验收→已完成） | **401** |
| roadmap | GET `/board/roadmap` | 一级总览（roadmap.py 解析器） | 200（7 项目） |
| roadmap | GET `/roadmap/{project}` | 二级详情（roadmap_parser 解析器） | 200 |
| roadmap | POST `/roadmap/{p}/draft/promote-to-plan` | 草案→方案 | **401** |
| roadmap | PUT `/roadmap/{p}/draft/{index}` | 编辑草案 | **401** |
| roadmap | DELETE `/roadmap/{p}/draft/{index}` | 取消草案 | **401** |
| roadmap | POST `/roadmap/{p}/subproject/activate` | 激活子项目→1:1 生成方案（后端还会 git commit+push，`server.py:4369-4394`） | **401** |
| roadmap | POST `/roadmap/{p}/milestone` | 新建里程碑 | **401** |
| roadmap | PUT `/roadmap/{p}/milestone/{title}` | 编辑里程碑 | **401** |
| roadmap | DELETE `/roadmap/{p}/milestone/{title}` | 删除里程碑 | **401** |
| ops | GET `/board/roadmap` `/loop/findings` `/board/ready_for_merge` `/cards?page_size=500` `/plans/list?status=待排期` `/ops/failures` | 六路并行拉取 | 全 200 |
| ops | GET `/roadmap/{proj}` ×N | 项目健康卡（**N+1**，每 30s×7 项目） | 全 200 |
| ops | POST `/loop/adopt` | 发现留档「已处理」 | **401** |
| dsh | GET `/ops/dsh-findings` | 报告清单+结构化 findings | 200 |
| dsh | GET `<report.path>`（前端拼接） | 报告原文 | **404**（M1） |
| dsh | POST `/loop/adopt` | 留档（source=dsh） | **401** |
| console | GET `/ops/summary` `/ops/ports` `/ops/relay-stats` `/ops/hp-health` `/ops/kb-health` `/board/states` `/board/ready_for_merge` `/config` `/ops/concurrency` `/ops/pg-health` `/ops/services` `/ops/portals` `/tasks/running` | 12+2 路并行，15s/8s 双定时器 | 全 200 |
| console | POST `/ops/service/{start\|stop\|restart}` | **launchctl 服务开关** | **401** |

轮询/SSE 总表：board 10s+SSE、plans 30s、roadmap 30s（二级页停刷）、ops 30s、dsh 30s、console 15s+8s、wall 纯 SSE——全部带 `document.visibilityState` 门控与卸载清理。

### 2.2 三类缺口

**① 前端在调但后端没有：仅 1 处（且是拼装错误，非路由缺失）**

| 前端调用 | 问题 | 证据 |
|---|---|---|
| dsh 页 `fetch(latest.path)` | 后端把 `path` 给成**文件系统绝对路径**（`server.py:3516` `"path": str(f)` → `/Users/fan/.ccc/data/dsh/patrol-report-37.md`），前端当 URL 直接 fetch → 404 → 原文永远显示「（无原文）」 | 实测 Network 条目 `GET /Users/fan/.ccc/data/dsh/patrol-report-37.md → 404`；`dshPage.js:282-292` |

除此外，7 页全部调用（含缓存白名单里在用的）后端均存在，浏览器实测零 404。

**② 后端有但前端没用（14 个，多数是对话栈遗产）**

| 路径 | 说明 |
|---|---|
| GET `/board/realtime` `/board/recent` `/board/by_project` `/board/states`（console 在用） `/board/arch` `/board/snapshot` `/board/roadmap/<project>` | 旧看板协议/桌面端兼容面；`/board/roadmap/<proj>` 是被 `/roadmap/{proj}` 取代的旧解析器（`opsPage.js:103-105` 注释自认「双解析器双真值」风险） |
| GET `/roadmap/projects` | 与 `/board/roadmap` 输出**逐字节相同**（实测均 38328 B），纯重复端点 |
| GET+POST `/conversation`、GET/POST/DELETE `/projects/<p>/threads…`、`/dsh/workspaces`、GET `/dsh/sessions/<id>`、POST `/loop/dsh-report`、POST `/plans/create` | 对话栈/旧创建入口遗产；前端 2026-08-24 拆除后零调用，但**接口仍全量暴露**（见 §5） |

**③ 参数或返回对不上（4 处）**

| # | 端点 | 错位 | 证据 |
|---|---|---|---|
| a | 所有写端点 | **前端不携带 token，服务端写闸默认开**：`CCC_WEB_WRITE_AUTH=1`（`server.py:1994` 默认）要求 Bearer，但 api.js 已「拆除 token 登录态」（`api.js:6` 注释），仅 wallPage 自带私有 token 流。且 `/config` 返回 `auth_configured:false`，`POST /session` 500「server auth not configured」→ **无 token 可获取，全部写操作必然 401** | curl 实测 `POST /tasks/__NONEXIST__/transition → 401`、`POST /plans/update → 401`、`POST /session → 500` |
| b | `GET /ops/dsh-findings` → dsh 页 | `path` 字段语义错位（文件路径当 URL，即缺口①） | 实测 404 |
| c | `GET /config` | console 设置区读 `config.ports.relay`，服务端 `_build_public_config` 只返回 web/board/engine 三键（`server.py:448-454`）→ 「中转站 —」恒空 | `consolePage.js:378` + `server.py:441-462` |
| d | `GET /ops/services` | 前端展示 `running` 字段按 launchctl 口径；当前 web 进程为手动拉起 → 显示「已停」，与事实相反（详见 M2） | 实测 JSON `com.ccc.web-server running:false` vs `ps` 86493 存活 |

---

## §3 主动线数据链路（文字版走查）

**看板（实时执行面）**
`mountBoard` → 并行 `GET /board/summaries`（按钮组）+ `/projects`（名称映射）→ `loadBoard`：并行 `GET /cards?project&page_size=1000` + `/tasks/running` + `/board/ready_for_merge` → `mergeDirtyFromRunning` 把运行时指标并进卡 → `renderBoard` 按 `board_column` 分五列（执行中/机审两列手渲染，上限 3 张，下方挂日志盒）→ **刷新双通道**：10s `setInterval` 可见性门控轮询 + SSE `/tasks/stream?ids=<执行中∪机审卡>`（snapshot 3 行起步 + log 增量 + 前端 5 行硬截断缓存，断线显示「连接中断，重连中…」）。
**状态流转（卡）**：卡详情弹窗按钮按状态显隐——打回→「重新分派」（`POST transition {status:'待分派'}`）/「标误报」（`POST false-positive`）；已回写→「机审」（`POST audit`）/「合入批准」（**仅 toast 提示去 2017 跑 `scripts/approve-merge.sh`，无线上动作**）；四态→「作废」（prompt 原因 + confirm）。
**写后**：`apiPost` 成功 → `invalidateCache('/')` 清全部缓存 → `loadBoard()` 重拉。

**计划（方案池）**
30s 轮询四路并行：`/projects`、`/cards?page_size=500`、`/plans/list`、`/plans/card-states` → 六列渲染（列签名去抖：数据没变不重建列 DOM）→ 点击/回车开详情（`/plans/detail?path=`，竞态序号守卫）→ 动作：拖拽卡片跨列=改状态（前端 `STATE_FLOW` 校验合法迁移，`POST /plans/update`）；「转为任务卡」弹层（节点②，勾选功能卡子集 → `POST /plans/convert {path, slices?}`）；「验收拍板」（待验收→`POST /plans/accept`）；深链 `#/plans?plan=<id>` 打开后抹参数防轮询重开。

**卡详情↔方案关联**：方案卡徽标从 `/cards` 拉 `state` 显示「警示」（有关联卡未关闭）+ 从 `/plans/card-states` 画六段流程条；反向从线路图 `#/plans?plan=` 下钻。

**审批（人审闸门）**：web 端审批动作=上面的 transition/audit/accept/convert；「合入批准」刻意不下沉（引导 CLI）。**当前全部被 401 写闸拦死（见 H1）**——线上实际只剩只读。

**墙（执行观察面）**：SSE `/wall/api/stream` 首帧全量 `state` 事件 + 后续 diff + 15s 心跳；完成/出错会话转「未读」区直到手动已读（localStorage 持久）；写通道（格内发消息）走 wallPage 私有 token 流（唯一实现 Bearer 的页面）。

**缓存一致性机制**：10s TTL + 在途去重 + 写后代次递增（防旧响应回填）。注：TTL 10s 小于多数页 30s 轮询间隔，缓存实际只服务「切走再切回」场景（`opsPage.js:492-494` 注释自认）。

---

## §4 浏览器实测实录（127.0.0.1:7788 真实走查）

方法：ZCode 内置浏览器逐页挂载；每页装 `window.__errs`（error + unhandledrejection 收集器）+ 读 `performance.getEntriesByType('resource')` 逐请求核对状态码；关键页截图。

| # | 页面/步骤 | 结果 | 加载表现 | 控制台报错 | 数据展示 |
|---|---|---|---|---|---|
| 1 | 信息墙 `#/wall` 首载 | ✅ 可用 | 16 资源全 200；SSE 已连接（统计行「活跃 0 · 未读 0 · 更新 03:29:40」持续跳动）；离线横幅隐藏 | **0 错误 0 未处理拒绝** | 空态「等待活跃对话…」正常（截图 /tmp/ccc-audit-wall-idle.png） |
| 2 | 看板 `#/board` | ✅ 可用（只读） | 12 资源 200：`/board/summaries` `/projects` `/cards?page_size=1000` `/tasks/running` `/board/ready_for_merge` `/board/summaries?workspaces=tst` | 0 | 五列全 0 张；项目按钮「全部/管线自检」；**已关闭 2 张卡（tst997/998）无任何列展示**（截图 /tmp/ccc-audit-board.png） |
| 3 | 计划 `#/plans` | ✅ 可用 | 5 资源 200（plans/list 等 4 API） | 0 | 72 方案六列分布 1/3/1/5/56/6；筛选按钮 5 项目 |
| 4 | 计划→方案详情（mx-plan-004） | ✅ 可用 | `/plans/detail` 200 | 0 | 徽标/功能卡清单（3）/正文渲染正常；按钮集符合状态机（待验收→验收拍板+编辑+改状态，无转卡按钮） |
| 5 | 计划→待排期方案→「转为任务卡」弹层 | ✅ 弹层可用（**未提交**） | — | 0 | 节点② 弹层 2 功能卡默认全选（截图 /tmp/ccc-audit-plans-convert.png）；提交按钮未点（写必 401，且避免真实转卡风险） |
| 6 | 线路图总览→qb 详情 | ✅ 可用 | `/board/roadmap` + `/roadmap/qb` 200 | 0 | 里程碑 rail 可切换、子任务卡 4 枚、草案池 2 条带三动作；**里程碑 M1/M2/M3 各重复两次**（源数据问题，M4） |
| 7 | 运维 `#/ops` | ✅ 可用 | **14 请求**：6 并行 + 7 个 `/roadmap/{proj}`（N+1 实锤） | 0 | 闸门计数 48/3/0/0；螺旋循环 0；失败原因 Top 渲染正常 |
| 8 | 巡检 `#/dsh` | ⚠ 可用带缺陷 | `/ops/dsh-findings` 200；**`GET /Users/fan/.ccc/data/dsh/patrol-report-37.md` → 404** | 0（静默失败） | 「10 份报告 · 最新 4 天前」与摘要区「DSH 暂无巡检报告 🎉」**同屏矛盾**；原文折叠区「（无原文）」 |
| 9 | 控制台 `#/console` | ⚠ 可用带真值错位 | 15 请求全 200 | 0 | 12 区块全部渲染；**「服务开关：CCC Web 已停」vs 进程实跑**；**「已开发成果：CCC 控制台 7788 离线」vs 本页正开着**；中转站「异常（已退役）」常驻 |
| 10 | 卡详情→审批（transition 等） | ❌ 无法走通 | — | — | 看板无任何活跃卡可点（已关闭卡无入口）；且 curl 实证写端点 401（§2.2③a）。**「审批」环节在 web 上当前不可用** |

全程 7 页 × 约 60 个网络请求，**控制台错误/未处理 Promise 拒绝合计 0**；页面均无布局崩坏（4 张截图佐证：`/tmp/ccc-audit-board.png`、`/tmp/ccc-audit-plans-convert.png`、`/tmp/ccc-audit-roadmap-qb.png`、`/tmp/ccc-audit-wall-idle.png`）。

补充 SSE 直测：`GET /wall/api/stream` 首帧 `event: state` 正常；`GET /tasks/stream?ids=tst997` 首帧 `event: snapshot {"work_id":"tst997","lines":[]}` 正常。

---

## §5 免鉴权暴露面盘点（7788 无鉴权前提下可读到什么）

前置事实：`/health` 实测 `auth_required:false, auth_configured:false`；全部 GET 免鉴权直通（`server.py:1988-1990`）；写端点默认要 token（但 token 无法签发，见 H1）。服务绑 127.0.0.1 回环——暴露对象=本机任意进程 + 可建 SSH 隧道/端口转发的局域网用户。

| # | 接口 | 暴露内容（实测取样） | 敏感度 |
|---|---|---|---|
| 1 | `GET /dsh/workspaces` | DSH 全部会话：标题+时间+条数。**标题中直接出现疑似 API Key 明文 `sk-or-v1-****`（会话 1787564967）**；本地路径 `/Users/fan/DeepSeek` | 🔴 高 |
| 2 | `GET /dsh/sessions/<id>` | 会话**全文逐条消息**。实测含内网安全排查细节（「sshd_config `PasswordAuthentication no`」「192.168.3.116:22 OPEN」等） | 🔴 高 |
| 3 | `GET /wall/api/active` + `/wall/api/stream` | 全部会话 sid 枚举（archived 列表 20+）+ 实时会话内容流 | 🟠 中高 |
| 4 | `GET /projects` | 本机/另一机的**文件系统绝对路径**含用户名：`/Users/fan/program/apps/*`、`/Users/apple/...`（两台机器账号名） | 🟠 中 |
| 5 | `GET /ops/ports` | 全监听端口+进程名+PID（3080 node、3283 ARDAgent、3456 ssh、8091 …） | 🟠 中 |
| 6 | `GET /ops/portals` | LAN IP 与内网服务地址表（`http://192.168.3.116:7788/3080/8765/8091`） | 🟠 中 |
| 7 | `GET /ops/services` | launchd label 清单与运行态 + （若鉴权修复后可）远程启停服务入口 | 🟠 中 |
| 8 | `GET /plans/list` + `/plans/detail?path=` | 方案**全文**（业务意图/依赖/实施细节）；路径穿越实测被挡（`?path=../../../../../etc/passwd` → 404「方案不存在」） | 🟡 中低 |
| 9 | `GET /cards` + `/tasks/{id}` | 卡全文：标题/验收标准/失败原因/执行体（实测 tst997 返回验收标准全文） | 🟡 中低 |
| 10 | `GET /loop/findings`（86KB）/`/ops/dsh-findings`/`/ops/failures` | 内部巡检发现、卡 ID、日志绝对路径 | 🟡 中低 |
| 11 | `GET /config` `/health` | 端口分配、模型档位、版本（设计即公开，`server.py:441-444` 注释） | 🟢 低 |
| 12 | 前端源码本身 | `wallPage.js:522` 硬编码「账号 ccc；口令见服务器 ~/.ccc/web-auth.txt」——**口令存放位置对任何页面访问者可见** | 🟠 中 |

---

## §6 代码健康

### 6.1 体量与热点

| 指标 | 数值 |
|---|---|
| JS | 24 文件 / **6291 行**；CSS 8 文件 / **9521 行**；HTML 1 文件 50 行 |
| 最大单文件 | `css/components.css` 4596 行；`css/shell.css` 3854 行；JS 侧 `plansPage.js` 875 > `boardPage.js` 818 > `wallPage.js` 736 > `roadmapPage.js` 672 |
| 服务端 `server.py` | 4740 行（路由+handler+静态+鉴权一锅烩，前端重构时连带拆分的候选） |
| CSS 加载方式 | 8 个样式表**全站每页全量加载**（index.html 头部），无按页拆分、无 purge；components/shell 两文件含大量已拆除对话栈的遗留样式 |

### 6.2 死代码（未被任何路由/页面引用）

| 文件/符号 | 行数 | 证据 |
|---|---|---|
| `js/state.js` | 49 | 全仓无 import（对话栈状态机遗留） |
| `js/ports.js` | 44 | 全仓无 import（地址寻址已同源化） |
| `js/markdown.js` | 333 | 全仓无 import（带语法高亮的旧渲染器） |
| `js/api.js` 导出 `loadProjects` / `getBoardTask` / `searchCards` | ~40 | 零调用方（plansPage 自写 loadProjects、boardPage 直调 apiGet） |
| `plansPage.js` `loadCards()`（111-121）、`_globalKeydown`（91-96，监听器从未 add） | ~20 | 函数定义后零调用 |
| `js/utils.js` 导出 `scrollToBottom` `generateId` `desktopThreadId` `relativeTime` `resolveProjectPath` | ~60 | 零调用（settings.js 注释自认「唯一消费者 utils.resolveProjectPath 全仓无调用方」） |
| `js/api.js:28-29` 缓存白名单 `'/claude/projects'` `'/claude/sessions'` | 2 行 | 对话栈遗产死条目 |
| 合计 | **约 550 行 JS 可直接删除（≈9%）** | — |

### 6.3 重复实现（同功能多份）

| 功能 | 副本 | 位置 |
|---|---|---|
| Markdown 渲染 | ×3 | `wallPage.js:66-140`（mdInline/mdBlock/md）、`plansPage.js:725-825`（renderMarkdown）、`markdown.js`（死代码整份） |
| `esc` HTML 转义 | ×2 | `wallPage.js:61-64` 本地自写 vs `utils.escapeHtml`（ui.js 已统一 re-export，wallPage 未用） |
| `agoText` 时间差 | ×2 | `opsPage.js:22-28` 与 `dshPage.js:20-26` 逐字相同 |
| 幂等 innerHTML | ×3 | `consolePage._setHtmlStable`、`dshPage._setHtmlStable`、`ui.setHtml`（三份语义重叠） |
| `debounce` | ×2 | `plansPage.js:83-89` vs `utils.debounce` |
| 剪贴板复制 | ×3 | `boardPage.copyTextToClipboard`（带 execCommand 降级）、`shell-ui.copyCode`（同降级逻辑）、ops/dsh 页内联 `navigator.clipboard` |
| 项目配色 | ×1+兜底 | `plansPage.js:31-40` PROJECT_COLORS 硬编码 7 前缀，新项目靠 hash 兜底色 |

### 6.4 硬编码与隐患清单

| # | 位置 | 内容 | 影响 |
|---|---|---|---|
| 1 | `wallPage.js:522` | 「账号 ccc；口令见服务器 ~/.ccc/web-auth.txt」prompt 文案 | 口令存放路径泄漏给任何访问者 |
| 2 | `wallPage.js:527` | `username: 'ccc'` 硬编码 | 改账号即坏 |
| 3 | `index.html:22` | 导航栏品牌戳 `v20260824t1` 硬编码 | 已过期（真实 HEAD=f885fcd26），与资源戳两套口径 |
| 4 | `settings.js:55` | 「CCC v0.70.0（2017 单端 ：7788…）」硬编码 | 与 `/config.version`（同为 v0.70.0）双源会漂移 |
| 5 | `server.py:1952` | 缓存戳依赖源文件魔法串 `v=20260809t12` 替换（index.html 现存 11 处占位） | 魔法串被误改 → 全站 immutable 缓存失控 |
| 6 | `plansPage.js:31-40` | 项目前缀→颜色硬编码 7 项 | 新项目无主题色（有兜底，影响低） |
| 7 | `server.py:302` | 静态白名单 `/data/cluster.js` 指向不存在文件（实测 404） | 遗留映射 |
| 8 | IP/端口类 | **前端 JS 逻辑零硬编码 IP/端口**（全部同源相对路径，`ports.js` 注释确认；仅注释与文案提及） | ✅ 良好 |

### 6.5 错误处理缺失点

- 100 处 catch；其中大量 `catch (_) {}` 静默吞（wallPage 9 处、roadmapPage 8 处等）。多数属「localStorage/渲染兜底」可接受，但以下为**用户可见的吞错**：
  - `api.js:193-198` `apiDelete` **不抛错**（线路图「取消草案」失败时界面无任何提示，仅 toast 不出现）；
  - `dshPage.js:288-292` 原文拉取失败静默降级「（无原文）」（配合 M1 实际是永久静默失败）；
  - `boardPage.js:333-335` SSE 坏事件 `catch (err) { /* 忽略坏事件 */ }` 双处；
  - `app.js:76-87` 动态 import 失败有兜底错误态（良好✅）。
- 良好实践也存在：api.js 15s 超时+瞬时重试、pageScopeAbort 切页中止、各页 `_disposed` 卸载守卫、竞态序号（boardPage `_loadSeq`、plansPage `_detailSeq`、roadmapPage `_openProjectSeq`）——这套模式在 7 页重复实现了 7 遍（P2 应抽公共基类）。

---

## §7 问题总表

**分级：高=影响使用或安全；中=功能缺口；低=体验卫生**

| 级 | # | 问题 | 证据 |
|---|---|---|---|
| 🔴 高 | H1 | **全站写链路断裂**：写闸默认开（`CCC_WEB_WRITE_AUTH=1`，server.py:1994）+ 凭证未配置（`/config auth_configured:false`，`POST /session` 500）+ api.js 不带 token（api.js:105-118）→ 看板重新分派/作废/机审/误报、计划改状态/编辑/转卡/验收拍板、线路图全部 7 个动作、loop 留档、服务开关**全部 401**。「审批」主动线线上不可用，web 退化为纯只读墙 | curl 实测 401×2 + 500×1；api.js 源码；§4 步骤 10 |
| 🔴 高 | H2 | **DSH 会话镜像免鉴权全量暴露**：`/dsh/workspaces`、`/dsh/sessions/<id>` 返回全部会话标题与全文，含**疑似明文 API Key（sk-or-v1-****）**及内网安全排查细节；前端已不消费，纯遗留攻击面 | §5 #1/#2 实测摘录 |
| 🔴 高 | H3 | 墙写口令提示硬编码进前端（「口令见服务器 ~/.ccc/web-auth.txt」），任何访问者可读 | wallPage.js:522 |
| 🟠 中 | M1 | DSH 报告原文 fetch 断链：后端给文件系统路径、前端当 URL → 永远「（无原文）」 | server.py:3516 + dshPage.js:284 + 实测 404 |
| 🟠 中 | M2 | 控制台「服务开关」真值错位：运行中的 web 服务显示「已停」可点「启动」（launchctl 口径 vs 手动进程）→ 修复鉴权后误点会**双开服务** | /ops/services `running:false` vs ps 86493 |
| 🟠 中 | M3 | portals 探活对回环绑定服务失真：本页所在 7788 被标「离线」（用 LAN IP 探活） | /ops/portals `alive:false` vs 实际访问中 |
| 🟠 中 | M4 | `docs/projects/qb/roadmap.md` 里程碑段整份重复（12/22/33 行 与 44/47/50 行两套 M1-M3）→ 线路图页里程碑翻倍（6 个）、完成率失真；前端/后端均无去重告警 | grep 原文 + /roadmap/qb 实测 6 里程碑 |
| 🟠 中 | M5 | 已关闭卡在看板**完全不可见**（FLOW_COLS 无已关闭列，boardPage.js:20），「共 0 张」与 `/board/states` 已关闭=2 并存——历史卡在 UI 无检索入口 | §4 步骤 2 实测 |
| 🟠 中 | M6 | ops 页 `/roadmap/{proj}` N+1：每 30s 轮询追加 7 请求；代码注释自认 TTL 10s 缓存救不了（opsPage.js:492-494） | §4 步骤 7 Network 实录 |
| 🟠 中 | M7 | 巡检页空 findings 文案矛盾：最新报告解析 0 条时显示「暂无巡检报告 🎉」，同页却写「10 份报告」 | dshPage.js:82-84 vs :273-275 实测截图 |
| 🟠 中 | M8 | 中转站已退役仍渲染占位并令总览常驻「有注意项/中转站 异常」 | consolePage renderRelay + 实测截图 |
| 🟡 低 | L1 | 品牌构建戳硬编码过期（v20260824t1 ≠ HEAD） | index.html:22 |
| 🟡 低 | L2 | 版本号双源（settings.js:55 vs /config.version） | §6.4 #4 |
| 🟡 低 | L3 | 死代码约 550 行（§6.2 清单） | grep 引用计数 |
| 🟡 低 | L4 | 六类重复实现（§6.3） | 源码对照 |
| 🟡 低 | L5 | CSS 9521 行全站加载、对话栈遗留样式未清 | §6.1 |
| 🟡 低 | L6 | 错误契约不统一：`{error}` vs `{ok,error}` vs 静默；apiDelete 吞错 | api.js:193-198 |
| 🟡 低 | L7 | console 设置区读不存在的 `config.ports.relay` 恒「—」 | consolePage.js:378 |
| 🟡 低 | L8 | 缓存白名单含 `/claude/*` 死条目 | api.js:28-29 |
| 🟡 低 | L9 | 静态白名单 `/data/cluster.js` 404 遗留 | server.py:302 实测 404 |

---

## §8 重构与打通建议（唯一推荐 + 分期）

### 8.1 技术栈去留：**保留现有原生 JS + Python stdlib 栈，不换栈；做「约定化+组件化」轻改造**

理由（唯一判断，非选择题）：
1. **运行质量已过关**：7 页 60+ 请求实测零控制台错误、零布局崩坏；15s 超时/重试/竞态守卫/卸载清理等工程模式齐全。问题不在「框架不行」，在**写链路断（H1）、暴露面（H2/H3）、契约漂移（③类）、死代码**——换栈一个都解决不了。
2. **体量不支持换栈成本**：JS 总共 6291 行，React/Vue + node 构建链带来的工具链维护、部署复杂度（单机 2017、launchd 拉起）远超收益。
3. 现有「页面模块 + 动态 import」已经是天然代码分割；补一个 ~100 行的 PageBase 基类即可消掉 7 页重复的 mount/unmount/轮询/竞态样板。

### 8.2 信息架构调整

- 导航按时间语义分组：**现在时**（信息墙、看板）｜**计划时**（计划、线路图）｜**回看**（运维、巡检、控制台）——现有 7 项平铺无主次，首屏默认墙（观察面）符合定位，保留。
- 术语统一：方案池「已回写=待合入」双叫法并存（plansPage 流程条 vs 看板列名），统一「已回写」。
- 看板补「已关闭」折叠列（M5）：数据已在 `/cards` 返回里，纯前端增量。
- 设置面板收编「版本」单一来源（读 `/config.version`），删硬编码。

### 8.3 功能打通缺口清单（对应 §2.2，全部须在 P0/P1 落地）

1. 写链路打通（H1）：配置 `CCC_WEB_USERNAME`/`CCC_WEB_PASSWORD_HASH`（服务端已支持，`server/web/README.md:72-79`）；api.js 统一 Bearer 注入（复用 wallPage 的 `ccc_token` localStorage 模式）；401 统一弹「输入看板口令」正式 UI（替换 prompt，**删除 web-auth.txt 路径提示**）；`/config` 增加返回 `write_auth_enabled` 供前端判断降级。
2. 遗留接口下线（H2）：`/conversation`、`/projects/*/threads*`、`/dsh/workspaces`、`/dsh/sessions/*`、`/loop/dsh-report`、`/plans/create` 前端零消费 → 服务端直接摘除（或纳入鉴权门）；`/dsh/*` 若保留必须加鉴权。
3. DSH 原文端点（M1）：新增 `GET /ops/dsh-report?name=<白名单校验的文件名>` 由服务端读文件返回；前端改调它。
4. 探活口径（M2/M3）：`/ops/services` 补「进程在跑但 launchd 未注册」的第三态；portals 对 127.0.0.1 绑定服务改本机探活。
5. ops N+1（M6）：后端加 `GET /roadmap/all` 聚合端点（或 /roadmap/{proj} 响应加 30s Cache-Control）。
6. 状态重复数据（M4）：清理 qb roadmap.md 重复段 + 前端对同名里程碑去重并告警。
7. 空态文案（M7）：`!reports.length` 与 `!findings.length` 分开判断。

### 8.4 分期计划

| 期 | 交付 | 内容 | 工作量 |
|---|---|---|---|
| **P0 打通**（先做，1 个迭代内） | 「能写、不漏」 | H1 写链路四件套（凭证配置脚本 / api.js Bearer / 401 统一 UI / 删口令路径提示）+ H2 遗留接口下线或加鉴权 + M1 原文端点 + M2/M3 探活口径 + H3 随 H1 顺带删除 | **2–3 人日** |
| **P1 优化**（1–2 周） | 「干净、一致」 | 死代码删除 550 行 + 缓存死条目；重复实现合并（md 渲染/esc/agoText/setHtmlStable/debounce/剪贴板各留一份）；错误契约统一（`{ok,error}` + apiDelete 抛错）；看板补已关闭折叠列；qb 数据修复+去重告警；ops 聚合端点；版本戳单一来源（品牌戳改读 /config，废魔法串替换改模板注入）；中转站区块退役摘除 | **5–8 人日** |
| **P2 重构**（按需启动，2–3 周） | 「可长期演进」 | PageBase 基类（mount/unmount/可见性门控轮询/竞态守卫/SSE 生命周期统一，7 页各 -30% 样板）；API 表唯一登记（路径+参数+返回注释集中在 api.js，逐页对照可生成，杜绝契约漂移）；CSS 按页拆分 + 对话栈遗留样式清除（预估 components/shell 瘦身 ≥50%）；`server.py` 拆分（路由表/静态/鉴权/各域 handler 分文件）；如后续复杂度上涨可引入 lit-html 级微库（仍不进打包链） | **10–15 人日** |

P0 完成的验收口径：在看板上真实完成一次「打回卡→重新分派」与「已回写卡→机审」；计划页完成一次「待排期→转卡」；线路图完成一次「草案→确认转方案」；无 token 时全站写按钮统一出登录面板；`/dsh/sessions/*` 匿名访问返回 401。

---

## 附：实测产物清单

- 截图：`/tmp/ccc-audit-board.png`（看板）、`/tmp/ccc-audit-plans-convert.png`（转卡弹层）、`/tmp/ccc-audit-roadmap-qb.png`（qb 线路图重复里程碑）、`/tmp/ccc-audit-wall-idle.png`（信息墙空态）
- 关键 curl 取证：§2.2③a（401×2+500×1）、§4 SSE 首帧×2、§5 各接口响应摘要、§8.3 路径穿越 404
- 代码证据均带 `文件:行号`，可按当前 HEAD（0e7363c7b 及之后，`server/web/` 自 1726b0180 起零变更）直接复核
