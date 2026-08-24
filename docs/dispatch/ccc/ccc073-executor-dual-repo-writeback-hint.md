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

**DSH 机审席 · 2026-08-24 · severity：轻**

### 范围核对（git 取证）

- `f54dd6741` 仅触 `scripts/dsh-executor.sh`（+9 行，白名单精确命中）；`c19982fc1` 仅触本卡（回写流程性改动）。两 commit 外零触碰，working tree clean。
- 远端分支 `codex/ccc073-executor-dual-repo-writeback-hint` = 本地 HEAD `c19982fc1`（`git ls-remote` 实证），push 属实；分支基点为当时 main 尖 `3db973f2f`，main 于 push 后 2 分钟另进无关 plan 提交（`de81895de`），属合入期正常分叉，非执行体缺陷。【复核注 2026-08-24】本席审计提交推送后远端分支尖已随之前移（写作时点快照，以 `git ls-remote` 现值为准）。
- 回写 diff 未触碰目标/实现/红线/验收/门禁；机审区占位行完好；状态=已回写未置已关闭。

### 独立复现证据（不采信执行体自述）

1. 门禁命令逐字复跑（worktree 内）：退出码=0；wrapper 独立截获日志 `/Users/fan/.ccc/logs/exec/ccc073.test-evidence.log` 尾部 `=== exit_code=0 ===`，双源一致。【复核更正 2026-08-24】test-evidence.sh 头行为覆盖写语义（`>` 重写整文件），执行体时段条目 ts=2026-08-24T04:43:56Z 已被机审复跑条目 ts=04:49:25Z 覆盖，原引用 04:43:56Z 系写作时点快照、现已不可观察；现存单条目（ts=04:49:25Z · exit_code=0）即机审独立复跑证据。
2. 本席自建 stub dsh 三场景实测 worktree 副本真实 PROMPT：A（BIZ+WT 非空）=HAS-HINT 且三处展开正确（`${WORKTREE}`=/Users/fan/program/CCC-wt/ccc073/、剥前缀相对路径=docs/dispatch/ccc/…md、主仓绝对路径）；B（BIZ 空）=NO-HINT；C（BIZ 非空+WT 空）=NO-HINT。与卡「实现」节及回写区自测完全一致。
3. 插入位置正确（PROMPT 构造后、`dsh` 调用前）；变量 L20/L22 先于 L79 定义，`set -euo pipefail` 下无 unset 风险；`PROMPT+=` 经实机运行验证可用。

### 对抗式发现（观察项，均不构成本卡缺陷）

- O1 `${CARD_PATH#/Users/fan/program/CCC/}` 硬编码规范检出根：非规范根下静默剥前缀失败，「相对路径」退化为绝对路径（良性降级）。此文案系卡「实现」节原文钦定，执行体无裁量权；且同脚本 L95/L114 已有同类既有硬编码。建议后续窄卡统一 CCC 根变量化。
- O2 边缘态 BIZ_WORKTREE 非空但目录不存在时 cd 落 WORKTREE，提示语「业务改动在当前目录实施」在该态下失真——需引擎误配才触发，且 fall-through 语义系既有行为。
- O3 部署依赖（非缺陷）：引擎实际拉起主仓副本（ccc073.log `cmd=/Users/fan/program/CCC/scripts/dsh-executor.sh`，本席误用主仓副本复现得 NO-HINT 反向印证），故本修复须待合入 main 并产线 pull 后方生效。

### 维护区核对（P1-b 机械判据）

四问勾选符均单选落于问题行方括号（[否]/[无]/[否]/[否]），说明非占位；Q2 声明经 `grep -rn '漏回写\|双仓' docs/notes/` 抽查属实（无可归档教训，唯一命中的「双仓合并」系 hp-plan-009 无关行）；回写区引用工件（f54dd6741、test-evidence 日志、远端分支）逐一存在。执行体将无据预填说明改为可证实实情，回写诚实度加分。

机审：通过

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
