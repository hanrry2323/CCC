# 任务卡 T51 · 知识库 MCP 优化（Claude Code 执行）

> 关联：ccc-plan-005 · 依据：老板点名「自建知识库 MCP 与优化做好」；现状=kb MCP（stdio）存在但无真实调用方，大脑直连 search.py，索引全量重建
> 执行体：Claude Code · 验收：Codex（严格）· 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 重出记录：2026-08-04 原卡作废（M1 worktree 方向不符）；2017 执行环境跑通（T53）后按 Engine 自动派发重出。
> 工作目录：`/Users/fan/program/ccc-dev-ws`（2017 开发 worktree）；分支：`codex/t51-kb-mcp-optimize`（先 `git fetch origin main && git checkout -b codex/t51-kb-mcp-optimize origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块（MCP 接入 / 索引增量 / BM25 调参 / 测试）立即 commit+push，禁止攒到结尾；执行超时 7200s。

## 目标

知识库 MCP 成为**真实可用的查询通道**（大脑/执行体/壳统一经它查知识库），索引增量更新，BM25 查询质量调优。

## 具体项

1. **调用方接入**：大脑 `/conversation` 的知识检索与 kb MCP 统一查询入口（brain.py 改为经 kb 查询服务，或明确 MCP 为唯一对外查询协议 + brain 走同一内核）；提供 CLI 查询（`ccc-kb-search.sh` 对齐）。
2. **索引增量更新**：indexer 按 mtime 增量重建（只重扫变化文档），替换全量重建；索引文件带 mtime 表。
3. **BM25 质量调优**：k1/b 调参 + 域过滤（nodes-paths/projects/decisions/lessons）+ 结果去重；建立查询用例集（≥10 题，覆盖四域）验证命中。
4. **MCP 服务健康**：mcp_server 自检/selftest 可用；`ide/mcp-manifest.md`（qx-map）登记 kb MCP 为准入服务。
5. 测试补齐 + 文档（server/kb/README）。

## 红线

- 只改 server/kb/、knowledge/、server/web/brain.py（仅查询入口）、server/tests/、qx-map ide/mcp-manifest.md；**禁止改 scripts/、deploy/、validate.py、CI（T52 所有权）**。
- 零外脑（D2）：kb 只读 knowledge/，禁止读 qx-map/hp-kb。
- 回写前必须 push 成功并附证据。

## 验收标准

1. 真实 MCP 查询实测一次（经 MCP 协议调用返回命中，非 search.py 直连绕过）。
2. 索引增量：改动 1 个知识文档后重建只扫该文档（日志/mtime 证据）。
3. 查询用例集 ≥10 题命中 ≥8（附每题命中域/分数）。
4. pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：MCP 接入方案、增量索引实现、BM25 调参结论、用例集结果、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code · 日期：2026-08-04

### MCP 接入方案

统一查询内核 `server/kb/service.py`：**大脑 / MCP / CLI 同一内核**。
- `mcp_server.py` 三工具（kb_search / kb_read / kb_list）全部改走 service；
- `brain.py` 知识检索入口改走 service（自动增量 ensure_index，异常静默降级不变）；
- 新 CLI `server/kb/cli.py`，`knowledge/ccc-kb-search.sh` 对齐（与 MCP 同结果）。
- 新增 `--health` / `--reindex-incremental`；selftest 扩数字检索 + 域过滤。
- qx-map `ide/mcp-manifest.md` 已登记 ccc-kb（stdio）为准入服务（qx-map commit `1c67b73`）。

### 增量索引实现

`server/kb/indexer.py`：索引文件升级 version 2，携带源文件 **mtime 表**（`mtimes`）。
- `incremental_index()` 只重扫 mtime 变化的源文件；无变化零扫；删除源移除其文档；v1 索引退化全量重建。
- `service.ensure_index()` 查询前自动增量：改动 1 个知识文档后只重扫该文档。
- 实测：touch `knowledge/domains/lessons/seed.md` → 增量重建只扫 1 个文件（`seed.md`）；无变化零扫。

### BM25 调参结论

- **数字分词**：数字串独立成 token，IP（192.168.3.116）/ 端口（7788/6100）可直接检索（此前 IP 零命中）。
- **域归一**：seed JSON 数字前缀 section（01-nodes-paths 等）构建时归一为域过滤名，域过滤恒生效。
- **跨源去重**：同 section 内 seed JSON ↔ domains MD 同实体折叠，保留分数高者（修复 qb/CCC 双源重复）。
- **k1/b**：走环境变量 `CCC_KB_BM25_K1` / `CCC_KB_BM25_B`（默认 1.2/0.75，标准 BM25）；网格（1.0–2.0 × 0.3–0.75）对用例集均 14/14 命中，默认稳健。

### 用例集结果

`knowledge/query-cases.md`：**14 题覆盖四域**（nodes-paths 4 / projects 4 / decisions 3 / lessons 3），
`test_kb_query_cases.py` 逐题验证 top-5 命中预期域——**14/14 命中**（≥8 达标）。

### pytest / 验证 / push 证据

- pytest 全量：**450 passed**（基座 397 → +53 新增用例）
- ruff：新代码全过（`server/kb/` 仅基座既有 2 处 UP038，非本次引入）；`py_compile` clean
- MCP 真实协议调用（JSON-RPC over stdio）：`kb_search("192.168.3.116", domain=nodes-paths)` 返回 6 条全 nodes-paths，命中 ✓
- 分支 `codex/t51-kb-mcp-optimize` 分步提交（A 索引增量 / B BM25 调参 / C 统一入口 / D 用例集 / E 文档），已全部 push：
  `091fc881` → `d84f56f5` → `05f57b2e` → `ee2a185e` → `cd2ec5c9`

---

## 验收区（Codex 独立取证 · 2026-08-04 · 合入 main + 2017 部署后）

**判定：✅ 通过。** 自动化流程真实开发闭环（Engine 派发 → 2017 claude 开发 → 分步提交 A/B/C/D/E → push → 验收 → 合入 → 部署）。

- **统一查询内核**：`server/kb/service.py` 为唯一查询入口，MCP/brain/CLI 同一服务（代码核验）✅
- **索引增量**：mtime 表 + 只重扫变化源（T51-A 091fc881）✅
- **BM25 调参**：数字分词 + k1/b 环境变量 + 跨源去重（T51-B d84f56f5）✅
- **用例集**：14 题覆盖四域自动化验证（T51-D ee2a185）；Codex 实测「LC1 教训」命中 lessons 域 ✅
- **MCP 真实协议调用**：JSON-RPC over stdio kb_search 实测命中（执行端证据）✅
- 回归：pytest 450（合入后全量）、ruff clean ✅；2017 已部署（HEAD 37748a5）✅
- 分步提交纪律全程生效（5 块独立 commit，无攒批）✅

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
