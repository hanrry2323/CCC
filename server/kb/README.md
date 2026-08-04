# server/kb —— CCC 知识库（查询内核 + MCP + CLI）

> T51 优化后：知识库成为真实可用的查询通道。大脑 / 执行体 / 壳统一经
> **统一查询内核**（`service.py`）查知识库；对外查询协议 = kb MCP（tools）。
> 索引按 mtime 增量更新；BM25 质量已调优（数字分词 / 域归一 / 跨源去重 / k1·b 可调）。

## 结构

```
server/kb/
├── indexer.py       # 索引构建：增量重建（mtime 表）+ 域命名归一
├── search.py        # BM25 检索内核：数字分词 / 域过滤 / 跨源去重 / k1·b 可调
├── service.py       # 统一查询入口（MCP / brain / CLI 同一内核）
├── mcp_server.py    # MCP stdio server（kb_search / kb_read / kb_list）
└── cli.py           # 查询 CLI（ccc-kb-search.sh 后端）
```

## 统一查询内核（service.py）

| 函数 | 说明 |
|------|------|
| `ensure_index()` | 无索引→全量构建；v2 索引→按 mtime 增量；v1 索引不动 |
| `search(query, domain, top_k)` | BM25 检索（自动增量 ensure_index，结果跨源去重） |
| `read_document(doc_id)` | 读条目全文 |
| `list_documents(domain)` | 列条目 |
| `health()` | 健康自检（索引目录 / 文档数 / 各域计数） |

调用方：
- **大脑**：`server/web/brain.py` 的 `_retrieve_kb_context` 经 `service.search` 检索（CCC_BRAIN_KB=1 开启）。
- **MCP**：`mcp_server.py` 三个工具全部走 `service`。
- **CLI**：`knowledge/ccc-kb-search.sh` → `python3 -m server.kb.cli` → `service`。

## MCP 服务

```bash
python3 -m server.kb.mcp_server                # 启动 MCP stdio server
python3 -m server.kb.mcp_server --selftest      # 自测（索引→三工具→数字检索→域过滤）
python3 -m server.kb.mcp_server --list-tools    # 工具清单
python3 -m server.kb.mcp_server --health        # 健康自检
python3 -m server.kb.mcp_server --reindex       # 全量重建
python3 -m server.kb.mcp_server --reindex-incremental  # 增量重建
```

工具：
- `kb_search(query, domain?)` — BM25 检索，返回 `{id, section, snippet, score}`
- `kb_read(path)` — 读条目全文
- `kb_list(domain?)` — 列条目

## 增量索引（T51）

- 索引文件 `knowledge/.index/documents.json`（version 2）携带 `mtimes` 表：`{源文件绝对路径: mtime}`。
- `incremental_index()` 只重扫 mtime 变化的源文件：无变化零扫；删除源移除其文档；v1 索引退化全量重建。
- `ensure_index()` 每次查询前自动增量：改动 1 个知识文档后，下一次检索只重扫该文档。
- 全量重建：`python3 -m server.kb.cli reindex`（首建 / 手动强制）。

## BM25 调参（T51）

| 参数 | 环境变量 | 默认 | 说明 |
|------|---------|------|------|
| k1 | `CCC_KB_BM25_K1` | 1.2 | 词频饱和度（默认即标准 BM25） |
| b   | `CCC_KB_BM25_B`   | 0.75 | 长度归一（默认即标准 BM25） |

- **数字分词**：数字串独立成 token，IP（192.168.3.116）/ 端口（7788/6100）可直接检索。
- **域归一**：seed JSON 数字前缀 section（01-nodes-paths 等）构建时归一为域过滤名（nodes-paths 等），域过滤恒生效。
- **跨源去重**：同 section 内 seed JSON 与 domains MD 的同实体结果折叠，保留分数高者。
- 调参结论：k1/b 网格（1.0–2.0 × 0.3–0.75）对用例集均 14/14 命中，默认值稳健；`reset_engine()` 后环境变量生效。

## 查询用例集

`knowledge/query-cases.md`：14 题覆盖四域（nodes-paths 4 / projects 4 / decisions 3 / lessons 3），
配套测试 `server/tests/test_kb_query_cases.py` 逐题验证 top-5 命中预期域。

## 测试

```bash
pytest server/tests/test_kb_search.py server/tests/test_kb_indexer.py \
       server/tests/test_kb_mcp.py server/tests/test_kb_service.py \
       server/tests/test_kb_query_cases.py server/tests/test_brain_kb.py -q
```

## 红线

- 只读 `knowledge/`（D2 零外脑），禁止读 qx-map / hp-kb。
- 端口 / 路径 / 参数走环境变量（`CCC_KB_INDEX_DIR` / `CCC_KB_BM25_K1` / `CCC_KB_BM25_B`），不硬编码。
