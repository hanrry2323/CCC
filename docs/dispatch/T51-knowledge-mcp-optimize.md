# 任务卡 T51 · 知识库 MCP 优化（Claude Code 执行）

> 关联：阶段 3 P1 · 依据：老板点名「自建知识库 MCP 与优化做好」；现状=kb MCP（stdio）存在但无真实调用方，大脑直连 search.py，索引全量重建
> 执行体：Claude Code · 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-04
> 作废记录：2026-08-04 方向调整——本卡按 M1 worktree 出卡，与「Codex 出卡 → 2017 Engine 自动执行」方向不符；作废，待 2017 执行环境（dev worktree + Engine 派发）跑通后重出（内容保留为参考）。
> 并行执行：**工作目录 `/Users/apple/program/ccc-ws-p1a`（分支 `codex/p1a-kb-mcp`）**，与 T52 并行；文件所有权见下

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

**执行体**：Claude Code · 日期：
