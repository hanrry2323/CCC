# CCC 知识库

> CCC 自建知识库。M4 移交后，CCC 所有决策/教训只写本库，不写外脑（qx-map / hp-kb）。
> 初始化日期：2026-08-02 · M4 刷新：2026-08-03 · 关联：INT-120（CCC 重构）· 任务卡：T36

## 结构

```
knowledge/
├── README.md                        # 本文件——用法 + 维护规则
├── domains/                         # 分域知识（可检索源）
│   ├── nodes-paths/                 #   节点/路径域
│   │   └── seed.md                  #     机器、IP、SSH、服务
│   ├── projects/                    #   项目元数据域
│   │   └── seed.md                  #     项目位置、性质、访问方式
│   ├── decisions/                   #   决策域
│   │   └── seed.md                  #     关键决策摘要
│   └── lessons/                     #   教训域
│       └── seed.md                  #     教训 + 红线
├── seed/                            # 种子包（结构化数据源，indexer.py 解析）
│   ├── 00-README.md
│   ├── 01-nodes-paths.json
│   ├── 02-project-metadata.json
│   ├── 03-key-decisions.json
│   └── 04-lessons.json
└── ccc-kb-search.sh                 # 基础检索脚本（关键词/域）
```

## 维护规则

### 新增知识

1. **决策** → 写入 `knowledge/domains/decisions/`，格式：标题 + 日期 + 摘要 + 状态。
2. **教训** → 写入 `knowledge/domains/lessons/`，格式：编号 + 标题 + 根因 + 修复 + 日期。
3. **节点/路径变更** → 更新 `knowledge/domains/nodes-paths/seed.md`，标注变更日期。
4. **项目元数据变更** → 更新 `knowledge/domains/projects/seed.md`。

### 独立纪律（D3 / D2）

1. CCC 知识库**独立运行**，运行时不再读 qx-map / hp-kb。
2. 新决策/教训**只写本库**，不写外脑（M4 起强制）。
3. 需要外脑信息时 → 从 `knowledge/domains/` 检索，不查 qx-map 原文。
4. 违反独立 = 漂移，验收即打回。

### 检索方式

> T51 起：MCP / 大脑 / CLI 统一走同一查询内核（`server/kb/service.py`）；
> 索引按 mtime 增量更新（改动文档后只重扫变化源）。详见 `server/kb/README.md`。

#### 方式一：MCP 服务（推荐，v1.0）

```bash
# 启动 MCP server（AI Agent 通过 stdio 协议调用）
python3 -m server.kb.mcp_server

# 自测
python3 -m server.kb.mcp_server --selftest

# 健康自检
python3 -m server.kb.mcp_server --health

# 列出工具
python3 -m server.kb.mcp_server --list-tools

# 全量重建索引
python3 -m server.kb.mcp_server --reindex

# 增量重建索引（只重扫变化的文档）
python3 -m server.kb.mcp_server --reindex-incremental
```

MCP server 暴露三个工具：
- **kb_search**(query, domain?) — BM25 检索，返回 `{id, section, snippet, score}`
- **kb_read**(path) — 读取指定知识条目全文
- **kb_list**(domain?) — 列出域内条目

#### 方式二：脚本检索（兼容，T51 起走统一内核）

```bash
# 全文关键词检索
bash knowledge/ccc-kb-search.sh <关键词>

# 指定域检索
bash knowledge/ccc-kb-search.sh <关键词> --domain nodes-paths
bash knowledge/ccc-kb-search.sh <关键词> --domain decisions
bash knowledge/ccc-kb-search.sh <关键词> --domain lessons
bash knowledge/ccc-kb-search.sh <关键词> --domain projects

# 列出指定域所有条目
bash knowledge/ccc-kb-search.sh --list --domain nodes-paths
```

#### 扩展接口

向量语义检索接口预留：`server/kb/search.py` 的 `Bm25Index` 类可替换为向量检索引擎，只需实现相同的 `search(query, domain, top_k) → list[dict]` 签名。索引格式（`documents.json`）也兼容外部 embedding 的向量存储。

## 来源

- 初始种子（2026-08-02）：外脑权威源 qx-map 一次性导入。
- M4 刷新（2026-08-03）：qx-map `__archive__/decisions/` + CCC 仓内 `docs/architecture.md` v0.70.0 + T31–T35 任务卡 + M2 生产验证记录。
- 之后独立维护，新决策/教训只写本库（D3 红线）。