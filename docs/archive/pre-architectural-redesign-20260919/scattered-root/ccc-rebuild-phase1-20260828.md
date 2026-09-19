# CCC 重建 Phase1 交付报告（rebuild/phase1 · 2026-08-28）

> 交付 = 清场 + 后半段自动闭环（已回写→CC审核→合入→提交→部署→探活→终态）。
> 方式：指令直改，不走 CCC 出卡流程；只读 config.env 未改任何风控配置。

---

## 一、任务一 · 清场清单（验收①）

### 1.1 备份（硬前置 · 先于一切改动，已完成并验包）
目录：`~/program/ccc-backup-rebuild-20260828/`

| 包 | 大小 | 内容 | 验包 |
|----|------|------|------|
| ccc-git-full-20260828.bundle | 19M | git bundle --all 全仓全 refs 历史 | `git bundle verify` OK（完整历史） |
| ccc-home-data-20260828.tar.gz | 301K | ~/.ccc/data 生产数据根（5.4M→压缩） | tar 退出 0 |
| ccc-repo-data-dispatch-20260828.tar.gz | 4.6M | 仓内 data/ + docs/dispatch + docs/archive | tar 退出 0 |
| ccc-worktree-backend-rework-20260828.tar.gz | 11M | 待删分支的 worktree 检出 | tar 退出 0 |

### 1.2 卡 / 索引清零
- `docs/archive/ccc-tasks/` **295 个归档卡文件删除**（rebuild/phase1 提交 `0d3349c4f`；**main 同步提交 `f00aec73e`**）。
- `docs/dispatch` 旧活动卡（tst006）删除。
- 三份索引：`docs/dispatch/cards.index.jsonl`（删除）、`data/cards/cards.index.jsonl`（删除）、`~/.ccc/data/cards/cards.index.jsonl`（删除）。
- 实测：**归档 0 文件；dispatch 仅剩 1 张新验收卡 tst997**；生产索引再生后仅含 tst997（旧卡在索引中为 0 记录）。

### 1.3 分支 / stash
- 删除本地分支 6 条：ccc-audit-v6、codex/ccc089-loop-infra-loop、codex/engine-refactor-e1e2、feat/047-unification、feat/frontend-rework、repair/scripts-v6-pin-plans-status。
- 删除 origin 远端分支 4 条：上述 3 条 + codex/tst006-e2e-add-smoke。
- 清理 stale ref：refs/remotes/golive/main、refs/bundle/f3/f32/f33。
- **5 条 stash 全清**。
- 实测：`git branch -a` = main + rebuild/phase1（+ origin/main 跟踪）；`stash list` = 0；`git status` 干净。

---

## 二、任务二 · 后半段闭环开发与流程测试（验收②）

### 2.1 交付物（rebuild/phase1 上逐步提交，非一锅端）
| commit | 内容 |
|--------|------|
| 0d3349c4f | 清场（归档/活动卡全清，历史留备份） |
| 6b945aa40 | phase2 模块 + 引擎挂接 + 单测 12 项 |
| 957c25d4f | 补 import json（ruff F821） |
| 6271b3f88 | 扫描扩展至 origin/codex/* 分支信封（已回写事实源） |
| 11e65cdbf | 分支名去 origin/ 前缀修复 |

- 新模块 `server/engine/phase2.py`：已回写 → CC 审核（claude -p，**失败重试 ≥3 次退避，耗尽 ledger 告警、卡保留已回写不静默丢卡**）→ 不通过自动打回+告警（不阻塞其他卡）→ 通过则合入 main → 门禁 → 提交 push → 部署 web → /health 探活 → 已关闭；部署失败自动重试。`--once` / `--daemon`；`--audit-driver` 测试隔离。
- 引擎挂接 `server/engine/main.py`：run_loop 每轮 + `--once` 自动调用 consume_once（事件感知 + 轮询兜底，**10 分钟 SLA**，实测 40s 内消费）。
- 单测 `server/tests/test_phase2.py` **13 项全绿** + ruff 通过。

### 2.2 流程测试实录（带时间戳）

**测试卡**：`docs/dispatch/tst/tst997-phase2-e2e.md`（状态已回写，模拟 DSH 前半段产物）→ 分支 `codex/tst997-phase2-e2e` 推 origin。

**Phase A — 真实 CC 驱动（fail-safe 验证）23:05:33 → 23:06:15（42s）**
```
scanned=1（分支信封识别）
claude 调用 rc=1（opencode.ai 网关 429 周配额，deepseek-v4-flash）
→ 重试 1/3、2/3、3/3（退避 5s/10s）
ledger 落 phase2_audit_fail（ts 2026-08-28T15:06:15Z）
卡保留「已回写」——不静默丢卡 ✓
```

**Phase B — mock:pass 驱动（全链闭环）23:06:55 → 23:07:01（6s）**
```
门禁「python3 -c print('phase2-gate-ok')」通过
合入 codex/tst997-phase2-e2e → main（ff，origin/main 顶层 = b480001f0 关闭提交）
卡置「已关闭」+ 机审区（结论：通过）→ 提交 → push main
部署拉起 web :7788（PID 12088）→ /health 探活 200
ledger 落 phase2_pass（ts 2026-08-28T15:07:01Z）
结果 {"scanned":1,"closed":1,...} ✓
```

**看板终态验证（main 检出 + web 重启后）**
```
curl :7788/cards → total=1
tst997 → {"state":"已关闭","board_column":"已关闭"}
web :7788 /health = 200（部署后存活）
```

**调试迭代（Phase B 两处 bug，均已修 + 单测覆盖）**
- 23:06:23 `fetch origin/origin/codex/...` → 分支名去 origin/ 前缀（11e65cdbf）
- 23:06:44 checkout main 被未提交改动阻断 → 工作区需干净（见遗留 4）

### 2.3 SLA 论证
触发 = 引擎 run_loop 事件感知（dispatch mtime 变化即触发）+ phase2 daemon 20s 轮询 + 引擎 heartbeat 兜底；本测试卡从出现到消费 ≤42s，远低于 10 分钟。

---

## 三、遗留问题记录（不顺手修，留后续轮次）

1. **【外部阻塞·高】真实 CC 审核被 opencode.ai 网关周配额拦截**（429，deepseek-v4-flash，约 08-30 重置）。Phase1 全链用 mock:pass 驱动验证通过；真实调用路径已验证 fail-safe（重试+告警+不丢卡）。配额恢复后 PHASE2_AUDIT_DRIVER 默认即 real，无需改码。
2. legacy DSH 机审 worker（main.py _run_audit_worker）仍在引擎内未拆除；本次 E2E 用 phase2 daemon 直跑（引擎 run_loop 挂接已就位）。拆除 legacy audit 属后续轮次。
3. 部署范围 = web(:7788)+探活；引擎服务部署与跨仓（业务仓）合入部署未纳入 Phase1。
4. phase2 依赖工作区干净（分支切换）；生产 main 检出下天然满足，dev 分支需先提交。
5. 分支消费后未自动删除 codex/* 分支（本次测试分支已手动删）；自动删分支入后续。
6. 主仓 data/cards/cards.index.jsonl 会被 loader 再生（gitignored 缓存）；「单一事实源」收敛（问题审计 R1）未在 Phase1 根治，入后续轮次。
7. main 与 rebuild/phase1 已同步清场；rebuild/phase1 含 phase2 代码（未合 main），main 含 tst997 验收卡。
