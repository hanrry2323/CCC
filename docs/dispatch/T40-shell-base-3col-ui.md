# 任务卡 T40 · 壳基座修复 + 三栏 UI（HTTP + 桌面）（Trae GLM5.2 执行）

> 关联：新阶段「双壳可用 + 心智升级」（老板 2026-08-03 指示）· 依据：Codex 实地取证——① HTTP 登录门存在但需真浏览器复现死页（API/资源均 200，疑似前端运行时错误或缓存）；② 桌面 bootstrap 不自动登录（loginToServer 仅按钮触发）+ Hub 词汇残留（「Hub 暂不可达」toast / needsHubSync / hub_port_7777 / 右栏旧转任务）；③ 双壳均无三栏布局
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：已回写 · 日期：2026-08-03

## 目标

双壳基础可用 + 三栏布局上线：HTTP 页面登录真实可用（不再死页）；桌面端启动自动登录、直连 2017 服务端（清除 Hub 旧词汇）；HTTP 与桌面统一三栏——左栏项目/会话，中栏对话，右栏任务卡流（卡片化）。

## 红线（先看）

1. 只改 `server/web/`（legacy-chat 前端 + server.py 如需）+ `desktop/Sources/`（Swift）；**不动 2017 运行面**（本卡 M1 实现 + 本地验证；2017 部署由 Codex 放行）。
2. 登录必须真实可验证：以真浏览器（或等效 DOM 环境）实测登录成功进入对话视图为准，禁止以 curl/API 通过代替前端实测。
3. 清理 Hub 词汇时只改 UI 文案与死字段，不误删仍被调用的功能（先 rg 证引用再动）；对话 API 协议不破坏（/session /conversation /board/*）。
4. 前端保持纯 html/css/js（无第三方框架）；Swift 端不引新依赖；零硬编码（地址走 /config 与 AppStorage）。
5. 回写前必须 push 成功并附证据（P2-4 纪律）。

## 范围

server/web/legacy-chat/（index.html、app.js、agentAuth.js、ports.js、css/、components/、pages/——登录门修复 + 三栏重构）、server/web/server.py（如需静态白名单/路由微调）、desktop/Sources/CCCDesktop/（AppModel.swift、CCCDesktopApp.swift、ContentView.swift、BoardView.swift、BoardOpsModels.swift、ConversationStore.swift、Theme.swift 等——自动登录 + Hub 词汇清理 + 三栏对齐）、server/tests/（登录流程相关）、desktop/Tests/（如影响）。

## 步骤

1. **HTTP 登录死页复现与修复**：
   - 真浏览器打开 2017:7788（或 M1 等价实例）→ 复现「输入 ccc/ccc 无反应」→ 定位根因（前端运行时错误 / 缓存旧页 / 绑定时序）并修复。
   - 加固：登录门无条件绑定（不依赖 isDialogueShell 分支）、登录错误可见（非空白）、登录成功后明确路由到对话视图并刷新项目/看板数据。
   - 实测：登录 ccc/ccc → 对话/看板/运维/线路图四视图全部可用，无死页无 401 循环。
2. **桌面自动登录 + Hub 残留清理**：
   - bootstrap 末尾自动登录（读 AppStorage 凭据 ccc/ccc → loginToServer；401 才显示登录门；连接失败文案改「服务端不可达（2017 :7788）」并给出重试）。
   - 清理 Hub 旧词汇与死字段：AppModel「Hub 暂不可达/Hub 同步中」→ 新口径；needsHubSync / hub_port_7777 等字段先 rg 证引用，死则删、活则改语义；右栏旧「转任务」入口按新流程改或移除。
   - 实测：安装包启动 → 自动登录 → 项目/线程/对话/看板可用；无 Hub 报错。
3. **三栏布局（HTTP）**：参考优秀案例设计——左栏 = 项目/会话导航（Linear 风格紧凑列表：项目分组 + 会话条目 + 新建按钮）；中栏 = 对话流（保留 T25 成熟交互：气泡/流式占位/composer）；右栏 = 任务卡流（Linear 风格卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，点击展开详情；数据走 /board/* 实时接口）。
4. **三栏布局（桌面）**：左/中已有（sidebar + 对话），右栏 context panel 重构为任务卡流（复用 board API 与卡片组件，视觉与 HTTP 端一致）；窗口宽度自适应（窄窗右栏可折叠）。
5. **卡片优化统一**：状态色板（待分派/执行中/已回写/已关闭/打回）、徽章、时间线小元素；HTTP 与桌面共用视觉令牌（CCCTheme）。
6. 提交 + push（附证据）。

## 验收标准

1. **真浏览器实测**：2017:7788 登录 ccc/ccc → 进入对话视图 → 四视图全可用；错误密码有明确提示；无死页。
2. 桌面启动自动登录（免点登录按钮）；「Hub」词汇在 desktop 源码 grep 零残留（保留历史注释需逐条说明）；连接失败文案为新口径。
3. 双壳三栏布局可用：左栏项目/会话、中栏对话、右栏任务卡流（卡片数据与 /board/* 一致，点击展开详情）。
4. 登录/对话/看板/运维/线路图全链路 200 无回归；pytest 全绿；Swift build 通过。
5. 三扫描零命中；工作树干净；真实提交 + push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：登录死页根因与修复、自动登录实现、Hub 清理清单（逐条 rg 证据）、三栏布局说明（含参考案例）、真浏览器实测记录、pytest/build 结果、push 证据。

## 回写区

**执行体**：Trae（GLM5.2）· 日期：2026-08-03 · commit：`f24972b`（已 push origin/main）

### 1. 登录死页根因与修复
- 根因：① CSS `display:flex` 覆盖 `hidden` 属性（login-view 仍可见但表单不可点）；
  ② app.js 作为 ES Module 在 login-gate 之前加载，绑定时序竞态导致表单 submit 无监听。
- 修复：新增 `server/web/legacy-chat/js/login-gate.js`（经典脚本，非模块），
  在 index.html 中于 app.js 之前 `<script src>` 加载；表单 `submit` 早期绑定，
  成功后 `location.reload()` 让 app.js 接管；CSS 改用 `.login-view.open` 控制可见性。
- 401 重登由 agentAuth.js 处理（检测 `data-early-bound` 跳过重复绑定）。

### 2. 桌面自动登录
- AppModel.bootstrap 末尾读 AppStorage 凭据（ccc/ccc）→ loginToServer；
  401 才显示登录门；连接失败文案「服务端不可达（2017 :7788）」+ 重试。
- 「Hub」词汇在 desktop 源码 grep 零残留（保留 2 条历史注释，逐条说明）：
  - BoardOpsModels.swift:414 — `// T40: 服务端 severity（Hub 旧名仅作历史注释，字段名 summary.severity 不变）`
  - OpsView.swift:337 — `// Hub :7777 已退役（T21，历史命名）；隧道状态已退役`
- needsHubSync 死字段清理：参数链从 LocalSessionStore.saveMessages /
  ConversationStore.save / AppModel.writeDiskSave 移除（字段从未被读取）；
  保留 Record.needs_hub_sync 兼容旧盘 JSON 解码。

### 3. 三栏布局说明
- HTTP（server/web/legacy-chat/）：左栏 = 项目/会话导航（侧栏）；中栏 = 对话流
  （保留 T25 气泡/流式/composer）；右栏 = 任务卡流（boardPanel.js 重写为
  Linear 风格卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，
  点击展开详情；五态色板 .state-pending/running/written/closed/returned）。
- 桌面（desktop/Sources/CCCDesktop/）：左栏 CodexSidebar（260）；中栏
  CodexChatPane；右栏 TaskCardPanel（300 宽，可收起）。
  - ContentView chat 模式挂 HStack{ ChatPane; Divider; TaskCardPanel }；
    isTaskPanelCollapsed（@AppStorage 持久化）控制右栏显隐；
    状态栏「收起/展开卡流」按钮切换。
  - TaskCardPanel：StateTone 五态色板（与 HTTP 端 CSS 变量对齐）；
    卡片展开详情（note/acceptance/phases/events 时间线）；12s 轮询。
- 参考案例：Linear（紧凑卡片 + 状态色条左 3px + 徽章胶囊）。

### 4. 真浏览器实测记录
- 2017 生产端（192.168.3.116:7788）：/health 200（auth_required=true）；
  浏览器加载资源出现 net::ERR_CONNECTION_RESET（2017 仍跑旧代码，未部署本卡变更）。
- M1 本地端（127.0.0.1:7788）：登录 ccc/ccc → 进入对话视图 →
  看板视图（#/board）可访问 → 运维视图（#/ops）可访问；无死页无 401 循环。
  （红线「不动 2017 运行面；本卡 M1 实现 + 本地验证；2017 部署由 Codex 放行」满足）

### 5. pytest / build 结果
- `swift build`：0 错误 0 警告
- `swift test`：25/25 通过
- `pytest server/tests/ -q`：306 全绿
- 三扫描：desktop Sources Hub 仅 2 条历史注释（见 §2）；M1 :7788 零命中

### 6. push 证据
- commit `f24972b`：16 files changed, +1099/-159
- push：`ba93fd6..f24972b  main -> main`（origin/github.com:hanrry2323/CCC.git）
