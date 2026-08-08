# 任务卡 mx026 · 公开化前期准备：敏感信息扫描与铺垫（OpenCode 执行）

> 关联：ccc-plan: medio-0 公开化前期准备：敏感信息扫描与铺垫 · 执行体：OpenCode · 验收：OpenCode · 状态：打回 · 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

medio-0 公开化前期准备（铺垫卡，不破坏、不切换）：全仓敏感信息扫描（git 历史私钥/token/内部 IP/本地路径）+ 公开化执行方案成文 + 补 LICENSE/README 公开说明；为转 GitHub Public 铺路。filter-repo 清理、切可见性、CI 恢复等破坏性/切换动作留给后续专门卡。

## 红线（先看）

1. **不做破坏性操作**：禁止 `git filter-repo`、禁止 force push、禁止改仓库可见性（Private→Public）、禁止改 git 历史——这些是后续执行卡的事，本卡只扫描与成文。
2. 只动白名单（新增文档/License/README 最小更新）；**禁止**改任何业务代码、CI 配置、进行中卡（mx023/024/025）相关文件。
3. 敏感信息扫描只读（git log/grep/checkout 历史文件查看），扫描到的内容**不回写敏感值本身**（只写位置/类型/范围）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- medio-0 仓 docs/ 或 .ccc/ 下新增公开化扫描/方案文档 ≤1 篇
- LICENSE 文件（新增）
- README.md（公开说明最小更新，如需）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，只读扫描敏感信息：
   - `git log --all --oneline` 定位签名私钥 `medio.p7b.pem` 相关 commit（用 `git log --all --follow -- <path>` 或 `git rev-list --all --objects | grep -i p7b/pem/key`）；确认历史中哪些 commit 含敏感文件。
   - `rg -n "token|secret|api[_-]?key|password|BEGIN.*PRIVATE" --glob '!target/**'` 扫描工作区；检查 `.env*`、config、脚本。
   - 内部信息：`feiniu`、`192.168.*`、`/Users/fan/` 等出现位置。
   - 记录每类敏感信息的位置、类型、范围（commit/文件），**不记录敏感值本身**。
2. 公开化执行方案成文（docs/ 或 .ccc/ 新增 ≤1 篇，如 `docs/public-release-plan.md`）：filter-repo 清理步骤（含备份/重写后 commit 变化说明）、签名重签需求、切 Public 顺序、公开后 CI 验证步骤、时间窗口建议（避开进行中卡）。
3. LICENSE 补全（若缺失，选 MIT）；README 若需公开说明做最小更新。
4. 回写区：扫描结论摘要（各类敏感信息数量/范围）、方案要点、LICENSE 选择理由。
5. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 全仓敏感信息扫描成文：git 历史中签名私钥（medio.p7b.pem）所在 commit 范围、token/密钥/.env/内部 IP（feiniu、192.168.*）/本地路径（/Users/fan/...）清单，回写 medio-0 仓 docs/ 或 .ccc/ 决策文档 ≤1 篇
2. 公开化执行方案成文：filter-repo 清理步骤、重签需求、切 Public 顺序、CI 恢复验证（仅方案，不执行破坏性动作）
3. 补 LICENSE（若缺失，选宽松协议如 MIT）与 README 公开说明（若需最小更新）
4. 零业务逻辑改动；不打断进行中卡（mx023-025 相关文件不碰）；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

升级批次 1 复核：DIVERGED 保留待批次 3/4。不改状态。

升级完成复核（2026-08-08 处置）：打回（未回写无产物）。理由：
- 回写区为空（从未回写）、无 commit 产物、无分支证据（DIVERGED 阻断后证据已随 fetch --prune 与孤儿清理移除）。
- DIVERGED 阻断属旧机制问题；批次 3 已实现「分叉 → 干净重建（worktree remove --force + branch -D + 从 origin/main 重建）」，升级后不再有该阻断。
- 如需执行本卡目标（medio-0 公开化扫描/方案/LICENSE），按升级后新机制重新出卡（新卡号）或经引擎重新派发；本卡打回为终态，不再自动拉起。


重派复核（2026-08-08 处置）：打回（执行体未产出，停循环）。理由：重派首轮执行体在 worktree 内 git 操作被本地改动冲突阻断（local changes would be overwritten），回写区始终为空、无产物。该卡目标（medio-0 公开化扫描/方案/LICENSE）如需执行，建议人工窗口在业务仓侧直接完成，或由平台侧确认 worktree 重建机制后再重派。打回为终态，不自动重试。
## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
