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

（验收席专用——执行体禁止写入）

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
