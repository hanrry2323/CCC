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

**DSH 机审席 · 2026-08-24 · severity：轻**

**范围核对**：分支 codex/ccc078-watchdog-janitor 与远端零偏差（`git rev-list --left-right --count origin/codex/ccc078-watchdog-janitor...HEAD` = `0 0`，本席复跑）；vs origin/main 仅触 `scripts/watchdog-ccc.sh`（白名单内）+ 本卡回写（步骤3-4授权）；实现提交 ad60cf1d6 = +199/-1（唯一删除行为注释行替换），健康检查/自愈/退出码逻辑未触碰；父提交经证在 origin/main 上（rebase 属实）。

**红线核验（对抗式 · 全数通过）**：
1. 只上报零删除：清道夫段（L119-338）grep 全部 rm/rmdir/kill/git branch -d/git worktree remove|prune 匹配均为建议字符串字面量，零执行路径；本席实跑后 CCC-wt 五目录、103 项 /tmp 残留、7899 监听进程全部原样存活。
2. 行为零变化：两处挂载点均 `janitor_sweep || true`，set -e 下函数体被 || 短路保护，失败不影响健康结论与退出码。
3. 卡头=已回写；机审区/验收区执行体未触碰。

**证据复现（不引用执行体自述，本席亲跑）**：
- 门禁：`bash -n … && bash scripts/watchdog-ccc.sh >/dev/null 2>&1` → `watchdog-exit=0` ✓
- 实跑汇总与 ~/.ccc/logs/watchdog.log 15:20 段逐项吻合：可回收worktree=1（feat-047 孤儿目录，ls 实存）、可删分支=1、遗留服务=2（7899 pid=76724 lsof 实存 + /tmp/ccc-* 共 103 项 wc -l 实测）✓
- 终态判定独立复现：ccc027/ccc075=TERMINAL(状态)、ccc078=ACTIVE ✓
- 去重生效：本席复跑一轮，JANITOR 日志零新增（状态文件 janitor/* mtime 未变）✓
- push 证据：patch-id(fcb3c5982) == patch-id(ad60cf1d6) == `54624c77a443…`，rebase 同一改动属实 ✓

**观察项（不影响结论）**：
- O1 未分化活跃分支会被标「可删分支」（15:10 段曾报 codex/ccc079）：字面符合卡规格「已合入即无独有提交」，有「正被 worktree 占用」警示兜底，误删亦无数据损失；后续若要降噪可加 ahead>0 过滤，属增强非缺陷。
- O2 类级去重窗口内新出现的同类项延迟至 24h 后才报——卡规格原文即「同类告警24h内不重复」，设计取舍一致。
- O3 awk 解析 registry.yaml 依赖缩进格式——registry 为受控唯一事实源，格式稳定，风险可接受。
- O4 自测期间中间缺陷版曾在生产日志留下同仓重复上报（14:37 段），最终提交已修复且回写区如实披露，非隐瞒。

**severity 三级评分**：影响面 1（纯只读上报段，健康链路零触碰）/ 改动深度 1（纯增量、防御完整）/ 红线邻近 1（零删除实证、白名单遵守）→ 合计 3 分 = 轻。

**维护区四问核对（机械判据 P1-b）**：四问均为单选 [否]/[无]，无模板占位；说明行各为一句实情。抽查属实：Q2 所述两处自测缺陷与日志证据吻合（REPO_ROOT 锚定代码在 L125-129、重复上报历史在 watchdog.log 14:37 段）；Q3/Q4「无文档/线路图变更」与 diff 一致。

机审：通过

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
