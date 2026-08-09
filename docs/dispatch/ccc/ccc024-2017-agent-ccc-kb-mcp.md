# 任务卡 ccc024 · 2017执行Agent接入ccc-kb MCP并重建索引（OpenCode 执行）

> 关联：ccc-plan-011 卡2 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

把 CCC 自建知识库（ccc-kb）MCP 接入 2017 执行 Agent（OpenCode + Claude Code），并将 2017 索引升级到 v2，使执行 Agent 派发时能直接经 ccc-kb 检索项目知识（项目元数据/决策/教训）。依据：ccc-plan-011 阶段一 1.2。

## 红线（先看）

1. **只改 2017 用户级配置**（`~/.config/opencode/opencode.json`、`~/.claude/settings.json`）+ 2017 本地 `--reindex`。**禁止改** CCC 仓代码、禁止改 registry/卡/看板数据。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 操作对象是 2017（`ssh fan@192.168.3.116`），非 M1；改配置前先备份原文件。

## 范围

- 2017 `~/.config/opencode/opencode.json` 的 `mcp` 段新增：
  ```json
  "ccc-kb": { "type": "local", "command": ["python3", "-m", "server.kb.mcp_server"], "environment": { "PYTHONPATH": "/Users/fan/program/CCC" }, "enabled": true }
  ```
- 2017 `~/.claude/settings.json` 的 `mcpServers` 新增同款 stdio 条目（command `python3 -m server.kb.mcp_server` + env `PYTHONPATH=/Users/fan/program/CCC`）。
- 2017 索引重建：`cd /Users/fan/program/CCC && python3 -m server.kb.mcp_server --reindex`（v1 旧索引 80 条不会自动升级，必须显式重建）。
- 验证性调用（只读，不改数据）。

## 步骤

1. 备份 2017 两份配置文件（`cp xxx xxx.bak-ccc-kb`）。
2. 按范围清单在 opencode.json + settings.json 加 ccc-kb 条目（对照 M1 `qx-map/.mcp.json` 的 ccc-kb 写法，env 键名以 2017 opencode.json 现有条目 schema 为准）。
3. 2017 执行 `--reindex`，确认输出显示文档数 ≥126（4 域齐全）。
4. 实测：2017 上 `opencode run --auto -p "用 ccc-kb 工具查 lessons 域，返回前 3 条教训"`，确认 MCP 调用成功且返回带 score 结果。
5. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 2017 `~/.config/opencode/opencode.json` 与 `~/.claude/settings.json` 均含 ccc-kb MCP 条目（原文可见）。
2. 2017 `--reindex` 成功，`kb --health` 显示 documents ≥126、section 含 lessons/projects/decisions/nodes-paths。
3. 2017 OpenCode 实测 `kb_search` 命中 lessons 域并返回 score（非空）。
4. 原配置文件有备份（`.bak-ccc-kb` 存在）。
5. 未改动任何 CCC 仓代码 / 卡 / 注册表。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **配置文件修改**：修改了 2017 宿主机上的 OpenCode 配置 (`~/.config/opencode/opencode.json`) 和 Claude settings 配置 (`~/.claude/settings.json`)，在 `mcp` 和 `mcpServers` 中分别正确添加了 `ccc-kb` MCP 服务的 stdio 配置。
2. **安全备份**：修改前成功备份了原始配置文件至同一目录下的 `.bak-ccc-kb` 备份。
3. **索引重建**：在 `/Users/fan/program/CCC` 路径下，通过 `python3 -m server.kb.mcp_server --reindex` 成功进行索引的全量重建，升级到 v2，共重建索引文档 126 篇。

### 测试结果
1. **健康检查验证**：执行 `python3 -m server.kb.mcp_server --health` 返回：
   ```json
   {"documents": 126, "index_dir": "/Users/fan/program/CCC/knowledge/.index", "ok": true, "sections": {"decisions": 15, "lessons": 24, "nodes-paths": 13, "projects": 74}}
   ```
2. **工具实测验证**：运行 `opencode run --auto "用 ccc-kb_knowledge_search 搜索 lessons 域，查询关于 '超时' 的教训"`，成功连接本地 `ccc-kb` MCP 并返回带 score 相关的教训：
   - L2: Executor 超时后 planner 不应越界 commit
   - L5-L10: 系列教训

### Push 证据
- **Commit Hash**: bb515d98

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `ccc-plan-011` 卡2 已经在本次开发中执行并回写，状态更新为已回写。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：本次为 2017 环境下的 Agent 用户级配置，未对业务代码或架构带来变更。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：未改变项目结构或路径，仅修改本地 Agent 配置文件。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：线路图未受影响，当前任务按既定计划完成。

## 机审区

**机审：通过**（2026-08-09 · 2017 机审席）

审查摘要：
- **范围**：卡分支相对切出点仅改动 `docs/dispatch/ccc/ccc024-2017-agent-ccc-kb-mcp.md` 一个文件（+27/-14，write-back）。`git diff origin/main` 所见 ccc027-032 卡"删除"为分支基准差异（切出点早于 main 出卡 `228b20e7`），非执行体所为，无越界。
- **意图**：按 ccc-plan-011 阶段一 1.2，将 CCC `server.kb.mcp_server` stdio 接入 2017 执行 Agent（OpenCode + Claude Code）并重建 v2 索引。范围限定 2017 用户级配置 + `--reindex`，不碰仓代码/registry/卡/看板，符合卡红线。
- **配置/实现**：复用既存 `server.kb.mcp_server`（薄驱动调用既有能力），无新依赖、无架构风险；操作对象为 2017（`fan@192.168.3.116`），配置前已备份 `.bak-ccc-kb`。
- **验收证据**：回写区报告 `--health` documents=126、sections 含 lessons/projects/decisions/nodes-paths 四域齐全；OpenCode 实测 `knowledge_search` 命中 lessons 返回带 score 教训。运行面证据与目录结构自洽。
- **维护区 Doc-Gate**：四问逐项勾选并填写真实说明，无占位。
- **结论**：无可修问题、无原则性红线问题。通过。

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
