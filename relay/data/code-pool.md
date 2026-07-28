# Flash · 付费-only 池说明

运行时真相源仍是本机 **`~/.ccc/relay/upstreams.json`**（gitignore）。本目录只提供名单与探针，**不会**自动灌入真 key。

## 现行默认（2026-07-28）

| 角色 | upstream 命名 | 模型 | 出口 |
|------|---------------|------|------|
| **flash 活跃付费** | `opencode-go-paid-*`（**恰好 1** `enabled`） | `deepseek-v4-flash` · `zen/go/v1` | **仅直连**（无 `proxy`） |
| **flash 备份付费** | 另一把 `opencode-go-paid-*`（`enabled:false`） | 同左 | 人通知后切换 |
| **Pro / code** | — | — | **轮空** |
| **免费 / MiniMax** | — | — | **禁止启用** |

模板：[`templates/relay-upstreams.example.json`](../../templates/relay-upstreams.example.json)

**扩容 ≠ 加免费钥**。额度用尽 = 人手切备份 Go 钥。

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

[`code-pool.curated.json`](./code-pool.curated.json) 含旧免费/实验项，**仅档案**；勿当现行启用清单。
