# Plan: cla:B1 — 从旧 qx 迁入最小爬虫并跑通 1 条

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

项目 `clawmed-ccc`（简称 cla）已完成 bootstrap + OBS 探针基础，当前有 8 个源文件（见下文文件树）。爬虫基础设施已就位（`BaseCrawler` + `CrawlerConfig` + `DemoCrawler` + CLI），但缺一个来自 qx 的真实爬虫本体。零件库 `/Users/apple/program/projects/qx/crawlers/` 下有 `sichuan_price_adapter/`、`nmpa_adapter/`、`dekyy_adapter/` 等完整生产级适配器，本次选四川价做首个迁入。

### 当前文件树
```
./tests/test_crawler_demo.py
./tests/test_obs4_util.py
./scripts/run_crawler.py
./src/crawlers/demo/__init__.py
./src/crawlers/demo/demo_crawler.py
./src/crawlers/__init__.py
./src/crawlers/base.py
./src/util_obs4.py
```

### 当前 git HEAD
```
dfdd2f6 docs: OBS3 流程压力探针 (phase 1/1, cla-obs3-docs)
6bd309d feat: OBS4 add util + test (phase 1/1, cla-obs4-util)
5724330 chore: bootstrap clawmed-ccc (CCC vertical base)
```

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口，当前仅注册 `DemoCrawler`（demo CLI exit 0，stdout 含 `阿莫西林胶囊`）
  - `src/crawlers/base.py` — `BaseCrawler` 抽象基类（4 个抽象方法：`_load_credential/login/crawl/extract`）。`run()` 串联全流程：加载凭证 → 登录 → 爬取 → 抽取
  - `src/crawlers/demo/demo_crawler.py` — `DemoCrawler` 实现（硬编码 3 条药品样本数据，`CrawlerConfig(name="demo", site_url="https://demo.local")`）
  - `tests/test_crawler_demo.py` — 4 单测（import/probe/run 返回 list/记录含必需字段），全部通过

- **当前结构要点**：
  1. `BaseCrawler.run()` 串联全流程，子类只需实现 4 个抽象方法
  2. `run_crawler.py` 用 `--name` 参数 + `crawler_map` dict 路由爬虫，缺 sichuan 注册
  3. 项目层级已标准化：`src/crawlers/<name>/` 定位爬虫包
  4. qx 的 `sichuan_price_adapter/` 含完整实现（requests API 调用、SQLite 持久化、CSV 导出、批处理），本次取骨架做最小迁入——聚焦 BaseCrawler 接口适配 + dry-run 模式，不复制持久化逻辑
  5. `src/util_obs4.py` 和 `tests/test_obs4_util.py` 为 OBS4 探针文件，与本 task 无关

- **待改动点**：
  - 新建 `src/crawlers/sichuan/__init__.py`（包标记）
  - 新建 `src/crawlers/sichuan/sichuan_crawler.py`（SichuanCrawler extends BaseCrawler）
  - 新建 `tests/test_crawler_sichuan.py`（5 条测试）
  - 修改 `scripts/run_crawler.py`：添加 `SichuanCrawler` import + `crawler_map` 注册
  - 更新 `README.md`：追加「爬虫快速运行」小节（≤10 行命令说明）
  - 写入迁移报告 `docs/migration-B1.md`（含 task id）
  - 写入 `.ccc/plans/` + `.ccc/phases/` 过程文件

---

## 范围

- **目标**：从 qx `sichuan_price_adapter/` 迁入最小四川价爬虫，适配 `BaseCrawler` 接口，dry-run 模式可跑通，pytest 全绿
- **只改文件**：
  ```
  src/crawlers/sichuan/__init__.py
  src/crawlers/sichuan/sichuan_crawler.py
  tests/test_crawler_sichuan.py
  scripts/run_crawler.py
  README.md
  docs/migration-B1.md
  .ccc/plans/cla-b1--qx--1-vded.plan.md
  .ccc/phases/cla-b1--qx--1-vded.phases.json
  ```
- **不改文件**：`src/crawlers/base.py`、`src/crawlers/demo/`、`tests/test_crawler_demo.py`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`reports/`、`.ccc/board/`、`.ccc/ops/`
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：迁入四川价爬虫代码 + 单测 + CLI 注册

### 做什么

从 qx `sichuan_price_adapter/` 迁入四川药械网价格爬虫，适配 `BaseCrawler` 接口。最小可跑版本：
- 不复制 qx 的 SQLite 持久化、CSV 导出、批处理等生产逻辑
- 核心是 4 个抽象方法实现：`_load_credential/login/crawl/extract`
- 支持 `CRAWLER_DRY_RUN` 环境变量切换 dry-run / real 模式
- dry-run 返回 3 条硬编码样本数据（不依赖 API 和凭证）
- 注册到 `run_crawler.py` 的 `crawler_map`，`--name sichuan` 可调用

### 怎么做

1. **创建 `src/crawlers/sichuan/__init__.py`**：
   - 包标记文件，内容：`"""Sichuan crawler package."""`

2. **创建 `src/crawlers/sichuan/sichuan_crawler.py`**：
   - 导入 `BaseCrawler`、`CrawlerConfig`
   - 类 `SichuanCrawler(BaseCrawler)`：
     - `__init__`：`self.config = CrawlerConfig(name="sichuan", site_url="https://ggfw.scyb.org.cn")`
     - `_load_credential`：检查 `~/.ccc/credentials/sichuan-001.json`——存在则 `json.load`，不存在返回空 dict
     - `login`：dry-run（`CRAWLER_DRY_RUN=1`）→ True；real 模式验证 credential 含 `base_url`
     - `crawl`：dry-run 调用 `_crawl_dry_run`；real 模式调用 `_fetch_price_data` + `_extract_price_records`
     - `extract`：委托 `_extract_price_records(raw)`
     - `_crawl_dry_run`：返回 3 条 mock 数据（阿司匹林肠溶片/氨氯地平/阿莫西林胶囊）
     - `_fetch_price_data`：`requests.post(..., timeout=30)` 到四川药械网 API
     - `_extract_price_records`：字段归一化（`product_name/spec/manufacturer/reference_price/unit/last_updated`）

3. **创建 `tests/test_crawler_sichuan.py`**（5 条测试，`TestSichuanCrawler` class）：
   - `test_sichuan_import`：验证 `SichuanCrawler` 可导入
   - `test_sichuan_crawler_initialization`：实例化 + `config.name == "sichuan"`
   - `test_sichuan_crawl_dry_run_returns_list`：`crawl()` 返回 list，len ≥ 1
   - `test_sichuan_crawl_dryrun_record_has_required_fields`：记录含 `product_name/spec/manufacturer/reference_price/unit`
   - `test_sichuan_load_credential_empty_path`：凭证文件不存在时返回空 dict

4. **修改 `scripts/run_crawler.py`**：
   - 添加 import：`from crawlers.sichuan.sichuan_crawler import SichuanCrawler`
   - 在 `crawler_map` 中加入 `"sichuan": SichuanCrawler`
   - CLI 的 `--name` help 文本同步更新

5. **验证**：
   - `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed
   - `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
   - `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`

### 验收清单

- [ ] `src/crawlers/sichuan/sichuan_crawler.py` 文件存在
- [ ] `SichuanCrawler` 继承 `BaseCrawler`，实现全部 4 个抽象方法
- [ ] dry-run 模式不需要凭证文件和外部网络
- [ ] 5 条单测覆盖 import、初始化、dry-run 返回 list、记录含字段、空凭证
- [ ] `run_crawler.py` 中 sichuan 注册正常（import + crawler_map 条目）
- [ ] pytest 9 个 case 全部通过
- [ ] 两 CLI（`--name demo` + `--name sichuan`）均 exit 0

### 验收

- 文件就位（参考：`test -f src/crawlers/sichuan/sichuan_crawler.py && test -f tests/test_crawler_sichuan.py` → exit 0）
- pytest 全绿（参考：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed）
- sichuan CLI 可跑（参考：`python3 scripts/run_crawler.py --name sichuan` → stdout 含 `Results: 3 rows`，exit 0）

---

## 改动 2（Phase 2）：文档 + README + CCC 过程文件

### 做什么

将迁入代码配套的文档和 CCC 控制面过程文件正式提交。Phase 1 与 Phase 2 分离，确保代码 diff 和文档 diff 干净独立。

### 怎么做

1. **Stage + commit Phase 1 代码**：
   - `git add src/crawlers/sichuan/ tests/test_crawler_sichuan.py scripts/run_crawler.py`
   - `git commit -m "feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)"`

2. **更新 `README.md`**：
   - 在 README 末尾添加「爬虫快速运行」小节，包含 4 条命令：
     - demo CLI：`python3 scripts/run_crawler.py`
     - demo 测试：`python3 -m pytest tests/test_crawler_demo.py -q --tb=short`
     - sichuan CLI（dry-run）：`python3 scripts/run_crawler.py --name sichuan`
     - sichuan 测试：`python3 -m pytest tests/test_crawler_sichuan.py -q --tb=short`

3. **创建 `docs/migration-B1.md`**：
   - 标题：`# B1 迁移报告：从 qx 迁入四川价爬虫`
   - 内容含：
     - 任务 ID：`cla-b1--qx--1-vded`
     - 迁移来源：`~/program/projects/qx/crawlers/sichuan_price_adapter/`
     - 迁入目标：`src/crawlers/sichuan/`
     - 三硬门验收表（代码迁入路径 / CLI 可跑通 / README ≤10 行）
     - 技术要点：BaseCrawler 适配、dry-run 模式设计、与 qx 原版差异

4. **写入 `.ccc/phases/cla-b1--qx--1-vded.phases.json`**：
   - 用本 plan 末尾 PHASES 段的 JSONL 内容覆盖

5. **Stage + commit Phase 2**：
   - `git add README.md docs/migration-B1.md .ccc/plans/cla-b1--qx--1-vded.plan.md .ccc/phases/cla-b1--qx--1-vded.phases.json`
   - `git commit -m "docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)"`

6. **最终全量验收**：运行全局验收清单中所有命令

### 验收清单

- [ ] `README.md` 含爬虫快速运行小节（共 ≤10 行命令说明）
- [ ] `docs/migration-B1.md` 存在且含 task id `cla-b1--qx--1-vded`
- [ ] `.ccc/phases/cla-b1--qx--1-vded.phases.json` 是合法 JSONL，每行含非空 description 与 scope
- [ ] `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- [ ] 两笔独立 commit，各含对应 phase 编号 + task id
- [ ] Phase 2 diff 不含代码文件（仅 `docs/` / `README.md` / `.ccc/`）
- [ ] Phase 1 diff 不含文档（仅 `src/crawlers/sichuan/` / `tests/` / `scripts/`）

### 验收

- README 含爬虫命令（参考：`grep -c "run_crawler" README.md` ≥ 1）
- 迁移报告含 task id（参考：`grep "cla-b1--qx--1-vded" docs/migration-B1.md` → exit 0）
- phases 合法 JSONL（参考：`python3 -c "import json; [json.loads(l) for l in open('.ccc/phases/cla-b1--qx--1-vded.phases.json')]"` → exit 0）
- 两笔独立 commit（参考：`git log --oneline -2` 显示两 phase 编号）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 创建 `sichuan_crawler.py` + `__init__.py` + 5 条单测 + `run_crawler.py` 注册 | `feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)` |
| 2 | README 爬虫命令 + migration-B1 报告 + .ccc/plans + .ccc/phases | `docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] `pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed，0 failed
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- [ ] `git ls-files src/crawlers/sichuan/ | wc -l` ≥ 2
- [ ] `git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] `git ls-files docs/migration-B1.md` → exit 0
- [ ] `git log --oneline -2` 显示两笔独立 commit，各含对应 phase 编号 + `cla-b1--qx--1-vded`
- [ ] 两笔 diff 均不越白名单——不触及 `src/crawlers/base.py`、`src/crawlers/demo/`、`VERSION` 等
- [ ] 不修改 `src/crawlers/base.py`、`demo/`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`reports/`、`.ccc/board/`、`.ccc/ops/`

---

## 验收

- **src 非空已提交**：`git ls-files src/crawlers/sichuan/ | wc -l` ≥ 2
- **pytest 全绿**：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed，0 failed
- **sichuan CLI 可跑**：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- **迁移报告含 task id**：`grep cla-b1--qx--1-vded docs/migration-B1.md` → exit 0
- **两笔独立 commit**：`git log --oneline -2` 输出显示两个不同 message，各含 phase 编号
- **diff 干净**：两笔 diff 合计不修改 `base.py`、`demo/`、`VERSION`、`SKILL.md`、`CLAUDE.md`、`reports/` 等禁止文件

---

## 后续步骤

- **B2 方向**：从 qx 迁入 `dekyy_adapter` 浏览器自动化爬虫或 `tfydd_adapter`，建立爬虫注册器支持按 name 批量调度
- **凭证管理**：建立 `~/.ccc/credentials/` 目录，打通 SichuanCrawler real-mode 的凭证加载路径
- **SichuanCrawler 生产增强**：接入 qx 的 SQLite 持久化层、批处理 ChunkInfo/ProcessResult 模式
- **OBS 自检集成**：将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
