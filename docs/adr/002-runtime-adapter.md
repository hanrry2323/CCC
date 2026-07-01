# ADR-002 — Runtime Adapter Pattern

## 状态

Accepted (2026-07-01)

## 决策

Runtime Adapter Pattern — `LlmRuntimeAdapter` interface + 多个实现:

```typescript
interface LlmRuntimeAdapter {
  run(prompt: string, opts: ExecOpts): Promise<ExecResult>
  cancel(runId: string): Promise<void>
  budget(opts: BudgetOpts): Promise<BudgetStatus>
}
```

**当前实现**:
- `ClaudeCodeAdapter` (基于 `claude -p`, 默认)

**未来实现** (planned):
- `OpenCodeAdapter` (基于 `opencode exec`)
- `McpAdapter` (基于 MCP server wrapper)
- `NativeAdapter` (直接调 Anthropic/OpenAI SDK)

## 配置

`./ccc.yaml` 单行切换:

```yaml
runtime: claude-code  # 改一行 = 换执行后端
```

## 理由

用户分析时指出 `claude -p` 等价于 `opencode` 等其他 CLI,
只是不同厂商的"长任务 LLM agent"封装. 用 Adapter Pattern 抽象后:
- 一个项目跑稳后, 切到 opencode/MCP 不需改代码
- 性能/cost 优化可一行为单位试不同后端
- 新厂商出现时可快速实现新 adapter

## 后果

**正面**:
- 配置驱动, 改动成本低
- Adapter 可独立测试
- 模型/工具生态演化不破坏框架

**负面**:
- Adapter 实现需维护
- 不同 adapter 行为可能有微妙差异, 需 conformance test 兜底
