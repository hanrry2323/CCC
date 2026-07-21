# Proactive 触发（CI / git hook → backlog）

> F4-3：外部信号自动投递 bug epic。契约入口：[`hub-api-v1.md`](hub-api-v1.md) §3b。  
> **不**接 CI 平台 API（本仓只提供接收口）；**不**改 transfer 字段 / Desktop / Engine 主循环。

## 语义

| 项 | 说明 |
|----|------|
| 入口 | `POST /api/desktop/proactive-epic` |
| 与 transfer | 等价进 backlog epic；**意图门外**的自动意图；人审 transfer 仍是主路径 |
| 执行标记 | `executor_intent=bug`（扇出时未知 executor 归一为 opencode） |
| 幂等 | `client_request_id = proactive:{source}:{payload_hash}` |
| Engine | **不** wake；依赖既有 tick 消费 backlog |
| 鉴权 | Basic Auth（内网；与 Hub 其它 `/api/desktop/*` 相同） |

## 最小请求

```json
{
  "project_id": "ccc-demo",
  "source": "ci",
  "title": "CI 失败：pytest scripts",
  "goal": "修复 macOS CI pytest 红灯并恢复绿通",
  "acceptance": ["pytest tests/scripts/ -q 绿"],
  "payload": {"job": "pytest", "run_id": "12345", "log_url": "https://…"}
}
```

`source` ∈ `ci` | `git_hook` | `external`。

## CLI

```bash
# stdin
echo '{"project_id":"ccc-demo","title":"CI 失败","goal":"修 pytest","payload":{"run_id":"1"}}' \
  | bash scripts/ccc-ingest-ci-failure.sh

# 文件
bash scripts/ccc-ingest-ci-failure.sh /tmp/ci-fail.json

# 覆盖 Hub / 项目
CCC_SERVER=http://192.168.3.116:7777 CCC_PROJECT_ID=qb \
  bash scripts/ccc-ingest-ci-failure.sh /tmp/ci-fail.json
```

环境变量：`CCC_SERVER`（默认 `http://127.0.0.1:7777`）、`CCC_CHAT_USER` / `CCC_CHAT_PASS`、`CCC_PROJECT_ID`（JSON 缺 `project_id` 时补全）。

## CI webhook 配置示例（后配）

GitHub Actions（示意；需自备 secrets `CCC_HUB_URL` / `CCC_HUB_AUTH`）：

```yaml
- name: Ingest CI failure to CCC
  if: failure()
  env:
    CCC_SERVER: ${{ secrets.CCC_HUB_URL }}
    CCC_CHAT_USER: ${{ secrets.CCC_HUB_USER }}
    CCC_CHAT_PASS: ${{ secrets.CCC_HUB_PASS }}
    CCC_PROJECT_ID: ccc-demo
  run: |
    jq -n \
      --arg title "CI 失败：${{ github.workflow }}" \
      --arg goal "修复 ${{ github.repository }}@${{ github.sha }} 的 CI 红灯" \
      --argjson payload '{"run_id":"${{ github.run_id }}","job":"${{ github.job }}"}' \
      '{project_id:env.CCC_PROJECT_ID, source:"ci", title:$title, goal:$goal, payload:$payload}' \
      | bash scripts/ccc-ingest-ci-failure.sh
```

git `post-receive` / `pre-push` 钩子同理：组装 JSON → 调本脚本。

## 鉴权提醒

- 默认账号仅适本机；共享 LAN 请换强密码或把 Hub 绑 `127.0.0.1` + SSH 隧道。  
- 本波次**不**做 spam 防护 / 鉴权绕过防护；勿把端点暴露公网。  
- 幂等依赖 `payload` 稳定；同一失败重试应带相同 `payload`（如同一 `run_id`）。
