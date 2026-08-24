# 任务卡 ccc085 · deploy 与 git_sync 的 FETCH_HEAD 并发竞态修复（DSH 执行）

> 关联：环节②交接(2026-08-25)问题1 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

消除 deploy-ccc.sh 的 git pull --ff-only 与 server/git_sync.py 周期性 fetch 对 .git/FETCH_HEAD 的并发无锁写导致的「Cannot fast-forward to multiple branches」间歇失败。

## 红线

- 白名单：scripts/deploy-ccc.sh、server/git_sync.py、server/tests/（如需回归）。
- 双侧同修（方向 A+B）：deploy 改 `git fetch --no-write-fetch-head origin main && git merge --ff-only origin/main`；git_sync.py:87 的 fetch 同加 --no-write-fetch-head。
- 不改 pull/ff 的既有成功语义（本地落后时仍能 ff）。

## 步骤

1. 修改两处命令形态；确认本机 git 2.39.2 支持 --no-write-fetch-head（git --version 取证）。
2. 自测：三守护常驻下连续跑 deploy-ccc.sh 全流程≥5 次（或等效仅执行其拉取段×10），0 次报 Cannot fast-forward；另造本地落后一 commit 场景验证仍能 ff 更新。

## 验收标准

- [ ] 连续≥5 次部署拉取零失败（附逐次输出）
- [ ] 落后场景 ff 更新行为不回归
- [ ] bash -n / py_compile 通过

## 回写要求

- 回写区附逐次跑批输出与 diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
