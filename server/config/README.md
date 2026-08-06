# config/ — 配置系统

> T1 已完成 · 依赖：无 · 被依赖：engine / board / web / relay / deploy

## 内容

| 文件 | 职责 |
|------|------|
| `config.example.env` | 全部运行参数占位 |
| `loader.py` | env 加载器 |
| `executors.example.json` | 契约 §7 执行体注册表模板 |

## 执行体注册表（2026-08-06 交叉验收）

| 角色 | 分类 | 当前绑定 | 说明 |
|------|------|---------|------|
| 开发执行体 | 可后台 CLI | **OpenCode** | 2017 默认可后台开发（6102） |
| 开发执行体 | 可后台 CLI | Claude Code | 点名开发（6100）；此时验收须 OpenCode |
| 维护执行体 | 可后台 CLI | OpenCode | 维护默认 OpenCode |
| 管理席 | — | Codex | 出卡/裁决；**不验收** |
| 验收席 | — | Claude Code | OpenCode 开发 → Claude 验收 |
| 验收席 | — | OpenCode | Claude 开发 → OpenCode 验收 |

**交叉规则**：执行体与验收必须互为 `OpenCode` ↔ `Claude Code`。`Codex` / `Cursor` 取消验收资格。  
机器校验：`server/board/roles.py` + `validate.py`（新卡 error）。

## 关键约定

- 新增配置：`config.example.env` 加占位 + `loader.py` 加键。
- 各模块只经 `load_config()` 读配置。
- 密钥只允许占位引用。
