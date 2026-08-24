# 任务卡 ccc078 · watchdog 清道夫巡检——陈旧 worktree/孤儿分支/遗留服务上报（DSH 执行）

> 关联：无方案（2026-08-24 地基加固 · 总调度直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

> 状态校正（2026-08-24 · 受老板一次性授权，总调度执行）：工程已交付且分支就绪，磁盘卡由「待分派」如实校正为「已回写」以终结重派循环；合入归环节②。

## 目标

今日清理实证的平台卫生债需要常态化盯防：陈旧 worktree、孤儿分支、遗留预检服务端口。
扩展 scripts/watchdog-ccc.sh 增加清道夫巡检段（只上报不自动删除）。

## 实现

白名单：scripts/watchdog-ccc.sh。

新增检查项（输出进既有 watchdog 日志管道）：
1. CCC-wt/* 与 apps/.ccc-wt/*/* 中对应卡已是终态（已关闭/作废/历史标记）的 worktree → 列「可回收」清单；
2. 各受管仓本地分支中已合入 origin/main 但仍存在的非豁免分支 → 列「可删分支」；
3. 7898/7899 及 /tmp/ccc-* 预检残留监听/目录 → 列「遗留服务」；
4. 每项附处置建议一行。阈值防刷屏：同类告警 24h 内不重复。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只上报不删除；现有健康检查行为零变化。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。职责终点=已回写，合入归环节②。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：bash -n scripts/watchdog-ccc.sh && bash scripts/watchdog-ccc.sh >/dev/null 2>&1; echo watchdog-exit=$?

## 回写区

（执行体回写）

- **实现说明**（2026-08-24）：scripts/watchdog-ccc.sh 新增 janitor_* 清道夫段（+199 行，纯增量）。
  ①可回收 worktree：遍历主仓与 registry.yaml 受管仓的 `git worktree list`，卡头终态（已关闭/作废/
  历史标记）→ 列「可回收」；worktree_root 下 git 未注册孤儿目录一并列入。②可删分支：本地分支已
  合入 origin/main(master)、豁免 main/master/develop/HEAD，被 worktree 占用时建议先移除再删；
  基于本地引用保守判定，不做 fetch。③遗留服务：7898/7899 监听逐 pid 上报；/tmp/ccc-* 按
  mtime≥24h 计残留，报总数+样例防刷屏。④同类告警 24h 去重（状态文件 ~/.ccc/logs/janitor/<key>，
  可经 CCC_JANITOR_REPEAT_SEC / CCC_JANITOR_TMP_MIN_AGE_SEC 覆盖）。挂载点仅两条退出路径前
  `janitor_sweep || true`：健康检查函数、判定逻辑、自愈动作、退出码零变化（红线2）。只上报零删除。
- **自测结果**：门禁 `bash -n … && bash scripts/watchdog-ccc.sh >/dev/null 2>&1; echo watchdog-exit=$?`
  → `watchdog-exit=0`。实跑明细（~/.ccc/logs/watchdog.log）：feat-047 孤儿目录上报 ✓；
  codex/ccc076·078「已合入被占用」上报、codex/ccc077 因 main 前进正确不报 ✓；7899 pid=76724 与
  /tmp 残留 103 项上报 ✓；连续两轮第二轮 JANITOR 日志零新增（去重生效）✓；终态判定函数对
  ccc027(已关闭)/ccc075(作废)=TERMINAL、ccc078(活跃)=ACTIVE ✓；健康输出仍为「健康」+exit 0 ✓。
- **push 证据**：分支 codex/ccc078-watchdog-janitor，实现提交已推送（rebase origin/main 前哈希
  fcb3c5982，rebase 后分支终态哈希 ad60cf1d6，两者 patch-id 同一改动）。2026-08-24 复核补记：
  `git rev-list --left-right --count origin/codex/ccc078-watchdog-janitor...HEAD` = `0 0`（远端零
  偏差）；门禁复跑 `watchdog-exit=0`；实跑汇总「可回收worktree=1 可删分支=1 遗留服务=2」，明细见
  ~/.ccc/logs/watchdog.log 15:20 段。卡回写为随后第二次 push（本行所在提交）。

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。地基加固直派卡无关联方案，无方案需同步。
2. **教训沉淀**：[无]
   - 说明：[无]。教训已随卡记录——自测暴露两处实现缺陷（脚本在 worktree 运行时 REPO_ROOT 漂移、
     去重分隔串笔误致同仓重扫）均已修复并复测；机制级教训随本卡即可，无需另沉淀 KB。
3. **档案/README**：[否]
   - 说明：[否]。纯脚本内增量巡检段，配置经环境变量覆盖，未改任何对外行为与文档口径。
4. **线路图**：[否]
   - 说明：[否]。单点卫生债常态化盯防，不构成新里程。
