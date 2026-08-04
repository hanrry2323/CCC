# fix-regress-atomic-update-move 执行报告

## 信息
- Phase: fix-regress-atomic-update-move-p1
- 退出码: 0

## 输出
```
{
  "phase_id": "fix-regress-atomic-update-move-p1",
  "exit_code": 0,
  "stdout": "完成。改动：\n\n1. **`scripts/_board_store.py`** — 新增 `FileBoardStore.update_and_move_task()` 方法，在锁内完成读→update_fn→写目标列→删源文件的原子操作。\n\n2. **`scripts/ccc-board.py`** — `regress_role()` 中“回归标记+移回 backlog”直接文件操作替换为 `store.update_and_move_task(...)`，消除 TOCTOU 竞态。\n\n- `pytest` 60/60 passed\n- 单 commit `cc519d9`\n",
  "stderr": "\u001b[0m\n> build · code\n\u001b[0m\n\u001b[0m# \u001b[0mTodos\n[•] Read _board_store.py to understand FileBoardStore\n[ ] Read ccc-board.py regress_role (L1862-1880)\n[ ] Add update_and_move_task to FileBoardStore\n[ ] Rewrite regress_role to use update_and_move_task\n[ ] Run pytest to verify\n[ ] Commit\n\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/_board_store.py\n\u001b[0m→ \u001b[0mRead scripts/ccc-board.py\u001b[90m [offset=1850, limit=60]\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-board.py\u001b[90m [offset=1909, limit=40]\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-board.py\u001b[90m [offset=1780, limit=70]\u001b[0m\n\u001b[0m✱ \u001b[0mGrep \"def regress_role\"\u001b[90m 1 match\u001b[0m\n\u001b[0m✱ \u001b[0mGrep \"^def move_task|^BOARD\\s*=|^store\\s*=|^list_tasks\\s*=\"\"\u001b[90m 4 matches\u001b[0m\n\u001b[0m✱ \u001b[0mGrep \"def move_task|BOARD\\s*=|store\\s*=|def list_tasks|from _board_store import|from _config import\"\u001b[90m 7 matches\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-board.py\u001b[90m [offset=80, limit=30]\u001b[0m\n\u001b[0m\n\u001b[0m# \u001b[0mTodos\n[✓] Read _board_store.py to understand FileBoardStore\n[✓] Read ccc-board.py regress_role (L1862-1880)\n[•] Add update_and_move_task to FileBoardStore\n[ ] Rewrite regress_role to use update_and_move_task\n[ ] Run pytest to verify\n[ ] Commit\n\u001b[0m\n\u001b[0m← \u001b[0mEdit scripts/_board_store.py\nIndex: /Users/apple/program/CCC/scripts/_board_store.py\n===================================================================\n--- /Users/apple/program/CCC/scripts/_board_store.py\n+
```
