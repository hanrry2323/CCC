# 任务卡 mx003 · recon business tracks for in-flight branches（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

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

**执行体**：OpenCode · 日期：2026-08-07

### 1. 业务仓只读侦察结果
- **分支与提交状态**：medio-0 业务仓工作区干净，当前位于 `codex/mx002-add-server-health-api-and-python-smoke-test` 分支。
- **本地与 origin 差异**：本地 `main` 领先 `origin/main` 1 个 commit（即安全修复 `2e093b5`）。
- **三条在飞分支对齐**：
  - `feature/library-management`（最新提交 `5991b25`）、`feature/ui-upgrade-to-emby-level`（最新提交 `dc94998`）、`fix/rss-bugs`（最新提交 `6c73e01`）相比 `origin/main` 的未合入提交数均为 0（它们均为 `origin/main` / `main` 的直接祖先，已 100% 合入 `main` 分支），无任何集成或冲突风险。
- **业务资产与架构决策 (ADR-001 ~ 013)**：
  - 后端：Rust Axum + SQLite (sqlx) 技术栈，支持一键删除+回收站与安全债务跟踪（ADR-001/002/012/013）。
  - 前端：React SPA + Tailwind CSS 4（ADR-003），支持 Web 与 Tauri Mac 桌面双模式部署（ADR-005/007）。
  - 移动端：HarmonyOS 客户端，支持分布式源（ADR-008）。
- **教训沉淀总结**：
  - 网络挂载定时增量扫描误删防护（修复为增量扫描跳过删除判定，且全量设置 10% 最小阈值守卫）。
  - iOS Safari video 切歌 DOM 重建导致授权丢失（修复为同元素存活切换）。
  - refill 自动加载状态 randomContext 同步（避免 refill 时追加全库随机视频）。

### 2. 回写修改详情
- **档案文件回写**：修改了 CCC 仓 `docs/projects/mx/README.md`，更新「线路 / 近况」为极简 3 行，并在「附 C」完整回写了《业务线路梳理》（媒体库管理、UI 体验升级、RSS 订阅修复、基础能力与安全等 4 条线路的状态、完成度与下一步意向），并在「附 D」整理了关键决策与教训沉淀。
- **路线图回写**：更新了 `docs/roadmap.md`，在末尾新增了 `## 业务线路（mx）` 段，内容与 mx README 完全一致。

### 3. 验证与探针结果
- 业务仓零修改验证：`git -C /Users/fan/program/apps/medio-0 status -sb` 为 clean。
- 卡头/看板一致性校验：运行 `python3 -m server.board.validate docs/dispatch` 成功，卡头无任何 error 阻塞，校验通过。
- **Push 证据**：
  - 分支：`codex/mx003-recon-business-tracks`
  - 提交 Hash：`56c1b3c97db244a1e944fca8980b181db7a1923e`

## 批注落实

无人工批注。

## 机审区

**机审**：Claude Code（2017 机审席）· 日期：2026-08-07 · 结论：**通过**

经完整 Code Review 流程（读卡验收 → 独立只读取证业务仓 → 核对回写 diff → 看板一致性命中），本次 mx003 回写内容全部经独立核实，验收标准 1-4 满足，未发现 P0/P1。无就地修复。

### 审查摘要
- **结论**：mx003 业务线路摸底回写**通过**。无 P0/P1。
- **独立取证通道**：均在 `/Users/fan/program/apps/medio-0` 业务仓只读执行（`git rev-list --count origin/main..<branch>`、`git merge-base --is-ancestor`、`git log -1`、`git status -sb`、`git branch -a`），未做任何 checkout/merge/写操作。

### 发现清单（经独立核实的事实）
| # | 声称 | 独立取证 | 结论 |
|---|------|----------|------|
| 1 | 三条在飞分支相对 origin/main 未合入提交数 0 | `rev-list --count origin/main..branch` 三条均 0 | ✅ 属实 |
| 2 | 三条分支已 100% 合入 main、为 origin/main 直接祖先 | `merge-base --is-ancestor <branch> origin/main` 三条均 YES | ✅ 属实 |
| 3 | main 领先 origin 1 commit（安全修复 2e093b5） | `rev-list --count origin/main..main`=1；`git log -1 main`=2e093b5 | ✅ 属实 |
| 4 | 业务仓工作区 clean、零改动 | `git status -sb`=clean（当前 `codex/mx002` 分支） | ✅ 属实 |
| 5 | 附 C 为业务线路梳理、附 A/B 技术栈与目录树完好 | README diff 核对：附 A/B 未动；「附 C：最近 15 条 commit」按卡 §5 替换为「附 C：业务线路梳理」+ 新增附 D | ✅ 符合卡结构 |
| 6 | roadmap「业务线路（mx）」与 README「线路/近况」一致（≤3 行） | 两文件 diff 交叉核对一致 | ✅ 属实 |
| 7 | 看板 validate 通过 | 索引同步后 `server.board.validate docs/dispatch` exit=0「卡头校验通过」(111 张卡) | ✅ 通过(条件) |

### 修复记录
- 无 P0/P1，**未做就地修复**。

### 复审结论
- **机审：通过**。未发现 P0/P1 阻断项；无需重新出卡或打回。

### 附注（P2 级，非阻断，供后续参考）
- 回写区 §3 对 `server.board.validate` 的表述「通过」严格成立的前提是**索引已同步**。该 CLI 的 `validate_cards` 仅在索引文件缺失时全量重建；索引陈旧时首次运行会报 `索引对账失败: 状态不一致`（旧索引=`待分派` vs 磁盘=`已回写`）并 exit 1，待 `load_dispatch_cards`（Engine/看板常规路径）增量刷新索引后即通过。此为本机 `~/.ccc/data/cards/cards.index.jsonl` 全局运行索引的时序特性，**非本次回写引入的代码/文档缺陷**，故不构成 P0/P1，未越界改动已回写区。
