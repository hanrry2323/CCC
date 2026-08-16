# 实验 F23 · description 漏参率 × 模型/effort

- **状态**：✅ 基线确认；跨模型对比挂账
- **批次**：B6 模型
- **环境**：会话日志 + 测试实例
- **日期**：2026-08-16

## 结论

**deepseek-v4-flash + reasoningEffort=high 的历史基线 = 57% 漏参**（生产会话 session-5a3a8ff3，116 次 run_code 调用，66 次顶层无 description 全失败）。**跨模型/effort 对比需每运行可指定模型的 harness，本环境未建 → 挂账**。机制面证据已充分：漏参是「模型把内层工具 description 当 run_code 的」混淆（B4 收口），非传输/校验层。

## 证据

- 历史基线：session-5a3a8ff3 116 调用，66 code-only（57%）全失败，50 有 desc 全成功（根因调研 2026-08-16）
- 本次实验全程（B0-B5，~12 次 headless）模型按「逐字执行」指令包裹代码时**不漏** description → **任务形态影响漏参率**：自由写作时易漏、逐字包裹时不易漏
- F23 对比实验设计要点（挂账项）：同任务 × 多模型（flash/code/pro）× 多 effort，各跑 N 轮自由写作统计漏参率

## 结论细节

- 漏参率与「模型自由发挥程度」强相关：给死代码→不漏；自由写→易漏。
- 这支持老板假设3的反面：**低档模型的参数纪律是硬短板，机制（curated/提示）只能缓解**。提升路径 = 模型选型 or 程序边界约束（lossless JSON 已拦一部分）。

## 未覆盖

- 跨模型/effort 的系统对比（flash vs code vs pro × effort 矩阵）——需 per-run 模型 override 的 harness。列为 F 组挂账。

## 风险 / 对 CCC 借鉴的影响

- 若 CCC 用 DSH code-run + 低档模型，**必填参数漏参是主要失效模式**——要么高模型、要么程序边界强约束（如 DSH 自动补 description）。
