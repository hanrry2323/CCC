# ccc (CCC 平台) 开发技能指南

> 项目：CCC — 自动化任务编排平台
> 技术栈：Python 3 / pytest / Bash / Markdown
> 仓库：M1 /Users/apple/program/CCC，Mac2017 /Users/fan/program/CCC（只 pull）

## 常用命令

- 运行测试：`python3 -m pytest server/tests/ -v`
- 单模块测试：`python3 -m pytest server/tests/test_engine_main.py -v`
- 代码检查：`ruff check server/`
- 编译检查：`python3 -m py_compile server/engine/main.py`
- 出卡：`scripts/new-card.sh --project ccc --title "..."`
- 看板：`curl http://192.168.3.116:7788/board/states`

## 关键模块

| 模块 | 路径 | 职责 |
|------|------|------|
| Engine | server/engine/ | 任务派发/收单/状态机 |
| Board | server/board/ | 看板/卡片解析/校验 |
| Web | server/web/ | HTTP API/看板 UI |
| KB | server/kb/ | 知识库检索/MCP |

## 开发守则

1. 改 engine 代码必须有对应测试（`server/tests/test_engine_*.py`）
2. 禁止硬编码机器路径/端口/模型名（门禁 `scripts/check-entry-docs.py`）
3. 项目注册只改 `docs/projects/registry.yaml`
4. 新功能先出卡，不在聊天里直接改
5. 改动后跑全量测试确保无回归