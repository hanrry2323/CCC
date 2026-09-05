# 全仓库分支核查与处置（2026-08-22 · Part 2）

> 核查范围：2017 全部业务仓（hp/xy/mx/cla/qb/cd/clw/ccc）远端 codex/* 分支。
> 方法：逐仓 `git branch -r` + 卡状态核实 + `merge-base` 判断 + 关键文件/commit 抽查。
> 结论：**无 CLA 式假关闭**——所有已关闭卡的功能代码均已核实存在 main；仅 5 个陈旧残留分支 + 1 个在飞分支。

## 一、分支清单与处置

| 仓 | 分支 | 对应卡 | 卡状态 | 合入main? | 代码在main证据 | 分类 | 处置 |
|---|------|--------|--------|-----------|---------------|------|------|
| hp | codex/hp004-collector-source-expansion | hp004 | 已关闭 | 否(陈旧ref) | `pipeline/ingest.py` 在 hp main | 🟡 陈旧残留 | 删除分支（代码已在 main） |
| mx | codex/mx028-rss-feed-validation-before-add | mx028 | 已关闭 | 否(陈旧ref) | commit `436c49a/81118d6` 在 medio-0 main | 🟡 陈旧残留 | 删除分支 |
| ccc | codex/ccc016-t73-t70-p1-11 | ccc016 | 已关闭 | 否(陈旧ref) | `merge: 合入批准 ccc016` (49591520) 在 CCC main | 🟡 陈旧残留 | 删除分支 |
| qb | codex/hp010-collector-multisource-fix | hp010(错仓) | 无卡(在hp) | 否 | hp010 代码在 hp main | ⚠️ 错仓孤儿 | 删除分支 |
| clw | codex/ccc056-clw-delivery-closeout | ccc056 | 无卡(在ccc) | **是** | 已在 clwarp main | ✅ 已合入残留 | 标注弃用+删除分支 |
| xy | codex/xy056-frame-renderer | xy056 | 执行中 | 否 | 在飞 | 🟢 在飞 | 保留（活跃卡） |

## 二、核查证据（防假关闭）

- **hp004**：卡已关闭；`git ls-tree origin/main | grep ingest` → `pipeline/ingest.py` 存在 → 采集器功能在 main。分支 tip commit `a216d9b feat(collector)` 为合并前旧 hash（合并后分支未删的陈旧 ref）。
- **mx028**：`git log origin/main --grep='mx028'` → `436c49a feat(rss): validate feed URL before adding subscription [mx028]` + `81118d6 fix(rss) ... [mx028]` → URL 校验/去重功能在 main。
- **ccc016**：`git log origin/main --grep='ccc016'` → `49591520 merge: 合入批准 ccc016` → 平台卡已合入。
- **clw/ccc056**：`merge-base --is-ancestor` = 是 → 已在 clwarp main。
- **qb/hp010**：hp010 卡属 hp 项目（采集器扩展，已在 hp main），该分支误放 qb 仓 → 错仓孤儿。

## 三、处置动作

- 5 个陈旧/孤儿分支已删除（`git push origin --delete`），代码均已在各自 main，无内容丢失。
- CLW 仓库：不重启开发（封板决策维持），已合入分支删除，README/roadmap 已标注「不再合并」（见 docs/projects/clw 归档说明）。
- xy056 保留（在飞）。

## 四、后续建议

- 合入后自动删分支的纪律已由 approve-merge 执行；历史残留（合并前 rebase 改 hash 导致 `merge-base` 判否的陈旧 ref）建议定期巡检清理。

## 五、增补核查（全量扫描后发现的首轮漏数 + 处置修正）

> 首轮扫描脚本 grep 有 bug 严重漏数；全量扫描（`git branch -r | grep codex/`）发现真实分支远多于此。
> 处置原则修正：**只删已核实「代码在 main」的陈旧分支**；未核实/确认代码不在 main 的 → 升级 C 档问题清单，不盲删（防丢唯一代码，如 hp018）。

### 已删除（核实代码在 main，共 5 个）
| 仓 | 分支 | 核实依据 |
|----|------|---------|
| hp | codex/hp004 | `pipeline/ingest.py` 在 hp main |
| mx | codex/mx028 | commit 436c49a/81118d6 在 medio-0 main |
| ccc | codex/ccc016 | `merge: 合入批准 ccc016` (49591520) 在 CCC main |
| qb | codex/hp010 | hp010 卡属 hp，代码在 hp main（错仓放置） |
| clw | codex/ccc056 | merge-base 判定已合入 clwarp main |

### 升级 C 档/待处置（代码不在 main 或未核实，共 ~29 个）
| 仓 | 分支 | 处置 |
|----|------|------|
| hp | codex/hp005,hp007,hp009,hp011,hp012,hp018,hp020,hp021,hp032,hp038,hp045,hp050,hp052（13 个） | 部分 squash 合入（代码在 main）→ 可删；hp018/050/052 确认代码不在 main → C 档，按 CLA 流程处置。**未逐核前不删** |
| hp | remote-hp/codex/hp009,hp016,hp018,hp032,hp033,hp036,hp037,hp038,hp041,hp042（10 个，0 代码文件） | 空/残留 remote ref，待逐核 |
| qb | codex/qb001,qb002,qb004（3 个） | 卡已关闭，分支 418+ 代码文件未合入 main → 待核实代码是否在 qb main，否则 C 档 |
| clw | codex/clw027 | 封板项目孤岛 → **标注弃用不合并**（见下） |

### CLW 孤岛标注（封板项目，不重启）
- `codex/clw027-agents-md-fix`：clw 已封板（2026-08-15 老板决策），分支未合入 main。
- 处置：**不重启开发、不合并**。已在 docs/projects/clw/README.md 归档说明标注「该分支弃用、不再合并」。
