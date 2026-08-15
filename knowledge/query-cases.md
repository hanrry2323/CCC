# 知识库查询用例集（T51）

> 验证 BM25 检索质量。每题标注预期命中域；命中判定：top-5 内出现预期域文档。
> 覆盖五域：nodes-paths（4）/ projects（4）/ decisions（3）/ lessons（3）/ plans（3）。
> 配套测试：`server/tests/test_kb_query_cases.py`。

| # | 查询 | 预期域 | 预期关键词 |
|---|------|--------|-----------|
| 1 | 192.168.3.116 | nodes-paths | mac2017 |
| 2 | M1 开发机 IP | nodes-paths | m1 |
| 3 | launchd 常驻 三服务 | nodes-paths | com.ccc.web-server |
| 4 | 中转站 6100 6102 | nodes-paths | 6100 |
| 5 | CCC 主仓 路径 | projects | CCC |
| 6 | qb 项目 路径 | projects | qb |
| 7 | xianyu 自动分发 平台 | projects | xianyu |
| 8 | qx-observer 项目 | projects | qx-observer |
| 9 | D10 杜绝 硬编码 | decisions | D10 |
| 10 | 双轨 决议 中转站 | decisions | D11 |
| 11 | 薄驱动 Engine 方案 | decisions | D1-D10 |
| 12 | Plan 自然语言 不能写命令 | lessons | L1 |
| 13 | 红线 不动系统文件 | lessons | 工程红线 |
| 14 | 验收 文档同步 证据 | lessons | LC1 |
| 15 | 桌面驾驶舱 | plans | clwarp |
| 16 | 心智分层 | plans | ccc-plan-008 |
| 17 | 视频里程碑 | plans | xy-plan-001 |

## 验证方法

```bash
# 全量自验（经统一查询内核，与 MCP 同结果）
python3 -m server.kb.cli search "192.168.3.116" --top-k 5

# 自动化验证
pytest server/tests/test_kb_query_cases.py -q
```

## 记录

- 2026-08-04 初建：14 题全部命中预期域（数字分词 / 域归一 / 跨源去重后）。
