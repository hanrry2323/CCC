# ADR: F-2 size_hint vs R-12 fallback quarantine 冗余判定

**日期**: 2026-07-12
**状态**: 已决 — 保留 F-2，补充 reviewer 端校验

---

## 上下文

v0.28.0 审查指出 F-2（大变更 size_hint）与 R-12（fallback quarantine）存在功能重叠：

- **F-2**: dev 角色 prompt 注入 `## 大变更提示`，要求 LLM 分批改
- **R-12**: reviewer 收到过大 diff 时超时 → fallback quarantine

两者都在"大变更"场景触发，但触发时机不同。

## 决策

**保留 F-2**，与 R-12 互补而非冗余。

| 维度 | F-2 | R-12 |
|------|-----|------|
| 触发时机 | dev 执行前（prompt） | reviewer 检查时（after dev） |
| 机制 | 提示 LLM 分批 | 检测超时 → quarantine |
| 开销 | 0（纯文本） | 耗时（reviewer LLM 已跑完） |
| 失效模式 | LLM 不听话 | LLM 超时 |
| 组合效果 | F-2 减少 R-12 触发概率 | R-12 兜住 F-2 未遵守的 case |

## 结论

F-2 是从源头减负（让 dev 少发大 diff），R-12 是兜底（dev 发了大 diff 时止损）。两者缺一不可。如果 F-2 单独存在，不听提示的 model 会绕过保护；如果 R-12 单独存在，每次大 diff 必须等 reviewer 超时才触发（资源浪费）。

## 后续

- F-2 阈值从纯行数改为加权判定（参见 F2-H1）
- R-12 超时阈值保持可配置（`_config.py` default_timeout）
