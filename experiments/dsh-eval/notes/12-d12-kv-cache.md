# 实验 D12 · compaction KV 缓存复用收益

- **状态**：✅ 完成（机制源码确认；收益量化可选）
- **批次**：B4 会话
- **环境**：源码
- **日期**：2026-08-16

## 结论

**compaction 摘要调用被构造成「下一次路由请求的真前缀」，复用了 provider 的 KV 缓存**（源码确认）。机制成立；具体收益（缓存命中 token 数）依赖 provider 用量指标，未实测量化。

## 证据

- `dsh-compaction-basic/lib/index.js:214-216`：把会话自身 system prompt + tools 放前面，「makes the auxiliary call a genuine prefix of the [next] request, so the provider's KV cache is reused instead of recomputed」
- `:257-259`：默认用 cache-reusing 的 `ctx.llm.stream()` 做摘要，追加 compaction 指令到会话前缀后
- `:639-643`：「Reconstruct the last routed request's cacheable prefix... the call is a genuine prefix and reuses the provider's KV cache」

## 结论细节

- 机制：摘要调用 = 上次路由请求的前缀 + compaction 指令 → provider 前缀缓存命中 → 省一次全量重算。
- 收益量化需 provider usage（`prompt_cache_hit_tokens`）实测；本环境 provider（opencode-go）未取用量，标可选。

## 未覆盖

- 真实 KV 命中率/省 token 数的端到端量化（需长会话触发 compaction + provider 用量）。可选增强。

## 风险 / 对 CCC 借鉴的影响

- 前缀缓存友好是 DSH 省 token 的核心设计之一（与 curated result 并列）；CCC 若用 code-run 编排，长会话的压缩前缀复用可显著降本。
