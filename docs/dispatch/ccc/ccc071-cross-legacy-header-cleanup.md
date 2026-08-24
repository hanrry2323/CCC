# 任务卡 ccc071 · 全仓历史卡头治理（非 xy）——移除违禁字段「批准」（DSH 执行）
> 批准：老板合入批准 · 2026-08-24

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

除 xy 外 63 张历史卡卡头含违禁自造字段「批准」（含 ccc 自身与 tst），批量移除（配套语义修复见 ccc072）。

## 实现

仅删除下列白名单文件头 12 行内的「> 批准：…」整行；其余内容逐字节保留。

## 范围

- docs/dispatch/ccc/ccc018-task.md
- docs/dispatch/ccc/ccc019-engine-gate-skip-metrics.md
- docs/dispatch/ccc/ccc020-prompt-injection-dashboard.md
- docs/dispatch/ccc/ccc068-validate-plans-utf8-gate.md
- docs/dispatch/cd/cd001-ui.md
- docs/dispatch/cd/cd002-task.md
- docs/dispatch/cd/cd003-ui.md
- docs/dispatch/cd/cd004-task.md
- docs/dispatch/cla/cla001-sqlite-m1-ccc-plan-032-2.md
- docs/dispatch/cla/cla016-sqlite-ledger-fix.md
- docs/dispatch/cla/cla017-gov-playwright.md
- docs/dispatch/cla/cla018-llm-provider-ollama-api.md
- docs/dispatch/cla/cla019-ssot.md
- docs/dispatch/cla/cla020-jobs.md
- docs/dispatch/cla/cla021-task.md
- docs/dispatch/cla/cla022-task.md
- docs/dispatch/cla/cla023-ai.md
- docs/dispatch/cla/cla024-api.md
- docs/dispatch/cla/cla025-webhook.md
- docs/dispatch/cla/cla026-spa-data-panel.md
- docs/dispatch/cla/cla027-opportunity-stream.md
- docs/dispatch/cla/cla028-compliance-panel.md
- docs/dispatch/hp/hp023-pipeline-ssot-m2-pipeline-ssot.md
- docs/dispatch/hp/hp030-m3-1.md
- docs/dispatch/hp/hp032-git-m2-git.md
- docs/dispatch/hp/hp033-ssot-m2-ssot.md
- docs/dispatch/hp/hp034-m2.md
- docs/dispatch/hp/hp035-m2.md
- docs/dispatch/hp/hp036-m2.md
- docs/dispatch/hp/hp037-m2.md
- docs/dispatch/hp/hp038-m3.md
- docs/dispatch/hp/hp039-pg-health-m3-pg-health.md
- docs/dispatch/hp/hp040-m3.md
- docs/dispatch/hp/hp041-cron-m3-cron.md
- docs/dispatch/hp/hp042-health-m3-health.md
- docs/dispatch/hp/hp043-collector-m4-collector.md
- docs/dispatch/hp/hp044-m4.md
- docs/dispatch/hp/hp045-chunk-m4-chunk.md
- docs/dispatch/hp/hp046-m4.md
- docs/dispatch/hp/hp047-m4.md
- docs/dispatch/hp/hp048-mx-m5-mx.md
- docs/dispatch/hp/hp049-qb-m5-qb.md
- docs/dispatch/hp/hp050-xy-m5-xy.md
- docs/dispatch/hp/hp051-m5.md
- docs/dispatch/hp/hp052-m5.md
- docs/dispatch/mx/mx036-websub.md
- docs/dispatch/mx/mx037-task.md
- docs/dispatch/mx/mx038-appstate.md
- docs/dispatch/mx/mx039-api.md
- docs/dispatch/mx/mx040-task.md
- docs/dispatch/mx/mx041-task.md
- docs/dispatch/mx/mx045-medio-0-ci-cd-filter-repo.md
- docs/dispatch/mx/mx046-medio-0-ci-cd.md
- docs/dispatch/mx/mx047-medio-0-ci-cd-ci-cd.md
- docs/dispatch/mx/mx052-opml-import-attribute-bug.md
- docs/dispatch/mx/mx053-task.md
- docs/dispatch/mx/mx054-opml-bearer-token-opml-bearer.md
- docs/dispatch/mx/mx055-rss-sql-rss-sql.md
- docs/dispatch/mx/mx056-ci-dependency-audit.md
- docs/dispatch/mx/mx057-frontend-deadcode-cleanup.md
- docs/dispatch/qb/qb007-task.md
- docs/dispatch/qb/qb008-strategycore-r14-strategycore.md
- docs/dispatch/tst/tst004-task.md
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只删除「> 批准：…」整行（含变体），该行以外逐字节保留。
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

测试：cd /Users/fan/program/CCC-wt/ccc071 2>/dev/null || cd /Users/fan/program/CCC; python3 -c "import pathlib;skip={'xy'};bad=[str(f) for f in pathlib.Path('docs/dispatch').glob('*/*.md') if f.parent.name not in skip and any(l.lstrip().startswith(('>批准：','> 批准：')) for l in f.read_text(encoding='utf-8').splitlines()[:12])];print(bad);raise SystemExit(1 if bad else 0)"

## 回写区

- 实现说明：2026-08-24 按白名单对 63 个非 xy 历史卡（ccc/cd/cla/hp/mx/qb/tst）以 Python keepends 逐字节删除头部前 12 行内的「> 批准：…」整行（每文件恰 1 行，LF 行尾原样），行外内容零改动。
- 自测结果：门禁命令真实退出码=0（bad=[]）；`git diff --numstat` 复核 63 文件 added=0 / deleted=63（纯删除）、白名单外零触碰。
- push 证据：实现 commit 8b4bfa7f6（63 files changed, 63 deletions）→ origin/codex/ccc071-cross-legacy-header-cleanup（fetch+rebase origin/main 后 push）。

## 机审区

**DSH 机审席 · 2026-08-24 · severity：轻**

v4 对抗式独立审查（第二轮入档）；下列证据均为本席在本 worktree 独立重跑所得，不采信执行体自述。

0. **审查对象与谱系**：被审实现 commit=`d44e0117c`、回写 commit=`43220ced6`（现行分支 origin/main..HEAD 共 4 提交：实现+回写+首轮机审入档+wrapper 结论戳）。本卡于 2026-08-24 12:53 全分支 fetch+rebase origin/main（尖端 `1e22a443e`）后重推，首轮机审所引 pre-rebase 锚点 `8b4bfa7f6`/`019309957` 仍存于对象库但已不在分支上；本席实证两代实现 commit patch-id 相等（`48c5c35b…`）——内容逐字节同源，故结论跨 rebase 有效，本轮以现行谱系锚点重新入档。
1. **范围核对**：实现 commit `d44e0117c` numstat=63 文件 ×（0 added / 1 deleted），改动集与卡白名单 63 项双向对称差=∅；回写 commit `43220ced6` 仅触本卡文件（状态→已回写、回写区、Q2 说明），机审区占位由机审 commit 替换、验收区未建、已关闭未置；本地 HEAD == `origin/codex/ccc071-cross-legacy-header-cleanup`，push 属实。
2. **完备性**：以实现父提交 `1e22a443e` 为基线全量扫描 `docs/dispatch/*/*.md`（排除 xy）头 12 行违例集，与白名单集合完全相等（双侧差∅）——无遗漏、无多改；xy 24 张按卡定义排除，归配套轨道。
3. **字节级核验**：以父 blob 删除「头 12 行内匹配 `>批准：` / `> 批准：` 的行」重建，63/63 与子 blob 逐字节相等（行外内容零改动实证）；实际 diff 真实删除恰 63 行、每文件恰 1 行，全部落在头部 ≤12 行内。
4. **门禁复跑**：卡内门禁命令原样执行 → `bad=[]`，退出码=0。
5. **维护区四问**：`server/board/docgate.py::verify_maintenance` 实跑 → `True []`——四问均单选（否/无/否/否）、说明非空非占位、Q1[否] 卡头无方案编号；声明属实（registry/README/roadmap 经两 commit numstat 实证零触碰）。

**打分**：影响面 1（纯历史文档单行删除，运行面/代码零涉及）＋ 改动深度 1（纯删行，字节级 63/63 复现）＋ 红线邻近 2（一次触 63 文件贴近「白名单外零触碰」红线，双侧集合相等实证合规；未推 main）＝ 4 → 轻。

**发现**：0 项代码实质缺陷；1 项记录缺陷已就地修复——首轮机审入档的 SHA 锚点（`8b4bfa7f6`/`019309957aa6`/merge-base `3db973f2f`/「恰 2 提交」）在 12:53 分支 rebase 后全部脱离现行谱系，按图索骥不可复现，本席已按现行谱系重写入档并实证 patch-id 同源。观察（非本卡缺陷，供下一程）：`docs/projects/*/plans/*.md` 方案页现存 42 处「> 批准：…」（hp/mx/qb/cd/ccc/xy，本席独立复数=42），不在本卡白名单，建议挂账确认归属 ccc072 或另卡治理；回写区「deleted=63」实为每文件 1 行 × 63 文件合计，已实证属实，表述可更精确。

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。本卡为一次性批量删行清理，未产出新教训；卡头字段语义问题由配套卡 ccc072 处理。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。

## 验收区

**合入批准** · 日期：2026-08-24
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
