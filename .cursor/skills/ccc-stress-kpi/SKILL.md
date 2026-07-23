# CCC stress KPI loop

Trigger: `压测 KPI` / `stress kpi` / `KPI 闭环` / arm-wake 后的 `AGENT_LOOP_WAKE_stress_kpi`.

## 目的

固定 profile（默认 `efficiency_six`）对业务仓压测 → 对照 `references/stress-kpi-scorecard.json` → **未过门禁就优化再压**，直到 PASS 或用尽 rounds。  
先打通 `ccc-demo`+`qb`，再套已注册旧仓/新仓（同 gates）。

## 硬规则

1. 指标 SSOT：`references/stress-kpi-scorecard.json`（改门槛先改它 + authority）。
2. **量测/门禁/再投递**可脚本化；**改码只经 Cursor**，且仅 `autopilot.code_change_allowlist`。
3. 每轮主攻 ≤2 个 `primary_fail`；禁止用加 `MAX_CONCURRENT` 当主药。
4. 推荐 **4** 轮、上限 **5** 轮（scorecard.rounds）。
5. `duration_s_fill_rate` 不达标 → verdict **INVALID**（不算通关）。

## 命令（2017 量测；M1 Cursor 改平台）

```bash
python3 scripts/ccc-stress-kpi-loop.py init --apps ccc-demo,qb --max-rounds 5
python3 scripts/ccc-stress-kpi-loop.py dispatch
python3 scripts/ccc-stress-kpi-loop.py arm-wake --seconds 3600
# Cursor: bash ~/.ccc/stress-matrix/kpi-loop-arm-wake.sh  (notify ^AGENT_LOOP_WAKE_stress_kpi)

python3 scripts/ccc-stress-kpi-loop.py evaluate
python3 scripts/ccc-stress-kpi-loop.py status
python3 scripts/ccc-stress-kpi-loop.py continue   # 优化部署后再投下一轮
```

门禁单测：

```bash
python3 scripts/ccc-stress-kpi-gate.py --run <run> --write
```

## 唤醒后 Agent 动作

读 `~/.ccc/stress-matrix/kpi-loop-wake-prompt.txt`，执行 evaluate → brief 对照 → PASS 停 / FAIL 按 allowlist 改 → push+2017 热更 → `continue` + 再 `arm-wake`。

## 新仓/旧仓接入压测

`init --apps <id>`（须已 register + baseline 对齐 + 无活跃 inflight）。同一 scorecard。
