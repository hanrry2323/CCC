# xianyu M6.1 内容库 API 制卡报告

日期：2026-09-05

## 业务仓只读核实

- 项目注册：`docs/projects/registry.yaml` 将 `xy` 注册为 active/taskable，Mac2017 业务仓路径为 `/Users/fan/program/apps/xianyu`。
- 业务仓入口：已只读读取根 `README.md`、`AGENTS.md`、`CLAUDE.md`；三者均指向 admin/API 与现有测试作为开发基准，并要求业务仓改动隔离在 Engine worktree。
- API 入口：业务仓 `admin/api/server.py`，FastAPI 适配服务；现有内容库路由为 `GET /api/v1/library`，扫描辅助为 `scan_library()` / `_scan_library_task()`。
- 产出基准：服务代码声明并扫描 `video-pipeline/output/`；业务仓实际目录核验显示该目录当前不存在，`workspace/outputs/` 与 `data/output/` 存在，但本卡要求执行体在 worktree 内再次以代码和现状核实，禁止凭空扩大扫描范围。
- 测试基准：业务仓 `tests/admin/test_library.py` 已覆盖视频、图文、无脚本降级、日期倒序、空态、扁平结构、新产出自动发现、同任务多产物、认证和不存在目录等契约；执行体需对照本卡坏 JSON/只读边界要求复核并补缺口，不重复造路由。
- 业务仓状态：核验时 `git status --short` 无输出；本次未修改业务仓。

## 制卡结果

- 卡号：`xy060`
- 卡文件：`docs/dispatch/xy/xy060-content-library-api.md`
- 卡标题：M6.1 内容库 API
- 状态：`待分派`
- 执行体/验收：DSH（按 Engine 自动认领；本次未手动启动 DSH）
- 范围节：仅写 CCC 仓内真实相对路径 `docs/dispatch/xy/xy060-content-library-api.md`；跨仓业务文件均放在基准文件/步骤自然语言，未写入范围节。
- 范围边界：仅约束业务 admin 只读适配层与内容库对应测试；明确排除 M6.2–M6.4、生产核心、调度、发布、数据库 schema、工作流 API 和真实产出写入。
- 验收点：API 可读、字段稳定、实时发现、空态、坏元数据/坏条目容错、日期倒序、认证与只读边界、既有/新增测试及编译 lint 门禁、`.ccc-result.md` 回写契约、前置机审与维护区四问证据。

## 校验与提交

- 制卡入口：`scripts/new-card.sh --project xy --id xy060-content-library-api -f /tmp/xy060-card.md`。
- 制卡校验：通过；脚本同时刷新索引并执行 `validate task cards (docs/dispatch)`，结果为 Passed。
- 卡提交：`9ee437aa4b3b3e389bf1bb6b5f603ef95f94abfb`。
- 推送：已推送 `origin/main`。
- 收口核验：提交后 CCC 工作区干净；业务仓未产生改动。

## 边界说明

本次只完成一张完整业务卡的生成、校验、提交和推送；未创建第二张卡，未修改 xianyu，未启动 DSH，未推进 M6.2、M6.3、M6.4，也未修改已完成里程碑。
