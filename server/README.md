# CCC 新服务端（server/）

> 2017 单端合体 · 重构定稿后的新栈。**现行两服务常驻（web-server / engine；board-scheduler 已收敛进 engine）。**
> 契约：CCC 重构契约 v1（执行体注册表 §7 五角色）· 关联：INT-120 · 版本：v2.0.0

## 定位

本目录是 CCC 重构后的**新服务端合体**（2017 单端），替代旧 `scripts/` 中的散装角色/阶段实现。
Engine 负责真实派发/收单（契约 §2 状态机 + §7 执行体注册表）；看板服务端从任务卡文档解析派生数据；HTTP API 提供对话/看板/运维/线路图四视图。
旧代码（`scripts/`、`app/`、`lib/`、`db/`）已退役归档，本目录不引用旧代码。

## 结构

| 目录 | 职责 | 施工卡 |
|------|------|--------|
| `engine/` | 薄驱动核心：发单、派发、收单、状态更新、执行体注册表读取 | T2 |
| `board/` | 看板服务端：任务板数据结构、查询、状态机 | T2 |
| `web/` | HTTP 前端：看板 UI、API 端点、实时更新 | T3（与 T2 并行） |
| `kb/` | 知识库：MCP 服务 + BM25 本地检索（纯 Python，零外部依赖） | T11 |
| `config/` | 配置系统：环境变量加载器 + 执行体注册表（契约 §7） | T1 已完成 |
| `deploy/` | 进程编排：plist 模板、启动/健康检查脚本 | T1 已完成 |
| `tests/` | 测试：冒烟 + 单元；新增模块必须同步补测试 | 随卡 |

模块依赖只允许单向（不可反向）：

```
config ─→ engine ─→ board ─→ web
deploy / tests 只消费上述模块，不被依赖
```

## 配置

1. 复制 `config/config.example.env` 为 `config/config.env`，填写占位参数（含必填 `PYTHON_BIN`）。
2. 复制 `config/executors.example.json` 为 `config/executors.json`，按环境填绑定。
3. 运行测试：`python3 -m pytest server/tests/ -q`

## 铁律

- **零硬编码**：端口、路径、模型名、上游地址、工具名一律走 `config.env` / 注册表变量；代码与模板出现字面量即验收不通过（硬编码扫描黑名单见 `deploy/README.md`）。
- **不落密钥**：密钥只允许占位引用（`$VAR_NAME` / `RELAY_UPSTREAM_KEY` 式引用）。
- **不引用旧代码**：旧 `scripts/`、`app/`、`lib/`、`db/` 已退役归档，本目录不引用。

## 扩展

- 新增组件 → 新建目录 + `README.md`（含职责/关键约定/相邻模块关系/施工入口）
- 新增配置 → `config.example.env` 加占位 + `loader.py` 加键（必填进 `REQUIRED_KEYS`，可选进 `OPTIONAL_KEYS`）
- 新增执行体 → `config/executors.example.json` 加条目（分类只允许「可后台 CLI」/「手动 GUI」）
