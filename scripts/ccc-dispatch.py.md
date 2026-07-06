# `ccc-dispatch.py` — v1.0 Task Dispatcher (Triple Output, No Auto-Dispatch)

> CCC v1.0 任务派单器。读 plan.md + phases.json，推断 capability，查询 cluster-bus，**输出三元组给人 review**。

## 用途

P0-2 落地：让用户说"按 ccc full 跑 X"后，CCC 输出 `[node_id, target, model_tier]` + 等 stdin 'yes' 才发。

## 用法

```bash
echo "yes" | python3 scripts/ccc-dispatch.py \
    --plan <path>/.ccc/plans/<task>.plan.md \
    --workspace <project_root>
```

## Triple Output

```
[dispatcher] plan=<task>
[dispatcher] needed_capability=<csv>
[dispatcher] candidates:
  - <node_id> @ <host:port>, capabilities=[...], load=<n>
[dispatcher] recommendation: <node_id> (score=<n>)
[dispatcher] model_tier: <flash|sonnet|opus|max>
[dispatcher] est_cost_seconds: <int>
[dispatcher] target: <host:port>
[dispatcher] VERDICT: ready-for-human-review (NOT auto-dispatch)
[dispatcher] AWAITING human confirmation: type 'yes' to dispatch
```

如果用户**不**输入 'yes' → ABORT exit=4。

如果 stdin 是 EOF（如 pipeline 末尾）→ ABORT（防自动派单）。

## Exit codes

- 0: dispatch artifact 写入完成
- 1: cluster-bus unreachable（网络层）
- 2: 无 candidates 候选（cluster 空或匹配 0）
- 3: 无 eligible node
- 4: 人工 yes 未确认 → ABORT

## Capability Inference

heuristic keywords in plan.md:
- `shell` / `python` / `git` → L1 capability
- `claude-p` → L2 capability
- `ollama` / `opus` / `deepseek` → specific capability

显式 marker `capability:` 或 `needs:` 行：

```
capability: shell, claude-p, git
```

显式优先于 keyword。

## Model Tier Inference

heuristic keywords:
- `opus` / `security` / `critical` → `opus`
- `flash` / `minimax` / `trivial` → `flash`
- else → `sonnet` (CCC Executor default)

## Score 函数

```
score = (matched / needed) - (load / 200)
```

- matched < needed: eligible（PoC 模式，开了宽口径）
- matched == 0: not eligible
- perfect match (matched == needed): score ≈ 1.0
- high load: penalty 最多 0.5

## Dispatch Artifact

`--workspace <workspace>` 写到：
- `<workspace>/.ccc/dispatches/dispatch-<task>.json`

字段：plan / picked_node / target / needed_capability / model_tier / est_cost_seconds / dispatched_at / note

`dispatched_at=0` 表示 PoC 模式 — 未真发 claude -p，仅落 artifact。

## Example (PoC 模式)

```bash
# 启动 bus + 注册 m1
python3 scripts/cluster-bus.py &
curl -X POST localhost:9100/api/node/register \
  -d '{"node_id":"m1","host":"127.0.0.1","port":9101,"capabilities":["shell","claude-p","git"]}'

# 跑 dispatcher
echo "yes" | python3 scripts/ccc-dispatch.py \
    --plan ~/.ccc/plans/v1.0-automation.plan.md \
    --workspace ~/program/CCC

# → recommendation: m1 (score=0.795)
# → artifact: .ccc/dispatches/dispatch-v1.0-automation.plan.json
```

## 红线 18 (capability 必须默认开启)

> 本 dispatcher 已默认开启 capability 匹配（不像 clwmmed v3.1 注释掉）。
> 此行为由 `tests/cluster/test-capability-required.py` 强制保障。

## 关联

- `references/cluster-protocol.md` § discovery
- `tools/cluster-doctor.sh` (诊断 cluster)
- `tests/cluster/test-capability-required.py` (红线 18 guard)
- `.ccc/reports/p0-2-ccc-dispatch.report.md` (实现报告)
