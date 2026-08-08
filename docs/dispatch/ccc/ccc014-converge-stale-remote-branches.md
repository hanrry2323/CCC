# 任务卡 ccc014 · 收敛历史已关闭卡的远端 codex 分支（OpenCode 执行）

> 关联：CCC 治理 · 历史残留收敛（2026-08-08） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-08

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

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
