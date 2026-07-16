# Plan: cla:B1.1 — 真正迁入爬虫骨架（B1 空发布回炉）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

HEAD `cfcd0c4` 的 git 仓库中，爬虫骨架代码**虽在磁盘且可运行，但从未被正式提交**——SichuanCrawler 及其测试仍为 untracked，run_crawler.py 与 docs 的修改也未 stage。B1 在 CCC 看板上标 released 但 git 历史中无对应 commit，属于假通过。本 task 强制补交。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口（已注册 beide demo + sichuan；工作区有 `SichuanCrawler` import 和 registry 条目，但从未提交）
  - `src/crawlers/base.py` — 抽象基类（HEAD 已提交）
  - `src/crawlers/demo/demo_crawler.py` — DemoCrawler 实现（HEAD 已提交）
  - `src/crawlers/sichuan/sichuan_crawler.py` — **untracked**，代码已正确实现全部 4 个抽象方法，使用 `CrawlerConfig(name="sichuan", ...)` 初始化
  - `tests/test_crawler_demo.py` — 4 单测（HEAD 已提交通过）
  - `tests/test_crawler_sichuan.py` — **untracked**，5 单测
  - `docs/migration-B1.md` — 工作区含完整迁移报告（含三硬门验收表、迁移清单、技术细节），但未提交
  - `README.md` — 工作区含「爬虫快速运行」小节（4 条命令：demo CLI、demo 测试、sichuan CLI、sichuan 测试），但未提交

- **当前结构要点**：
  1. `SichuanCrawler` 代码正确：`__init__` 已用 `self.config = CrawlerConfig(...)`，已实现 `extract()` 委托 `_extract_price_records()`
  2. `run_crawler.py` 工作区的 sichuan 注册代码无重复 import（之前 B1 plan 描述的重复导入/字段名 bug 已在工作区修干净）
  3. 所有 9 个单测（demo 4 + sichuan 5）当前全绿
  4. 两 CLI（demo + sichuan）均 exit 0，stdout 含样本数据
  5. README 已有完整爬虫运行命令段落

- **待改动点**：
  - `scripts/run_crawler.py` 第 42-43 行：残留重复 `print(f"Sample (first 3 fields):")`——仅 demo 分支路径有，sichuan 分支正常
  - `scripts/run_crawler.py`：工作区 diff 需纳入正式提交
  - `src/crawlers/sichuan/`、`tests/test_crawler_sichuan.py`：从 untracked 变为 committed
  - `docs/migration-B1.md`、`README.md`：从 modified→unstaged 变为 committed
  - `.ccc/phases/cla-b1-1-migrate.phases.json`：当前 staging 区含非标 schema，需重写为规范 JSONL

---

## 范围

- **目标**：将 SichuanCrawler 及相关文件正式提交到 git 历史，使 B1.1 不再假通过——`src/crawlers/` 有真实提交文件、pytest 全绿、README 命令可跑。
- **只改文件**：
  ```
  src/crawlers/sichuan/sichuan_crawler.py
  src/crawlers/sichuan/__init__.py
  tests/test_crawler_sichuan.py
  scripts/run_crawler.py
  docs/migration-B1.md
  README.md
  .ccc/plans/cla-b1-1-migrate.plan.md
  .ccc/phases/cla-b1-1-migrate.phases.json
  ```
- **不改文件**：`src/crawlers/base.py`、`src/crawlers/demo/`、`tests/test_crawler_demo.py`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`reports/`、`.ccc/board/`、`.ccc/ops/`
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：真正的代码迁入——stage & commit 全部爬虫代码

### 做什么

将 SichuanCrawler 全套代码（源文件、测试、CLI 注册）从 untracked/modified 变成 committed。当前 `src/crawlers/sichuan/` 的代码和 `tests/test_crawler_sichuan.py` 均在磁盘但 git 不跟踪——这意味着「B1 代码迁移」在 CCC 看板上标了 released 但仓库里看不到。本 phase 强制修正：修复 run_crawler.py 残留的重复 print、stage 所有文件、commit 到 git history。

### 怎么做

1. **修复残留 bug**：
   - `scripts/run_crawler.py` 第 42 行和第 43 行是两行完全相同的 `print(f"Sample (first 3 fields):")`——删掉第 43 行的重复语句（保留 42 行足够）

2. **Stage 代码文件**：
   - `git add src/crawlers/sichuan/`（untracked → tracked）
   - `git add tests/test_crawler_sichuan.py`（untracked → tracked）
   - `git add scripts/run_crawler.py`（modified → staged）

3. **确认 pytest 全绿**（重复确认，确保 fix 后不引入新问题）：
   - `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed，0 failed

4. **确认 CLI 双爬虫可跑**：
   - `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含样本数据
   - `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含样本数据

5. **Commit**：
   - `git commit -m "feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + README/doc (phase 1/2, cla-b1-1-migrate)"`
   - 确保工作区未 stage 的 `README.md` 和 `docs/migration-B1.md` 在 Phase 2 才引入，不在本 phase 混入

### 验收清单

- [ ] `src/crawlers/sichuan/` 及 `tests/test_crawler_sichuan.py` 已被 git 跟踪（git ls-files 可查到）
- [ ] `scripts/run_crawler.py` 已提交（工作区不再显示该文件为 modified）
- [ ] run_crawler.py 第 43 行重复 print 已删除
- [ ] pytest 9 个 case 全部通过
- [ ] 两 CLI（demo + sichuan）均 exit 0 且 stdout 含样本
- [ ] commit message 含 `phase 1/2` + `cla-b1-1-migrate`
- [ ] diff 不越 Phase 1 白名单——不触及 `src/crawlers/base.py`、`demo/`、`VERSION` 等
- [ ] `README.md` 和 `docs/migration-B1.md` 未在本 phase 被 stage

### 验收

- 四川价文件已跟踪（参考：`git ls-files src/crawlers/sichuan/ | wc -l` → ≥2（`__init__.py` + `sichuan_crawler.py`））
- 测试文件已跟踪（参考：`git ls-files tests/test_crawler_sichuan.py` → exit 0）
- pytest 全绿（参考：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed）
- CLI demo（参考：`python3 scripts/run_crawler.py --name demo` → stdout 含 `阿莫西林胶囊`）
- CLI sichuan（参考：`python3 scripts/run_crawler.py --name sichuan` → stdout 含 `Results: 3 rows`）
- 重复 print 已去（参考：`grep -c "Sample (first 3 fields)" scripts/run_crawler.py` → 1）
- commit 含 phase 编号（参考：`git log -1 --oneline | grep "phase 1/2"` → exit 0）

---

## 改动 2（Phase 2）：非代码文档提交 + CCC 过程文件

### 做什么

Phase 1 只提交了代码。Phase 2 提交与之配套的文档（migration-B1.md 迁移报告 + README 爬虫命令段落）和 CCC 控制面文件（.ccc/plans + .ccc/phases）。两个 phase 分离是为了满足「代码与文档分层」的工程原则——Phase 1 的 diff 干净地只含代码改动，Phase 2 的 diff 干净地只含文档和过程文件。

### 怎么做

1. **确认 Phase 1 已成功且 HEAD 在新 commit**（不是旧 HEAD `cfcd0c4`）
   - `git log -1 --oneline | grep "phase 1/2"`

2. **Stage 文档文件**：
   - `git add docs/migration-B1.md`
   - `git add README.md`

3. **写入 phases.json**：
   - 用本 plan 末尾 PHASES 段的内容覆盖 `.ccc/phases/cla-b1-1-migrate.phases.json`（当前 staging 区含非标 schema，需重写为规范 JSONL 格式：2 行 JSONL，每行含 phase/status/description/scope/subtasks/timeout/commit/notes）
   - `git add .ccc/phases/cla-b1-1-migrate.phases.json`

4. **写入 plan.md**：
   - 用本 plan 正文覆盖 `.ccc/plans/cla-b1-1-migrate.plan.md`
   - `git add .ccc/plans/cla-b1-1-migrate.plan.md`

5. **确认无误**：
   - `git diff --cached --name-only` 只包含白名单文件
   - 无代码文件混入（`src/`、`tests/test_crawler_*.py`、`scripts/`）

6. **Commit**：
   - `git commit -m "docs: B1.1 迁移报告 + README 爬虫命令 + CCC 过程文件 (phase 2/2, cla-b1-1-migrate)"`

7. **最终全量验收**：运行全局验收清单中所有命令

### 验收清单

- [ ] `docs/migration-B1.md` 已被 git 跟踪
- [ ] `README.md` 已被 git 跟踪（含爬虫快速运行段落）
- [ ] `.ccc/phases/cla-b1-1-migrate.phases.json` 是规范 JSONL，每行含非空 `description` 与 `scope`
- [ ] `.ccc/plans/cla-b1-1-migrate.plan.md` 已被 git 跟踪
- [ ] commit message 含 `phase 2/2` + `cla-b1-1-migrate`
- [ ] diff 仅含 `docs/`、`README.md`、`.ccc/` 白名单——无 `src/`、`tests/`、`scripts/` 代码文件
- [ ] 两笔独立 commit 各含对应 phase 编号

### 验收

- 迁移报告已跟踪（参考：`git ls-files docs/migration-B1.md` → exit 0）
- README 已跟踪（参考：`git ls-files README.md | grep README` → exit 0）
- phases 为合法 JSONL（参考：`python3 -c "import json; [json.loads(l) for l in open('.ccc/phases/cla-b1-1-migrate.phases.json')]"` → exit 0；每行 desc/scope 非空）
- 两笔独立 commit（参考：`git log --oneline -2` 显示 `phase 1/2` 和 `phase 2/2`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 修复 duplicate print + stage & commit sichuan 全套（源文件/测试/CLI 注册） | `feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + README/doc (phase 1/2, cla-b1-1-migrate)` |
| 2 | stage & commit docs/migration-B1.md + README.md + .ccc/plans + .ccc/phases | `docs: B1.1 迁移报告 + README 爬虫命令 + CCC 过程文件 (phase 2/2, cla-b1-1-migrate)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] `pytest tests/ -q --tb=short` → 9+ passed，0 failed
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- [ ] `git ls-files src/crawlers/sichuan/ | wc -l` ≥ 2
- [ ] `git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] `git ls-files scripts/run_crawler.py` → exit 0
- [ ] `git ls-files docs/migration-B1.md` → exit 0
- [ ] `git ls-files README.md` → exit 0
- [ ] `git log --oneline -2` 显示两笔独立 commit，各含对应 phase 编号 + `cla-b1-1-migrate`
- [ ] 两笔 diff 均不越白名单——不触及 `src/crawlers/base.py`、`src/crawlers/demo/`、`VERSION` 等
- [ ] 不修改 `src/crawlers/base.py`、`demo/`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`reports/`、`.ccc/board/`、`.ccc/ops/`

---

## 验收

> 全局硬门确认。

- **src 非空且已提交**：`git ls-files src/crawlers/ | wc -l` ≥ 6（base + demo × 2 + sichuan × 2 + `__init__.py`）
- **pytest 全绿**：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed，0 failed
- **README demo 命令可跑**：`python3 scripts/run_crawler.py`（不带参数）→ exit 0，stdout 含 `Results: 3 rows`
- **两笔独立 commit**：`git log --oneline -2` 输出显示两个不同 message，各含 phase 编号
- **diff 干净**：两笔 diff 合计不修改 `base.py`、`demo/`、`VERSION`、`SKILL.md`、`CLAUDE.md`、`reports/` 等禁止文件

---

## 后续步骤

- **B2 方向**：从 qx 迁入 dekyy 浏览器自动化爬虫或 tfydd 适配器，建立爬虫注册器支持按 name 批量调度
- **凭证管理**：建立 `~/.ccc/credentials/` 目录支持 real-mode 爬虫（sichuan crawler 已有此路径但未建目录）
- **SichuanCrawler 代码整洁**：`sichuan_crawler.py` 第 34 行 `self.logger` 在 real-mode 凭证错误路径中未定义——可移入 `__init__` 初始化 logging，但当前不阻塞
- **OBS 自检集成**：将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
