# 任务卡 ccc090 · new-card.sh 出卡原子化——落盘即提交即推送（DSH 执行）

> 关联：R1-R4 出卡吃单窗三次实锤 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

出卡工具内建原子性：new-card.sh 在写卡成功后**同一进程链内自动** `git add <卡> && git commit`（消息前缀 docs(card):）并尝试 `git push origin main`（任务卡 push 属出卡 SOP），任一步失败即非零退出并保留现场文件。彻底消灭「落盘未提交被 _force_align_dispatch 按 untracked 清除」的吃单窗（R3/R4 共四次实锤）。

## 红线

- 白名单：scripts/new-card.sh。
- --dispatch-dir 指向临时目录（测试形态）时跳过 git 步骤，保持现有测试兼容。
- push 失败不回滚本地 commit（卡已在本地受保护），输出显式警告与手动补推指引。

## 步骤

1. 写卡+validate 通过后追加原子提交段（git add 单文件→commit→push，逐段捕获 rc 并输出明确日志）。
2. 自测：真实出一张演练卡验证全链；tmp 目录模式验证跳过逻辑。

## 验收标准

- [ ] 真实出卡后 git log 立即可见该卡 commit 且已推送
- [ ] tmp 模式零 git 副作用
- [ ] bash -n 通过

## 回写要求

- 回写区附演练卡号与 push 输出；维护区四问如实。

## 人工批注

（留空）

## 回写区

**执行体**：DSH · 日期：2026-08-25

### 实现说明

- 白名单内唯一代码改动：`scripts/new-card.sh`（+47 行）。写卡+validate 通过后、输出 `CARD_PATH=` 前，同一进程链插入原子提交段：`git add <单卡>` → 无暂存防御 → `git commit -m "docs(card): <卡ID> <标题>"` → `git push origin <当前分支>`，逐段捕获 rc 并输出明确日志。
- 跳过逻辑（红线2）：沿用 plan-to-cards.sh 先例——仅当 CARD_PATH 位于本仓 git toplevel 内才执行 git 段；`--dispatch-dir` 指向树外临时目录（测试形态）时打印「跳过原子提交」并零 git 副作用。
- 失败语义：add 失败 exit 5 / commit 异常或失败 exit 6 / push 失败或分支不可判定 exit 7，均非零退出且现场卡文件一律保留；push 失败不回滚本地 commit，stderr 输出显式警告与手动补推指引（红线3）。
- 对卡面的一处必要偏差声明：卡面写「尝试 `git push origin main`」。实现在中枢主仓 main 分支出卡时与卡面完全等价；在 worktree/其他分支出卡时改推「卡 commit 所在分支」。原因：worktree 场景字面执行 `git push origin main` 推的是共享 local main ref（不含新卡 commit，卡实际未达远端，还可能误动 main）。此为达成卡意图「卡必达远端、消灭吃单窗」的修正，请机审复核。

### 自测结果（附命令）

1. `bash -n scripts/new-card.sh` → 通过。
2. tmp 模式零 git 副作用：`--dispatch-dir $(mktemp -d)` 出 tst001-tmp-selftest → rc=0、卡落盘、日志「dispatch-dir 在仓外（测试形态），跳过原子提交（零 git 副作用）」、HEAD 不变、git status 无新增条目。
3. 现有测试兼容：`python3 -m pytest server/tests/test_card_dispatch_gate.py server/tests/test_plans.py -x -q` → **84 passed**。
4. 真实演练全链（本仓树内）：演练卡号 **tst005-ccc090-atomic-drill**（`bash scripts/new-card.sh --project tst --title "ccc090 自测演练卡…" --slug ccc090-atomic-drill --dispatch manual`），脚本日志：
   ```
   [OK] 出卡成功 + validate 通过: …/docs/dispatch/tst/tst005-ccc090-atomic-drill.md
   [codex/ccc090-newcard-atomic d18e40fbc] docs(card): tst005 ccc090 自测演练卡：…
    1 file changed, 121 insertions(+)
   [OK] 已本地提交：docs(card): tst005（吃单窗已消除）
   [OK] 已推送 origin/codex/ccc090-newcard-atomic
   ```
   演练卡为本卡自测产物（派发 manual、标题已注明勿认领），供环节②归档。

### push 证据

- 实现 commit：`3573c193e`（fix(new-card): 出卡原子化…）
- 演练卡自动 commit：`d18e40fbc`（docs(card): tst005 …）
- 远端核验：`git ls-remote origin codex/ccc090-newcard-atomic` = `d18e40fbcd7593d950b986d31e54724aa43de527` = 本地 HEAD，两 commit 均已在 origin。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：本卡关联为 R1-R4 吃单窗实锤直派，无 prefix-plan-NNN 方案编号，无方案文件需同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：「出卡必须原子提交防 _force_align_dispatch 清 untracked」已直接固化为 scripts/new-card.sh 工具行为与头注释，不另立 notes 条目。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：仅改变 scripts/new-card.sh 的行为（新增原子提交段），目录结构/技术栈/路径零变化。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：吃单窗消除属 R 系列既定收口项落地，近况与下一步不变。
