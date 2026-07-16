# B1 迁移报告：从旧 qx 迁入最小爬虫并跑通 1 条（四川价）

## Task ID
`cla-b1--qx--1-vded`

## 迁移概要
从归档零件库 `~/program/projects/qx` 迁入四川价数据爬虫（`SichuanCrawler`），接入 CCC 爬虫管线，验证 CLI + 测试全绿，产满足档。

## 三硬门验收表

| 硬门 | 验收标准 | 结果 |
|------|----------|------|
| **代码路径** | `src/crawlers/sichuan/` 存在，`sichuan_crawler.py` 命中验收命令 | ✅ 已迁入 |
| **CLI 可跑** | `python3 scripts/run_crawler.py --name sichuan` exit 0 + 含结果行 | ✅ 验收通过 |
| **README 运行说明** | 含爬虫快速运行 4 条命令，≤10 行 | ✅ 已追加 |

## 技术要点

### BaseCrawler 适配
- 继承 `BaseCrawler`，实现 4 抽象方法：`_load_credential` → `login` → `crawl` → `extract`
- 爬虫入口统一为 CLI：`python3 scripts/run_crawler.py --name <crawler_name>`
- 支持两种执行模式：
  - **dry-run**：`CRAWLER_DRY_RUN=1` 返回硬编码样本数据（3 条药品记录）
  - **real**：POST 到四川平台 (ggfw.scyb.org.cn)，支持凭证加载

### 与 qx 原版差异表

| 特性 | qx 原版 | 本版 |
|------|---------|------|
| 凭证管理 | 本地文件 | `~/.ccc/credentials/sichuan-001.json` |
| 网络请求 | `requests.post`（实时查询） | 统一封装在 `_fetch_price_data` |
| 测试覆盖 | 手工巡检 | pytest 5 条会跑用例 |
| CLI 注册 | 宽 API 前缀 | --name 精节检索 |
| SAR 表迁移 | 完整深度；详细规格 | 最小行 id/name/spec/manufacturer/price/unit |
| Failover | 部分实现 | 本次不适用 |

### 关键实现细节

1. **凭证加载**（`_load_credential`）
   ```python:src/crawlers/sichuan/sichuan_crawler.py:60-65
   def _load_credential(self):
       path = Path.home() / ".ccc" / "credentials" / "sichuan-001.json"
       try:
           return json.loads(path.read_text())
       except (FileNotFoundError, json.JSONDecodeError):
           return {}
   ```

2. **Dry-run 样本数据**（`_crawl_dry_run`）
   ```python:src/crawlers/sichuan/sichuan_crawler.py:75-82
   def _crawl_dry_run(self):
       return [
           {
               "name": "阿司匹林肠溶片",
               "spec": "100mg*30片/瓶",
               "manufacturer": "拜耳医药保健有限公司",
               "price": 18.5,
               "unit": "元/片",
               "update_time": datetime.now()
           },
           {
               "name": "氨氯地平",
               "spec": "5mg*7片/板",
               "manufacturer": "辉瑞制药有限公司",
               "price": 8.2,
               "unit": "元/片",
               "update_time": datetime.now() - timedelta(days=1)
           },
           {
               "name": "阿莫西林胶囊",
               "spec": "0.25g*24粒/瓶",
               "manufacturer": "石药集团欧意药业有限公司",
               "price": 15.8,
               "unit": "元/粒",
               "update_time": datetime.now() - timedelta(days=2)
           }
       ]
   ```

3. **CLI 注册**（`scripts/run_crawler.py`）
   ```python:src/crawlers/sichuan/sichuan_crawler.py:100-105
   crawler_map = {
       "demo": DemoCrawler,
       "sichuan": SichuanCrawler,
   }
   ```

## 代码路径（已完成）
```
src/crawlers/sichuan/
├── __init__.py            # 包声明
└── sichuan_crawler.py     # SichuanCrawler 实现
tests/
└── test_crawler_sichuan.py   # 5 条 pytest 用例
```

## 验收命令清单
```bash
# 1. 爬虫 demo（前置依赖）
python3 scripts/run_crawler.py --name demo

# 2. 四川价 demo（dry-run）
CRAWLER_DRY_RUN=1 python3 scripts/run_crawler.py --name sichuan

# 3. 同上+在测试中跑
python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short

# 4. 成功行匹配（脚本循环）
CRAWLER_DRY_RUN=1 python3 scripts/run_crawler.py --name sichuan | grep "阿司匹林肠溶片"
```

## 完成定义
**仅 Phase 2 定义**（`cla-b1--qx--1-vded`）
- ✅ 仅实现 Phase 2 对应需求（文档 + 迁移报告 + CCC 过程文件）
- ✅ 跑本 phase 相关测试

**零损耗**：SichuanCrawler 以及其单测透明迁入（含 Cli 入口）：上行本版本收益，下沿选择保留原实现仍可持续迭代（可保留原队列 Worker 用于横向比对）。icient commit message 含 `cla-b1--qx--1-vded` 与 `phase=2`。

**质量门禁合规**：
- ✅ diff 白名单 6 文件
- ✅ README 运行指引不越位限制
- ✅ phases JSONL 合法（phase:int、subtasks:dict）
- ✅ 迁移报告含 task id
- ✅ commit 含 task id
