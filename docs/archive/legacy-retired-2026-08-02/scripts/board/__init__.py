"""board — CCC 看板职责拆分包（F-ROLE-02）。

子模块:
  context   — workspace 上下文（无模块级 ROOT 补丁）
  lock      — 统一 fcntl.flock
  prompt    — phase/role prompt 拼装
  phase     — phases.json 依赖 / 失败传染
  store / store_ops — CRUD / FileBoardStore
  slots     — 跨进程 opencode 槽位
  roles/    — 角色实现包（product/dev/reviewer/…）
"""
from board.context import (
    board_dir,
    clear_workspace,
    ccc_home,
    events_dir,
    get_workspace,
    set_workspace,
)
from board.lock import (
    acquire_board_lock,
    acquire_flock,
    acquire_named_lock,
    release_board_lock,
    release_flock,
    release_named_lock,
)
from board.prompt import build_dev_phase_prompt, build_dev_phase_prompt_with_hint
from board.store_ops import (
    create_task,
    get_store,
    list_tasks,
    move_task,
    quarantine,
    reset_store_cache,
    update_index,
)

__all__ = [
    "set_workspace",
    "clear_workspace",
    "get_workspace",
    "board_dir",
    "events_dir",
    "ccc_home",
    "acquire_flock",
    "release_flock",
    "acquire_named_lock",
    "release_named_lock",
    "acquire_board_lock",
    "release_board_lock",
    "build_dev_phase_prompt",
    "build_dev_phase_prompt_with_hint",
    "get_store",
    "reset_store_cache",
    "create_task",
    "list_tasks",
    "move_task",
    "update_index",
    "quarantine",
]
