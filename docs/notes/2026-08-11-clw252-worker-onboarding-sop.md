# 252 Worker 接入与实跑 SOP（2026-08-11 · 集群 Worker 池）

> 状态：**技能同步已完成（--check OK）**；定时认领配置受阻于 252 SSH 不稳（banner 超时）。
> 本 SOP 记录 252(W9) 作为远端 Worker 的接入路径，供 SSH 稳定后或 252 本机执行。

## 背景

252（192.168.3.252，Windows，W9 Claude Code）是集群 Worker 池第一真实远端节点。
clw019 曾成功（252 主动认领执行只读审查）；本次 252 实跑闭环目标是**真跨节点执行 REMOTE 卡**。

**已确认**：252 SSH 22 端口通，但 banner exchange 频繁超时（历史已知问题）——连接间歇可用（成功窗口几秒），远程大量配置不可行，需 252 本机操作或先修网络。

## 已完成（M1 侧）

| 项 | 状态 | 证据 |
|----|------|------|
| 252 skill 目录建 | ✅ | `C:/Users/win/.claude/skills/ui-ux-pro-max/` + `code-review/`（SKILL.md 已传） |
| sync-skills 252 适配 | ✅ | c80ca4cd：Windows base64+python 传输 / python hashlib 校验 / SSH 重试容错 |
| 252 --check | ✅ | ui-ux-pro-max + code-review hash 一致 |
| 认领协议 v1 | ✅ | worker-claim.sh + Engine _claim_round + 超时回收（8c40e151） |
| 2017 模拟闭环 | ✅ | clw020 认领→回写→机审通过（audit=True） |

## 待办（252 本机或 SSH 稳定后）

### 1. 同步 252 的 CCC 仓
```bash
cd C:/Users/win/ccc && git pull origin main
```

### 2. 252 侧配置 worker-claim（Windows 计划任务，每 2 分钟）
```bat
:: 用 Git Bash 跑认领（252 有 git bash + python）
schtasks /Create /TN "ccc-worker-claim" /TR "C:\Program Files\Git\bin\bash.exe -lc 'cd /c/Users/win/ccc && WORKER_ID=W9 EXEC_TOOL=claude scripts/worker-claim.sh'" /SC MINUTE /MO 2 /F
```
> 说明：worker-claim.sh 认领前会自动调 sync-skills.py --check（skill 存在性校验）。

### 3. 认领执行验证
- 出一张 REMOTE 卡（执行体 W9 + 派发 scheduler，轻量运维任务）
- 252 计划任务认领 → 执行（claude）→ 回写 → Engine 收单 → 机审
- **证据**：执行痕迹在 252（`C:/Users/win/ccc` 下日志/产物），Engine 心跳 claim_collected 递增

### 4. SSH 稳定性处理
- worker-claim.sh / sync-skills.py 已带重试容错（4 次重试 + 30s 超时）
- 认领失败 → 卡保持待分派可重认领（断点续传兜底）
- 若 252 持续 banner 超时 → 建议先修 252 OpenSSH（升级/网络）再接入

## 验收标准

- [ ] 252 定时认领运行（计划任务在）
- [ ] 252 实跑一张 REMOTE 卡：认领→执行→回写→Engine 收单→看板已回写
- [ ] 执行痕迹在 252（非 2017）
- [ ] SSH 抖动时认领容错（不误判执行中）

## 风险

- **252 SSH 不稳**（banner 超时）是当前唯一阻塞——远程配置需重试窗口或 252 本机操作
- 若 252 无法稳定接入，2017 模拟闭环（clw020）已是认领协议的功能实证，集群实跑可等 252 网络修复
