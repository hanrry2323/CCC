# Flash 单通道 · 免费池说明

运行时真相源仍是本机 **`~/.ccc/relay/upstreams.json`**（gitignore）。本目录只提供名单与探针，**不会**自动灌入真 key。

## 现行默认（2026-07-28）

| 角色 | upstream 命名 | 模型 | 出口 |
|------|---------------|------|------|
| **flash 免费打头** | `opencode-go-*` / 迁入的原 code 钥 | `deepseek-v4-flash-free` · GLM-4.7 · `big-pickle` | **仅直连**（无 `proxy`） |
| **flash 付费兜底** | `opencode-go-paid-*`（恰好 2） | `deepseek-v4-flash` · `zen/go/v1` | 直连 |
| **Pro / code** | — | — | **轮空**（`enabled:false` 或无行） |

模板：[`templates/relay-upstreams.example.json`](../../templates/relay-upstreams.example.json)

**IP 轮换退役**：不再半直连半 HK。扩容 = 加免费钥行，不是加 VPS。

## 接入 / 探针

```bash
LOOP_UPSTREAMS_FILE=~/.ccc/relay/upstreams.json node relay/scripts/probe-opencode-go.mjs

# 经 relay 烟测（Anthropic + OpenAI 同 flash 池）
curl -sS http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ok"}]}'

curl -sS http://127.0.0.1:4002/v1/chat/completions \
  -H 'content-type: application/json' -H 'authorization: Bearer local' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ok"}]}'
```

## 历史 curated

[`code-pool.curated.json`](./code-pool.curated.json) 现以 OpenCode Zen 模为主；Groq/OpenRouter 等可作实验。讯飞已退役。
