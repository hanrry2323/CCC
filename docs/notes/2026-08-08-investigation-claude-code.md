> ⚠️ 史 · 2026-08-08：排查指令

# 排查指令 · CCC 产线深度问题排查（2026-08-08）

> 角色：你是 CCC 平台的产线排查工程师。任务：**只读排查、不修改任何代码/配置/生产文件**，按下面 5 个问题逐一定位根因，输出结论报告。
>
> 工作目录：`/Users/apple/program/CCC`（M1 主仓，git 已同步 origin/main）。
> 可读：本仓源码 + `docs/dispatch/*/*.md` 卡文件 + 2017 只读日志（`ssh fan@192.168.3.116` 仅 `ls/cat/tail/ps/git log`，**禁止写、禁止改生产**）。

---

## 背景

CCC 产线 08-07 → 08-08 自动化跑了 60 张卡、314 个执行事件、总时长 61.3h。发现三类**假失败**（大量重试空转 + 超时），需要你确认代码根因并给修复方向。真实打回率其实很低，问题集中在「门禁误判」和「重试失控」。

## 排查问题（按优先级）

### P1. 机械门禁「exit 0 但无有效产物」误判 → 死循环重试

**现象**：`xy018` 开发实际完成（代码已 push 到 `codex/xy018-*`、12 项 pytest 过、回写区已填），但被机械门禁判「exit 0 但无有效产物」→ 连续重试 20 次 → 7200s 超时。证据：
- `/Users/fan/.ccc/logs/exec/xy018.log` 尾部（已完成 push 的完整输出）
- worker-events：`xy018 run fail 20 次 + timeout 1 次`

**待查**：
1. `server/engine/main.py:928-948`（机械门禁）判定条件 `_worktree_has_new_commit` + `_worktree_has_nonempty_diff`。为什么已 push 的卡还会判定失败？
2. 是否因为「分支已 push 到 origin 但 worktree 本地相对 `origin/main` 无 diff」——`origin/main..HEAD` 是**本地未合并提交**，若执行体先 rebase 了 origin/main 或提交被 push 后分支落后，diff 判定就失真？
3. 失败后重试时，卡状态从 `已回写` 回退到 `待分派`，再派发是**新建 worktree 还是复用旧 worktree**？旧 worktree 残留会不会导致新派发时 diff=0？
4. `server/engine/main.py:568-596` 的判定是否应该换成「相对 **push 后远端分支**」而非本地 `origin/main`？

### P2. 已关闭卡在「死分支」上反复被拉起续审

**现象**：`mx015` 代码正确、机审通过，但引擎在一条**落后 9 个提交的死分支**上反复拉起机审 21 次 + 1 超时；实际卡早已在 main 关闭。证据：
- `/Users/fan/.ccc/logs/exec/mx015.audit.log` 尾部（机审席自己写明「main 上已关闭，不应重开审计」）
- worker-events：`mx015 run fail 21 次 + timeout 1 次`

**待查**：
1. 机审/收单前是否检查「卡当前是否已关闭」（`server/engine/main.py:472` 只有 worktree 清理时才遍历 CLOSED；收单/机审候选是否漏了这个 guard）？
2. `_run_machine_audit_after_writeback` / `_audit_round`（`main.py:1145` / `:1506`）拉机审时，是否校验 worktree 分支相对 `origin/main` 已过时/落后？
3. 「打回 → 待分派」自动重试时，`store.py:217-220` 的 `retry_count` 上限有没有生效？为什么能重试 20+ 次？

### P3. 「干净树 / 空提交」被当失败

**现象**：`hp009`/`hp010`/`hp011` 等已实际完成并 push，但出现 `nothing to commit, working tree clean`（第二次提交无新改动，git 返回非 0）→ 被记为「退出码非 0」→ 各重试 4–5 次。证据：
- `/Users/fan/.ccc/logs/exec/hp011.log` 尾部（"nothing to commit" + 已完成描述）
- worker-events：`hp009 run fail 5 次`、`hp010 run fail 4 次`、`hp011 run fail 4 次`

**待查**：
1. 执行体模板（`server/config/executors.json`）要求「完成 commit+push + 更新卡头为已回写」。若执行体分两次 commit（一次业务代码、一次卡头），第二次 `git commit` 遇到干净树返回非 0 → `_dispatch_and_collect` 判失败。
2. 收单判定（`main.py:958-966` 退出码非 0 即失败）是否应该把「git 输出含 `nothing to commit`/`Everything up-to-date`」识别为**无害信号**而不是失败？
3. 执行体卡流程模板是否应该改为「先检查 diff 再 commit，无改动则跳过」？

### P4. 失败重试无指数退避 / 无上限保护

**现象**：xy018、mx015 各重试 20+ 次，大量空转 + 占用槽位 + 顶死其他卡。

**待查**：
1. `server/engine/task.py:43`（机审失败 → 已回写 → 待分派自动重试）和 `store.py:217` 的重试计数逻辑：`retry_count` 怎么算、上限在哪、达到上限后行为？
2. `EXECUTOR_MAX_*_CONCURRENT` 槽位（`main.py:296-325`）是否被重试卡长期占满？
3. 是否已有「同卡连续失败 N 次 → 进隔离/人工」的熔断？没有的话，修复方向建议。

### P5. engine 服务被 SIGTERM 停掉未自动拉起

**现象**：08-08 11:18 `com.ccc.engine` + `com.ccc.board-scheduler` 收到 SIGTERM 优雅关闭，launchctl 中服务消失、未被拉起，全产线悬挂约 1 小时（已手动 `launchctl bootstrap` 恢复）。证据：
- `/Users/fan/.ccc/logs/engine.log` 尾部「收到 SIGTERM, 优雅关闭中...」
- `launchctl list | grep ccc`（恢复后：engine/board-scheduler 已回）

**待查**：
1. plist 的 `KeepAlive=true` + `RunAtLoad=true` 配置下，为什么 SIGTERM 后服务没被自动重启？（可能原因：手动 `launchctl unload` 后未 bootstrap、或进程退出码导致 launchd 判定非异常）
2. 2017 侧是否有定时任务/脚本可能对 engine 发 SIGTERM？（检查 cron、launchd 其他 job、部署脚本）
3. 建议：engine 是否需要「看门狗自愈」——比如 web-server 检测 engine 心跳超过 N 秒则告警/自动拉起？

---

## 输出要求

对每个问题输出：

```
### 问题 N：<标题>
- 根因确认：<代码位置 file:line + 逻辑说明>
- 证据链：<日志/数据>
- 影响范围：<哪些卡/流程受影响>
- 修复方向（3 条以内，不实施）：
  1. ...
  2. ...
- 是否与「60 卡经验升级」相关：<是/否 + 一句理由>
```

最后给一个 **P0-P5 优先级排序** + 「哪些必须进 M8 架构升级、哪些只是补丁」。

只读执行，不要改任何文件。
