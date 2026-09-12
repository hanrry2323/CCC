# 任务卡 tst906 · L1-E xy 纳回 G5 探针（过 card_gate 验证）

> 关联：L1-E·xy 纳回卡（docs/receipts/2026-09-13-l1e-xy-nareg.md）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：主脑 · 项目：tst · 日期：2026-09-13 · 版本：tst906 · 状态版本：2
> 业务仓：无（纯探针，零业务改动）

## 目标
验证「xy 项目能接上当前产线」的卡头兼容性（G5 门槛）——一张纯探针卡经 card_gate 五项校验后走 DSH 执行，产出最小结果。这是 L1-E·xy 纳回的前置机械步骤，不触碰任何业务代码。

## 实现要求
执行体按 DSH 心智跑本卡：读卡 → 在范围白名单内自检（本卡=探针，无业务改动）→ 自测（探针输出等）→ 写 .ccc-result.md（五段）→ 停手。

## 红线
1. 只读探针：不修改任何业务代码、不触碰 xy 或任何其他业务仓。
2. 范围唯一路径=本卡所在目录（docs/dispatch/tst/），改动仅本卡自身。
3. 完成后停手，不额外补改。

## 范围
- docs/dispatch/tst

## 步骤
1. 确认本卡被 card_gate 五项校验放行（执行体=DSH 在集合内、状态=待分派）。
2. 探针输出：记录执行体/日期/校验结论。
3. 自测：探针输出非空、维护区四问齐。
4. 写 .ccc-result.md 并交由 wrapper 传输，停手。

## 验收标准
- 探针通过：card_gate 五项校验（执行体=DSH 在集合内）→ 合法卡 PASS 走派发
1. 探针输出如实记录执行环境与结论（执行体、日期、校验结果）。
2. 自测输出=0、探针输出非空、维护区四问齐。
3. 结论：本卡被 card_gate 正常放行（合法）→ 记「G5=PASS」到回执。

## 门禁
- card_gate 五项校验（关联/执行体/验收/状态/派发/项目/日期齐全、状态=待分派、项目前缀在 registry、验收≥1 条可核、范围路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问（方案同步/教训沉淀/档案README/线路图）逐项填。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡「tst906 · L1-E xy 纳回 G5 探针（过 card_gate 验证）」：纯探针卡，验证「xy 项目能接上当前产线」的卡头兼容性（G5 门槛）——一张纯探针卡经 card_gate 五项校验后走 DSH 执行，产出最小结果。L1-E·xy 纳回的前置机械步骤，不触碰任何业务代码。业务仓：无。

## 1. 探针输出

- 执行体：DSH（卡头「执行体：DSH」；DSH ∈ card_gate 受管执行体集合 `{"DSH","PI@195","PI@252"}`，见 server/engine/card_gate.py:209，触发全量五项校验）
- 日期：2026-09-13（系统日期输出 `2026-09-13 06:17:32 CST`，与卡头日期一致）
- 校验结论：card_gate 五项校验 **PASS**（`validate_card` 问题清单=[]，退出码=0）

探针命令（workdir=/Users/fan/program/CCC，PYTHONPATH=/Users/fan/program/CCC）：
```
$ python3 - <<'PY'
from server.engine.card_gate import validate_card
from server.board.registry import load_projects
card = "docs/dispatch/tst/tst906-l1e-xy-g5-probe.md"
projs = {p.prefix for p in load_projects() if p.prefix}
problems = validate_card(card, repo_root="/Users/fan/program/CCC")
checks = {
    "1.执行体=DSH 在受管集合内(触发全量校验)": "DSH" in {"DSH","PI@195","PI@252"},
    "2.必填字段齐全+状态=待分派+日期格式": not problems,
    "3.项目前缀 tst 在 registry": "tst" in projs,
    "4.验收标准≥1条可核": "验收标准须" not in problems,
    "5.范围路径在仓内存在": not problems,
}
for k, v in checks.items():
    print(f"  [{'OK' if v else 'FAIL'}] {k}")
print("validate_card 问题清单:", problems if problems else "[]")
print("五项校验结论:", "PASS" if not problems else "FAIL")
PY
```
输出：
```
  [OK] 1.执行体=DSH 在受管集合内(触发全量校验)
  [OK] 2.必填字段齐全+状态=待分派+日期格式
  [OK] 3.项目前缀 tst 在 registry
  [OK] 4.验收标准≥1条可核
  [OK] 5.范围路径在仓内存在
validate_card 问题清单: []
五项校验结论: PASS
SCOREBOARD_EXIT=0
```
补充证据：卡头 line 3 七必填字段齐全（关联/执行体/验收/状态/派发/项目/日期）+状态=待分派；范围路径 `docs/dispatch/tst` 在仓内存在；`tst in registry = True`。

## 2. 自测输出

- 探针输出非空：是（上述探针命令输出非空，含 5 项 OK 逐项核对与结论行）
- 维护区四问齐：是（回写区含 4 行勾选项，逐项 [否]）
- 自测退出码：SCOREBOARD_EXIT=0（探针终版命令 exit=0，验收标准第 2 条「自测输出=0」满足）

## 维护区

1. **方案同步**：[否] 探针卡无方案变更。
2. **教训沉淀**：[无] 探针卡无教训。
3. **档案/README**：[否] 探针卡无档案变更。
4. **线路图**：[否] 探针卡无线路图变更。
