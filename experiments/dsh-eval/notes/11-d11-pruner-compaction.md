# 实验 D11 · pruner 与 compaction 叠加行为

- **状态**：✅ 完成（源码级）
- **批次**：B4 会话
- **环境**：源码
- **日期**：2026-08-16

## 结论

**pruner（确定性剪裁）先于 compaction（LLM 摘要）执行，两道防线都是 `surfaceOp replace` 遮蔽（原文保留在日志）**。超长工具结果先被 pruner 无模型裁剪，若上下文仍超限，再由 compaction 做 LLM 摘要压缩。报告维度三的「先跑 pruner 再 retainTokens=0 强制压缩重试」得到源码确认。

## 证据

- pruner 阈值：`thresholdChars: 8192, headChars: 4096, tailChars: 1024`（dsh-compaction-tool-result-pruner/lib/index.js:10-12）
- compaction 触发：`contextWindow * 0.8` 阈值 + `CONTEXT_WINDOW_EXCEEDED` 时「先 pruner 再强制压缩」（dsh-compaction-basic，报告维度三已述）
- 两者都用 `surfaceOp replace` → 遮蔽而非删除，原文仍可审计

## 结论细节

- 叠加顺序：**pruner（无模型、确定性、剪大结果）→ compaction（有模型、摘要、压旧 span）**。
- pruner 只处理超大工具结果（>8192 字符）的头/尾保留；compaction 处理整体上下文超限。
- 两层的遮蔽都保留原文日志 → 审计友好。

## 风险 / 对 CCC 借鉴的影响

- 无模型剪裁优先、LLM 压缩兜底——先省 token 再动模型，是好的分层设计，CCC 上下文治理可照搬。
- 「遮蔽不删」保证可审计，符合 CCC 证据链要求。
