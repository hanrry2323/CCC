# SSOT — 真相源地图

## 产品叙事

| 文件 | 角色 |
|------|------|
| `docs/VISION.md` | **对外/对内产品叙事 SSOT** |
| `docs/product/dialogue-orchestration-boundary.md` | **对话面/编排面边界基线**（信息流契约） |
| `docs/product/ccc-desktop-architecture.md` | Desktop 产品形态 |
| `VERSION` | 版本号权威 |
| `CHANGELOG.md` | 变更史权威 |
| `STARTUP-BRIEF.md` | Agent 启动（省 token） |
| `README.md` | 对外首页（须与 VISION 一致） |

## 运行时

F-ROLE-03: CCC 运行时真相源在 `scripts/`（`ccc-engine.py`、`ccc-board.py`、`_board_store.py`、`chat_server/`）。

| 目录 | 状态 |
|------|------|
| `scripts/` | **SSOT** — Engine / Board / Hub / Patrol |
| `scripts/chat_server/` | Hub UI + API（产品入口） |
| `skills/` | 阶段默认能力包（非用户角色菜单） |
| `app/` | 实验性 services，不接入 Engine 主循环 |
| `lib/` | 通用工具，可被 scripts 选用 |
| `src/` | 零散实验，非看板流水线 |

新增看板/编排逻辑请改 `scripts/`，不要平行实现第二条流水线。

文档总索引：`docs/INDEX.md`。
