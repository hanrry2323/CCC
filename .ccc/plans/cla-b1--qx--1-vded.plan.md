# Plan: cla:B1 — 从旧 qx 迁入最小爬虫并跑通 1 条（闭环）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

B1 核心迁移已通过前序多轮迭代完成（提交于 `4ab2b91`/`9db6db1`/`30fc4da` 等），当前需做正式闭环验收与过程文件写入。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口，已注册 `demo` + `sichuan`
  - `src/crawlers/base.py` — `BaseCrawler` 抽象基类，`run()` 串联全流程
  - `src/crawlers/sichuan/__init__.py` / `sichuan_crawler.py` — 四川价爬虫（已迁入，git 跟踪）
  - `src/crawlers/demo/demo_crawler.py` — DemoCrawler（3 条 mock 记录）
  - `tests/test_crawler_demo.py` / `test_crawler_sichuan.py` — 各 4+6=10 条测试，全绿
  - `docs/migration-B1.md` — B1 迁移报告（已提交，有未 stage 的格式增强）
  - `README.md` — 已含「爬虫快速运行」小节（4 条命令）

- **当前结构要点**：
  1. `SichuanCrawler` 已迁入 `src/crawlers/sichuan/`（2 文件均被 git 跟踪）
  2. dry-run 管线断裂已在 `30fc4da` 修复（`_crawl_dry_run` 返回 API 同形字段 + `test_run_dry_run_total`）
  3. 当前 pytest 10 passed（demo 4 + sichuan 6）
  4. CLI `--name sichuan` 输出合法药品数据（exit 0，中文药品名 + 参考价格）
  5. `docs/migration-B1.md` 有未 stage 的格式重写（表格化 + 分节增强）
  6. `.ccc/plans/` + `.ccc/phases/` 过程文件待覆盖为本轮内容

- **待改动点**：
  - `.ccc/plans/cla-b1--qx--1-vded.plan.md` — 覆盖为本 plan
  - `.ccc/phases/cla-b1--qx--1-vded.phases.json` — 覆盖为本轮 JSONL
  - `docs/migration-B1.md` — 提交未 stage 的格式增强

---

## 范围

- **目标**：B1 爬虫迁入正式闭环——验证 sichuan/demo 代码/CLI/测试全部就位，提交含 task id 的最终 commit
- **只改文件**：
  ```
  docs/migration-B1.md
  .ccc/plans/cla-b1--qx--1-vded.plan.md
  .ccc/phases/cla-b1--qx--1-vded.phases.json
  ```
- **不改文件**：`src/`、`scripts/`、`tests/`、`README.md`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`tests/test_obs1_smoke.py`、`docs/OBS1.md`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：B1 闭环验收 + 过程文件

### 做什么

B1 爬虫迁入的正式闭环收尾。代码已全部就位——sichuan_crawler 已迁入、6 条测试全绿、dry-run 管线已修复、README 说明已更新。本 phase 验证全部硬门条件，写入 CCC 过程文件，stage `docs/migration-B1.md` 的未提交格式增强，提交含 task id 的最终 commit。不做任何代码逻辑变更。

### 怎么做

1. **验证核心就位**：
   - `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed
   - `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
   - `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `阿司匹林肠溶片`、`参考价格: 18.5`
   - `git ls-files src/crawlers/sichuan/sichuan_crawler.py` → exit 0
   - `grep -c '爬虫快速运行' README.md` → 1（确认 README 小节存在）

2. **写入 CCC 过程文件**：
   - `.ccc/phases/cla-b1--qx--1-vded.phases.json` ← 本 plan 末尾 PHASES 段 JSONL 内容
   - `.ccc/plans/cla-b1--qx--1-vded.plan.md` ← 本 plan 正文（写入动作已完成）

3. **Stage + commit**（严控范围，防夹带无关文件）：
   - `git add docs/migration-B1.md .ccc/plans/cla-b1--qx--1-vded.plan.md .ccc/phases/cla-b1--qx--1-vded.phases.json`
   - `git diff --cached --stat` 验证只有上述 3 文件
   - `git commit -m "docs: B1 爬虫迁入闭环 — sichuan 验证 + CCC 过程文件 (phase 1/1, cla-b1--qx--1-vded)"`

4. **全量验收**：执行全局验收清单所有命令

### 验收清单

- [ ] pytest 10 passed（4 demo + 6 sichuan），0 failed
- [ ] sichuan CLI exit 0，stdout 含 `Results: 3 rows`
- [ ] sichuan CLI stdout 含 `阿司匹林肠溶片`、`参考价格: 18.5`
- [ ] demo CLI exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `git ls-files src/crawlers/sichuan/sichuan_crawler.py` → exit 0
- [ ] `git ls-files tests/test_crawler_sichuan.py` → exit 0
- [ ] README.md 含「爬虫快速运行」小节
- [ ] `.ccc/phases/cla-b1--qx--1-vded.phases.json` 合法 JSONL（每行非空 description + scope）
- [ ] `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- [ ] commit message 含 `cla-b1--qx--1-vded`
- [ ] diff 不越白名单——不修改 `src/`、`scripts/`、`tests/`、`README.md`

### 验收

- 测试全绿（参考：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → stdout 含 `10 passed`）
- CLI 可跑（参考：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`、`阿司匹林肠溶片`、`参考价格: 18.5`）
- 代码路径已迁入（参考：`git ls-files src/crawlers/sichuan/sichuan_crawler.py tests/test_crawler_sichuan.py` → 2 file paths）
- phases JSONL 合法（参考：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-b1--qx--1-vded.phases.json` → exit 0）
- commit 含 task id（参考：`git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0）

---

## 验收

- [ ] **测试全绿**：`python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed，0 failed
- [ ] **sichuan CLI 可跑**：`python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `阿司匹林肠溶片`、`参考价格: 18.5`
- [ ] **demo 无影响**：`python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] **代码路径已迁入**：`git ls-files src/crawlers/sichuan/sichuan_crawler.py tests/test_crawler_sichuan.py | wc -l` → 2
- [ ] **READIME 含运行说明**：`grep -q '爬虫快速运行' README.md` → exit 0
- [ ] **phases JSONL 合法**：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-b1--qx--1-vded.phases.json` → exit 0
- [ ] **commit 含 task id**：`git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0
- [ ] **diff 合规**：`git diff --name-only HEAD~1..HEAD | grep -cE '^(src/|tests/|scripts/)'` → 0（本 phase 不动代码）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | B1 闭环验证 + docs 格式增强 stage + CCC 过程文件 | `docs: B1 爬虫迁入闭环 — sichuan 验证 + CCC 过程文件 (phase 1/1, cla-b1--qx--1-vded)` |

---

## 全局验收清单

- [ ] `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- [ ] `git ls-files src/crawlers/sichuan/sichuan_crawler.py tests/test_crawler_sichuan.py | wc -l` → 2
- [ ] `grep -q '爬虫快速运行' README.md` → exit 0
- [ ] `.ccc/phases/cla-b1--qx--1-vded.phases.json` 合法 JSONL（每行非空 description + scope）
- [ ] `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- [ ] commit message 含 `cla-b1--qx--1-vded`
- [ ] `git diff --name-only HEAD~1..HEAD | grep -cE '^(src/|tests/|scripts/|README\.md)'` → 0（不越白名单）
- [ ] `git log -1 --oneline | grep cla-b1--qx--1-vded` → exit 0

---

## 后续步骤

- **B2 方向**：从 qx 迁入 `dekyy_adapter`（Playwright 浏览器自动化爬虫，`~/program/projects/qx/crawlers/dekyy_adapter/dekyy_crawler.py`）或 `tfydd_adapter`，建立爬虫注册器支持按 name 批量调度
- **凭证管理**：完善 `~/.ccc/credentials/` 目录，打通 SichuanCrawler real-mode 凭证加载 + `_fetch_price_data` 网络请求
- **自检集成**：将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`，在 OBS 探针中增加「爬虫可调度」断言
- **持久化层**：从 qx 迁入 SQLite 持久化（`persist.py`）或 PG 持久化（`persist_pg.py`），与爬虫抽取结果对接

## 完成定义（仅 Phase 1）
1. 仅实现 Phase 1 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-b1--qx--1-vded` 与 `phase=1`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase
