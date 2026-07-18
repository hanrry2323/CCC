"""board.roles — 稳定角色入口（实现已下沉到子模块）。"""
from __future__ import annotations

from board.roles.product import (
    product_role,
    launch_product_async,
    check_product_async,
)
from board.roles.dev import (
    dev_role,
    dev_role_launch,
    dev_role_relaunch,
    dev_role_check_complete,
)
from board.roles.reviewer import (
    reviewer_role,
    launch_reviewer_async,
    check_reviewer_async,
)
from board.roles.tester import (
    tester_role,
    launch_tester_async,
    check_tester_async,
)
from board.roles.ops import ops_role
from board.roles.kb import kb_role
from board.roles.audit import audit_role
from board.roles.regress import regress_role

__all__ = [
    "product_role",
    "launch_product_async",
    "check_product_async",
    "dev_role",
    "dev_role_launch",
    "dev_role_relaunch",
    "dev_role_check_complete",
    "reviewer_role",
    "launch_reviewer_async",
    "check_reviewer_async",
    "tester_role",
    "launch_tester_async",
    "check_tester_async",
    "ops_role",
    "kb_role",
    "audit_role",
    "regress_role",
]
