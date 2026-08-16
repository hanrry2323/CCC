# 实验 C9 · both 模式实际调用路径

- **状态**：✅ 完成
- **批次**：B3 模式
- **环境**：测试实例（headless，DSH_TOOLS_MODE=both）
- **日期**：2026-08-16

## 结论

**both 模式下模型走直接工具调用路径，不用 run_code**（deepseek-v4-flash 实测）。会话 `session-cf8a0c07-58b4-4f12-96db-3a8d18200394`，`code-dispatch: 0`，模型自述「直接调用 bash 工具，没有写代码程序」。

## 方法

headless 以 `DSH_TOOLS_MODE=both` 跑简单任务「列出当前目录文件 + 说明调用方式」，观察会话工具调用形态。

## 结果

- 模型：直接调用 `bash`（`ls -la`），无 run_code。
- 会话：`code-dispatch: 0`（无代码路径）。
- 模型自述：「用的是直接调用工具的方式——直接调用 bash 工具……没有写代码程序去封装工具调用。」

## 解读

- 当 native schema + tools:sdk **同时**暴露，模型（deepseek 系，原生工具调用训练主导）选择熟悉路径。
- **CodeRun 范式的收益只有在 code 是唯一路径时才显现**——both 模式对 deepseek 模型实际≈native。
- 这与「想用 code-run 节约调用就得强制 code 模式」一致。

## 未覆盖

- both 模式下写代码类任务（复杂多步编排）是否仍会切到 code 路径？本测试是简单任务，复杂任务的行为未测。

## 风险 / 对 CCC 借鉴的影响

- 若要 CodeRun 的并发/编排收益，必须 **code 或 both+提示强引导**；both 默认走 native，节约目标落空。
- CCC 选 DSH 执行模式时：code=要代码编排、native=要直接调，both 是个「模型自己选」的模糊档。
