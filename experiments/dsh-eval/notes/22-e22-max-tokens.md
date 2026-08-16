# 实验 E22 · max-tokens 截断续写方案评估

- **状态**：✅ 完成（机制确认 + 设计评估）
- **批次**：B5 多代理
- **环境**：源码
- **日期**：2026-08-16

## 结论

**max-tokens 截断（finish_reason=length）会吞掉整个工具调用**（assembler 过滤 tool-call）——机制确认。**「保留已生成 arguments 续写补全」是可行的设计修复**（DSH 自述维度八也提出同款），但当前未实现，属 DSH 内部改造建议。

## 证据

- 报告维度八（DSH 自述）：「max-tokens 截断会吞掉整个工具调用（assembler.js:121-126 在 finish=max-tokens 时过滤所有 tool-call）」
- `dsh-llm-deepseek/lib/index.js:333`：`if (typeof choice.finish_reason === "string") pendingFinish...`（finish_reason 处理入口）
- `:164-165`：wire finish_reason → harness FinishReason 映射
- DSH 自述修法建议：「传输侧 finish_reason=length 时保留已生成 arguments 续写」

## 结论细节

- 当前行为：length 截断 → 该 tool-call 整个丢弃 → 模型下轮重试（浪费一轮 + 可能再截断）。
- 续写方案：保留部分 arguments，作为「继续完成此 JSON」的 prompt 发给模型——减少丢失。
- 与 description 根因无关但同属「工具调用健壮性」范畴。

## 未覆盖

- 续写方案的实际实现与收益验证（DSH 内部改造，非本仓库可控）。列为对 DSH 的上游建议。

## 风险 / 对 CCC 借鉴的影响

- 长 code 的 run_code 调用被截断概率高（description 根因会话里 code 最长 6KB）——CCC 吸收时需给 run_code 代码留足 max-tokens 或精简提示。
