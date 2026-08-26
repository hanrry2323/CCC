# CCC 教训 · 2026-08-26

1. **git_sync 对齐会秒级回吃 dispatch 未提交编辑**：卡文件/.md 任何修改必须与 `git add+commit+push` 一气呵成；只改不提交 = 数秒内被 `_force_align_dispatch` 还原为 origin/main（本日 tst005、ccc095 两度实证）。批量操作前可 SIGSTOP 三 watcher（engine/web/scheduler）实现竞态免疫，trap 保证恢复。
2. **engine 建 worktree 与出卡提交存在竞态**：卡落盘瞬间（未 commit）即被 2 秒级轮询扫描并创建 worktree，分支基点落后主树一拍 → 「worktree 无卡副本」防护闸无限跳过派发。解法：worktree 内 `git merge --ff-only origin/main` 对齐后下一心跳自动恢复派发。
3. **管理席直改卡也必须同步填写维护区**：否则机审门禁 Doc-Gate 打回 + 审计熔断连锁（本日 ccc095 首轮异席机审实证——回写区已填但维护区占位即遭「强制直接打回不予重试」）。
