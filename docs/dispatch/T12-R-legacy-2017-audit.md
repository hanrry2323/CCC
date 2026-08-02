# 任务卡 T12-R · 退役清单补核（2017 依赖方）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：已回写 · 日期：2026-08-02
> 前置：T12 验收打回（清单未覆盖 2017 依赖方）

## 打回问题清单（T12 未通过原因）

1. **2017 依赖方核实缺失**：任务书步骤 2 明列「2017 旧引擎进程（实测）、qb 产线引用」，清单只覆盖 M1 侧进程/plist/端口，未核实 2017 侧。
2. **实测事实（验收方）**：Mac2017 上旧引擎进程正在运行（`/Users/fan/program/CCC/scripts/ccc-engine.py`，验收实测 PID），qb 产线依赖 `scripts/`——`scripts/` 的退役放行条件必须包含「2017 旧引擎停止 / 切换到新栈」，当前清单缺失，处置顺序不完整。

## 目标

补齐 2017 依赖方核实（只读实测），更新退役清单的处置顺序与放行条件。

## 红线（先看）

1. **只读核验**：ssh 到 2017 仅执行只读命令（ps / lsof / ls / cat 配置），不修改、不停服务、不部署任何东西。
2. 不删除、不移动任何文件；不碰运行面；不读写外脑。
3. 验收标准不可自行解释；完成必须提交（真实 commit）。
4. 工作树只允许预存 1 个无关改动（`_update_handoff.py`）。

## 范围

- 只改：`docs/legacy-retirement-list.md`（补 2017 依赖方小节 + 放行条件）。
- 只读参考：2017 `~/program/CCC/`、`~/.ccc/`（engine.env、control.json、launchd、plist）。

## 步骤

1. ssh 2017 实测（只读）：旧引擎进程与端口、launchd 注册、`~/.ccc` 中指向 `scripts/` 的引用。
2. 核实 qb 产线对 `scripts/` 的依赖（2017 仓内引用 / 配置 / 启动链）。
3. 更新 `docs/legacy-retirement-list.md`：新增「2017 依赖方」小节（实测证据）；`scripts/`（及受 2017 影响的目录）退役放行条件补充「2017 旧引擎停止 / 切换到新栈」。
4. 提交 `docs(legacy):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 清单含 2017 依赖方实测证据（进程 / 端口 / 引用路径）。
2. `scripts/` 退役放行条件含「2017 旧引擎停止 / 切换」前提；处置顺序据此完整。
3. 零删除、零移动、零运行面动作（只读命令为证）。
4. 真实提交；工作树仅剩 1 个预存项。

## 回写要求

结果摘要（人话一句）、2017 实测证据、更新后的放行条件、commit hash；按契约 §3 同步更新本卡卡头状态。

## 回写区

### 结果摘要

SSH 只读实测 Mac2017，确认旧引擎 3 进程运行中（PID 28004/64950/89608），qb 产线依赖 `scripts/` 绝对路径引用，更新退役清单含 2017 依赖方小节 + 放行条件。

### 2017 实测证据

**旧引擎进程**：
- PID 28004: `ccc-engine.py` → 端口 7776, launchd `com.ccc.engine`, RUNNING
- PID 64950: `ccc-board` → 端口 7775, launchd `com.ccc.board`, RUNNING
- PID 89608: `ccc-chat-server` → 端口 7777, launchd `com.ccc.chat-server`, RUNNING

**Launchd plist**：3 个活跃（engine/board/chat-server），2 个备份

**`~/.ccc/` 配置**：
- `control.json`: mode=enabled, host_role=mac2017_orchestration
- `engine.env`: AGENT_PLANNER_BASE_URL=http://127.0.0.1:6100

**qb 产线依赖**：`~/program/apps/qb/.ccc/plans/` 中大量引用 `scripts/ccc-hub-lens.py`、`scripts/ccc-board.py`、`scripts/ccc-mind-update.py` 等绝对路径

### 更新后的放行条件

`scripts/` 退役放行条件新增：
1. **2017 旧引擎停止**：`com.ccc.engine`（PID 28004, 7776）、`com.ccc.board`（PID 64950, 7775）、`com.ccc.chat-server`（PID 89608, 7777）全部停止，launchd plist 卸载
2. `control.json`（2017）模式降为 `disabled` 或删除
3. qb 产线引用路径从 `scripts/` 切换到 `server/` 新栈命令

### 已验证红线

- ✅ 只读核验：仅 SSH 执行 ps/lsof/launchctl/list/cat，零修改、未停服务、未部署
- ✅ 零删除、零移动文件
- ✅ 工作树仅剩 `_update_handoff.py`（1 个预存项）

### Commit

```
d67b48b docs(legacy): T12-R 退役清单补核——2017 依赖方
```
