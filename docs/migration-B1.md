# Migration Report: B1 — 从 qx 迁入最小爬虫 — cla-b1--qx--1-vded

## 任务信息

- **Task ID**: `cla-b1--qx--1-vded`
- **执行角色**: CCC product（验收）+ CCC dev（执行）
- **执行时间**: 2026-07-17
- **执行命令**: `none`（manual 执行）

## 迁入代码清单

| 目标文件路径 | qx 来源路径 | 用途 | 改动说明 |
|---|---|---|---|
| `scripts/run_crawler.py` | (精简出口路由) | 提供统一 CLI 入口 | 移向 `cla-bmed-ccc` 作为 `run_crawler.py` |
| `src/crawlers/base.py` | `qxo/crawlers/base.py` | BaseCrawler + CrawlerConfig 类 | 移动并简化 import 依赖 |
| `src/crawlers/demo/demo_crawler.py` | `qxo/_wrappers/demo_wrapper.py` | DemoCrawler 模拟实现 | 按本地 BaseCrawler 适配，3 条模拟药品 |
| `src/crawlers/demo/__init__.py` | (构造) | 包声明 | 与 `src/crawlersiệt/__init__.py` 同级 |
| `src/crawlers/__init__.py` | (构造) | 包声明 | 确保 `from crawlers.xxx import Crawler` 可用 |
| `tests/test_crawler_demo.py` | (构造) | Demo 爬虫 4 单测 | 覆盖 CLI、导入、爬虫调用、字段校验 |

## 验收状态

| 验收项 | 验证命令 | 结果 | 备注 |
|---|---|---|---|
| [CLI 可运行] `python3 scripts/run_crawler.py --name demo` | exit 0，stdout 含 "crawl OK" | ✅ | 返回 3 条药品记录 |
| [测试全绿] `python3 -m pytest tests/test_crawler_demo.py -q` | 4 passed | ✅ | 测试覆盖完整 |
| [README 区块存在] `grep -q '爬虫快速运行' README.md` | exit 0 | ✅ | 对应 148-154 行 |
| [src 非空] `git ls-files src/crawlers/ | wc -l` | 4 files | ✅ | 包含 base.py + demo/ |

## 预留（待 Phase 2 迁入）

- **四川价爬虫（sichuan_price_adapter）**: 738 行，需包装为 `SichuanCrawler(BaseCrawler)`，支持 dry-run/real 双模式
  - 文件概览: `scripts/gentle_coat/harvest/20240207-220933-sichuan-price-harvest.tar.gz`（原始 tarball）
  - 还原后路径: `crawlers/sichuan_price_adapter/sichuan_price_adapter.py`
  - 当前暂存: (None)

## 后续方向

- Phase 2：迁入四川价爬虫，适配 BaseCrawler 接口
- B2：迁入 tfydd/dekyy 浏览器自动化爬虫
- 建立 CrawlerRegistry，支持按 name 批量调度多爬虫

---

**Status**: Phase 1 完成 ✅ | **Commit Message**: `docs: B1 迁移报告—Demo 爬虫迁入确认 (phase 1/2, cla-b1--qx--1-vded)`
