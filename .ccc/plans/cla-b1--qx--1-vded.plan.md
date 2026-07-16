# Plan: cla:B1 — 从旧 qx 迁入最小爬虫并跑通 1 条

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

B1 首笔提交 `c8c3d31` 已将 demo 爬虫迁入并提交（src + tests），但四川价爬虫代码仍在 untracked 区且存在接口缺陷，run_crawler.py 的 sichuan 分支也未被提交。B1.1 仅写了 docs 未修代码。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口（HEAD 只注册 demo；工作区含 sichuan 注册但未提交且有两个 bug：第 25–28 行重复 `sys.path.insert` + import，第 54 行 sichuan 分支用 `generic_name` 但 sichuan dry-run 记录字段为 `product_name`）
  - `src/crawlers/base.py` — 抽象基类，声明 4 个抽象方法 + `run()` 编排；**未定义 `__init__` 或 `_config()` 工具方法**——子类必须直接设 `self.config`
  - `src/crawlers/demo/demo_crawler.py` — 已提交，正确实现全部 4 个抽象方法，通过 `self.config = CrawlerConfig(...)` 初始化
  - `src/crawlers/sichuan/sichuan_crawler.py` — **untracked**，含两个阻塞 bug：
    1. **`extract()` 缺失** → Python 拒绝实例化抽象类
    2. **`__init__` 调用 `self._config()`** → BaseCrawler 无此方法（DemoCrawler 用 `self.config = CrawlerConfig(...)`），构造时崩溃
  - `tests/test_crawler_demo.py` — 4 单测已提交通过
  - `tests/test_crawler_sichuan.py` — **untracked**，5 单测（因 sichuan 无法实例化，0/5 可通过）

- **当前结构要点**：
  1. BaseCrawler 不提供 `__init__` 或 `_config()`，子类必须自行 `self.config = CrawlerConfig(...)`
  2. DemoCrawler 写法是唯一正确参考——直接设 config + 实现全部 4 个抽象方法
  3. SichuanCrawler 的 `_extract_price_records()` 已有抽取逻辑但未通过 `extract()` 入口暴露
  4. `run_crawler.py` 的 unstaged diff 含重复导入和字段名笔误
  5. README.md 工作区已含 "爬虫快速运行" 4 条命令（demo + sichuan 两套 CLI + 两套测试）——基本就绪

- **待改动点**：
  - `sichuan_crawler.py`：`__init__` 改 `self.config = CrawlerConfig(...)` | 补 `extract(self, raw)` 委派 `_extract_price_records(raw)` | 加 `CrawlerConfig` import
  - `run_crawler.py`：删第 25–28 行重复 import | `generic_name` → `product_name`
  - `test_crawler_sichuan.py`：确认 `__init__` 修复后所有测试通过
  - 创建 `docs/migration-B1.md` 含 task id + 迁移清单 + 验收结果

---

## 范围

- **目标**：修复并提交四川价爬虫代码，确保 demo + sichuan 两爬虫 CLI 均可跑通（dry-run），创建 B1 迁移报告
- **只改文件**：
  ```
  src/crawlers/sichuan/sichuan_crawler.py
  tests/test_crawler_sichuan.py
  scripts/run_crawler.py
  docs/migration-B1.md
  ```
- **不改文件**：`src/crawlers/base.py`、`src/crawlers/demo/`、`tests/test_crawler_demo.py`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`VERSION`、`CLAUDE.md`、`SKILL.md`
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：修复 SichuanCrawler + 清理 run_crawler.py + 提交代码

### 做什么

SichuanCrawler 现有两块阻塞缺陷导致无法实例化或运行。本 phase 修复后使其成为 BaseCrawler 完整子类，同时清理 run_crawler.py 在 B1 期间引入的重复导入和字段名笔误。提交后 demo + sichuan 两路单测全绿，两路 CLI exit 0。

### 怎么做

1. **修复 `sichuan_crawler.py`**：
   - 导入 `CrawlerConfig`（当前缺该 import）：`from crawlers.base import BaseCrawler, CrawlerConfig`
   - 改 `__init__`：去掉 `self._config(...)` + `super().__init__(cfg)`，改为 `self.config = CrawlerConfig(name="sichuan", site_url="https://ggfw.scyb.org.cn")`——与 DemoCrawler 写法一致
   - 补 `extract(self, raw) -> List[Dict[str, Any]]`：直接委托 `return self._extract_price_records(raw)`

2. **清理 `run_crawler.py`**：
   - 删第 25–28 行内部的 `import sys` + `sys.path.insert(0, ...)` + `from crawlers.sichuan...`——顶部的 import 已经够用
   - 第 54 行 `generic_name` → `product_name`（sichuan dry-run 记录用 `product_name`）

3. **确认测试通过**：
   - `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short`

4. **Stage + commit**：
   - `git add src/crawlers/sichuan/ tests/test_crawler_sichuan.py scripts/run_crawler.py`
   - commit message: `feat(crawler): 迁入四川价爬虫 — 修复 extract()+__init__ + 注册 CLI (phase 1/2, cla-b1--qx--1-vded)`

### 验收清单

- [ ] SichuanCrawler 可实例化（_config bug 已修复，extract 已实现）
- [ ] demo 4 单测 + sichuan 5 单测全部通过
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0, stdout 含 "Results: 3 rows"
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0, stdout 含 "Results: 3 rows"
- [ ] run_crawler.py 无重复 import
- [ ] commit message 含 `phase 1/2` + `cla-b1--qx--1-vded`
- [ ] diff 不越 Phase 1 白名单

### 验收

- 四川价可实例化（参考：`python3 -c "from crawlers.sichuan.sichuan_crawler import SichuanCrawler; SichuanCrawler()"` → exit 0）
- 双爬虫单测全绿（参考：`python3 -m pytest tests/ -q --tb=short` → 9+ passed，0 failed）
- CLI demo（参考：`python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `Sample: 阿莫西林`）
- CLI sichuan（参考：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Sample:` 且 `参考价格` > 0）
- 无重复导入（参考：`grep -c 'import sys' scripts/run_crawler.py` ≤ 1）

---

## 改动 2（Phase 2）：B1 迁移报告 + 验收闭环

### 做什么

创建 B1 迁移报告，记录 demo + sichuan 两爬虫迁入情况和验收结果。Phase 2 无代码改动，纯文档。

### 怎么做

1. **创建 `docs/migration-B1.md`**：
   - 标题含 task id `cla-b1--qx--1-vded`
   - 迁移清单表：B1 → Phase 1（demo）+ Phase 2（sichuan）
   - 来源标注：demo 爬虫为新建样例；sichuan 爬虫原始来源为 qx `crawlers/sichuan_price_adapter/`
   - 验收状态表（三硬门）：src code / pytest / CLI
   - 实测命令输出（stdout 摘要）

2. **覆盖 `.ccc/plans/cla-b1--qx--1-vded.plan.md`**（内容同本 plan）

3. **覆盖 `.ccc/phases/cla-b1--qx--1-vded.phases.json`**（2 phases JSONL）

4. **Stage + commit**：
   - `git add docs/migration-B1.md .ccc/plans/cla-b1--qx--1-vded.plan.md .ccc/phases/cla-b1--qx--1-vded.phases.json`
   - commit message: `docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)`

### 验收清单

- [ ] docs/migration-B1.md 存在且含 task id
- [ ] 迁移清单涵盖 demo + sichuan 两段
- [ ] 验收状态表显示 src/pytest/CLI 三硬门均 PASS
- [ ] .ccc/plans 和 .ccc/phases 已覆盖
- [ ] commit message 含 `phase 2/2` + `cla-b1--qx--1-vded`

### 验收

- 迁移报告含 task id（参考：`grep -q 'cla-b1--qx--1-vded' docs/migration-B1.md` → exit 0）
- 计划/阶段文件就位（参考：`test -f .ccc/plans/cla-b1--qx--1-vded.plan.md && test -f .ccc/phases/cla-b1--qx--1-vded.phases.json` → exit 0）
- 两笔独立 commit（参考：`git log --oneline -2` 含 `phase 1/2`、`phase 2/2`）

---

## 验收

> 全局独立二级标题，硬门验收。

- **爬虫可运行**：`python3 scripts/run_crawler.py --name demo && python3 scripts/run_crawler.py --name sichuan` → 两次 exit 0
- **全站测试绿**：`python3 -m pytest tests/ -q --tb=short` → 9+ passed
- **迁移报告含 task id**：`grep -q 'cla-b1--qx--1-vded' docs/migration-B1.md` → exit 0
- **两笔 commit 各含 phase 编号**：`git log --oneline -2` 显示 `phase 1/2` 和 `phase 2/2`
- **diff 不越白名单**：两笔 diff 均不修改 `base.py`、`demo/`、`VERSION` 等禁止文件

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 修复 SichuanCrawler（extract+__init__）+ 清理 run_crawler.py + 提交 | `feat(crawler): 迁入四川价爬虫 — 修复 extract()+__init__ + 注册 CLI (phase 1/2, cla-b1--qx--1-vded)` |
| 2 | 创建 B1 迁移报告 + .ccc 过程文件 | `docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)` |

---

## 全局验收清单

- [ ] Phase 1 只改 src/crawlers/sichuan/、tests/test_crawler_sichuan.py、scripts/run_crawler.py
- [ ] Phase 2 只改 docs/migration-B1.md、.ccc/plans/、.ccc/phases/
- [ ] demo 爬虫 CLI exit 0 + stdout 含样本数据
- [ ] sichuan 爬虫 CLI exit 0 + stdout 含样本数据
- [ ] `python3 -m pytest tests/ -q --tb=short` → 全部通过
- [ ] docs/migration-B1.md 含 task id
- [ ] 两笔独立 commit 各含对应 phase 编号 + task id
- [ ] 不修改 base.py、demo/、VERSION 等禁止文件

---

## 后续步骤

- **B2 方向**：从 qx 迁入 dekyy 浏览器自动化爬虫或 tfydd 适配器
- **爬虫注册器**：建立 registry 支持按 name 批量调度（替换当前硬编码 dict）
- **凭证管理**：建立 `~/.ccc/credentials/` 目录支持 real-mode 爬虫
- **README 爬虫文档**：若工作区版本已有 sichuan 命令则跳过，否则补充

## 完成定义（仅 Phase 2）
1. 仅实现 Phase 2 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-b1--qx--1-vded` 与 `phase=2`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase
