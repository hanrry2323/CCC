# 方案 · DSH 信息墙并入 CCC 与前端深度融合路线

> 项目：ccc · 编号：ccc-plan-045 · 状态：已确定 · 作者：DSH（ox-alpha）· 工具：DSH
> 创建：2026-08-24 · 更新：2026-08-24
> 关联卡：无（ccc 前缀 taskable:false，平台自研直接开发）
> 关联方案：034-frontend-performance-rootfix（前端性能基线）· 043-dsh-execution-model
> 移交事实源：`~/program/apps/dsh-wall/docs/HANDOVER.md`（commit 782d960）

## 目标

把 dsh-wall 监控墙等价移植进 CCC（reader + API + 页面），对话入口替换为信息墙；
并给出 CCC 前端与 DSH/Cordis 深度融合的架构判断与分期路线。

## 背景

老板 2026-08-24 拍板：监控墙整体移植进 CCC 成为统一前端的组成部分，dsh-wall 终止独立维护；
后续以「CCC 一切皆插件 × Cordis 能力」做深度融合。当前最紧急任务：对话页职能由信息墙承接。

## 一、CCC 前端现状架构（巡检后事实）

```
2017 :7788 = server/web/server.py（stdlib ThreadingHTTPServer, HTTP/1.1 keep-alive）
├── 静态面：_STATIC_WHITELIST 显式映射 + legacy-chat/ 目录兜底（免鉴权，登录入口类）
├── 免鉴权 API 组：/health /config /projects /tasks/running /cards /tasks/stream(SSE)
│     —— 机制：路由分发位置在 _check_auth() 之前（非 _NO_AUTH_PATHS 集合）
├── 鉴权 API 组：Bearer token（_check_auth），T45 默认 auth_required=0 全放行
├── SSE 范式：text/event-stream + Connection: close + 15s 心跳 + 断连静默（034 定稿）
└── legacy-chat/ SPA（vanilla ES modules，无框架无构建）
      ├── 路由：hash router + 懒加载 import + 模块级 PAGES 注册表（045 巡检修复后）
      ├── 数据层：api.js TTL 缓存 + pageScopeAbort + 写后代次失效
      └── 七视图：chat(对话) / board / plans / roadmap / console / ops / dsh
```

**关键判断**：
1. legacy-chat 是「面向任务卡流程」的运维台；信息墙是「面向 DSH 会话执行」的实时观察面。
   二者数据源不同（dispatch 卡文件 vs `~/.dsh/sessions` 会话流），互补而非重叠。
2. 对话页的实质职能（向 DSH 会话发消息、看会话进展）墙已用官方 RPC（session.prompt queue）
   实现且更实时——替换成立。
3. server.py 单文件 4714 行已是集成热点，墙并入必须走独立模块（wall.py）+ 最薄挂线，
   避免继续膨胀 handler 类。

## 二、DSH 融合点评估（结合 Cordis「一切皆插件」）

| 融合点 | 现状 | Cordis 视角的终局形态 | 分期 |
|---|---|---|---|
| 会话只读镜像 | dsh_reader.py（历史）+ wall reader.py（实时流）双通道 | DSH 侧提供统一只读 Inspect Provider；CCC 订阅而非解析 | P2+ |
| 回写通道 | session.prompt queue RPC（信封已实证） | DSH Tool 化：CCC 出卡动作可直接注册为 DSH 工具调用 | P2 |
| 归档联动 | workspace.json archivedSessionIds 单向读 + RPC 写回 | 双向事件订阅（DSH event bus → 墙状态机） | P3 |
| 审批/提问帧 | 已实证不可行（不落盘、不在 Web 暴露、WS 私有握手）——见 HANDOVER §4.3 | 等 DSH 官方开放 pending 查询 RPC 后再接；禁止破解 WS | P3+ |
| 新建会话 | 未实证（Host 有 workspaceRegistry.create，Web 暴露名待查） | 只读探测 :3080 实证后再上「＋新建对话」 | P2 |
| 人格/KB 注入 | legacy-chat 经 6100 大脑桥 | 在 DSH preset 层解决，不走旧 /conversation（HANDOVER §五 P2 明确） | P2 |

**架构红线（从 HANDOVER §4.3 固化）**：零碰 DSH 核心、纯本地文件只读解析 + 官方 RPC 回写。
一切融合方案不得引入对 session.jsonl 结构之外的 DSH 内部耦合。

## 三、分期路线

### P1 等价移植（本次执行）
1. reader + 状态管理 + RPC 转发 → `server/web/wall.py`（单模块，自包含，逻辑照搬 dsh-wall 两文件）
2. API 并入 server.py：`GET /wall/api/active`、`GET /wall/api/stream`(SSE)、
   `POST /wall/api/dsh/prompt`、`POST /wall/api/dsh/archive`；路由置于鉴权门之前
   （与 /tasks/stream 同组，延续墙 LAN 无鉴权现状，auth_required=1 时行为与看板 SSE 一致）
3. 页面 → `server/web/wall/index.html`（单文件零依赖），三处绝对路径改 `/wall/*` 前缀，
   其余逐字节不动；顶栏加一枚「控制台 ↗」链接回 /app（唯一 UI 改动，防导航死胡同）
4. 入口替换：`/` 根路径改服务墙页（打开即墙）；legacy-chat 整体保留在 `/app`
  （回滚位），其 hub-nav「对话」标签改指 `/wall`
5. launchd com.dsh.wall（:3081）暂不停——CCC 侧实测通过后由老板择机执行 HANDOVER §六清库

### P2 对话升级（下期）
「＋新建对话」（先实证 session 创建 RPC）/ 历史抽屉 / 聚焦全屏阅读态打磨 /
legacy-chat 对话链路退役评估（board/plans/ops 等视图保留）。

### P3 清库退役
HANDOVER §六清单：final tag → README 归档声明 → launchctl unload → 仓库存档。

## 方案内容（本次改动清单）

> **P1.5 深度融合已执行（2026-08-24，老板指令升级：不做跳转页，直接融合 + 拆旧对话栈）**

| 文件 | 动作 |
|---|---|
| `server/web/wall.py` | 新增：reader 状态机 + 快照轮询线程 + DSH RPC 转发（自包含） |
| `server/web/wall/index.html` | 已删除：独立墙页被 SPA 视图取代（P1 过渡产物） |
| `server/web/server.py` | 挂线：import wall、serve_forever 启轮询线程、4 个 `/wall/api/*` 路由；`/` 与 `/wall` 均指统一壳 |
| `legacy-chat/js/pages/wallPage.js` | 新增：墙视图模块——稳定宿主模型跨路由保留、SSE 生命周期归 mount/unmount、主题跟随壳层 theme.js、格内对话走 /wall/api/dsh/prompt |
| `legacy-chat/css/wall.css` | 新增：墙样式自 v0.3.4 提取，全部 `#view-wall` 作用域化；主题令牌不重复定义（variables.css 单一来源） |
| `legacy-chat/index.html` | 重写壳：删除侧栏/composer/titlebar/login-view 等对话 DOM；hub-nav 首项「信息墙」+ ⚙设置入口；view-wall 容器 |
| `legacy-chat/js/app.js` | 重写瘦身：仅剩路由注册表+主题+toast 注册+设置入口（原 613 行对话装配全删） |
| `legacy-chat/js/api.js` | 精简：拆除 streamChat/会话历史长轮询/Claude·DSH 会话镜像/token 登录态；保留缓存/abort/超时/看板计划数据面 |
| `legacy-chat/js/router.js` | 默认路由 wall；chat 路由移除；showHubChatNotice 双壳分支退役 |
| 删除 24 文件 | message/composer/sidebar/attachments/toolCall/slash/quickPrompts/keyboard/fixedActions/titlebar/dualPane/streamRegistry/chatStatus/chatErrors/relayStats/export/boardPanel/taskDialog/artifacts/dispatchFormat/auth/agentAuth/login-gate/bootloader + dual-pane.css |

**已知边界（诚实声明）**：
- 服务端 `/conversation`、`/claude/*`、brain bridge 心跳等旧对话后端暂保留（本次拆前端栈；
  后端下线需先确认 ai-loop-router/Desktop 无外部消费）
- `auth_required=1` 模式下前端不再有登录 UI（默认 LAN 免登录不受影响）；如需可后续加独立最小登录组件
- legacy-chat 目录名暂不改（纯命名债，改目录=全量资源路径 churn，择机单独处理）

## P2/P3（更新）

- P2 对话升级：「＋新建对话」（先实证 session 创建 RPC）/ 历史抽屉 / 墙视图聚焦阅读态打磨
- P3 清库退役：✅ 已执行（2026-08-24 老板批准）——v0.3.4-final tag、launchd 卸载、
  :3081 下线、仓库存档至 ~/program/archive/dsh-wall；监控连续性验证通过

## 验收标准

- [x] 测试端口实例：`/wall/api/active` 返回真实 DSH 会话快照（与 :3081 形状一致）
- [x] `/wall/api/stream` SSE 首帧立即推送、15s 心跳、断连不炸线程
- [x] 格内对话 POST /wall/api/dsh/prompt 校验分支正确（真实发送走官方 RPC，老板实测）
- [x] `/` 返回统一壳且默认渲染信息墙；CDP 真浏览器冒烟：墙挂载/切页回归/零控制台错误/
      旧对话 DOM 零残留
- [x] pytest 全量与基线一致；ruff 通过；py_compile 通过
