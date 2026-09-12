# 任务卡 xy070 · 状态口径回填（008/roadmap 计划状态修正）

> 关联：xy-plan-008（G4 治理债）· 执行体：DSH · 验收：DSH · 状态：已关闭 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy070 · 状态版本：12
> 业务仓：无（文档收口，改 CCC 仓内 xy 计划文档）

## 目标
修正 xy 两份计划文档的口径矛盾，让看板/方案状态如实反映进度：
1. `docs/projects/xy/plans/008-high-expression-v2.md`：头部「进度：2/2 (100%)」与「状态：部分执行」矛盾——**回填为「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」**，进度行与描述一致。
2. `docs/projects/xy/roadmap.md` M6 段：6.1「内容库 API」、6.2「工作流 API」实际已合入（xy060/xy061 已交付），**从「计划中」回填为「已完成」**并注记关联卡号。

## 实现要求
用文本编辑（Edit）精确改两处状态字段，不改结构/其他内容；改后自测（grep 确认新值在位、旧值消失）。

## 红线
1. 只改上述两文件的**状态/**进度字段行**，不重构段落、不改其他项目、不动 xianyu 业务仓。
2. 不启动 M7、不触碰 Cookie 外部账号、不发布。
3. 若发现 roadmap/008 既有内容与实况还有冲突，如实记进回执别硬改。

## 范围
- docs/projects/xy/plans/008-high-expression-v2.md
- docs/projects/xy/roadmap.md

## 步骤
1. 读两个文件相关段，确认现状。
2. `plans/008`：进度行旁加注「M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；头部「状态」保持「部分执行」但补一句注记，消除「100% 但部分执行」的矛盾。
3. `roadmap.md` M6：6.1/6.2 状态改「已完成」，注记「（xy060/xy061 合入）」。
4. 自测：grep 新状态再位、旧「计划中」对 6.1/6.2 不再命中；plans008 无「进度 2/2 (100%)」无解释的孤立行。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. `grep "6.1 内容库" roadmap.md` 显示状态=已完成（xy060 注记）；6.2 同。
2. `grep "进度：2/2" plans/008` 所在行有「M5 主体完成…」注记，不再是孤立矛盾行。
3. diff 仅两文件、共 ≤15 行改动（含加注行）。
4. 无 M7/Cookie/业务仓改动。

## 门禁
- card_gate 五项校验（必填字段齐全、状态=待分派、项目前缀 xy 在 registry、验收=Claude Code（phase2 机审）、范围两路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问（方案同步/教训沉淀/档案README/线路图）逐项填。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡 xy070「状态口径回填（008/roadmap 计划状态修正）」：修正 `docs/projects/xy/plans/008-high-expression-v2.md` 头部「进度：2/2 (100%)」与「状态：部分执行」的口径矛盾，回填为「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」并在进度行加注「M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；将 `docs/projects/xy/roadmap.md` M6 段 6.1「内容库 API」、6.2「工作流 API」从「计划中」回填为「已完成」并注记 xy060/xy061 合入。人工批注：无批注（占位）。实现范围仅上述两文件的状态字段行：不改结构/其他内容/其他项目、不动 xianyu 业务仓、不启动 M7、不触碰 Cookie 外部账号、不发布。本轮为复核复报轮：前序实现与机审补位均已推送（期成 commit 24f24845d → Q1 补位 84c90a51d），本轮全量重验状态在位、机审 Q1/Q2 补位已落实，无需新增业务改动，复报如下。

## 1. 探针输出

- **派发目录与目标仓不匹配（实测复核，延续前轮结论）**：卡范围两路径属 CCC 仓（origin=git@github.com:hanrry2323/CCC.git，worktree `/Users/fan/program/CCC-wt/xy070`，branch codex/xy070）；wrapper 派发的工作目录 `/Users/fan/program/apps/.ccc-wt/xy/xy070` 仍为 **xianyu 业务仓** worktree（origin=git@github.com:hanrry2323/xianyu.git，branch codex/xy070-state-backfill），`docs/projects/xy/plans/` 实测不存在（ls 退出码非 0），无卡白名单文件。按卡红线「不动 xianyu 业务仓」在 CCC worktree `/Users/fan/program/CCC-wt/xy070` 执行核验；xianyu 业务仓跟踪面无 git 改动（git status 仅既有 untracked .venv）。
- **机审补位状态（Q1/Q2 本轮逐项实测核实）**：① 机审区「结论：不通过」原因为方案 xy-plan-008「关联卡」不含本卡 ID xy070（机审引用的是补位前旧值）——现 `008-high-expression-v2.md:6` 关联卡已含「xy070（治理回填）」（commit 84c90a51d 已推送，grep 退出码 0）；② 回执教训沉淀引用文件实测存在：`docs/notes/2026-09-06-p1-completion-report.md`（第 33-34 行为「维护区四问 JSON 映射 / docgate.py::parse_maintenance_section 门禁」机制原文）与 `docs/lessons.md`（Lesson 50/51 机审打回处理，第 2265/2280 行，grep 退出码 0）。
- **现状确认（实现全量在位）**：008 头部（`:3`）「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」、进度行（`:8`）「2/2 (100%) —— M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；roadmap M6（`:55/:56`）6.1/6.2 均为「已完成（xy060/xy061 合入）」；git 状态：branch codex/xy070，本地与 remote tip 均 84c90a51d（ls-remote 核验一致），工作区仅未跟踪 .ccc-result.md/.venv-hub。
- **红线 3 残余口径（超出本卡范围，未改动，记回执转治理）**：`roadmap.md:42` M5 里程碑仍为「计划中（M6 全部卡验收后启动）」，与 008「部分执行（M5 主体完成）」不一致；且 M6 尚未全验收（6.3/6.4 仍计划中）。属同族口径债，超出本卡两处字段白名单与验收标准「diff ≤15 行」约束，如实记入回执未硬改。
- 交付佐证：`docs/archive/ccc-tasks/xy/xy060-content-library-api.md`、`xy061-m6-2-workflow-api-verify.md` 卡头均「状态：已关闭」，支撑「已完成（xy060/xy061 合入）」注记（前轮已实测）。

## 2. 自测输出

```
$ cd /Users/fan/program/CCC-wt/xy070
$ grep -n "6.1 内容库\|6.2 工作流" docs/projects/xy/roadmap.md          # 验收①
55:  - 6.1 内容库 API · 状态：已完成（xy060 合入） · 方案：xy-plan-009
56:  - 6.2 工作流 API · 状态：已完成（xy061 合入） · 方案：xy-plan-009
# exit=0
$ grep -n "进度：2/2" docs/projects/xy/plans/008-high-expression-v2.md  # 验收②
8:> 进度：2/2 (100%) —— M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径
# exit=0
$ grep -nE "进度：2/2 \(100%\)$" docs/projects/xy/plans/008-high-expression-v2.md
# 孤立矛盾行：无输出，exit=1（预期）✓
$ grep -n "关联卡" docs/projects/xy/plans/008-high-expression-v2.md     # 机审 Q1 前置
6:> 关联卡：xy059、xy064、xy067、xy065、xy066、xy068、xy069、xy070（治理回填）；其余功能卡待出（xy059=html-preview CLI 已回写）
# exit=0 → xy070 已在关联卡
$ grep -n "状态：部分执行" docs/projects/xy/plans/008-high-expression-v2.md
3:> 项目：xy · 编号：xy-plan-008 · 状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出） · 作者：OpenCode（集群架构） · 工具：OpenCode
# exit=0
$ sed -n '33,34p' docs/notes/2026-09-06-p1-completion-report.md          # 机审 Q2 前置
4. **引擎收单优先读 JSON sidecar** — server/engine/main.py::_apply_executor_result_to_card：优先读 <id>-ccc-result.json（json.loads 提取 card_title/probe_output/selftest_output/maintenance → 直接映射回写区/维护区，不做字符串 split）；JSON 不存在/解析失败/结构非法 → 回退既有 .ccc-result.md split 逻辑（兼容窗口完整保留）。
   - 维护区四问从 JSON maintenance 对象映射为卡面格式 N. **name**：[choice] 说明，与 new-card.sh 模板及 docgate.py::parse_maintenance_section 兼容。
$ grep -n "Lesson 5[01]" docs/lessons.md | head -2                      # 机审 Q2 前置
2265:## Lesson 50：机审 infra 判定过宽会吞掉真实的「机审：不通过」
2280:## Lesson 51：机审多轮结论不能被「首个锚点后 20 行」窗口误判
$ git diff 0cb53741a..84c90a51d --stat    # 验收③：业务文件仅 008+roadmap 两文件、10 行改动（≤15）
 docs/dispatch/xy/xy070-state-backfill.md         | 2 +-    # 引擎卡头修复 3c37c3fe6（非执行体改动）
 docs/projects/xy/plans/008-high-expression-v2.md | 6 +++--- # 实现 4 行 + 关联卡补位 2 行
 docs/projects/xy/roadmap.md                      | 4 ++--
$ git ls-remote --heads origin codex/xy070
84c90a51daead47dbd191c5a615725356e90543d        refs/heads/codex/xy070   # 远端 tip 与本地一致 ✓
$ git status --short            # CCC worktree：仅 ?? .ccc-result.md / ?? .venv-hub（均未跟踪，不提交）
$ git -C /Users/fan/program/apps/.ccc-wt/xy/xy070 status --short          # 验收④：xianyu 业务仓仅 ?? .venv、?? .ccc-result.md（均未跟踪）
```

验收标准逐条：① 6.1/6.2 状态=已完成 +（xy060/xy061 合入）注记 ✓；② 进度行含「M5 主体已完成…」注记、孤立矛盾行消除 ✓；③ diff 业务文件仅 008+roadmap、10 行改动（≤15）✓；④ 无 M7/Cookie/业务仓改动 ✓。机审补位前置：008 关联卡已含 xy070（grep 退出码 0）✓；Q2 引用文件实测存在且内容核验通过 ✓。本轮为复核轮，实现与补位均已在位且已推送，无新增业务改动。退出码：命中类 grep 0、无命中 grep 1（预期）、git 命令 0。

## 维护区

1. **方案同步**：[是] 008 头部状态回填「部分执行（M5 主体完成，5.1-5.3 功能卡待出）」+ 进度行加注（M5 主体完成、2/2 为子项完成口径）消除「100% vs 部分执行」矛盾；方案 008「关联卡」已纳入 xy070（84c90a51d）；卡头「关联：xy-plan-008」已由引擎补齐（3c37c3fe6）。本轮复核状态在位，无新增方案改动。
2. **教训沉淀**：[有] 机审打回教训——维护区 Q1 声明[是] 时方案「关联卡」字段必须含本卡 ID、Q2[有] 必须引用实测存在的沉淀文件；机制出处 docs/notes/2026-09-06-p1-completion-report.md（维护区四问 JSON 映射与 docgate.py::parse_maintenance_section 门禁，第 33-34 行），机审打回处理参照 docs/lessons.md Lesson 50/51（第 2265/2280 行）。本轮复核后此节原样成立。
3. **档案/README**：[否] 未动架构/接口/README，仅 008 状态/进度/关联卡行与 roadmap 6.1/6.2 状态行（含前轮关联卡补位）。
4. **线路图**：[否] roadmap 6.1/6.2 状态回填即线路图本体更新（前轮完成），本轮无新增规划。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：通过
- 理由：CC 审核通过，自动合入完成
