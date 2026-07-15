# app/ / lib/ / src/ — 旁路模块（非 SSOT）

F-ROLE-03: CCC 运行时真相源在 `scripts/`（`ccc-engine.py`、`ccc-board.py`、`_board_store.py`）。

| 目录 | 状态 |
|------|------|
| `scripts/` | **SSOT** — Engine / Board / Chat / Patrol |
| `app/` | 实验性 services（prompt/patterns），不接入 Engine 主循环 |
| `lib/` | 通用 retry/dead_letter 工具，可被 scripts 选用 |
| `src/` | 零散实验（如 backtest_engine），非看板流水线 |

新增看板/角色逻辑请改 `scripts/`，不要在本目录平行实现第二条流水线。
