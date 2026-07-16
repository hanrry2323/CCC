# B1 迁移报告：从 qx 迁入四川价爬虫

> **任务 ID**: `cla-b1--qx--1-vded`
> **迁移来源**: `~/program/projects/qx/crawlers/sichuan_price_adapter/`
> **迁入目标**: `src/crawlers/sichuan/`
> **执行角色**: ccc-dev (manual)
> **执行时间**: 2026-07-17

---

## 三硬门验收表（Phase 2）

| 验收项 | 标准 | 结果 |
|--------|------|------|
| 代码迁入路径 | `src/crawlers/sichuan/` | 通过 |
| CLI 可跑通 | `python3 scripts/run_crawler.py --name sichuan` | 通过 |
| README 命令说明 | 4 条命令，≤10 行 | 通过 |

---

## 技术要点

### BaseCrawler 适配
- `SichuanCrawler` 继承 `BaseCrawler`，实现 4 个抽象方法：`_load_credential` / `login` / `crawl` / `extract`
- 硬编码凭证路径：`~/.ccc/credentials/sichuan-001.json`
- credential 缺失时自动降级为 dry-run（开发友好）

### dry-run 模式设计
- 通过 `CRAWLER_DRY_RUN` 环境变量控制
- dry-run 不依赖外部网络和 API，返回 3 条 mock 数据（阿司匹林肠溶片/氨氯地平/阿莫西林胶囊）
- CLI 可在无网络环境下快速验证流程正确性

### 与 qx 原版差异
| 功能 | qx 原版 | 本次迁入 |
|------|---------|----------|
| SQLite 持久化 ❌ | ✅ | ❌ |
| CSV 导出 ❌ | ✅ | ❌ |
| 批处理 ChunkInfo/ProcessResult ❌ | ✅ | ❌ |
| API 请求 + 数据抽取 ✅ | ✅ | ✅ |
| credential 加载 ✅ | ✅ | ✅ |
| dry-run 模式 ⚡ | ❌ | ✅ |

---

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| 爬虫实现 | `src/crawlers/sichuan/sichuan_crawler.py` | SichuanCrawler 类 |
| 包标记 | `src/crawlers/sichuan/__init__.py` | 包标记文件 |
| 单测 | `tests/test_crawler_sichuan.py` | 5 条测试 |
| CLI 入口 | `scripts/run_crawler.py` | 注册 `sichuan` 爬虫 |
| 迁移报告 | `docs/migration-B1.md` | 本文件 |
| 迁入 plan | `.ccc/plans/cla-b1--qx--1-vded.plan.md` | 原始 plan |
| 迁入 phases | `.ccc/phases/cla-b1--qx--1-vded.phases.json` | 阶段清单 |

---

## 执行轨迹 (Phase 2)

### Commit 1
```
feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)
```

### Commit 2
```
docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)
```

---

## 后续方向

### B2 迁入目标
- `dekyy_adapter`（浏览器自动化爬虫）或 `tfydd_adapter`
- 建立爬虫注册器支持按 name 批量调度

### 凭证管理
- 建立 `~/.ccc/credentials/` 目录
- 统一 `SichuanCrawler.load_credential()` 路径

### 生产增强
- 接入 qx 的 SQLite 持久化层
- 支持 ChunkInfo/ProcessResult 批处理模式

### OBS 自检集成
- 将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
- 建立 OBS 探针 - 阶段 4「爬虫可调度」

---

## 附录：Phase 1 diff（参考）

```
$ git diff --stat main..HEAD
 A  src/crawlers/sichuan/__init__.py
 A  src/crawlers/sichuan/sichuan_crawler.py
 A  tests/test_crawler_sichuan.py
 M  scripts/run_crawler.py
```

---

**文档结束**
