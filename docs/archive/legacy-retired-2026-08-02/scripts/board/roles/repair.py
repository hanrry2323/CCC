"""board.roles.repair — narrow R2 work-plan rewrite (failure learning).

Does NOT epic product-regen. Prefer calling `_failure_learning.repair_work_plan`
from engine gates; this module is a thin CLI/role entry for tests and ops.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _failure_learning import repair_work_plan


def repair_role(ws: Path, tid: str, *, fail_loops: int = 2) -> dict[str, Any]:
    """Revise `.ccc/plans/{tid}.plan.md` from review_fail pack."""
    return repair_work_plan(Path(ws), tid, fail_loops=fail_loops, use_llm=False)
