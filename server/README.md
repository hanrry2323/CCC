# CCC 新服务端（server/）

> 2017 单端合体骨架 · P2 开发基座。**只写骨架与模板，不部署、不碰 2017 运行面。**
> 契约：CCC 重构契约 v1（执行体注册表 §7 五角色）· 关联：INT-120 · 前序：T0 清场 → T1/T1-R 骨架

## 定位

本目录是 CCC 重构后的**新服务端合体**（2017 单端）基座，替代旧 `scripts/` 中的散装角色/阶段实现。
T2（Engine 薄驱动 + 看板服务端）与 T3（看板前端）在本目录施工，T4（自带中转站部署）在其上收口。
旧代码（`scripts/`、`app/`、`desktop/`、`lib/`、`db/`）与本目录**互不引用、零改动**。

## 结构

| 目录 | 职责 | 施工卡 |
|------|------|--------|
| `engine/` | 薄驱动核心：发单、派发、收单、状态更新、执行体注册表读取 | T2 |
| `board/` | 看板服务端：任务板数据结构、查询、状态机 | T2 |
| `web/` | HTTP 前端：看板 UI、API 端点、实时更新 | T3（与 T2 并行） |
| `relay/` | 中转站：模型出口上游路由与密钥管理 | T4 |
| `kb/` | 知识库：MCP 服务 + BM25 本地检索（纯 Python，零外部依赖） | T11 |
| `config/` | 配置系统：环境变量加载器 + 执行体注册表（契约 §7） | T1 已完成 |
| `deploy/` | 进程编排：plist 模板、启动/健康检查脚本 | T1 已完成 |
| `tests/` | 测试：冒烟 + 单元；新增模块必须同步补测试 | 随卡 |

模块依赖只允许单向（不可反向）：

```
config ─→ engine ─→ board ─→ web
              ↘  relay（engine 经 relay 出模型）
deploy / tests 只消费上述模块，不被依赖
```

## 配置

1. 复制 `config/config.example.env` 为 `config/config.env`，填写占位参数（含必填 `PYTHON_BIN`）。
2. 复制 `config/executors.example.json` 为 `config/executors.json`，按环境填绑定。
3. 运行测试：`python3 -m pytest server/tests/ -q`

## 铁律

- **零硬编码**：端口、路径、模型名、上游地址、工具名一律走 `config.env` / 注册表变量；代码与模板出现字面量即验收不通过（硬编码扫描黑名单见 `deploy/README.md`）。
- **不落密钥**：密钥只允许占位引用（`$VAR_NAME` / `RELAY_UPSTREAM_KEY` 式引用）。
- **不改旧代码**：`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动。
- **不碰运行面**：本目录产出只到模板/脚本，不注册 launchd、不启动服务。

## 扩展

- 新增组件 → 新建目录 + `README.md`（含职责/关键约定/相邻模块关系/施工入口）
- 新增配置 → `config.example.env` 加占位 + `loader.py` 加键（必填进 `REQUIRED_KEYS`，可选进 `OPTIONAL_KEYS`）
- 新增执行体 → `config/executors.example.json` 加条目（分类只允许「可后台 CLI」/「手动 GUI」）
