"""board role re-exports + ccc_board namespace (test monkeypatch compat).
"""
# flake8: noqa
import types as _types

from board.roles.dev import (  # noqa: E402
    dev_role_launch,
    dev_role_relaunch,
    dev_role_check_complete,
)
from board.roles.reviewer import (  # noqa: E402
    reviewer_role,
    clear_stale_review_locks,
)
from board.roles.tester import tester_role  # noqa: E402
from board.roles.kb import kb_role  # noqa: E402
from board.roles.product import (  # noqa: E402
    launch_product_async,
    check_product_async,
)
from board.roles.audit import (  # noqa: E402
    audit_role,
    _classify_task_intake,
    _run_auto_fix,
    _run_quick_fix,
    _evolve_run_one,
)
from board.roles.common import MAX_RETRY  # noqa: E402
from board.phase import (  # noqa: E402
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _check_phase_failures,
    _current_running_phase,
)

# 兼容测试 monkeypatch：ccc_engine.ccc_board.X（不再 importlib 整文件加载 monolith）
ccc_board = _types.SimpleNamespace(
    dev_role_launch=dev_role_launch,
    dev_role_relaunch=dev_role_relaunch,
    dev_role_check_complete=dev_role_check_complete,
    reviewer_role=reviewer_role,
    tester_role=tester_role,
    kb_role=kb_role,
    MAX_RETRY=MAX_RETRY,
    clear_stale_review_locks=clear_stale_review_locks,
    launch_product_async=launch_product_async,
    check_product_async=check_product_async,
    audit_role=audit_role,
    _classify_task_intake=_classify_task_intake,
    _run_auto_fix=_run_auto_fix,
    _run_quick_fix=_run_quick_fix,
    _evolve_run_one=_evolve_run_one,
    _load_phases=_load_phases,
    _resolve_phase_dependencies=_resolve_phase_dependencies,
    _apply_phase_status_updates=_apply_phase_status_updates,
    _check_phase_failures=_check_phase_failures,
    _current_running_phase=_current_running_phase,
)

