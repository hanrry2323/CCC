# 任务卡 mx003 · recon business tracks for in-flight branches（OpenCode 执行）

> 关联：mx 业务线路摸底 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

在 Mac2017 `/Users/fan/program/apps/medio-0` 做只读侦察：对齐三条在飞功能分支（`feature/library-management`、`feature/ui-upgrade-to-emby-level`、`fix/rss-bugs`）相对 main 的差异、完成度与合入风险；梳理 medio-0 业务线路图；结果回写到 CCC 仓档案 `docs/projects/mx/README.md` 与 `docs/roadmap.md`「业务线路（mx）」段，为后续 mx 出卡提供依据。

## 红线（先看）

1. **绝对禁止**修改、添加、删除 medio-0 业务仓（`/Users/fan/program/apps/medio-0`）任何文件；只读 `ls`/`cat`/`git log`/`git diff`/`find`；禁止 `cargo build`/`npm install`/启服务/改配置；禁止 checkout/合并分支、禁止创建分支。
2. 文档改动**只允许**在 CCC 仓本机：`docs/projects/mx/README.md`、`docs/roadmap.md`、本任务卡。
3. 禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/mx/xxx.md` 业务详文）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 只读侦察：`/Users/fan/program/apps/medio-0`（git 分支/提交状态、三条在飞分支相对 main 的 diff 与完成度、`adr/`、`docs/lessons.md`、`README.md` 主要功能、`scripts/` 概览）
- 回写：`docs/projects/mx/README.md`（档案五节 + 附 A 技术栈 + 附 B 目录树 + 附 C 业务线路梳理）
- `docs/roadmap.md` 末尾新增「业务线路（mx）」总览段（参考 ccc010 的 xy 段格式）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，跑只读 git 侦察：
   - `git status -sb`、`git branch -a`、`git log -15 --oneline`、`git log -1 --format="%h %ad %s" --date=iso`
2. 逐一对齐三条在飞分支（**只读，禁止 checkout/merge**）：
   - 对 `feature/library-management`、`feature/ui-upgrade-to-emby-level`、`fix/rss-bugs` 分别跑：
     - `git log origin/main..<branch> --oneline`（未合入提交数）
     - `git diff --stat origin/main...<branch>`（改动规模）
     - `git log -1 --format="%h %ad %s" --date=iso <branch>`（最近提交时间，判断活跃度）
   - 归纳每线：意图、完成度估计、与 main 脱节程度、合入风险（冲突面/改动规模/陈旧度）
3. 只读浏览业务资产：
   - `ls adr/` + `adr/*.md` 标题级浏览（ADR-001~013，记录关键架构决策）
   - `docs/lessons.md`、`docs/deployment.md` 标题级浏览
   - `README.md` 主要功能段、`scripts/` 顶层概览
4. 整理总结：
   - 核心技术栈（复用 mx001 摸底，仅补充变化）
   - **业务线路梳理**：按三条在飞分支 + main 已发布能力归纳线路（媒体库管理 / UI 升级至 Emby 级别 / RSS 修复 / 基础能力），每线标注现状、完成度、下一步意向
   - 当前分支/提交状态（main 领先/落后 origin 情况、工作区是否干净）
5. 回写 CCC 仓 `docs/projects/mx/README.md`：按五节模板填充（是什么/路径/在 CCC 怎么动/线路与近况/禁区），附 A 技术栈表、附 B 目录树（深度 3）、附 C 业务线路梳理；「线路 / 近况」≤3 行。
6. `docs/roadmap.md` 末尾新增 `## 业务线路（mx）` 总览段：按线路列出现状 + 下一程意向一行（参考 ccc010 xy 段格式）；与 mx README「线路 / 近况」一致。
7. 探针自检：`git -C /Users/fan/program/apps/medio-0 status -sb` 仍为 clean（业务仓零改动）；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
8. commit+push 到卡内分支 `codex/mx003-recon-business-tracks`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `docs/projects/mx/README.md` 五节完整填充，附 C 业务线路梳理覆盖三条在飞分支（意图/完成度/合入风险/下一步），并写清业务仓路径 `/Users/fan/program/apps/medio-0`。
2. `docs/roadmap.md` 含「业务线路（mx）」总览段：媒体库管理 / UI 升级 / RSS 修复等线路现状 + 下一程意向一行；mx README「线路 / 近况」与其一致（≤3 行）。
3. medio-0 业务仓保持零改动（`git -C /Users/fan/program/apps/medio-0 status -sb` clean，无新增/修改/删除文件、无新分支）。
4. `python3 -m server.board.validate docs/dispatch` 通过（卡头/看板一致性）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
