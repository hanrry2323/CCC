# Plan: cla:B1 — 从旧 qx 迁入最小爬虫并跑通 1 条（四川价）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

clawmed-ccc 已有 DemoCrawler 骨架（`base.py` → `DemoCrawler`）、CLI 入口（`scripts/run_crawler.py` 仅注册 demo）、README 尚未提及爬虫运行。需从归档零件库 `~/program/projects/qx` 迁入真正能跑通的数据爬虫——优先四川价。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口，当前仅注册 `DemoCrawler`
  - `src/crawlers/base.py` — `BaseCrawler` 抽象基类，4 个抽象方法 + `run()` 串联全流程
  - `src/crawlers/demo/demo_crawler.py` — DemoCrawler 实现（3 条 mock 药品记录）
  - `tests/test_crawler_demo.py` — 4 条 demo 单测
  - `src/util_obs4.py` + `tests/test_obs4_util.py` — OBS4 工具链

- **当前结构要点**：
  1. BaseCrawler 接口定义清晰：`_load_credential` → `login` → `crawl` → `extract` → `run()`
  2. DemoCrawler 是全流程存根，4 条测试验证了骨架可用
  3. CLI 仅支持 demo，执行 `python3 scripts/run_crawler.py --name demo` 可跑（虽然 SichuanCrawler 还没创建）
  4. README 无爬虫运行指引

- **待改动点**：
  - `src/crawlers/sichuan/__init__.py` — 新建包声明
  - `src/crawlers/sichuan/sichuan_crawler.py` — 新建 `SichuanCrawler(BaseCrawler)`，实现 4 个抽象方法，支持 dry-run + real 模式
  - `tests/test_crawler_sichuan.py` — 新建，≥4 条单测覆盖 dry-run 管线
  - `scripts/run_crawler.py` — 增加 `SichuanCrawler` 导入和注册
  - `README.md` — 追加「爬虫快速运行」小节（≤10 行）
  - `docs/migration-B1.md` — 新建迁移报告（含 task id）
  - `.ccc/plans/cla-b1--qx--1-vded.plan.md` — 本 plan
  - `.ccc/phases/cla-b1--qx--1-vded.phases.json` — phases JSONL

---

## 范围

- **目标**：从 qx 迁入四川价爬虫（`SichuanCrawler`），跑通 dry-run 管线，CLI exit 0 + pytest 10 passed，README 含运行指引，迁移报告含 task id
- **只改文件**：
  ```
  scripts/run_crawler.py
  src/crawlers/sichuan/__init__.py
  src/crawlers/sichuan/sichuan_crawler.py
  tests/test_crawler_sichuan.py
  README.md
  docs/migration-B1.md
  .ccc/plans/cla-b1--qx--1-vded.plan.md
  .ccc/phases/cla-b1--qx--1-vded.phases.json
  ```
- **不改文件**：`src/crawlers/base.py`、`src/crawlers/demo/`、`tests/test_crawler_demo.py`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`src/crawlers/__init__.py`、`VERSION`、`CLAUDE.md`、`SKILL.md`
- **不复制旧仓**：不复制 qx 的 `.ccc/plans|phases|reports|board`、`_archive/` 仅参考不当来源
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：四川价爬虫实现 + 单测 + CLI 注册

### 做什么

从 qx `crawlers/sichuan_price_adapter/` 和 `crawlers/_wrappers/sichuan_wrapper.py` 提炼最小可跑的 `SichuanCrawler`。设计关键点：dry-run 模式（`CRAWLER_DRY_RUN=1`）返回硬编码样本数据，不依赖网络和凭证；real 模式调用 `_fetch_price_data` POST 请求。CLI 注册后 `--name sichuan` 即可运行。

### 怎么做

1. **`src/crawlers/sichuan/__init__.py`** — 空包声明 `"""Sichuan crawler package."""`
2. **`src/crawlers/sichuan/sichuan_crawler.py`** — 类 `SichuanCrawler(BaseCrawler)`：
   - `config = CrawlerConfig(name="sichuan", site_url="https://ggfw.scyb.org.cn")`
   - `_load_credential()` — 尝试读 `~/.ccc/credentials/sichuan-001.json`，不存在返回 {}
   - `login(credential)` — `CRAWLER_DRY_RUN=1` 直接返回 True；real 模式校验 `base_url`
   - `crawl()` — dry-run 调 `_crawl_dry_run()`（3 条样本：阿司匹林肠溶片/氨氯地平/阿莫西林胶囊），real 调 `_fetch_price_data()` + `_extract_price_records()`
   - `_crawl_dry_run()` — 返回同形 dict 列表（name/spec/manufacturer/price/unit/update_time）
   - `_fetch_price_data(token)` — requests POST 到四川平台，30s 超时
   - `_extract_price_records(api_data)` — 字段映射为 `product_name/spec/manufacturer/reference_price/unit/last_updated`
   - `extract(raw)` — 委托 `_extract_price_records(raw)`
3. **`tests/test_crawler_sichuan.py`** — ≥5 条单测：
   - `test_run_dry_run_total` — `run()` 完整 dry-run 管线返回 ≥1 条记录
   - `test_sichuan_import` — 模块可导入
   - `test_sichuan_crawler_initialization` — 实例化 config.name == "sichuan"
   - `test_sichuan_crawl_dryrun_record_has_required_fields` — 字段齐套
   - `test_sichuan_load_credential_empty_path` — 凭证不存在时返回空 dict
   - 每条用 `os.environ["CRAWLER_DRY_RUN"]="1"` 包裹
4. **`scripts/run_crawler.py`** — 增加 `from crawlers.sichuan.sichuan_crawler import SichuanCrawler`，`crawler_map` 增加 "sichuan" 键

### 验收清单

- [ ] `SichuanCrawler` 模块可导入且不报语法错误
- [ ] 全部测试通过：`pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed，0 failed
- [ ] CLI 可跑：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `阿司匹林肠溶片`、`参考价格: 18.5`
- [ ] CLI demo 不受影响：`python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `src/crawlers/sichuan/` 下 2 文件被 git 跟踪
- [ ] 新测试被 git 跟踪：`git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] 不修改已有文件（`scripts/run_crawler.py` 是新增 import，不算修改逻辑）
- [ ] diff 不越白名单（不碰 `base.py`、`demo/`、`obs4`）

### 验收

- **测试全绿**（参考：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → stdout 含 `10 passed`）
- **sichuan CLI 可跑**（参考：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `阿司匹林肠溶片`）
- **demo 无退化**（参考：`python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`）
- **代码已迁入**（参考：`git ls-files src/crawlers/sichuan/ | wc -l` → 2）

---

## 改动 2（Phase 2）：文档 + 迁移报告 + CCC 过程文件

### 做什么

Phase 1 代码落地后，补全文档和 CCC 过程文件：README 追加「爬虫快速运行」小节（≤10 行，含 demo + sichuan 共 4 条命令），新建 `docs/migration-B1.md` 迁移报告（含 task id、代码路径、CLI 验收三硬门），写入 `.ccc/plans/` 和 `.ccc/phases/` 过程文件，产生含 task id 的 commit。

### 怎么做

1. **`README.md`** — 在末尾（License 之前）插入「爬虫快速运行」小节，4 条命令：
   ```markdown
   ## 爬虫快速运行

   ```bash
   python3 scripts/run_crawler.py
   python3 -m pytest tests/test_crawler_demo.py -q --tb=short
   python3 scripts/run_crawler.py --name sichuan
   python3 -m pytest tests/test_crawler_sichuan.py -q --tb=short
   ```
   ```
2. **`docs/migration-B1.md`** — 新建迁移报告，包含：
   - Task ID: `cla-b1--qx--1-vded`
   - 迁移概要：从 qx `sichuan_price_adapter/` 迁入
   - 三硬门验收表（代码路径 / CLI 可跑通 / README 运行说明）
   - 技术要点：BaseCrawler 适配、dry-run 模式设计、与 qx 原版差异表
   - 完成定义
3. **`.ccc/plans/cla-b1--qx--1-vded.plan.md`** — 覆写为本 plan 正文
4. **`.ccc/phases/cla-b1--qx--1-vded.phases.json`** — 覆写为 2-phase JSONL（本 plan 末尾 PHASES 段）
5. Stage + commit（diff 白名单 6 文件）

### 验收清单

- [ ] README.md 含「爬虫快速运行」小节，仅 4 条命令（≤10 行）
- [ ] `docs/migration-B1.md` 含 task id `cla-b1--qx--1-vded`
- [ ] `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- [ ] `.ccc/phases/cla-b1--qx--1-vded.phases.json` 合法 JSONL（每行非空 description + scope）
- [ ] commit message 含 `cla-b1--qx--1-vded`
- [ ] diff 不越白名单——不修改 `src/`、`tests/`（Phase 1 代码）、`scripts/`
- [ ] Phase 2 与 Phase 1 的 commit 前后有序

### 验收

- **README 含运行指引**（参考：`grep -q '爬虫快速运行' README.md` → exit 0）
- **迁移报告含 task id**（参考：`grep 'cla-b1--qx--1-vded' docs/migration-B1.md` → exit 0）
- **phases JSONL 合法**（参考：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-b1--qx--1-vded.phases.json` → exit 0）
- **commit 含 task id**（参考：`git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0）

---

## PHASES

```jsonl
{"phase":1,"description":"四川价爬虫实现 + 单测 + CLI 注册","subtasks":{"run_crawler_py":{"description":"在 scripts/run_crawler.py 中增加 SichuanCrawler 导入和注册","type":"add"},"sichuan_init_py":{"description":"新建 src/crawlers/sichuan/__init__.py 包声明","type":"add"},"sichuan_crawler_py":{"description":"新建 src/crawlers/sichuan/sichuan_crawler.py 实现 SichuanCrawler 类","type":"add"},"test_crawler_sichuan_py":{"description":"新建 tests/test_crawler_sichuan.py 单测文件（≥5 条）","type":"add"},"README_md":{"description":"在 README.md 追加爬虫快速运行小节（4 条命令）","type":"add"}}}
{"phase":2,"description":"文档 + 迁移报告 + CCC 过程文件","subtasks":{"README_md":{"description":"追加爬虫快速运行小节（4 条命令）","type":"add"},"migration_b1_md":{"description":"创建 docs/migration-B1.md 迁移报告","type":"add"},"plan_file":{"description":"更新 .ccc/plans/cla-b1--qx--1-vded.plan.md","type":"update"},"phases_json":{"description":"生成 .ccc/phases/cla-b1--qx--1-vded.phases.json JSONL","type":"add"}}}
```

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | SichuanCrawler 实现 + 单测 + CLI 注册 | `feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)` |
| 2 | README 运行指引 + migration 报告 + CCC 过程文件 | `docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)` |

---

## 全局验收清单

- [ ] `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed，0 failed
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `git ls-files src/crawlers/sichuan/ | wc -l` → 2
- [ ] `git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] `grep -q '爬虫快速运行' README.md` → exit 0
- [ ] `grep 'cla-b1--qx--1-vded' docs/migration-B1.md` → exit 0
- [ ] `.ccc/phases/cla-b1--qx--1-vded.phases.json` 合法 JSONL（每行非空 description + scope）
- [ ] `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- [ ] commit message 含 `cla-b1--qx--1-vded`
- [ ] `git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0（最终 commit）
- [ ] diff 不越白名单——所有改动在白名单 8 文件内

---

## 验收

- [ ] **测试全绿**：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed，0 failed
- [ ] **sichuan CLI 可跑**：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `阿司匹林肠溶片`、`参考价格: 18.5`
- [ ] **demo 无退化**：`python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] **代码已迁入**：`git ls-files src/crawlers/sichuan/ | wc -l` → 2
- [ ] **测试已迁入**：`git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] **README 含运行指引**：`grep -q '爬虫快速运行' README.md` → exit 0
- [ ] **迁移报告含 task id**：`grep 'cla-b1--qx--1-vded' docs/migration-B1.md` → exit 0
- [ ] **phases JSONL 合法**：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-b1--qx--1-vded.phases.json` → exit 0
- [ ] **phases phase 为 int**：`python3 -c "import json,sys; assert all(type(j['phase'])==int for j in [json.loads(l) for l in open(sys.argv[1])])"`
- [ ] **phases subtasks 为 dict**：`python3 -c "import json,sys; assert all(type(j['subtasks'])==dict for j in [json.loads(l) for l in open(sys.argv[1])])"`
- [ ] **commit 含 task id**：`git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0
- [ ] **diff 合规**：`git diff --name-only HEAD~1..HEAD | grep -cE '^(src/crawlers/(?!sichuan/)|tests/test_crawler_demo)'` → 0（不越白名单）

---

## 后续步骤

- **B2 方向**：从 qx 迁入 `dekyy_adapter`（Playwright 浏览器自动化爬虫），建立爬虫注册器支持按 name 批量调度
- **凭证管理**：完善 `~/.ccc/credentials/` 目录，打通 SichuanCrawler real-mode 凭证加载 + `_fetch_price_data` 网络请求
- **自检集成**：将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
- **持久化层**：从 qx 迁入 SQLite 持久化，与爬虫抽取结果对接

## 完成定义（仅 Phase 2）
1. 仅实现 Phase 2 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-b1--qx--1-vded` 与 `phase=2`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase
