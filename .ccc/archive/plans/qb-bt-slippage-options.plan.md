# Plan: qb-bt-slippage-options — 可配置滑点模型

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

当前回测引擎仅支持单一 flat 百分比滑点模型，`BacktestConfig.slippage_pct: float = 0.0`，通过 `_apply_slippage()` 做 `price * (1 ± pct/100)` 线性缩放。`src/matching/slippage.py` 已有 `ConstantSlippage` / `SquareRootSlippage` / `FixedSlippage` 三个模型，但不被回测引擎使用。

### 代码结构分析

- **入口/核心文件**：
  - `src/backtest_engine/runner.py` — `BacktestConfig`（第 51-84 行）+ `_apply_slippage()`（第 316-324 行）+ `_execute_signal()`（第 326-397 行）
  - `src/matching/slippage.py` — `SlippageModel` ABC + `FixedSlippage` 档位模型（第 120-165 行，`TIERS` 常量+ `lookup()`）
  - `backtest/run_backtest.py` — CLI 入口，第 470-503 行 `main()` 解析参数，第 185-203 行 `run_backtest()` 创建 `BacktestConfig`
  - `tests/backtest/test_runner_slippage.py` — 4 个 flat 模型测试

- **当前结构要点**：
  - `_apply_slippage()` 签名只有 `(price, side)`，无 `amount` 参数，无法实现按量滑点
  - `BacktestConfig` 只有 `slippage_pct` 一个字段，无模型类型选择器
  - CLI `--help` 只有 `--fee`，无 `--slippage-*` 参数，CLI 驱动的回测永远 `slippage_pct=0.0`
  - `execute_signal` 第 334 行调用 `_apply_slippage(exec_price, sig.side)` — `sig.amount` 已存在但未传入
  - `_force_close_all`（第 438-484 行）不回传滑点（末端强平是人为事件），保持不动

- **待改动点**：
  - `src/backtest_engine/runner.py` — `BacktestConfig` 新增 `slippage_model` + `slippage_params`，重构 `_apply_slippage()` 支持 dispatch
  - `backtest/run_backtest.py` — 新增 `--slippage-model` / `--slippage-pct` CLI 参数；`run_backtest()` 和 optimize 分支传递新字段
  - `tests/backtest/test_runner_slippage.py` — 新增 volume-based 模型测试

---

## 范围

- **目标**：在回测引擎中实现三种可选的滑点模型（flat 固定百分比 / volume-based 按量比例档位 / disable 无滑点），通过 CLI 和 `BacktestConfig` 配置
- **只改文件**：
  - `src/backtest_engine/runner.py`
  - `backtest/run_backtest.py`
  - `tests/backtest/test_runner_slippage.py`
- **不改文件**：
  - `src/matching/slippage.py`（独立执行栈模型，保持不动）
  - `src/backtest_engine/recorder.py` / `replay.py`
  - 任何 `src/strategies/`、`src/worker/`、`dashboard/`、`src/config/` 代码
  - `tests/backtest/test_runner.py` / `test_replay.py`（回归不破坏即可）
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1/1）：三模型滑点引擎 + CLI + 测试

### 做什么

**为什么做**：当前只支持 flat 百分比滑点，且 CLI 不暴露滑点配置。生产回测需要 volume-based 模型（大单滑点高、小单滑点低）来反映真实市场影响。同时 flat 和 disable 模型作为灵活选择。

**预期效果**：
- `BacktestConfig` 通过 `slippage_model` 字符串选择模型：`"flat"` / `"volume_based"` / `"disable"`
- volume-based 模式下使用金额档位查表（复用 `src/matching/slippage.py::FixedSlippage.TIERS` 的默认值），档位可通过 `slippage_params` 自定义覆盖
- CLI 新增 `--slippage-model` 和 `--slippage-pct` 参数
- 现有 4 个 flat 滑点测试完全向后兼容

### 怎么做

**文件 `src/backtest_engine/runner.py`**：

1. **`BacktestConfig` 新增字段**（第 51-64 行 dataclass）：
```python
slippage_model: str = "disable"       # "flat" / "volume_based" / "disable"
slippage_params: dict = field(default_factory=dict)  # volume_based 时可用 {"tiers": [[max_amt, bps], ...]}
```
保留 `slippage_pct: float = 0.0` 作为 flat 模型的百分比值（向后兼容）。

2. **`_apply_slippage` 重构**（第 316-324 行）：
```python
def _apply_slippage(self, price: float, side: str, amount: float = 0.0) -> float:
    model = self.config.slippage_model

    if model == "disable" or self.config.slippage_pct <= 0:
        return price

    if model == "flat":
        slip = self.config.slippage_pct / 100.0
        if side in ("buy", "enter_long"):
            return price * (1 + slip)
        if side in ("sell", "exit_long", "close_long"):
            return price * (1 - slip)
        return price

    if model == "volume_based":
        tiers = self.config.slippage_params.get("tiers") or _DEFAULT_VOLUME_TIERS
        bps = self._lookup_volume_slippage(amount, tiers)
        slip = bps / 10000.0  # bps to decimal
        if side in ("buy", "enter_long"):
            return price * (1 + slip)
        if side in ("sell", "exit_long", "close_long"):
            return price * (1 - slip)
        return price

    return price  # unknown model → no slippage
```

3. **新增模块级常量 + 辅助方法**（在 class 外或内均可）：
```python
_DEFAULT_VOLUME_TIERS = [
    (0.001, 1.0),    # <= 0.001: 1 bps
    (0.01, 2.0),     # <= 0.01:  2 bps
    (0.1, 5.0),      # <= 0.1:   5 bps
    (1.0, 10.0),     # <= 1.0:  10 bps
    (float("inf"), 20.0),  # > 1.0: 20 bps
]

@staticmethod
def _lookup_volume_slippage(amount: float, tiers: list[tuple[float, float]] | None = None) -> float:
    tiers = tiers or _DEFAULT_VOLUME_TIERS
    for max_amt, bps in tiers:
        if amount <= max_amt:
            return bps
    return tiers[-1][1]  # fallback to max tier
```

确保 `_DEFAULT_VOLUME_TIERS` 与 `src/matching/slippage.py::FixedSlippage.TIERS` 的值一致以保持对齐。

4. **`_execute_signal` 调用处**（第 334 行）改为传入 `amount`：
```python
exec_price = self._apply_slippage(exec_price, sig.side, sig.amount)
```

**文件 `backtest/run_backtest.py`**：

5. **`BTConfig` dataclass**（第 55-65 行）新增字段：
```python
slippage_model: str = "disable"
```

6. **CLI 参数**（第 471-503 行 `main()` 解析器）新增：
```python
parser.add_argument("--slippage-model", default="disable", choices=["flat", "volume_based", "disable"],
                    help="滑点模型: flat=固定百分比, volume_based=按量比例档位, disable=无滑点")
parser.add_argument("--slippage-pct", type=float, default=0.0,
                    help="flat 模型滑点百分比（如 0.5 = 0.5%%）")
```

7. **`run_backtest()` 函数**（第 185-203 行）创建 `BacktestConfig` 时透传新字段：
```python
runner_config = BacktestConfig(
    ...
    slippage_model=config.slippage_model,
    slippage_pct=args.slippage_pct if hasattr(args, 'slippage_pct') else config.slippage_pct,  # 通过 BTConfig 或 args
)
```

这里注意：`run_backtest()` 当前接受 `BTConfig`，而 `BTConfig` 没有 `slippage_pct` 字段。有两个方案：
- 方案 A（推荐）：`BTConfig` 新增 `slippage_pct: float = 0.0` 字段，`run_backtest()` 透传给 `BacktestConfig`
- 方案 B：修改 `run_backtest()` 签名，额外接受 `slippage_pct` 参数

推荐方案 A（改动最小，与 `BTConfig` 已有的 `fee_rate` 模式一致）。

8. **optimize 路径**（第 568-573 行）创建 `BacktestConfig` 时同样透传：
```python
runner_config = BacktestConfig(
    ...
    slippage_model=args.slippage_model,
    slippage_pct=args.slippage_pct,
)
```

**文件 `tests/backtest/test_runner_slippage.py`**：

9. 新增 5 个测试：
   - `test_volume_based_buy_large_amount` — 大单（1.5 BTC）→ 20 bps → 100 * (1 + 0.0020) = 100.2
   - `test_volume_based_small_amount` — 小单（0.0005 BTC）→ 1 bps → 100 * (1 + 0.0001) = 100.01
   - `test_disable_model_no_slippage` — `slippage_model="disable"` → 价格不变
   - `test_flat_model_backward_compat` — `slippage_model="flat"` + `slippage_pct=0.5` → 与现有 flat 测试行为一致（`test_buy_slippage_increases_price` 用例覆盖）
   - `test_volume_based_invalid_tier_fallback` — amount 超过所有档位 → 返回最后档 bps

### 验收清单

- [ ] `BacktestConfig` 新增 `slippage_model` + `slippage_params` 字段，默认 behavior 不变
- [ ] `slippage_model="disable"` → 价格不变（等价于 `slippage_pct=0.0`）
- [ ] `slippage_model="flat"` + `slippage_pct=0.5` → 精确匹配现有 flat 行为
- [ ] `slippage_model="volume_based"` → 0.5 BTC 10 bps，1.5 BTC 20 bps
- [ ] `_execute_signal` 传入 `amount`，volume-based 模型正确使用
- [ ] CLI `--slippage-model` 解析正确，`--help` 显示 choices
- [ ] CLI `--slippage-pct` 在 `--slippage-model flat` 时生效
- [ ] 现有 4 个 flat 测试全部通过（`test_runner_slippage.py`）
- [ ] volume-based buy/sell 方向正确（buy 涨价，sell 降价）
- [ ] 未知 model 字符串 → 不做滑点（安全 fallback）

### 验收

- [验收条件 1：全部 slippage 测试通过（原 4 + 新 5 = 9）]（参考：`cd ~/program/projects/qb && .venv/bin/python -m pytest tests/backtest/test_runner_slippage.py -v -q`）
- [验收条件 2：compile 零错误]（参考：`.venv/bin/python -m compileall -q src/backtest_engine/runner.py backtest/run_backtest.py`）
- [验收条件 3：CLI `--help` 显示新参数]（参考：`.venv/bin/python backtest/run_backtest.py --help | grep -E "slippage-model|slippage-pct"`）
- [验收条件 4：CLI 实际验证 flat 模式]（参考：`.venv/bin/python backtest/run_backtest.py --strategy buy_hold --symbol BTC/USDT --slippage-model flat --slippage-pct 0.5 2>&1 | tail -5`）
- [验收条件 5：diff 范围仅限白名单]（参考：`git diff --stat` 确认只有 3 个文件变化）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | BacktestConfig 三模型 + _apply_slippage 重构 + CLI + 测试 | `feat(backtest): 可配置滑点模型 flat/volume_based/disable (phase 1/1)` |

---

## 全局验收清单

- [ ] `python3 -m compileall -q src/backtest_engine/runner.py backtest/run_backtest.py` — 零错误
- [ ] `pytest tests/backtest/test_runner_slippage.py -v -q` — 全部通过（9 个测试）
- [ ] `pytest tests/backtest/ -q` — 无回归
- [ ] diff 范围仅限 runner.py + run_backtest.py + test_runner_slippage.py
- [ ] Phase 1 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（1 个 phase）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

- `SquareRootSlippage`（Almgren-Chriss 平方根冲击）可作为后续模型扩展到 backtest 引擎
- volume-based 档位可通过 `slippage_params` 中的 config yaml 覆盖，未来可对接 `config/streams.yaml` 风格的配置体系
