# 实验 E21 · web-search credentials 持久化

- **状态**：✅ 完成（源码级）
- **批次**：B5 多代理
- **环境**：源码
- **日期**：2026-08-16

## 结论

**web-search 的凭据走 credentials 服务（`credentialRef`），可经 Models 页/凭据服务持久化；当前未配 `DEEPSEEK_API_KEY`，故 21 次 `WEB_PROVIDER_CREDENTIAL_MISSING`**。配置后可恢复（前提：当前模型档 opencode-go 仍能路由到 DeepSeek 搜索端点）。

## 证据

- `dsh-web-search-deepseek/lib/index.js:2`：`import { credentialRef } from "@deepseek-ai/dsh-credentials"`
- `:174-176`：`apiKey()` 解析 `options.apiKey` → credentialRef → 无则抛错
- `:185`：`WebError('DeepSeek search has no API key...')`（即 WEB_PROVIDER_CREDENTIAL_MISSING 源头）
- `:100-104`：有 key 才走搜索端点

## 结论细节

- 凭据来源链：调用方显式 apiKey → credentialRef（credentials 服务，Models 页可写）→ env。
- 当前 opencode-go 档下，web_search 需要的是 **DeepSeek 官方搜索的 DEEPSEEK_API_KEY**，与 LLM provider（opencode-go）解耦。
- 持久化路径存在（credentials 服务），但需正确设置 key。

## 未覆盖

- 端到端：在 Models 页写入 DEEPSEEK_API_KEY 后 web_search 是否真恢复（需 GUI 操作，未测）。

## 风险 / 对 CCC 借鉴的影响

- web_search 是「半可用」工具（机制在、key 缺）——CCC 若依赖 DSH 联网搜索，要么配 key 要么用外部搜索替代。与「能力声明 vs 部署就绪」区分一致。
