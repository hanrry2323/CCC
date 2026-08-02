# web/ — 看板静态页

> 施工卡：T3（本卡）· 依赖：`board/` 导出数据（`web/data/board.js`）· 零 API / 零 fetch，`file://` 可开

## 职责

- 看板 UI：三视图切换——实时（按状态）、7 天回写、按项目分类。
- 线路图占位（P3 派生视图前置壳）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
- 顶部状态徽章（契约 §2 各状态计数）；深/浅主题可切换（视觉沿用架构全景页令牌）。

## 关键约定

- **零 API / 零 fetch**：数据以 `window.BOARD_DATA = {...}` 变量注入（`data/board.js`），`<script src>` 读取，`file://` 可直接打开。
- 页面不直连 `board/` 内部；数据由 `board/export.py` 从任务卡导出，再生成/提交 `data/board.js`。
- 端口 / 服务无关：本目录是静态资源，不监听任何端口。
- 视觉沿用架构全景页（`docs/ccc-refactor-architecture.html`）CSS 令牌与深/浅主题。

## 内容

| 文件 | 职责 |
|------|------|
| `index.html` | 页壳：顶栏 + 状态徽章 + 主题开关 + 四标签 + 视图区 |
| `css/style.css` | 深/浅主题令牌 + 卡片/徽章/线路图样式 |
| `js/app.js` | 渲染 `window.BOARD_DATA` 三视图 + 线路图 + 徽章 + 主题切换 |
| `data/board.js` | **导出产物**（`window.BOARD_DATA`），由 `board/export.py` 生成 |

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `board/` | 消费 `export.py` 产出的 `data/board.js`，不 import |
| `engine/` | 不依赖 |
| `config/` | 不依赖（无服务 / 无端口） |

## 施工入口

- 重新导出：`$PYTHON_BIN -m server.board.export`（扫描 `docs/dispatch/` → 重写 `data/board.js`）。
- P3：在线路图区块接入「确认可用」交互（人只做确认）。
- T4：如需服务化，另开卡加 HTTP 壳；本卡不做。
