"""派发门禁声明式框架（借鉴 Cordis 依赖图思想 · 轻量前置条件版）。

把 Engine 派发主循环（main.py:run_once）里的顺序 if/elif 门禁，抽成
「门禁注册表 + requires 前置条件声明」——每个门禁声明依赖的前置门禁，
框架按 order 排序、校验依赖构成 DAG、遇首块即短路。

设计定位（与 Cordis 的对应）：
- Cordis `inject: ['a','b']`（服务依赖图，满足才激活）→ 本项目 `requires`
  （前置门禁名，先 PASS 才评估）。语义更朴素：CCC 门禁是「前置条件」
  而非「服务 ACTIVE」。
- Cordis Fiber 生命周期自动清理 → 复用 DispatchPool（main.py 现状，零改动）。
- 不引入 Cordis 运行时（JS vs Python）；本模块是纯 Python 框架。

用法：
    from server.engine.gates import GateRegistry, DispatchGate, GateResult

    reg = GateRegistry()
    reg.register(DispatchGate(
        name="parent_closed", order=40,
        check=lambda ctx: GateResult(
            passed=(_parent_blocks_dispatch(ctx.work, ctx.by_id) is None),
        ),
    ))
    result = reg.run(ctx)   # None = 全链放行；否则返回首个阻断结果
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.engine.pool import DispatchPool
from server.engine.store import BoardStore
from server.engine.task import Work

if TYPE_CHECKING:
    from server.engine.dispatch import ExecutorRegistry

logger = None  # 延迟初始化避免循环导入（main.py 装配时再注 logger）


@dataclass(frozen=True)
class GateResult:
    """单个门禁判定。passed=False 等价原 `continue`（跳过本卡进入下一张）。

    Attributes:
        passed: 门禁是否放行。
        reason: 阻断原因（passed=False 时记录，供日志/统计）。
    """

    passed: bool
    reason: str = ""


@dataclass
class GateContext:
    """每轮派发的共享上下文（main.py 构造；work/slots/counters 为跨卡可变状态）。

    Attributes:
        work: 当前待派发卡（每卡循环覆盖）。
        registry: 执行体注册表（热读时每轮可替换）。
        by_id: 全量 work 索引（依赖/父卡检查用）。
        runtime: sidecar 运行时状态（infra 冷却等）。
        now_ts: 当前时间戳（冷却判定基准）。
        store: 看板对接接口。
        log_dir: 执行体日志目录（marker 读写）。
        cfg: 平台配置。
        pool: 派发线程池。
        probe_url: 探活地址（可空）。
        slots: 剩余执行槽位（AUTO submit 后递减）。
        max_concurrent: 全局并发上限。
        timeout: 执行超时秒数。
        counters: 本轮统计计数（summary 用）。
    """

    work: Work
    registry: Any
    by_id: dict[str, Work]
    runtime: dict[str, Any]
    now_ts: float
    store: BoardStore
    log_dir: Path
    cfg: dict[str, Any]
    pool: DispatchPool
    probe_url: str
    slots: int
    max_concurrent: int
    timeout: int
    counters: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchGate:
    """一个派发门禁。

    Attributes:
        name: 唯一名（依赖图节点标识）。
        order: 严格顺序（保持现状执行序；requires 自动校验须先于本门禁）。
        check: ctx -> GateResult；内部可做副作用（计数、状态转移、marker、submit）。
        requires: 前置门禁名集。任一项未 PASS → 本门禁自动短路。
    """

    name: str
    order: int
    check: Callable[[GateContext], GateResult]
    requires: tuple[str, ...] = ()


@dataclass
class GateRegistry:
    """派发门禁注册表（与 scheduler.TaskRegistry 同构 + 依赖边）。

    Attributes:
        gates: name -> DispatchGate。
    """

    gates: dict[str, DispatchGate] = field(default_factory=dict)

    def register(self, gate: DispatchGate) -> None:
        """注册门禁；重名抛 ValueError。"""
        if gate.name in self.gates:
            raise ValueError(f"duplicate gate: {gate.name}")
        self.gates[gate.name] = gate

    def ordered(self) -> list[DispatchGate]:
        """按 order 排序；校验 requires 为「已注册且先序」→ 简单 DAG 判定，杜绝环。

        Returns:
            按执行顺序排列的门禁列表。

        Raises:
            ValueError: requires 引用未注册门禁，或依赖后于本门禁（构成环）。
        """
        gates = sorted(self.gates.values(), key=lambda g: g.order)
        seen: set[str] = set()
        for g in gates:
            missing = set(g.requires) - seen - {g.name}
            if missing:
                raise ValueError(f"gate {g.name!r} 依赖未先序注册/执行: {sorted(missing)}")
            seen.add(g.name)
        return gates

    def run(self, ctx: GateContext) -> GateResult | None:
        """按序执行门禁链；首个 passed=False 即停（等价原 continue）。

        Returns:
            None = 全链放行（AUTO 走到 submit 成功）；
            否则返回首个阻断结果。
        """
        results: dict[str, GateResult] = {}
        for gate in self.ordered():
            # 依赖短路（防御；正常线性链到不了这里）：前置未 PASS → 直接阻断
            for req in gate.requires:
                r = results.get(req)
                if r is None or not r.passed:
                    return r or GateResult(passed=False, reason=f"前置门禁 {req} 未通过")
            res = gate.check(ctx)
            results[gate.name] = res
            if not res.passed:
                return res
        return None
