# Code 梯队精选免费池

运行时真相源仍是本机 **`~/.ccc/relay/upstreams.json`**（gitignore）。本目录只提供名单与探针，**不会**自动灌入真 key。

## 现行默认（2026-07-27）

| 角色 | upstream 命名 | 模型 | 出口 |
|------|---------------|------|------|
| **code 主力** | `opencode-code-*` | `big-pickle` + `deepseek-v4-flash-free` | 一半直连、一半 `proxy: http://127.0.0.1:18080`（HK） |
| **Pro** | （空档） | — | 客户端 `pro` → relay 回落 `flash` |
| **flash** | `opencode-go*` | `deepseek-v4-flash-free` | 同双出口模式 |
| **末位兜底** | `zhipu-code` | `glm-4-flash` | 默认 `enabled:false` |
| **退役** | `xfyun-code` | — | 套餐到期，勿再启用 |

模板：[`templates/relay-upstreams.example.json`](../../templates/relay-upstreams.example.json)  
迁移（2017）：`python3 relay/scripts/migrate-code-to-opencode-free.py`

## 接入 / 探针

```bash
# 探测 flash + code OpenCode 钥
LOOP_UPSTREAMS_FILE=~/.ccc/relay/upstreams.json node relay/scripts/probe-opencode-go.mjs

# 仅 code 档
LOOP_PROBE_FILTER=code LOOP_UPSTREAMS_FILE=~/.ccc/relay/upstreams.json \
  node relay/scripts/probe-opencode-go.mjs

# 经 relay 烟测
curl -sS http://127.0.0.1:4002/v1/chat/completions \
  -H 'content-type: application/json' -H 'authorization: Bearer local' \
  -d '{"model":"code","max_tokens":16,"messages":[{"role":"user","content":"ok"}]}'
```

## IP 轮换口径

不做独立动态 IP 池进程。多 key × 多 `proxy` URL = 多出口。扩容 = 再加 VPS CONNECT + 新 upstream 行。

## 历史 curated

[`code-pool.curated.json`](./code-pool.curated.json) 现以 OpenCode Zen 写码模为主；Groq/OpenRouter 等可作实验，不再主推讯飞。
