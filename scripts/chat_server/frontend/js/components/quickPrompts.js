/**
 * Hub SPA 快捷动作 → 发给 Agent 的完整指令（对用户气泡只显示短标签）。
 *
 * 语义对齐 Desktop QuickPrompts.swift（透镜 live，非本机 Glob/Read）。
 * 主入口 = Desktop；本文件避免平行真理。
 */

export const REPLY_COMPACT =
  '【对用户回复】中文白话、短句（≤3 句先结论）；只谈问题/场景/能力模块/步骤/取舍；' +
  '禁止文件路径、英文符号名、命令行、大段代码；禁止复述工具过程；' +
  '禁止 transfer-outbox / Terminal / cat > / script_seed / A/B 菜单。字数上限见各任务。';

const INVESTIGATE =
  '你是 Desktop 全功能 App Agent。业务仓事实：一等 hub_* 工具（MCP ccc-hub）或透镜；' +
  '禁止 ssh、禁止本机业务树 Read/git。对齐基线是深对齐可选，非硬门槛。' +
  '板堵：本会话 hub_repair(clear_blockers)；禁止甩锅编排运维；禁止教用户贴命令；禁止默认投卫生 epic。' +
  'digest 不作终局。';

const VERIFY =
  '## 现况核实（静默）\n' +
  '作答前 hub_board + hub_git；再 hub_locate/hub_file 定点 1～3 路径。\n' +
  'ready_for_task=false 或 inflight>0（非纯业务脏）→ clear_blockers；仅业务脏/真在飞时禁新产品 epic。\n' +
  '禁止向用户输出 Hub CLI / outbox / Terminal。\n';

/** 看仓况（旧名「下一步」· 非必经） */
export const NEXT_STEP_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：看仓况并给最佳方案（可选步骤，非定稿必经）\n' +
  INVESTIGATE + '\n' + VERIFY +
  '继承会话目标；不必先点对齐基线。直接给最佳方案，勿甩 A/B。\n\n' +
  '## 输出（总字数 ≤220）\n' +
  '### 判断\n一句：最该推进什么（含是否可开工 / 是否已板务）。\n' +
  '### 最佳方案\n做什么 / 为何现在 / 不做会怎样。\n' +
  '### 备选（可选，一句）\n';

/** 扫风险 */
export const SCAN_RISKS_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：业务/发布风险\n' +
  INVESTIGATE + '\n' + VERIFY +
  '## 输出（≤200字）\n' +
  '### 风险\n- 会怎样坏；无则「无明显风险」\n' +
  '### 建议\n一句处理顺序。\n' +
  '### 可否定稿\n可以 / 暂缓 — 一句理由\n';

/** 解释未提交 */
export const EXPLAIN_DIFF_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：解释未提交改动在「产品上」在干什么\n' +
  '经透镜 git summary 归纳；勿本机 git。\n\n' +
  '## 输出（≤220字）\n' +
  '### 在做什么\n### 风险\n### 要不要提交\n';

/** 结构审阅 */
export const MAP_REVIEW_PROMPT =
  REPLY_COMPACT +
  '\n\n# 任务：用架构视角讲清本项目\n' +
  INVESTIGATE +
  '\n用透镜 tree/locate；回复禁止路径与符号名。\n\n' +
  '## 输出（≤280字）\n' +
  '### 架构一句话\n### 发现\n### 结论\n### 下一步\n';

/** 定稿方案 */
export const FINALIZE_WORK_PREFIX =
  REPLY_COMPACT +
  '\n\n# 任务：把本会话方案定稿为可投递 CCC 的契约包\n' +
  INVESTIGATE + '\n' + VERIFY +
  '## 定稿前必修（静默）\n' +
  '1. 归纳共识；透镜核实 scope 路径真实存在。\n' +
  '2. 验收可执行；板堵先 repair；仅业务脏/真在飞 → feasibility=blocked。\n' +
  '3. 二级卡仅 title/human_note 可改；方案字段锁死。\n' +
  '4. 机械探针 executor_intent=python。\n\n' +
  '## 输出\n' +
  '白话 2～4 句 + 恰好一个 ```ccc-transfer``` JSON 块。\n';
