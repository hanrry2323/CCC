# 方案 · clwarp agent 状态感知机制（屏幕特征→状态）

> 项目：clw · 编号：clw-plan-004 · 状态：作废 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-11 · 更新：2026-08-13
> 关联方案：clw-plan-001/002/003（此前均为可用性收口，本方案引入 agent 语义层）
> 参考案例：herdr `src/detect/manifests/*.toml`（Apache-2.0，调研报告见 reference/herdr/ANALYSIS-for-clw-2026-08-11.md）

> **状态说明**：本文档为**机制设计文档**，先落盘供老板使用 herdr 后对比体会；实现出卡前需老板确认。参考 herdr 的直接体验由 M1 herdr 实例提供。

## 目标

给 clwarp 增加 **agent 状态感知**：侧边栏每个会话不再是「存在/不存在」二元，而是实时显示 **working（干活）/ blocked（等审批/提问）/ idle（空闲）/ unknown** 四种状态，并据此提供「谁卡住了」「谁在干活」的一眼视图。这是 clwarp 从「终端显示器」升级为「agent 驾驶舱」的分水岭能力。

## 背景

- clwarp v0.3.0 现状：侧边栏只有会话树 + Git 状态，**不知道 agent 是在干活、等审批还是卡死**
- 参考案例 herdr 已实现：19 种 agent 的「屏幕特征→状态」检测清单，纯后端读 PTY 缓冲实现，agent 升级用「证据化快照门禁」控制漂移
- 老板已确认 herdr 直接使用（M1 安装完成），后续把该机制补齐到 clwarp

## 机制设计（核心）

### 1. 状态模型

| 状态 | 含义 | 判定依据（示例） |
|------|------|-----------------|
| working | 正在执行任务 | 屏幕出现「esc to interrupt」「ctrl+c to interrupt」等运行中提示 |
| blocked | 等待人工输入 | 屏幕出现「esc to cancel」「enter to confirm」+ 导航提示等审批/提问 UI |
| idle | 等待下一条指令 | 无运行/审批特征，提示符就绪 |
| unknown | 无法判定 | 有 agent 进程但特征不匹配（不证明完成） |

### 2. 检测架构（照 herdr 解耦）

```
PTY 输出缓冲（Rust 后端已具备）
      ↓ 采样
屏幕快照（bottom 区域 / OSC title / 整屏近屏）
      ↓ 匹配
检测清单（声明式 TOML，每个 agent 一份）
      ↓ 命中
状态机（working/blocked/idle/unknown 收敛）
      ↓ 事件推送（Tauri Event，沿用 clw009 事件链路）
前端侧边栏状态灯
```

原则（照 herdr AGENTS.md）：
- **检测解耦**：detector 只读屏幕快照，不碰 PTY 解析/渲染状态
- **证据化**：改检测规则必须先抓真实底栏快照（`herdr agent read <pane> --source detection`），AND/OR 显式编码，禁止凭猜
- **不匹配整窗文本**：状态判定只认固定控件/底栏，不匹配用户可见视口（用户可滚动）

### 3. 检测清单结构（示例 · 仿 claude.toml）

```toml
id = "claude"
aliases = ["claude-code"]

[[rules]]
id = "live_blocked_form"
state = "blocked"
priority = 980
region = "after_last_horizontal_rule"
visible_blocker = true
contains = ["esc to cancel"]
any = [
  { contains = ["enter to confirm"] },
  { contains = ["enter to select"] },
]

[[rules]]
id = "interrupt_hint_working"
state = "working"
priority = 110
region = "whole_recent"
visible_working = true
any = [
  { contains = ["esc to interrupt"] },
  { contains = ["ctrl+c to interrupt"] },
]
```

- 每规则 = 区域（`bottom_non_empty_lines(N)` / `osc_title` / `after_last_horizontal_rule` / `whole_recent`）+ 关键字/正则 → 状态
- 优先级高者先命中；无命中且进程存活 → idle/unknown
- 覆盖范围：先做 claude/codex/opencode 三份（对应 clwarp 已支持的 3 provider），不追 19 种

### 4. 事件与前端

- 沿用 clw009 的 Tauri Event 推送链路（`terminal-output` 已实时推）→ 新增 `agent-state` 事件，携带 `{ pane_id, agent, state }`
- 侧边栏会话项加状态灯：绿=working、黄=blocked（含「等审批」提示）、灰=idle、问号=unknown
- blocked 时可点击聚焦到对应终端（现有 focus 逻辑复用）

### 5. 范围外（本期不做）

- agent 互驱（等另一 agent blocked 再接手）——留待与 CCC Worker 池（ccc-plan-020）结合时单独立项
- socket API server 化——留待远程中继方案
- 会话持久化/恢复——单独方案（clw-plan-005 候选）

## 验收标准（草案）

- [ ] claude/codex/opencode 三份检测清单落地，四态（working/blocked/idle/unknown）判定可复现
- [ ] 侧边栏状态灯实时更新，blocked 态有明确视觉提示
- [ ] 改检测规则前必须抓快照留档（证据化门禁），agent 升级导致特征漂移时能快速定位
- [ ] 回归：终端交互/会话切换不回归（沿用 clw015 保活、clw016 CSP）

## 备注

- 本方案为 clw **v0.4.0 候选主线**，排在远程中继/持久化之前（状态感知是「驾驶舱」语义的第一块）
- herdr 是**成熟参考实现**：`/Users/apple/program/reference/herdr/src/detect/manifests/` 19 份清单 + `src/detect/manifest.rs` 可整段借鉴思路（Apache-2.0，搬运需保留版权声明）
- 老板验证路径：先用 M1 herdr 实测状态灯效果（working/blocked 判定是否符合直觉）→ 再回来拍板本方案细节
