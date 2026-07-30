# FlowWeave 对照 → CCC 产线落地（2026-07-30）

> 目标：评估开源 FlowWeave 可借鉴点，**不做成第二个 FlowWeave**；只服务 CCC 心智：  
> 对话理解意图 → **意图链自动投入** → Engine 自动开发/验收 → 失败自愈。

## 定位差

| | FlowWeave | CCC |
|--|-----------|-----|
| 主业 | 本地代码理解 + Agent 桌面工作台（画布/适配器） | Hub→Engine **产线编排** + Desktop 意图门 |
| 写码 | 本机 Agent + 确认执行 | 权威仓 Engine（OpenCode）扇出 |
| 不做 | 产线调度 / 看板飞轮 / 双机拓扑 | 画布主控、六 IDE 适配器 |

昨日曾合入再删：`_code_indexer` / `_agent_bridge` / `_diff_check`（`c20ec3e`→`d67d772`）——**未进主路径的实验脚本，禁止无脑恢复**。

## 对照表

| FlowWeave 优势 | CCC 缺口（当时） | 本次改造 |
|----------------|------------------|----------|
| 三级扫描（glob→AST→跨文件） | Hub `hub_modules`/locate 已够产线；全量 tree-sitter 非热路径 | **不恢复** `_code_indexer`；继续透镜 + modules |
| ToolAdapter + plan/execute 确认 | CCC 已有 transfer_gate + Engine；人点按钮成瓶颈 | **自动投链**（删「转意图卡」按钮；Agent 出契约即 promote） |
| Agent Protocol 文件桥 | CCC 冲刷器 = sidecar outbox；平行 bridge 死路径 | **不恢复** `_agent_bridge` |
| 敏感文件/大 diff/删除预警 | transfer_gate 缺敏感 scope | **薄** `_diff_check.py` → `sensitive_scope` 入 gate；DoD 已有 scope/噪音卫生 |
| 插件/skill 生态 | CCC 用仓内 skills + SOP 注入 | **不搬** Electron 插件栈 |
| 原子写/suggestedActions | 部分已有 | 保持现有 outbox/atomic；失败给 `fix_hint` |

## 硬结论

1. 可借鉴：**安全检查模型**（敏感路径）映射到 transfer_gate；**确认门**思想保留为 gate（系统质控），但**发起权**从「人点按钮」改为「Agent 理解后自动投链」。  
2. 不重叠 / 不做：画布、六适配器、独立文件桥、全仓 AST 索引主路径。  
3. 产线验收仍靠：意图链 SOP + Engine + abnormal/post-exhaust 自愈 + 真实业务卡。
