# 任务卡 T65 · T-B5 双壳对齐（桌面端补齐 HTTP 新能力）（Claude Code 执行）

> 关联：前端四板块架构（T-B5 双壳对齐）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t65 -b codex/t65-dual-shell-align origin/main`；分支 `codex/t65-dual-shell-align`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

桌面端与 HTTP 壳关键能力对齐：看板三视图切换、右栏关联卡流 + task_status 联动、控制台驾驶舱样式、免登录直连。

## 具体项

1. **看板三视图**：桌面端 BoardView 对齐 HTTP 三视图（列表默认/Kanban/分组切换，复用现有数据源 + 视图切换 UI）。
2. **右栏关联卡流 + task_status 联动**：桌面右栏 TaskCardPanel 支持关联过滤（当前项目未关闭 + 会话关联）与对话内 task_status 事件实时刷新（Swift 流式事件处理已有，补 task_status 分支）。
3. **控制台驾驶舱样式**：桌面 OpsView/控制台对齐 HTTP 驾驶舱（计数/注意清单/后台进程）。
4. **免登录直连**：确认桌面免登录模式（auth_required=false 直连，已有）实测。
5. 构建 + 测试 + 老板实测窗口。

## 红线

1. 只改 desktop/Sources/CCCDesktop/（BoardView、TaskCardPanel、AppModel、ContentView、OpsView、StreamTests）+ desktop/Tests；**禁止改 server/（T64 所有权）**。
2. 复用现有 Swift 组件与 StateTone 色板；不引新依赖。
3. 回写前 push 成功并附证据。

## 验收标准

1. 桌面看板三视图切换可用（与 HTTP 行为一致）。
2. 右栏关联过滤 + task_status 事件刷新实测（Swift 测试/模拟）。
3. 控制台驾驶舱样式对齐；免登录直连正常。
4. swift build 0 警 + swift test 全绿；push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：对齐项实现、Swift 测试、build 结果、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
