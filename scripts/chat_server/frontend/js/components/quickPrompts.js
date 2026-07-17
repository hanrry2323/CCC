/**
 * Hub 快捷动作 → 发给 Agent 的完整指令（对用户气泡只显示短标签）。
 *
 * 原则：
 * - 对用户：回复精简、结构化
 * - 对 Agent：先做足探测/读码/可选 skill，再给结论；禁止空话套话
 */

export const REPLY_COMPACT =
  '【对用户回复】用中文、短句、少装饰；禁止复述工具过程；禁止大段代码；' +
  '能用列表就不用散文。字数上限见各任务。';

/** 下一步 */
export const NEXT_STEP_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：给出「下一步开发」决策建议\n' +
  '你是本仓库的技术负责人。先私底下把功课做完，再给用户极短结论。\n\n' +
  '## 必修探测（按序，能跑就跑）\n' +
  '1. 读 `.ccc/profile.md`、`.ccc/state.md`（若存在）；再扫 `README.md` / `GOAL.md` / `CLAUDE.md` 开头。\n' +
  '2. 跑 `git status -sb` 与 `git log -8 --oneline`；若有脏文件，看 `git diff --stat`。\n' +
  '3. **优先**用 codebase-memory / 代码地图类 skill 或 MCP：`list_projects` → `get_architecture` 或 `search_graph` 抓主模块；' +
  '不可用则用 Glob/Grep 定位入口（main、app、scripts、src）。\n' +
  '4. 若有 `.ccc/board/`：数一下 backlog / planned / in_progress / abnormal 量级，点名是否卡在 product/契约。\n' +
  '5. 对照本会话已讨论内容，消掉已否决方案。\n\n' +
  '## 决策标准\n' +
  '- 优先：解阻塞（失败/脏树/契约）> 可验证的小步交付 > 大重构\n' +
  '- 每条建议必须可执行（谁改什么、怎么验收），禁止「继续优化」「加强测试」这类空话\n\n' +
  '## 输出格式（总字数 ≤220）\n' +
  '### 下一步\n' +
  '1. …（≤28字）\n' +
  '2. …\n' +
  '3. …\n' +
  '最佳：<编号或标题> — <一句理由>\n' +
  '若尚未对齐基线：第一行写「假设：…」再给选项。\n';

/** 扫风险 */
export const SCAN_RISKS_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：真实风险扫描（不是清单模板）\n' +
  '## 必修探测\n' +
  '1. `git status --porcelain`；有脏文件则 `git diff --stat`，并对 Top 变更文件抽样 `git diff`（找密钥、半截重构、调试残留）。\n' +
  '2. 读 `.ccc/state.md` / 控制面暗示；若 `.ccc/stats/failures.jsonl` 或 `abnormal` 列可读，提炼近期失败类型。\n' +
  '3. 有 codebase-memory：对脏文件或核心模块 `detect_changes` / `trace_path`；否则 Grep 危险模式（TODO|FIXME|password|api_key|skip|xfail）。\n' +
  '4. 快速看测试入口是否明显坏（缺 pytest.ini、测试目录空、最近失败线索）。\n\n' +
  '## 输出（≤200字）\n' +
  '### 风险\n' +
  '- 只写**会踩坑**的项（影响发布/下达/数据/安全）；无则「无明显风险」\n' +
  '### 建议\n' +
  '一句可执行处理顺序。\n';

/** 解释未提交 */
export const EXPLAIN_DIFF_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：解释未提交改动的真实意图与风险\n' +
  '## 必修探测\n' +
  '1. `git status --porcelain` + `git diff --stat`\n' +
  '2. 按变更量排序，对前 5 个文件读 `git diff`（或 Read 关键关键）\n' +
  '3. 若可用 codebase-memory：`detect_changes()` 映射受影响符号；评估扇入/调用方\n' +
  '4. 标注是否像 WIP、是否含密钥/生成物、是否该拆 commit\n\n' +
  '## 输出（≤220字）\n' +
  '### 在做什么\n' +
  '- 按文件/模块点名（动词开头）\n' +
  '### 风险\n' +
  '一句\n' +
  '### Commit？\n' +
  '建议：现在 commit / 先补测 / 先拆分 — 一句理由\n';

/** 结构审阅（代码地图） */
export const MAP_REVIEW_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：用代码地图 / 结构图审阅本项目\n' +
  '## 必须调用 skill / 工具（有则用，无则降级说明）\n' +
  '优先加载并遵循 **codebase-memory（代码地图）** skill：\n' +
  '1. `list_projects` → 确认本仓是否已索引；未索引则说明，并改用 Glob/Read 手工建「迷你架构」\n' +
  '2. `get_architecture` 或 `get_graph_schema` + `search_graph` 抓核心包/入口\n' +
  '3. 对 1～2 个关键路径 `trace_path(direction="both", depth=2~3)`（或高扇出函数）\n' +
  '4. 可选：`search_graph(max_degree=0, exclude_entry_points=true)` 找可疑死代码（抽样即可）\n' +
  '5. 对照 `.ccc/profile.md` / README，标出文档与代码不一致处\n\n' +
  '## 审阅维度（每维最多 2 条证据）\n' +
  '- 边界是否清晰（入口 / 领域 / 基础设施）\n' +
  '- 高耦合或上帝模块\n' +
  '- 危险依赖边（跨层、循环、隐式全局）\n' +
  '- 与当前看板/目标的错位\n\n' +
  '## 输出（≤280字，必须含结论）\n' +
  '### 架构一句话\n' +
  '### 发现\n' +
  '- …（带符号或路径）\n' +
  '### 结论\n' +
  '健康 / 需治理 / 阻塞开发 — 一句\n' +
  '### 下一步\n' +
  '唯一最该做的一件事（可直接变成任务标题）\n';

/** 定稿方案 — 见 dispatchFormat，此处仅补工作协议前缀 */
export const FINALIZE_WORK_PREFIX =
  REPLY_COMPACT +
  '\n\n# 任务：把本会话方案定稿为可投递 CCC 的契约包\n' +
  '## 定稿前必修（静默完成）\n' +
  '1. 归纳本会话共识；丢弃被否决项。\n' +
  '2. 用 Glob/Read（或 codebase-memory）核对你将写入 `scope` 的每个路径：必须是仓库内真实相对路径；禁止 `["all"]`、禁止臆造。\n' +
  '3. Phase 拆分遵循：可独立验收、依赖用 `depends_on`、单 phase timeout 合理（默认 600）。\n' +
  '4. 「验收」必须可执行（命令或可观察结果），至少 1 条。\n' +
  '5. 复杂度：改动 ≤2 文件小步 → small；跨模块/多 phase → medium；架构级 → large。\n' +
  '6. 若信息不足：仍输出块，但在 PLAN「目标」首条写清假设；不要改用闲聊格式。\n\n' +
  '## 输出约束\n' +
  '只输出下面这一个块（不要前后解释、不要省略分隔符）。\n\n';
