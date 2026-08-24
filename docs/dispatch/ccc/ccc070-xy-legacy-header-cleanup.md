# 任务卡 ccc070 · xy 历史卡头治理——移除违禁字段「批准」（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

xy 项目 24 张 OpenCode 时代历史卡卡头含 DOC-PROTOCOL §2.3 违禁自造字段「批准」，阻塞 xy 出卡通道。批量移除该行（配套语义修复见 ccc072）。批准真值由 ledger 与 BoardItem.approval 权威承载。

## 实现

仅删除下列白名单文件头 12 行内的「> 批准：…」整行；其余内容逐字节保留。

## 范围

- docs/dispatch/xy/xy033-m2-2-1-chromium.md
- docs/dispatch/xy/xy034-m2-2-1-launchd.md
- docs/dispatch/xy/xy035-m2-2-1-rewriter-mock.md
- docs/dispatch/xy/xy036-m2-2-1-bgm.md
- docs/dispatch/xy/xy037-m2-2-2-openclaw-plugin.md
- docs/dispatch/xy/xy038-m2-2-2-daily-video-tts.md
- docs/dispatch/xy/xy039-m2-2-2.md
- docs/dispatch/xy/xy040-m3-3-1.md
- docs/dispatch/xy/xy041-m3-3-1.md
- docs/dispatch/xy/xy042-m3-3-1.md
- docs/dispatch/xy/xy043-m3-3-2.md
- docs/dispatch/xy/xy044-m3-3-2.md
- docs/dispatch/xy/xy045-m3-3-2.md
- docs/dispatch/xy/xy046-m3-3-3.md
- docs/dispatch/xy/xy047-m3-3-3.md
- docs/dispatch/xy/xy048-m3-3-3.md
- docs/dispatch/xy/xy049-m2-2-3-admin.md
- docs/dispatch/xy/xy050-m2-2-3-worker.md
- docs/dispatch/xy/xy051-m2-2-3.md
- docs/dispatch/xy/xy052-library-api.md
- docs/dispatch/xy/xy053-workflow-api.md
- docs/dispatch/xy/xy054-preview-pages.md
- docs/dispatch/xy/xy055-workflow-visualization.md
- docs/dispatch/xy/xy059-html-preview-cli.md
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

测试：cd /Users/fan/program/CCC-wt/ccc070 2>/dev/null || cd /Users/fan/program/CCC; python3 -c "import pathlib;bad=[f.name for f in pathlib.Path('docs/dispatch/xy').glob('*.md') if any(l.lstrip().startswith(('>批准：','> 批准：')) for l in f.read_text(encoding='utf-8').splitlines()[:12])];print(bad);raise SystemExit(1 if bad else 0)"

## 回写区

- 实现说明：白名单 24 文件逐一处理，每文件头 12 行内恰命中 1 行「> 批准：…」（23 张在第 2 行、xy054 在第 4 行；全目录扫描确认 xy 白名单外无任何「批准」行）；以 `splitlines(keepends=True)` 仅移除目标行，脚本内逐文件断言「新内容 = 原内容去掉该行」逐字节一致后写回。删除行统计：2026-08-17×18、08-18×1、08-20×2、08-21×2、08-24×1。
- 自测结果：门禁命令原样运行，输出 `[]`，退出码=0；`git diff -U0` 复核 24 files changed, 24 deletions(-)，0 新增行，删除行全部为「> 批准：…」行。
- push 证据：分支 codex/ccc070-xy-legacy-header-cleanup，实现 commit 28fcd9d00（push 前 fetch+rebase origin/main），push 后以 `git ls-remote` 核验远端 hash 一致（见维护区上方 commit 记录与 wrapper 证据日志）。

## 机审区

**DSH 机审席 · 2026-08-24 · severity：轻**

审查方式：v4 对抗式独立审查，全部结论经命令独立复现，不采信执行体自述。

1. 范围核对：`git diff --name-only 28fcd9d00^..e471df00f` 共 25 文件 = 白名单 24 张 xy 卡 + 本卡自身（回写授权内）。实现 commit 28fcd9d00 仅触 24 张白名单文件，回写 commit e471df00f 仅触本卡。白名单外零触碰 ✓
2. 实现正确性：逐文件 `git diff -U0` 全部为 ADD=0 / DEL=1，被删行均为「> 批准：老板合入批准 · <日期>」；python 逐字节重建断言（父版本 blob − 该批准行 ≟ 当前工作区内容）24/24 PASS，除该行外零字节变动。行位直方图 {第2行:23, 第4行:1} 与删除日期统计（08-17×18、08-18×1、08-20×2、08-21×2、08-24×1）均与回写区自述吻合（xy054 在第 4 行属实）。
3. 门禁复跑：卡内门禁命令原样执行，输出 `[]`，退出码=0。
4. 残留扫描：`grep -rnE '^\s*>\s*批准' docs/dispatch/xy/` 全目录零命中——含白名单外在内已无任何「> 批准」字段行，「白名单外无残留」声明独立复核成立。
5. 业务意图依据：docs/DOC-PROTOCOL.md:80 明文「禁止加 批准/审批/review 等自造字段」，本卡即清偿该违禁债务；批准真值权威承载属实（server/board/card_header.py:139 approval 字段、server/board/loader.py:145 BoardItem.approval）。语义修复归 ccc072，本卡未越界做语义改动。
6. 红线核验：分支 codex/ccc070-xy-legacy-header-cleanup 未直推 main；`git ls-remote` 远端 hash e471df00f 与本地 HEAD 一致；机审区未被执行体触碰；状态=已回写、未置已关闭。
7. 维护区四问（P1-b 机械判据）：四问均为合规单选（[否]/[无]），说明非空非占位；`server.board.docgate.verify_maintenance` 对本卡实跑 OK=True、PROBLEMS=[]。Q2「机制性教训已在同期 notes 记录」抽查属实——docs/notes/2026-08-24-ccc-locale-sed-byteslice.md 存在且确为机制性教训条目。

风险论证（本次 0 发现项）：批量删行类操作最大风险是误伤非目标行或编码损坏，已由逐字节重建断言排除（24/24）；漏改风险由全目录残留扫描排除（零残留）；门禁假绿风险以比门禁更严的全文件扫描交叉验证排除。

观察（不计 severity、不构成打回）：维护区 Q3/Q4 说明仅写「[否]。」，极简但符合 P1-b 字面标准（单选合规、说明非空非占位、与勾选自洽）。

机审：通过（被审 e471df00f166）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。机制性教训已在同期 notes 记录。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
