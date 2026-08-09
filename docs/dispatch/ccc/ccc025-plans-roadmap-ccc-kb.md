# 任务卡 ccc025 · plans与roadmap纳入ccc-kb知识库索引（OpenCode 执行）

> 关联：ccc-plan-011 卡3 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

把 `docs/projects/<prefix>/plans/*.md` 方案与 `docs/roadmap.md` 纳入 ccc-kb 索引（新增 plans 域），使执行 Agent 与巡查 Agent 能经 kb_search 检索到方案/线路图内容。依据：ccc-plan-011 阶段一 1.3。

## 红线（先看）

1. **只改 `server/kb/` 代码 + `server/tests/test_kb_query_cases.py` + `knowledge/query-cases.md`**。**禁止**复制方案到 `knowledge/domains/`（违背 DOC-PROTOCOL 单一主档）；禁止改 `docs/projects/*/plans/*.md` 内容本身。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 域归一必须同步改全（indexer + search + mcp_server + cli），否则 MCP domain 过滤失效。

## 范围

- `server/kb/indexer.py`：`_SECTION_ALIASES`（L27-32）加 `"plans"`/`"roadmap"` 归一到 `plans` 域；`scan_source_files`（L201-216）加扫 `docs/projects/*/plans/*.md` + `docs/roadmap.md`。
- `server/kb/search.py`：`_SECTION_ALIASES`（L28-33）+ `_canonical_section`（L36-38）同步 plans 域。
- `server/kb/mcp_server.py`（L66/L94）+ `server/kb/cli.py`（L88/L93）：domain 描述加 `plans`。
- `server/tests/test_kb_query_cases.py`：`test_covers_four_domains`（L82）改为五域 + 补 plans 用例；`knowledge/query-cases.md` 同步。
- 复用 `_parse_domain_markdown`（indexer.py L168-196，按 `##` 分段）解析方案 md。

## 步骤

1. 读 `server/kb/indexer.py` / `search.py` 现状，确认域归一两处别名表 + 扫描函数。
2. 按范围清单实现 plans/roadmap 扫描与 plans 域归一（4 个代码文件）。
3. 本地 `--reindex` 重建索引，确认 documents 数增加（方案文件 + roadmap 进入索引）。
4. 实测：`kb_search("Loop Observer")` 命中 `docs/projects/ccc/plans/011-loop-observer-architecture.md`；`kb_search("业务线路")` 命中 roadmap。
5. 改测试断言（四域→五域）+ 补 plans 查询用例；`pytest server/tests/test_kb_*.py` 全绿。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `kb_search("Loop Observer")` 返回命中，id/section 指向 011 方案文件。
2. `kb_search("业务线路（xy）")` 命中 `docs/roadmap.md`。
3. `pytest server/tests/` 全绿（含 test_kb_query_cases 五域断言）。
4. `--health` 显示 sections 含 plans，文档数较 v1 增加。
5. `knowledge/domains/` 未被写入任何方案副本（单一主档未破坏）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09
- **实现说明**：
  1. 在 `server/kb/indexer.py` 的 `_SECTION_ALIASES` 与 `server/kb/search.py` 的 `_SECTION_ALIASES` 加上了 `"plans"`/`"roadmap"` 到 `"plans"` 域的��一。
  2. 在 `server/kb/indexer.py` 的 `scan_source_files` 中，新增扫描 `docs/projects/*/plans/*.md` 方案文件与 `docs/roadmap.md`。
  3. 修改了 `_parse_domain_markdown` 的 `section` 归一逻辑和 `base_id` 的生成，对 `roadmap.md` 和各项目 `plans` 文件生成了唯一的 `base_id`（例如：`domains::plans::ccc::011-loop-observer-architecture`），从而在统一解析 markdown 标题分段时避免冲突。
  4. 修改 `server/kb/mcp_server.py` 与 `server/kb/cli.py`，在其 `domain` 过滤选项描述中同步加入了 `plans` 选项。
  5. 修改 `server/tests/test_kb_query_cases.py`，将 `test_covers_four_domains` 升级为 `test_covers_five_domains`，增加并补充 plans 用例。
  6. 同步修改了 `knowledge/query-cases.md`，加入了 3 个 plans 域用例（桌面驾驶舱、心智分层、视频里程碑），均全绿通过。
- **测试结果**：
  - 本地运行 `python3 -m server.kb.cli reindex` 构建成功，242 个 documents 成功编入索引。
  - `python3 -m pytest server/tests/test_kb_*.py` 128 个测试全量通过！
- **push 证据**：
  - Commit Hash: `1ea45ba160f6ff3d94567fc82902b0132cecfbdf`
  - 分支: `codex/ccc025-plans-roadmap-ccc-kb`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联的 ccc-plan-011 (plans与roadmap纳入ccc-kb知识库索引) 阶段一 1.3 方案状态已经完全对齐，对应的开发任务卡已完成并顺利推入「已回写」阶段。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本任务为知识库域扩展常规特性开发，未在编码/流程上触发具有泛化意义的新型架构教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：本项目未引入新的第三方依赖，未改变原有知识库（BM25 检索）的架构实现和技术栈，项目结构完全保持不变。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：本卡不改变现有的产品路线图。

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

## 机审区

机审：通过
来源：engine 自动落盘（engine-audit）· 2026-08-09 23:04
证据：erver/kb/` 4 个文件 + `test_kb_query_cases.py` + `knowledge/query-cases.md`，域归一两处别名表同步 plans、扫描函数补 roadmap.md + `docs/projects/*/plans/*.md`，四域→五域断言。改动严格落在卡白名单内，无越界，无违规写 `knowledge/domains/` 副本，架构归一一致（indexer/search/mcp/cli 四端同步）。**代码本身通过。** **打回原因：维护区未完成（Doc-Gate 完成钩子未落实）** — 非机械问题，是原则性门禁。 卡 `ccc025-plans-roadmap-ccc-kb.md` 现状： - 卡头状态仍是 `待分派`，未按步骤 6 改为「已回写」。 - `## 回写区` 为空（L58 仅「执行体：OpenCode · 日期：」占位
