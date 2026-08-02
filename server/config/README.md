# config/ — 配置系统

> T1 已完成 · 依赖：无 · 被依赖：engine / board / web / relay / deploy

## 内容

| 文件 | 职责 |
|------|------|
| `config.example.env` | 全部运行参数占位：端口（engine/board/web/relay）、`PYTHON_BIN`、数据/日志路径、上游与密钥引用、注册表路径 |
| `loader.py` | env 加载器：缺项/空值/文件缺失报错（`ConfigError`）；可选键给默认值 |
| `executors.example.json` | 契约 §7 五角色执行体注册表 |

## 执行体注册表（契约 §7 五角色）

| 角色 | 分类 | 当前绑定 | 说明 |
|------|------|---------|------|
| 开发执行体 | 手动 GUI | Trae | 人工接单（积分过渡期），Engine 只发单/跟踪/收单 |
| 开发执行体 | 可后台 CLI | OpenCode | Engine 自动拉起 |
| 维护执行体 | 可后台 CLI | Claude Code | Engine 自动拉起 |
| 管理席 | — | Codex | 方案/拆卡/裁决，不执行 |
| 验收席 | — | Codex | 验收，不执行 |

- 分类只允许「可后台 CLI」/「手动 GUI」；管理席/验收席不做执行，分类为「—」。
- 工具名是**配置值**、允许出现；代码/模板中禁止字面工具名。

## 关键约定

- 新增配置：`config.example.env` 加占位 + `loader.py` 加键（必填 → `REQUIRED_KEYS`，可选 → `OPTIONAL_KEYS`）。
- 各模块只经 `load_config()` 读配置，禁止散落读环境变量。
- 密钥只允许占位引用。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| 所有模块 | 经 `loader.load_config` 取运行参数 |
| `engine/` | 读 `EXECUTOR_REGISTRY_PATH` 指向的注册表 |

## 施工入口

- T2：engine 接 `loader.load_config` 与注册表读取。
