# 2026-09-02 · tst 预演卡残留清理收尾记录

> 日期：2026-09-02 20:55 CST · 席位：CCC 2017 管理席（S116-01） · 类型：鉴证+清理收尾 · 关联：tst994/995/996
> 依据：DOC-PROTOCOL（六态/作废终态）；archive-cards.sh 已核对非本场景；清理目标 = 作废/已关闭卡残留的工作区与分支。

## 一、清理动机

看板真相源 `~/.ccc/data/cards/cards.index.jsonl` 现有 6 张 tst 预演卡，全为终态（3 已关闭 / 3 作废）。
核对三种操作后确认：`archive-cards.sh` 仅归档「关闭超 6 个月」卡，不适用 08-30 临期卡；作废卡按协议**保留历史、不删文件**。
故「丢弃」「清理」的正确落点 = **清除残留工作区与分支，保留卡文件终态记录**。

## 二、残留清删明细

| 卡 | 状态 | CCC 仓 | ccc-tst 业务仓残留 | 处置 |
|---|---|---|---|---|
| tst994 | 已关闭 | worktree `/private/tmp/ccc-base-*`（detached·prunable） | 本地分支 `codex/tst994-pipeline-drill-add3`、远端分支同、worktree `~/.ccc-wt/tst/tst994` | see 三 |
| tst995 | 作废 | 无 | 无 | 本干净 |
| tst996 | 作废 | 无 | 无 | 本干净 |

## 三、tst994 清理动作（ccc-tst 仓）

1. 安全检查：`git log main..5e8813a` = 空 → 开发 commit `0e1580c`（add 纯函数/单测）已合入 main，清删不丢产物。
2. 删除 worktree `~/.apps/.ccc-wt/tst/tst994`（`--force`，含 `__pycache__`/.pytest_cache），无未提交/未合入改动。
3. 推送删除远端分支 `origin/codex/tst994-pipeline-drill-add3`。
4. 删除本地分支 `codex/tst994-pipeline-drill-add3`（was `5e8813a`）。

## 四、终态核验

- ccc-tst 仓：`git branch -a` 无 tst99/codex 残留；`git worktree list` 仅 `main`。
- CCC 仓：主树分支空、worktree 仅 `main`；含卡号分支全空。
- 卡文件 `docs/dispatch/tst/tst99{4,5,6}-*.md` 保留为终态历史记录（已关闭/作废），板面不显示。

## 五、未动之作

- tst997/998/999（已关闭，非本清理目标）未动。
- 三张作废卡文件按协议不删、不移档案区。
- 看板 0 待办、无未合入代码；平台 HEAD=`3ff539fa4` 与线上一致。