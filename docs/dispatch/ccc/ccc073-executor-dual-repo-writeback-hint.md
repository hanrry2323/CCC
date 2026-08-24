# 任务卡 ccc073 · 执行体 wrapper 双仓回写语义提示（DSH 执行）
> 批准：老板合入批准 · 2026-08-24

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-24

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

- 【第2轮更正】首轮所引 `f54dd6741`/`c19982fc12e7` 为 rebase 前哈希——分支先后 fetch+rebase origin/main 重写全链，旧哈希仅 reflog 可达、克隆方不可解析；新旧树内容经 `git diff <旧> <新> -- <路径>` 逐文件证零差异后换为现行可达哈希：`6bf9caa7c` 仅触 `scripts/dsh-executor.sh`（+9 行，白名单精确命中）；`e6c0e087b` 仅触本卡（回写流程性改动）。两 commit 外零触碰；merge-base=origin/main，分支独有 diff 仅此两文件。回写区所引 `f54dd6741` 同系 rebase 前哈希，与 `6bf9caa7c` 树内容零差异（回写区属执行体辖区，本席不改其文，仅此注记）。
- 【第2轮时序更正】真实拓扑（commit author/committer date + reflog 实证）：执行体自 main 尖 `3db973f2f` 开工（author 12:41–12:42），期间 main 先进 `de81895de`→`1e22a443e`，执行体按卡步骤3「push 前 fetch+rebase」重放后首推——首轮「main 于 push 后 2 分钟另进 de81895de」表述失实，但「正常分叉、非执行体缺陷」之方向性结论不变。本轮机审席启动时分支又被对齐至 main 尖 `c46bf39d5`（mx 无关提交，behind 归零）；本席完成机审区修正后以 force-with-lease（租约锁死远端现值）推送收敛，防覆盖他人推进。
- 回写 diff 未触碰目标/实现/红线/验收/门禁；状态=已回写未置已关闭。

### 独立复现证据（不采信执行体自述）

1. 门禁命令逐字复跑（worktree 内）：退出码=0；wrapper 独立截获日志 `/Users/fan/.ccc/logs/exec/ccc073.test-evidence.log` 尾部 `=== exit_code=0 ===`，双源一致。【复核更正 2026-08-24】test-evidence.sh 头行为覆盖写语义（`>` 重写整文件），执行体时段条目 ts=2026-08-24T04:43:56Z 已被机审复跑条目 ts=04:49:25Z 覆盖，原引用 04:43:56Z 系写作时点快照、现已不可观察；现存单条目（ts=04:49:25Z · exit_code=0）即机审独立复跑证据。【第2轮注】本席复跑走独立日志目录（EXECUTOR_LOG_DIR 重定向），产线证据日志未被再覆盖，现存条目仍为 04:49:25Z 单条。
2. 本席自建 stub dsh 三场景实测 worktree 副本真实 PROMPT：【第2轮独立重跑吻合】A（BIZ+WT 非空）=HAS-HINT 且三处展开逐一正确（worktree 绝对路径 `/tmp/…/wtA/`、剥前缀相对路径 `docs/dispatch/ccc/…md`、主仓绝对路径）；B（BIZ 空）=NO-HINT；C（BIZ 非空+WT 空）=NO-HINT。渲染文本与卡「实现」节逐字一致。与卡「实现」节及回写区自测完全一致。
3. 插入位置正确（PROMPT 构造后、`dsh` 调用前）；变量 L20/L22 先于 L79 定义，`set -euo pipefail` 下无 unset 风险；`PROMPT+=` 经实机运行验证可用。
4. 【第2轮】维护区 Q2 抽查复跑：`grep -rn '漏回写\|双仓' docs/notes/` 唯一命中 hp-plan-009「双仓合并」无关行，Q2[无] 声明属实。

### 对抗式发现（观察项，均不构成本卡缺陷）

- O1 `${CARD_PATH#/Users/fan/program/CCC/}` 硬编码规范检出根：非规范根下静默剥前缀失败，「相对路径」退化为绝对路径（良性降级）。此文案系卡「实现」节原文钦定，执行体无裁量权；且同脚本 L95/L114 已有同类既有硬编码。建议后续窄卡统一 CCC 根变量化。
- O2 边缘态 BIZ_WORKTREE 非空但目录不存在时 cd 落 WORKTREE，提示语「业务改动在当前目录实施」在该态下失真——需引擎误配才触发，且 fall-through 语义系既有行为。
- O3 部署依赖（非缺陷）：引擎实际拉起主仓副本（ccc073.log `cmd=/Users/fan/program/CCC/scripts/dsh-executor.sh`，本席误用主仓副本复现得 NO-HINT 反向印证），故本修复须待合入 main 并产线 pull 后方生效。
- O4【第2轮新增·流程观察】分支两度全链 rebase 使机审区/回写区内的 commit 哈希引用失稳（首推前哈希在推后即不可达）。建议后续流程约定：涉及 rebase 的卡，回写/机审区引用以「主题词 + 短哈希」双写或在 rebase 后由最后写入者统一刷新一次。

### 维护区核对（P1-b 机械判据）

四问勾选符均单选落于问题行方括号（[否]/[无]/[否]/[否]），说明非占位（Q3/Q4 说明为单选符复述实情，非模板占位符）；Q2 声明经抽查属实（见复现证据 4）；回写区引用工件（test-evidence 日志、远端分支）存在，commit 哈希见范围核对第2轮更正注记。执行体将无据预填说明改为可证实实情，回写诚实度加分。

被审对象（现行可达哈希）：代码=`6bf9caa7c`，回写=`e6c0e087b`；severity 三级评分：影响面 2（执行体引导文案，波及所有业务仓型卡的执行质量）· 改动深度 1（纯提示文案 +9 行条件块）· 红线邻近 1（不触红线，越界风险为零）→ 合计 4 = 轻。

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

## 验收区

**合入批准** · 日期：2026-08-24
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
