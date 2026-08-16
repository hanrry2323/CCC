# 实验 B5 · run_code 内层工具超时机制与可配置性

- **状态**：✅ 完成（源码级确认）
- **批次**：B2 链路
- **环境**：源码
- **日期**：2026-08-16

## 结论

**不存在报告所称的固定「30s 内层工具超时」。真实机制是两层、均可配置：**
1. **运行时 `computeMs` 计算预算**：默认 **60000ms（60s）**，zod schema `z.number().default(6e4)`（dsh-code-runtime-worker-thread/lib/index.js:650）——可经 code-runtime 插件配置调高。
2. **单工具调用 `timeoutMs`**：bash 工具支持程序内传 `timeoutMs` 参数（dsh-tool-bash/lib/index.js:122 校验、:399 透传）——长任务可在程序里自设。

**报告维度七「run_code 内层工具另有 30s 超时、20MB 输出上限」中「30s」表述不准确**（未见 30000ms 硬编码；真实默认是 60s compute 预算）。

## 证据

- `computeMs: z.number().default(6e4)` — code-runtime-worker-thread/lib/index.js:650（60s 默认，可配）
- 预算语义：worker 事件循环忙时（eventLoopUtilization，:911）消耗 computeMs；另有墙钟预算
- bash `timeoutMs` 参数：dsh-tool-bash/lib/index.js:122（校验正数）、:273（schema）、:399（透传执行）
- tools 插件配置 schema：`mode` + `maxParallelSubCalls`（dsh-tools/lib/index.js:2549-2554），无固定 tool-call 超时项
- 取消机制为 AbortSignal（dsh-tools/lib/types/index.js:739+），非固定时长

## 结论细节

- **长跑批任务不会必然撞 30s**：可程序内传 bash `timeoutMs`，或经配置调 `computeMs`。
- 但 `computeMs` 60s 是「忙时计算」预算，与墙钟不同——纯 IO 等待不耗 compute；重计算任务会更快撞预算。

## 未覆盖

- `computeMs` 配置调高的端到端实测（改 code-runtime 配置 → 跑 >60s 重计算任务验证）。源码 schema 明确，实测为可选增强。

## 风险 / 对 CCC 借鉴的影响

- 执行体长任务的超时预算可调，是优点；但默认 60s compute 对重计算任务偏紧，CCC 吸收时需按任务类型配预算。
- 「30s」误标提醒：报告二手数据需复核源码，本次纠正一处。
