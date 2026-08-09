# 任务卡 ccc014 · 收敛历史已关闭卡的远端 codex 分支（OpenCode 执行）

> 关联：ccc-plan-004 · 历史残留收敛（2026-08-08） · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-08

## 目标

收敛 CCC 仓 23 个历史已关闭卡的远端 codex 分支残留（已审计：分支独有提交全部为卡文件回写/机审/验收区，无 main 之外的真实代码产物），使 `--ready` 扫描队列干净、历史噪音归零。

## 红线（先看）

1. **只删已确认清单内的远端 codex 分支**（见下方范围）；禁止动 `main`、禁止动任何业务仓分支、禁止动未在清单内的分支。
2. 删除前对每个分支执行 `git diff --name-only origin/main origin/codex/<b>` 复核：若含非 `docs/` 文件的真实独有改动 → **跳过并记录**，不删。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 仅远端引用删除：`git push origin :codex/<branch>` × 23（分支清单见下方步骤 1）
- 业务仓（xianyu/medio-0 等）的 codex 分支**不在本卡范围**（xy027 在 xianyu 仓的 prm-verify 交付另行处置）

## 步骤

1. 在 2017 `/Users/fan/program/CCC` 拉取最新 main，复核清单（23 个）：
   `hp016-collector-pipeline-repair mx009-atom-parser-library mx013-architecture-doc-dev-guide mx014-crawl-all-image-localization mx015-crawl-all-error-writeback mx016-pc-keyboard-shortcuts mx017-rss-image-proxy mx018-rss-reader-css-class mx019-backend-coverage-core-tests mx020-rss-save-transaction mx021-scheduled-health-probe mx022-opml-import-attribute-order mx023-frontend-coverage-ci-gate mx025-core-module-coupling-audit xy016-video-pipeline-recon-html-report xy017-storage-layout-normalize xy019-prod-gap-fix xy020-round2-legacy-inventory xy021-purge-hardcode-old-rules xy022-dynamic-path-derivation xy023-env-credential-alignment xy025-media-quality-acceptance xy027-prm-gate-verifier`
   每个分支执行复核：独有提交（`git log --oneline origin/main..origin/codex/<b>`）全部为 docs(card)/docs(dispatch) 且 `git diff --name-only origin/main origin/codex/<b>` 无非 docs 真实改动 → 列入删除；否则跳过记录。
2. 逐个执行 `git push origin :codex/<branch>` 删除清单内远端分支；删除后 `git remote prune origin`。
3. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `git branch -r | grep origin/codex/` 仅剩本卡自身分支（`ccc014-converge-stale-remote-branches`）与未删清单外分支
2. `git push origin :codex/<清单内分支>` 逐个返回成功（附删除输出）
3. 回写区填：复核结论摘要（每分支独有提交类型）、删除数/跳过数（跳过须附原因）、push 证据（commit hash）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 实现说明
我们严格按白名单及红线要求，对 CCC 仓 23 个已关闭的历史 codex 分支进行了全面复核和清理：
1. **安全复核**：针对所有 23 个分支执行 `git log origin/main..origin/codex/<branch>` 与 `git diff --name-only origin/main...origin/codex/<branch>`，确认它们独有的提交和改动全部且仅包含对应任务卡的 markdown 文件（落点均在 `docs/dispatch/` 目录下），不包含任何对非 `docs/` 文件的真实独有改动。所有分支 100% 符合安全删除红线。
2. **清理删除**：逐个执行 `git push origin :codex/<branch>` 成功删除了这 23 个远端分支，并运行 `git remote prune origin` 进行了远端修剪，使 `git branch -r | grep origin/codex/` 列表干净，未在清单内的任何其他分支及 `main` 分支均未受任何影响。

### 详细清单与执行结果
- **hp016-collector-pipeline-repair**: 已确认仅修改 `docs/dispatch/hp/hp016-collector-pipeline-repair.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/hp016-collector-pipeline-repair)
- **mx009-atom-parser-library**: 已确认仅修改 `docs/dispatch/mx/mx009-atom-parser-library.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx009-atom-parser-library)
- **mx013-architecture-doc-dev-guide**: 已确认仅修改 `docs/dispatch/mx/mx013-architecture-doc-dev-guide.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx013-architecture-doc-dev-guide)
- **mx014-crawl-all-image-localization**: 已确认仅修改 `docs/dispatch/mx/mx014-crawl-all-image-localization.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx014-crawl-all-image-localization)
- **mx015-crawl-all-error-writeback**: 已确认仅修改 `docs/dispatch/mx/mx015-crawl-all-error-writeback.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx015-crawl-all-error-writeback)
- **mx016-pc-keyboard-shortcuts**: 已确认仅修改 `docs/dispatch/mx/mx016-pc-keyboard-shortcuts.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx016-pc-keyboard-shortcuts)
- **mx017-rss-image-proxy**: 已确认仅修改 `docs/dispatch/mx/mx017-rss-image-proxy.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx017-rss-image-proxy)
- **mx018-rss-reader-css-class**: 已确认仅修改 `docs/dispatch/mx/mx018-rss-reader-css-class.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx018-rss-reader-css-class)
- **mx019-backend-coverage-core-tests**: 已确认仅修改 `docs/dispatch/mx/mx019-backend-coverage-core-tests.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx019-backend-coverage-core-tests)
- **mx020-rss-save-transaction**: 已确认仅修改 `docs/dispatch/mx/mx020-rss-save-transaction.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx020-rss-save-transaction)
- **mx021-scheduled-health-probe**: 已确认仅修改 `docs/dispatch/mx/mx021-scheduled-health-probe.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx021-scheduled-health-probe)
- **mx022-opml-import-attribute-order**: 已确认仅修改 `docs/dispatch/mx/mx022-opml-import-attribute-order.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx022-opml-import-attribute-order)
- **mx023-frontend-coverage-ci-gate**: 已确认仅修改 `docs/dispatch/mx/mx023-frontend-coverage-ci-gate.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx023-frontend-coverage-ci-gate)
- **mx025-core-module-coupling-audit**: 已确认仅修改 `docs/dispatch/mx/mx025-core-module-coupling-audit.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/mx025-core-module-coupling-audit)
- **xy016-video-pipeline-recon-html-report**: 已确认仅修改 `docs/dispatch/xy/xy016-video-pipeline-recon-html-report.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy016-video-pipeline-recon-html-report)
- **xy017-storage-layout-normalize**: 已确认仅修改 `docs/dispatch/xy/xy017-storage-layout-normalize.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy017-storage-layout-normalize)
- **xy019-prod-gap-fix**: 已确认仅修改 `docs/dispatch/xy/xy019-prod-gap-fix.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy019-prod-gap-fix)
- **xy020-round2-legacy-inventory**: 已确认仅修改 `docs/dispatch/xy/xy020-round2-legacy-inventory.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy020-round2-legacy-inventory)
- **xy021-purge-hardcode-old-rules**: 已确认仅修改 `docs/dispatch/xy/xy021-purge-hardcode-old-rules.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy021-purge-hardcode-old-rules)
- **xy022-dynamic-path-derivation**: 已确认仅修改 `docs/dispatch/xy/xy022-dynamic-path-derivation.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy022-dynamic-path-derivation)
- **xy023-env-credential-alignment**: 已确认仅修改 `docs/dispatch/xy/xy023-env-credential-alignment.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy023-env-credential-alignment)
- **xy025-media-quality-acceptance**: 已确认仅修改 `docs/dispatch/xy/xy025-media-quality-acceptance.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy025-media-quality-acceptance)
- **xy027-prm-gate-verifier**: 已确认仅修改 `docs/dispatch/xy/xy027-prm-gate-verifier.md`，已删除 (To github.com:hanrry2323/CCC.git - [deleted] codex/xy027-prm-gate-verifier)

- **删除数**：23
- **跳过数**：0

### 测试结果
运行 `git branch -r | grep origin/codex/` 列表为空（本卡分支 `ccc014-converge-stale-remote-branches` 待此次 commit + push 后远端可见，属于当前活跃分支）。

### push 证据
本卡修改及成果提交已 push 到本卡分支：
- 分支名：`codex/ccc014-converge-stale-remote-branches`
- 提交哈希：72ee0ca4197f70ac256962496a4a989083021e97

## 机审区

**机审席**：2017 CCC 机审 · 日期：2026-08-08

**机审：通过**

### 审查摘要
按 code-review 清单独立复核（同工具独立审查，不因同工具放水）。本卡为纯远端分支收敛（无可审计的业务代码产物），重点核验执行真实性与红线范围。

### 发现清单
- **无 P0 / P1 发现。** 23 个分支删除、范围收敛、卡状态三方面全部核验通过。

### 独立取证（直接查 GitHub origin，不依赖本地缓存）
1. `git ls-remote --heads origin | grep codex/` → 仅剩 `codex/ccc014-converge-stale-remote-branches`（本卡自身分支），**23 个目标分支均已从远端物理删除**，与回写「删除 23 / 跳过 0」一致。
2. `refs/heads/main` = `026dd51b`，main 完整未动；远端 `backup/` 前缀分支（含 `backup/xianyu-*`）均在，证明删除严格限定在清单 codex 分支、**未波及业务仓分支**（xianyu/medio-0 不在范围，正确）。
3. 卡内清单唯一分支名去重计数 = 23，与回写删除数逐条吻合；回写详细清单逐分支附 `[deleted]` push 输出。

### 修复记录
无（未发现需修复项，无需提交修复 commit）。

### 复审结论
- 回写区删改仅限本卡 `.md`（`git diff 026dd51b 4701cc63 --name-only` → ALL DOCS-ONLY）；分支已 rebase 到最新 main（含 `026dd51b`）。
- 卡头状态「已回写」正确；未写 `## 验收区`、未置「已关闭」——执行体按红线正确停手，等老板「合入批准」。
- `## 人工批注` 仅占位符，无老板批注，无需核对批注落实。
- **验收标准 3 条全部满足**：① 远端 codex/ 仅剩本卡分支 ✓ ② 23 删除全部成功（ls-remote 佐证）✓ ③ 回写区填复核结论/删除数/跳过数/push 证据 ✓。
- **结论：通过**，可听老板「合入批准」。
