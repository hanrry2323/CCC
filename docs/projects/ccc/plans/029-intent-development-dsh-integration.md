# 方案 · 意图开发定位强化 + DeepSeek Harness 接入

> 项目：ccc · 编号：ccc-plan-029 · 状态：已确认 · 作者：老板 · 工具：Claude Code
> 创建：2026-08-14 · 更新：2026-08-14
> 关联卡：无
> 关联方案：ccc-plan-027（功能卡两级模型）
> 里程碑：无（方向性方案；可作新里程碑种子）
> 决策源：qx-map `__archive__/decisions/意图开发定位与DeepSeekHarness协同-2026-08-14.md`

## 目标

把 CCC 的定位钉死为**意图开发平台**，明确「不做工具、只做编排」的边界，确立与执行层工具（重点：DeepSeek Harness）的协同方式，并把「一切皆插件」理念吸收进意图层流程设计。

## 背景

DeepSeek Harness（DSH）2026-08-13 发布开源（MIT · 一切皆插件 · 基于 Cordis）。它是 DeepSeek 首款 Agent 框架，定位执行层。对谈后老板定调：

1. 之前定位正确——**CCC 不做 IDE/工具，做编排**。
2. CCC 的外部层（文档 / 项目管理 / 进程管理 / 项目周期管理）是给 Harness 这类工具补的，这类能力 Harness 天生没有。
3. **「意图开发」是 CCC 的重要定位**，需要加固。
4. DSH 是下一步重点接入的 IDE 工具。
5. 学习 DSH「一切皆插件」——CCC 的 Skill / Worker / 节点其实也是插件。

## 方案内容

### 1. 定位钉死（已同步 PRIME-DIRECTIVE §0 + INDEX §0）

**CCC = 意图开发平台，不做工具。** 意图开发四要素：孕育（草案/线路图）→ 澄清（对话收敛）→ 固化（功能卡+验收点）→ 闭环（看板+Loop）。

**执行层 = 可替换执行体槽位**：DSH（headless）/ Claude Code / OpenCode 按 `executors.json` 接入，退出码收单。执行层永远不决定意图。

### 2. DeepSeek Harness 接入（下一步重点）

| 项 | 内容 |
|----|------|
| 定位 | 重点接入的 IDE 工具 / 执行层执行体候选 |
| 优势 | 模型同源（DeepSeek 系）；headless = one-shot runner 契合薄驱动 Engine 契约；Trajectory 可作验收证据原料 |
| 动作 | ① 实测 `dsh headless` 跑一张探针卡验证接入可行性；② 通过则入 `executors.json` 注册表；③ Trajectory 评估接入 card-evidence |
| 门槛 | Developer Preview，兼容性可能被破坏——接入前先实测，不预判 |

### 3. 一切皆插件（意图层吸收）

不照搬 Cordis，吸收「可替换性」作为流程设计默认取向：

- **Skill** → 独立加载/卸载，按角色动态注入（role-skills 已做一半，继续补齐）
- **Worker / 执行体** → 注册表驱动、可替换（已是插件语义，保持）
- **节点 / 门禁** → 每道闸是可替换策略（transfer_gate / 机审 / 合入批准）
- **回写 / 观测** → 每类回写是可插拔钩子（Doc-Gate / 四问 / 证据链）

### 4. 外部层能力独占（加固）

文档（DOC-PROTOCOL / registry / 三层金字塔）、项目管理（里程碑进度）、进程管理（Engine 派发收单）、项目周期管理（看板+Loop 反哺）——**这是 CCC 对 Harness 的护城河**，持续做扎实。

## 验收标准

- [ ] PRIME-DIRECTIVE §0 定位声明已写入，三层金字塔未被破坏
- [ ] INDEX §0 已加定位指针，决策源可回链
- [ ] qx-map 决策已归档（`意图开发定位与DeepSeekHarness协同-2026-08-14.md`）
- [ ] `dsh headless` 实测结果已记录（探针卡跑通 / 跑不通 + 原因）

## 功能卡

> 一个功能一张卡。节点② 老板确认后转卡。DSH 接入涉及执行体实测，需老板确认边界。

### 实测 DeepSeek Harness headless 接入

目标：验证 DSH headless 能否作为 CCC 执行体跑一张探针卡，产出实测结论。

实现：装 Node 工具链 → `npx @deepseek-ai/dsh web` 起服务验证模型连通 → 研究 `dsh` CLI headless 调用方式 → 用探针卡（如纯文档改动）走一遍「拉起→执行→退出码→回写」。

验收：实测结论落卡；能跑通则给出 `executors.json` 接入方案；跑不通则记录原因与替代路径。

## 备注

- **红线**：ccc 平台自研，本方案不走 Engine 自动出卡，由 M1 直接开发（与 ccc-plan-027 同规则）。
- DSH 为 Developer Preview，一切以实测为准，不写死接入承诺。
- 未来方向三线：意图层加深 / 执行层扩展（DSH）/ 插件化改造（Skill/Worker/节点）。
