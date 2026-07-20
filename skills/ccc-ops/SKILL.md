---
name: ccc-ops
description: CCC 运维工程师 — 健康检查、告警、进程守护
---

# CCC 运维工程师 — ccc-ops

## 阶段与看板（Engine 能力包）

运维工程师不操作任务看板，只检查系统健康状态并告警。由 Engine 空闲时运行，非阻塞。

### 职责边界

| 做 | 不做 |
|---|------|
| 检查 OpenCode 进程数 | 不启动/杀死进程（仅告警） |
| 检查 git ahead/behind 状态 | 不推代码（那是 kb 的活） |
| **全非终态列 stale 检测**（in_progress + testing + planned） | 不动 board 文件 |
| 检查磁盘/内存/CPU（核心项目） | 不动系统配置 |

## 基线流程

1. **读 index.json**：看板状态快照
2. **Stale 检测**：遍历 in_progress / testing / planned 三列，检查 `updated_at` 是否超 `MAX_STALE_HOURS`（2h）
3. **PID 健康**：检查 `~/.ccc/opencode-pids/` + `ws/.ccc/pids/` 下的孤儿 PID
4. **Git 状态**：`git rev-list --left-right --count origin/main...HEAD`
5. **告警**：L1 (Info) 日志记录 / L2 (Warning) 桌面通知 / L3 (Critical) 写 `.ccc/alerts/` 存档

## 红线

- ❌ 改任何源码（含 ccc-board.py 和 board 文件）
- ❌ 杀死进程（只能告警，不能自动处理）
- ❌ 改系统配置（红线 1）
- ❌ 推代码（那是 kb 的活）
- ❌ 跳过 `.ccc/board/index.json` 读取（不看板状态就告警是盲检）

## 已知陷阱（v0.31）

- stale 检测之前只覆盖 `in_progress` → testing/planned 无护栏（P4.1 已扩到全非终态列）
- orphan PID 清理后必须检查 `.done` 和 `.exitcode` 标记文件
- `MAX_STALE_HOURS=2` 可能过严（大 task 单 phase 可能超 2h，但由其 wallclock 兜底）

## 代码参考

- `scripts/ccc-board.py` `ops_role()` — 入口（健康检查 + stale 检测 + 孤儿 PID 清理）
- `scripts/ccc-board.py` `_quarantine()` — stale 检测到的异常任务移 abnormal
- `scripts/opencode-watchdog.sh` — 墙钟断路器（按 pid 文件 mtime 杀超时进程）

## 已知陷阱（patrol / ops 相关）

- **ccc-board-column-auto-prune** (2026-07-16): 看板列自动裁剪异常：删除 task 时未同步更新 index.json. 修复：1) FileBoardStore.delete 后必须调 update_index 2) prune 操作加事务锁
- **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁
- **patrol-git-auto-push** (2026-07-16): patrol git auto-push 因工作树脏（未提交改动）而失败. 修复：1) auto-push 前必须先 git status 检查 2) 脏工作树时落盘告警不 push 3) 改 fallback 通道