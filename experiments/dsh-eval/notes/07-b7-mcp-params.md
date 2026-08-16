# 实验 B7 · MCP 参数白名单

- **状态**：✅ 完成（源码级；端到端受环境限制）
- **批次**：B2 链路
- **环境**：源码 + 测试实例（环境差异）
- **日期**：2026-08-16

## 结论

**DSH 不设 MCP 参数白名单——schema 未声明的多余键会被原样透传给 MCP server**，是否接受由 server 决定。**附带环境发现：headless 测试实例未挂 MCP 工具**（hp-kb/ccc-kb 只在 web profile 配置），`mcp__*` 在 headless 的 tools 命名空间不存在。

## 方法

- 端到端尝试（headless）：`tools.mcp__hp-kb__knowledge_search` 带/不带多余键 → 均报 `is not a function`（MCP 工具不存在）。
- 源码级确认：dsh-mcp-client 转发逻辑。

## 证据

**端到端（headless，会话 session-77806332-6395-4e6a-950f-2c3c4d640394）**：
```
MCP_TOOLS=                        ← tools 里无任何 mcp__ 前缀工具
WITH_EXTRA_ERR tools.mcp__hp-kb__knowledge_search is not a function
CLEAN_ERR      tools.mcp__hp-kb__knowledge_search is not a function
```

**源码（dsh-mcp-client/lib/index.js）**：
- `callToolUncached` → `client.request({method:"tools/call", params:{name: rawName, arguments: args}})`（:82-87）——**完整 args 直接进 MCP 请求，无过滤**。
- 工具执行 `async (args, exec) => callToolUncached(client, rawName, args, ...)`（:213-215）——args 原样传。
- `inputSchema` 原样当 parameters（:141-152），模型侧 SDK 类型带 `& Record<string, JsonValue>`（报告维度二已述）→ **模型可传未声明键**。

## 结论细节

1. **白名单行为**：多余键 DSH 不拦、不剥，原样发给 server；server（hp-kb）是否容忍未知参数决定成败。
2. **环境差异**：headless profile 的 bundle 只有 dsh-base+dsh-headless，MCP client 未挂；web profile 经 cordis.patch.yml 挂了 hp-kb/ccc-kb。→ headless 实验若要测 MCP，需在 headless profile 补 mcp-client 补丁 + symlink（web profile 的做法）。

## 未覆盖

- hp-kb 对未知参数的实际响应（容忍/拒绝）——需在挂上 MCP 的实例端到端测，或直连 8083 发 JSON-RPC。列为可选增强。

## 风险 / 对 CCC 借鉴的影响

- MCP 桥「无白名单透传」是把参数校验责任推给 server；CCC 若接 MCP 工具，server 侧要自己校验未知键（防注入/误用）。
- headless 与 web 工具面不一致是 DSH 部署注意点：实验/执行体选型要清楚各 profile 挂了哪些工具。
