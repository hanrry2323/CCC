# M5 里程碑（2026-08-07）

> 北星不变。冻结心智补丁。

## 结论

Engine `--audit` 真机审狗粮跑通：`ccc007` 有 `audit.log` + 生产卡 `## 机审区`（非 `first-audit-evidence`），已进 `/board/ready_for_merge`。出卡模板加一行 rebase 提醒。xy002 仍执行中 → 挂账。

## 交付

| 项 | 证据 |
|----|------|
| 真机审 | 2017 `~/.ccc/logs/exec/ccc007.audit.log`；runner `{"audited":["ccc007"]}`；卡头机审：通过 |
| rebase 提醒 | `scripts/new-card.sh` 步骤含 `git rebase origin/main`；dry-run 命中 |
| ready | `GET /board/ready_for_merge` → ccc007；分支 `codex/ccc007-m5-audit-dogfood-rebase-hint` @ `4c93d9f` |
| 回归 | `pytest server/tests/` 全绿；`new-card --project cd --dry-run` 含 rebase |

## 挂账

| 项 | 状态 |
|----|------|
| **xy002** | 执行中（OpenCode 扫 `/Users/fan/program/apps/xianyu`）；未回写 → M6 |
| **ccc007 合入** | 待老板人审 diff 后「合入批准」 |

## 度量

| 指标 | 结果 |
|------|------|
| 老板调度 | 1（批 M5） |
| Engine 真机审落盘 | 1（ccc007） |
| 新 SOP | 0 |
