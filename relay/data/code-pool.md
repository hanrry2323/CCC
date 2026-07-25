# Code 梯队精选免费池

运行时真相源仍是本机 **`upstreams.json`**（gitignore）。本目录只提供名单与探针，**不会**自动灌入真 key。

## 精选 6 家（默认）

见 [`code-pool.curated.json`](./code-pool.curated.json)。排除：GitHub Models（上下文过小）、Cloudflare（适配成本）、TOS avoid、keyless。

| name | 注册 | 备注 |
|------|------|------|
| code-groq | https://console.groq.com | 首选 |
| code-opencode-zen | https://opencode.ai | Zen 额度 |
| code-openrouter-free | https://openrouter.ai | `:free` 模型 |
| code-zhipu | https://open.bigmodel.cn | 免费档 |
| code-qwen | https://dashscope.aliyun.com | 兼容模式 |
| code-xfyun | 讯飞星辰 | 稳锚，可非免费 |

## 接入步骤

```bash
# 1. 从 example 拷模板（或手工合并 curated）
cp upstreams.json.example upstreams.json
# 编辑填入各家 API Key，并保留 quota 字段

# 2. 探针（替换 NAME）
node scripts/probe-code-upstream.mjs --name code-groq

# 3. 过检后再启用自动化任务指向 :4002 model=code
npm run build && npm start
```

## 注入 curated（可选）

```bash
# 只合并 data/code-pool.curated.json → upstreams.json（占位 key，需自行替换）
node scripts/inject-free-models.mjs
```

## 网关相关环境变量（v4.2）

| 变量 | 默认 | 含义 |
|------|------|------|
| `STALL_IDLE_MS` | 45000 | 流式空闲超时，超时且未写客户端可换渠 |
| `FAILOVER_MAX_ATTEMPTS` | 6 | 跨上游尝试上限 |
| `FAILOVER_MAX_MS` | 45000 | 单请求 failover 墙钟 |

Admin：`GET /admin/ledger` · `GET /admin/trail`
