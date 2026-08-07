# 任务卡 hp001 · 首次摸底：recon baseline 与业务线路图梳理（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

hp 项目首次进 CCC 自动开发流程：在 Mac2017 `/Users/fan/program/apps/hp` 做只读侦察（recon + baseline），摸清技术栈、目录、git 状态与文档/运行时资产，输出业务线路图梳理；结果回写到 CCC 仓档案 `docs/projects/hp/README.md` 与 `docs/roadmap.md` 业务线路段。

## 红线（先看）

1. **绝对禁止**修改、添加、删除 hp 业务仓（`/Users/fan/program/apps/hp`）任何文件；只读 `ls`/`cat`/`git log`/`find`，禁止 `pip install`/`npm install`/启服务/改配置；`local/` 为运行时 untracked 目录，只看不碰。
2. 文档改动**只允许**在 CCC 仓本机：`docs/projects/hp/README.md`、`docs/roadmap.md`、本任务卡。
3. 禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 只读侦察：`/Users/fan/program/apps/hp`（git 状态、目录树、README/AGENTS/VERSION、`docs/dev-plan.md`、`docs/audit/` 基线报告、`docs/knowledgebase/`、`docs/lessons.md`、`scripts/`、`local/` 概览）
- 回写：`docs/projects/hp/README.md`（档案五节 + 技术栈 + 目录树 + 线路梳理）
- `docs/roadmap.md` 末尾新增「业务线路（hp）」总览段（参考 ccc010 的 xy 段格式）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/hp`，跑只读侦察：
   - `git status -sb`、`git branch -a`、`git log -15 --oneline`（记录分支/最近提交/是否 ahead）
   - `find . -maxdepth 2 -type d -not -path '*/\.*' | head -50` 扫描目录结构
   - 读 `README.md`、`AGENTS.md`、`VERSION`、`CHANGELOG.md`（前 40 行）
2. 梳理业务资产（只读 `cat`/`head`）：
   - `docs/dev-plan.md`（规划 SSOT：近端目标/约束/入口端口/已完成）
   - `docs/audit/hp-baseline-2026-08-03.md`（Phase 0 基线：运行时端口、PG 表/chunk 填充率、collector 停摆、K23 未交付等结论）
   - `docs/knowledgebase/`、`docs/postmortems/`、`docs/lessons.md` 标题级浏览，归纳业务模块
   - `scripts/` 与 `local/` 顶层概览（只 `ls`）
3. 整理总结：
   - 核心技术栈（语言/框架/数据库/向量/运行时服务）
   - 项目运作方式（文档仓 + `local/` 运行时 + hp@192.168.3.131 部署节点；入口端口以 qx-map path-authority 为准）
   - **业务线路梳理**：按 Phase/模块归纳当前线路（如 Phase 0 基线 → Phase 1 复验 → 检索入口自检 → K23 chunk metadata 补档 → collector 恢复 → Dashboard 维护 → 教训沉淀），标注每线现状与下一步意向
   - 当前分支/提交状态
4. 回写 CCC 仓 `docs/projects/hp/README.md`：按五节模板填充（是什么/路径/在 CCC 怎么动/线路与近况/禁区），附 A 技术栈表、附 B 目录树（深度 3）、附 C 业务线路梳理。
5. `docs/roadmap.md` 末尾新增 `## 业务线路（hp）` 总览段：按线路列出现状 + 下一程意向一行（参考 ccc010 xy 段格式）；`docs/projects/hp/README.md`「线路 / 近况」≤3 行同步一致。
6. 探针自检：`git -C /Users/fan/program/apps/hp status -sb` 仍为 clean（业务仓零改动）；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支 `codex/hp001-recon-baseline-roadmap`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `docs/projects/hp/README.md` 五节完整填充，含附 A 技术栈、附 B 目录树、附 C 业务线路梳理（模块/现状/下一步），并写清业务仓路径 `/Users/fan/program/apps/hp`。
2. `docs/roadmap.md` 含「业务线路（hp）」总览段：各线路现状 + 下一程意向一行；hp README「线路 / 近况」与其一致（≤3 行）。
3. hp 业务仓保持零改动（`git -C /Users/fan/program/apps/hp status -sb` clean，无新增/修改/删除文件）。
4. `python3 -m server.board.validate docs/dispatch` 通过（卡头/看板一致性）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明

1. 深入侦察了 Mac2017 `/Users/fan/program/apps/hp` 业务仓只读基线状态，摸清了技术栈（Python psycopg2 后端 + React 前端 + pgvector + Ollama 1024 维）、目录布局（`local/` 为 untracked 部署、`tests/`、`docs/`）、git 状态（clean, main 分支 ahead 1）及文档资产。
2. 在 CCC 仓回写了项目档案 `docs/projects/hp/README.md`，填充了「是什么/路径/在 CCC 怎么动/线路与近况/禁区」五节框架，并新增了附 A（技术栈表）、附 B（深度 3 目录树）、附 C（基于 Baseline 梳理的 Phase 0-5 业务线路与意向）。
3. 在 `docs/roadmap.md` 末尾增设 `## 业务线路（hp）` 总览段，详细列出 `hp001` 到 `hp003` 的进度（`hp001` 为 `待合入批准`），并归纳了 hp 下一程意向。

### 测试结果

- 验证业务仓 `/Users/fan/program/apps/hp` 零改动：`git -C /Users/fan/program/apps/hp status -sb` 为 clean。
- 本地自检：通过了 `python3 -m server.board.validate docs/dispatch` 卡头/看板一致性及项目前缀对账校验（卡头修改为「已回写」且更新缓存后校验无阻断阻碍）。

### push 证据

- **分支**：`codex/hp001-recon-baseline-roadmap`
- **Commit Hash**：`accc74270151ef82bba5ee9e057b7eff9080fa27`

