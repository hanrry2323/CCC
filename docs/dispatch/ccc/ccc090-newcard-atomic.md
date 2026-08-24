# 任务卡 ccc090 · new-card.sh 出卡原子化——落盘即提交即推送（DSH 执行）

> 关联：R1-R4 出卡吃单窗三次实锤 · 执行体：DSH · 验收：DSH · 状态：待分派（机审打回·重试中） · 派发：engine · 项目：ccc · 日期：2026-08-25

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

## 机审区

**DSH 机审席 · 2026-08-25 · severity：中**

### 范围核对（通过）

- 分支 `codex/ccc090-newcard-atomic` 相对基点 c5d927686 触碰面仅 3 文件：`scripts/new-card.sh` +47/-0（白名单内唯一代码改动，`git show --numstat 3573c193e` 实证）、演练卡 tst005 +121、本卡回写 +45/-2。无越界、无 `git add -A`。
- 远端核验独立复现：`git ls-remote origin codex/ccc090-newcard-atomic` = `a955b3160` = 本地 HEAD；实现 commit 3573c193e 与演练 commit d18e40fbc 均在 origin 历史中。

### 验收标准独立复核（3/3 通过，不采信自述）

1. bash -n：本席复跑 PASS。
2. tmp 模式零 git 副作用：本席独立复现 `--dispatch-dir $(mktemp -d)` → rc=0、卡落 tmp、「跳过原子提交」日志、HEAD 前后一致、`git status` 干净。
3. 真实出卡即提交即推送：d18e40fbc 即原子段自动产物（121 行卡文件单文件提交），已达远端。

另：`pytest server/tests/test_card_dispatch_gate.py server/tests/test_plans.py -q` 本席复跑 84 项全过（退出码 0），「现有测试兼容」声明字面属实——但注意该套件对 new-card.sh 用的是 mock（server/tests/test_plans.py:116），**不覆盖真实原子段**。

### 发现（对抗式）

**F1（定级依据 · 中）：非零退出语义外溢至两个未改调用方的失败回滚路径。**
新增原子段使 new-card.sh 出现「卡已写盘且已 commit 之后仍非零退出」（exit 5/6/7，scripts/new-card.sh:463-497），打破调用方隐含契约「rc≠0 ⇒ 无卡」。依赖该契约做回滚的调用方：
- `server/board/plans.py:1275-1284` convert_plan：rc∈{5,6,7} 时 `_rollback_created()`（plans.py:1061-1067，纯 `unlink`）删除工作区卡文件——但卡已在 HEAD；结果为孤儿 docs(card) 提交 + 工作区 deleted 状态 + 重试生成同号卡的重复历史。触发门槛低至网络抖动（push 失败）。
- `scripts/plan-to-cards.sh:137-138` 及 Phase 2 校验失败处 `rm -f "$c"` 回滚同理退化。
- 成功路径不受损但每次批量转卡多 N 条中间模板 docs(card) 提交（goal/白名单/验收注入发生在原子提交之后），属历史噪音非缺陷。
缓解：无数据丢失（卡在 git 历史）、单卡直出主路径完全正常。修复需动 plans.py / plan-to-cards.sh，均在卡白名单之外，本席不可就地修——故不为「轻」。处置建议供引擎下一程：回滚改 `git rm -f`+识别 rc 5/6/7 走「保留已提交卡」分支，或对纯 push 失败降级 rc0+警告（语义取舍需老板定夺）；补真仓集成用例。

**F2（轻微 · 不计分）：树内/树外判定为字符串前缀匹配**（new-card.sh:463），PROJECT_ROOT_REAL 为物理路径而 CARD_PATH 沿逻辑路径，符号链接祖先或含 `..` 的 --dispatch-dir 可致树内卡被静默归类仓外跳过原子提交（quiet 下无提示且 rc=0）。与既有 FORBIDDEN_PREFIXES 判定同构（:130-131 先例），实发概率低，建议后续两侧 realpath 归一。

**F3（轻微 · 不计分）：detached HEAD 时 exit 7**——本地提交已完成却报全局失败，叠加 F1 会诱发对一张已受保护卡的误回滚（同根问题）。

### 复核意见

- 推送分支偏差声明（回写区）：**成立并采纳**。worktree 场景字面 `git push origin main` 推的是共享 local main ref（不含新卡提交），改推当前分支是达成「卡必达远端、消灭吃单窗」意图的正确修正，且中枢 main 上出卡时与卡面等价。
- 威胁模型属实：`server/git_sync.py:141` `_force_align_dispatch` 确会对 dispatch 目录未跟踪文件执行 unlink，吃单窗风险真实存在，本卡业务意图正当且在其范围内达成。
- 实现质量：逐段捕获 rc、pathspec 限定的暂存检查（`git diff --cached --quiet -- <卡>`）、无 origin 跳推、退出码 5/6/7 与既有 0/1/2/3 无冲突且头注释文档化——工程质量良好。
- 维护区四问机械判据：四问均单选+一句实情，抽查属实（Q2 头注释固化实证于 diff；Q3 分支 stat 零结构变化实证）。

机审：不通过（中severity：白名单内实现、验收标准与维护区全过，唯 F1 非零退出语义令 plans.py/plan-to-cards.sh 失败回滚退化为删已提交卡且无法在本卡白名单内就地修复，转引擎按上述建议现状处理后续审）
