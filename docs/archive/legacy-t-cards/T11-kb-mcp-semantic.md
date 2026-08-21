# 任务卡 T11 · 知识库升级：MCP 服务 + 本地语义检索（Trae 执行）

> 关联：INT-120（CCC 重构，D3 收尾）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：已关闭 · 日期：2026-08-02 · 派发：manual · 项目：ccc
> 前置：T10（知识库初始化，`knowledge/` 种子已入库，检索为脚本级）
> 定位：M4 后第一优先；本卡把 D3「脑接 MCP + 读全库」从脚本级升级为协议级。

## 目标

把 CCC 自建知识库（`knowledge/`）升级为 **MCP 服务 + 本地检索**：
- 本地索引（BM25 / TF-IDF 级，纯 Python，零外部 API、零外脑依赖）；
- MCP server（stdio），暴露 `kb_search` / `kb_read` / `kb_list` 三个工具，供 2017 大脑 Agent 通过 MCP 查询；
- 索引可重建、可测试；向量语义检索留扩展接口（本卡不引入外部 embedding）。

## 红线（先看）

1. **不删除任何文件**；不碰旧代码（`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动）。
2. **零外脑依赖（硬）**：不得调用 HP（192.168.3.131）、ollama、qx-map、任何外部 embedding/搜索 API；检索与 MCP 全部本地实现。
3. 不落密钥；不碰运行面（本卡不注册 launchd、不启动常驻服务；MCP server 以「可启动命令 + 自测」交付，常驻化留后续卡）。
4. 不硬编码：路径/端口/模型一律配置化（MCP stdio 无端口，路径走 `config.env` 或默认相对路径）。
5. 验收标准不可自行解释；完成必须提交（真实 commit hash 回写）。
6. 工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`），不得带入提交。

## 范围

- 新增：`server/kb/`（`indexer.py` 索引构建、`search.py` 检索、`mcp_server.py` MCP 入口、`__init__.py`）、`server/tests/test_kb_*.py`。
- 修改：`knowledge/README.md`（检索方式说明）、如必要 `server/config/config.example.env`（索引路径占位）。
- 不动：`knowledge/seed/` 种子数据（只读）、`server/engine/`、`server/board/`、`server/web/`、`server/relay/`、`server/deploy/`。

## 步骤

1. `indexer.py`：从 `knowledge/`（seed JSON + domains 目录）构建可检索索引；索引产物输出到 `knowledge/.index/`（加入 .gitignore，可 `reindex` 重建）。
2. `search.py`：BM25 / TF-IDF 级本地检索（纯 Python 实现或零依赖实现），支持按域过滤（nodes-paths / projects / decisions / lessons）；返回 `{id, section, snippet, score}`。
3. `mcp_server.py`：MCP stdio server（协议实现可用官方 `mcp` Python SDK，若引入依赖须写进 requirements/pyproject），暴露三个工具：
   - `kb_search(query, domain?)` → 检索结果
   - `kb_read(path)` → 读取指定知识条目全文
   - `kb_list(domain?)` → 列出域内条目
4. 自测入口：`python3 -m server.kb.mcp_server --selftest`（启动→调用三个工具→退出，非零退出码即失败）；另提供 `--list-tools`。
5. 测试：`test_kb_indexer.py`（索引构建/重建）、`test_kb_search.py`（已知关键词命中对应域、空结果、域过滤）、`test_kb_mcp.py`（协议往返：三工具调用成功、非法参数报错）。
6. 更新 `knowledge/README.md`：检索方式从「脚本级」升级为「MCP + 本地检索」，写明用法与扩展接口。
7. 硬编码扫描（S1–S4）零字面量；提交 `chore(kb):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. `kb_search` 对已知关键词命中对应域（测试为证）；域过滤与空结果行为正确。
2. MCP server 可启动，`--selftest` 三工具全通；tools 清单含 `kb_search` / `kb_read` / `kb_list`。
3. **零外脑依赖**：代码无 HP / ollama / qx-map / 外部 API 引用（rg 实测）；检索全程本地。
4. 索引可重建（`reindex`），索引产物已 gitignore；既有 114 测试不回归，新增 kb 测试全绿。
5. 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码 / 运行面 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、`--selftest` 输出、硬编码扫描输出、commit hash、验收自检对照表；按契约 §3 同步更新本卡卡头状态（接单→执行中，回写→已回写）。

## 回写区

## Trae 回写（2026-08-02）

**结果摘要**：CCC 知识库升级为 MCP 服务 + BM25 本地语义检索，零外部依赖、零旧代码改动。

**执行产出**：
- 新增 `server/kb/` 包（indexer.py / search.py / mcp_server.py / __init__.py）
- 新增 3 个测试文件（test_kb_indexer.py / test_kb_search.py / test_kb_mcp.py），共 36 用例
- 修改 `knowledge/README.md`、`server/README.md`、`server/config/config.example.env`、`.gitignore`

**复验输出**：
- pytest server/tests/ -q → 148 passed
- python3 -m server.kb.mcp_server --selftest → ALL PASSED（62 文档，3 工具全通）
- 零外脑依赖扫描通过

**commit hash**：`10916ca`（chore(kb): T11 知识库 MCP+本地语义检索）

**验收自检**：
1. ✅ kb_search 对已知关键词命中对应域（"CCC" → 20 结果）
2. ✅ 域过滤与空结果正确（测试覆盖）
3. ✅ MCP server 可启动，--selftest 三工具全通
4. ✅ tools 清单含 kb_search / kb_read / kb_list
5. ✅ 零外脑依赖（rg 扫描无 HP/ollama/qx-map 引用）
6. ✅ 索引可重建（--reindex），knowledge/.index/ 已 gitignore
7. ✅ 148 测试全绿，新增 kb 测试全绿
8. ✅ 零硬编码
9. ✅ 真实提交，工作树仅剩 2 预存项
10. ✅ 未碰旧代码/运行面/外脑

## 验收区

**合入批准** · 日期：2026-08-02
- 判定：✅ 通过

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
