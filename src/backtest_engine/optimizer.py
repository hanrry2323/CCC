"""
ParamOptimizer - Grid search parameter optimization for backtest strategies.

Provides a reusable ParamOptimizer class that performs exhaustive grid search
over strategy parameters, collects metrics, and ranks results by configurable metrics.
"""

from typing import Dict, List, Any, Optional, Sequence
import json
from src.backtest_engine.runner import BacktestRunner
from src.backtest_engine.recorder import BacktestRecorder
from src.utils.registry import STRATEGY_REGISTRY


class ParamOptimizer:
    """Grid search parameter optimizer for backtest strategies."""

    def __init__(
        self, strategy_class: Any, config: Dict[str, Any], bars: List[Dict[str, Any]]
    ):
        """
        Initialize the parameter optimizer.

        Args:
            strategy_class: Strategy class from STRATEGY_REGISTRY
            config: Backtest configuration dictionary
            bars: Market data bars
        """
        self.strategy_class = strategy_class
        self.config = config
        self.bars = bars
        self._runner = BacktestRunner(config=config)
        self._recorder = BacktestRecorder()

    def grid_search(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """
        Perform exhaustive grid search over parameter combinations.

        Args:
            param_grid: Dictionary mapping parameter names to lists of values

        Returns:
            List of result dictionaries. Each result contains:
                - params: The parameter combination used
                - metrics: Dictionary of calculated metrics

        Example:
            >>> optimizer = ParamOptimizer(SMA, config, bars)
            >>> param_grid = {'period': [7, 14, 21], 'offset': [3, 7]}
            >>> results = optimizer.grid_search(param_grid)
            >>> # results will have 6 entries (3×2 combinations)
        """
        results = []
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for combination in self._cartesian_product(param_values):
            params = dict(zip(param_names, combination))

            try:
                result = self._run_backtest_with_params(params)
                results.append(result)
            except Exception as e:
                print(f"Error running backtest with params {params}: {e}")

        return results

    def rank(
        self,
        results: List[Dict[str, Any]],
        metric: str = "total_return_pct",
        top_n: int = 10,
        ascending: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Rank results by specified metric.

        Args:
            results: List of result dictionaries from grid_search()
            metric: Metric to rank by (total_return_pct, sharpe_ratio, etc.)
            top_n: Number of top results to return
            ascending: If True, lower values rank higher

        Returns:
            Sorted list of top N results
        """
        if not results:
            return []

        sorted_results = sorted(
            results,
            key=lambda x: x["metrics"].get(metric, float("-inf")),
            reverse=not ascending,
        )

        return sorted_results[:top_n]

    def print_ranking(
        self,
        results: List[Dict[str, Any]],
        top_n: int = 10,
        metric: str = "total_return_pct",
    ) -> str:
        """
        Print formatted ranking table to stdout.

        Args:
            results: List of ranked results
            top_n: Number of top results to display
            metric: Metric used for ranking

        Returns:
            Formatted string with table header, separator, and result rows
        """
        if not results:
            return "No results to display."

        top_results = self.rank(results, metric=metric, top_n=top_n)

        output = []
        output.append(f"\nTop {len(top_results)} results by {metric.upper()}:\n")

        header = f"{'Rank':<6}{'Params':<30}{'Return %':<10}{'Sharpe':<10}"
        header += f"{'Max Drawdown %':<12}{'Profit Factor':<12}{'Trades':<8}"
        header += f"{'Win Rate %':<10}{'Final Equity':<12}\n"
        output.append(header)

        separator = "-" * len(header)
        output.append(separator)

        for i, result in enumerate(top_results, 1):
            params = ", ".join([f"{k}={v}" for k, v in result["params"].items()])
            metrics = result["metrics"]
            output.append(
                f"{i:<6}{params:<30}{metrics.get('total_return_pct', 0):<10.2f}"
            )
            output.append(f"{'':<36}{metrics.get('sharpe_ratio', 0):<10.2f}")
            output.append(f"{'':<36}{metrics.get('max_drawdown_pct', 0):<12.2f}")
            output.append(f"{'':<36}{metrics.get('profit_factor', 0):<12.2f}")
            output.append(f"{'':<36}{metrics.get('total_trades', 0):<8}")
            output.append(f"{'':<36}{metrics.get('win_rate', 0):<10.2f}")
            output.append(f"{'':<36}{metrics.get('final_equity', 0):<12.2f}\n")

        return "".join(output)

    def _create_v2_strategy(self, params: Dict[str, Any]) -> Any:
        """Create strategy instance using v2 pattern."""
        try:
            strategy = self.strategy_class(params=params, bars=self.bars)
            return strategy
        except Exception as e:
            raise ValueError(f"Failed to create strategy with params {params}: {e}")

    def _run_backtest_with_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run single backtest with given parameters."""
        strategy = self._create_v2_strategy(params)

        backtest_result = self._runner.run_backtest(strategy, self.bars)
        trade_records = self._recorder.record_trades(backtest_result, strategy)

        metrics = {
            "total_return_pct": backtest_result.get("total_return_pct", 0),
            "sharpe_ratio": backtest_result.get("sharpe_ratio", 0),
            "max_drawdown_pct": backtest_result.get("max_drawdown_pct", 0),
            "profit_factor": backtest_result.get("profit_factor", 0),
            "total_trades": backtest_result.get("total_trades", 0),
            "win_rate": backtest_result.get("win_rate", 0),
            "final_equity": backtest_result.get("final_equity", 0),
        }

        return {"params": params, "metrics": metrics}

    @staticmethod
    def _cartesian_product(
        values_lists: Sequence[Sequence[Any]],
    ) -> List[Dict[str, Any]]:
        """Compute Cartesian product of multiple lists."""
        if not values_lists:
            return [{}]

        def helper(idx: int, current: List[Any]) -> List[List[Any]]:
            if idx == len(values_lists):
                return [current[:]]

            results = []
            for value in values_lists[idx]:
                current.append(value)
                results.extend(helper(idx + 1, current))
                current.pop()

            return results

        return helper(0, [])


def build_optimizer(
    strategy_name: str, args: Dict[str, Any], bars: List[Dict[str, Any]]
) -> ParamOptimizer:
    """Factory function to build ParamOptimizer from CLI args."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    strategy_class = STRATEGY_REGISTRY[strategy_name]

    return ParamOptimizer(
        strategy_class=strategy_class, config=args.get("config", {}), bars=bars
    )
