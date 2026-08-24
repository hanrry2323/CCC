# 任务卡 ccc073 · 执行体 wrapper 双仓回写语义提示（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

业务仓型任务卡的开发视图里没有卡文件，DSH 首轮普遍漏做 CCC 侧回写（xy059 首轮实证）。修复=dsh-executor.sh PROMPT 增补双仓语义提示。

## 实现

白名单：scripts/dsh-executor.sh。当 BIZ_WORKTREE 非空时 PROMPT 追加：
「双仓提示：本卡文件位于文档仓分支副本 ${{WORKTREE}}/ 下（相对路径 ${{CARD_PATH#/Users/fan/program/CCC/}}）。业务改动在当前目录实施；卡文件的状态回写、回写区与维护区四问必须在文档仓 worktree 的卡副本上完成并 commit+push 到同一分支；主仓 ${{CARD_PATH}} 只读勿动。」
WORKTREE 缺失场景不加误导提示。文案外零逻辑变化。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. PROMPT 文案之外零逻辑变化。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码/文件现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc073 2>/dev/null || cd /Users/fan/program/CCC; bash -n scripts/dsh-executor.sh && grep -q "双仓提示" scripts/dsh-executor.sh

## 回写区

（执行体回写 · 2026-08-24）
- 实现说明：scripts/dsh-executor.sh 在 PROMPT 构造之后追加条件块——BIZ_WORKTREE 非空且 WORKTREE 非空时，PROMPT 尾部按卡「实现」节原文追加双仓提示（${WORKTREE}、${CARD_PATH#/Users/fan/program/CCC/}、${CARD_PATH} 均为 shell 展开）；WORKTREE 为空时不追加，避免引用空路径误导。文案外零逻辑变化（diff 仅 +9 行，无其他改动）。
- 自测结果：① 卡门禁 `bash -n scripts/dsh-executor.sh && grep -q "双仓提示" scripts/dsh-executor.sh` 退出码=0；② stub dsh 三场景实测 wrapper 真实 PROMPT：A（BIZ+WT 非空）=HAS-HINT 且三处变量展开正确（worktree 绝对路径 / 相对路径已剥前缀 docs/dispatch/... / 主仓绝对路径），B（BIZ 空）=NO-HINT，C（BIZ 非空+WT 空）=NO-HINT；③ test-evidence.sh 独立截获门禁 exit_code=0。
- push 证据：分支 codex/ccc073-executor-dual-repo-writeback-hint，代码 commit f54dd6741（仅 scripts/dsh-executor.sh，+9 行），卡回写随本 commit 入库；push 前 fetch+rebase origin/main，push origin 已执行成功。

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。本卡为 PROMPT 提示文案增补，未产出新的可复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
