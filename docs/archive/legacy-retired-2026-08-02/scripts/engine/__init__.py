"""engine — CCC Engine 运行时拆包（slot / active_tasks / hang / gates）。

ccc-engine.py 主循环保留 tick 与控制面；高内聚状态机落在本包。
"""
from __future__ import annotations

__all__ = ["slots", "active_tasks", "hang", "gates"]
