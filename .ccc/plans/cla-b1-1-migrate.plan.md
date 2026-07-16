# Plan: cla:B1.1 — 爬虫骨架迁移报告 + 硬门验收（B1 空发布回炉）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

B1（cla-b1--qx--1-vded）已于 `0e275bb` 完成 demo 爬虫代码迁移，但未产出迁移报告。当前代码结构已就位，B1.1 回炉交付正式审计文件。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口，`crawler_map = {"demo": DemoCrawler}`
  - `src/crawlers/base.py` — CrawlerConfig + BaseCrawler 抽象基类（来自 qx `crawlers/base.py`）
  - `src/crawlers/demo/demo_crawler.py` — DemoCrawler，3 条硬编码药品，完整实现 run() 生命周期
  - `src/crawlers/demo/__init__.py` / `src/crawlers/__init__.py` — 包声明
  - `tests/test_crawler_demo.py` — 4 单测（全部通过）
  - `tests/conftest.py` — `sys.path.insert` src-layout 修正
  - `src/util_obs4.py` — OBS4 工具模块（非本 task 范围）
  - `tests/test_obs4_util.py` — OBS4 单测（非本 task 范围）
  - `README.md` — 146-154 行 `## 爬虫快速运行` 区块已存在

- **当前结构要点**：
  1. **三硬门已全部通过**：`src/crawlers/` 非空（6 文件），`python3 scripts/run_crawler.py` exit 0 输出 crawl OK，`pytest tests/test_crawler_demo.py -q` 4 passed
  2. 代码从 qx `crawlers/base.py` 和 `_wrappers/demo_wrapper.py` 迁入，已适配 clawmed-ccc 的 BaseCrawler 接口
  3. 未创建 `docs/migration-B1.md`——迁移遗产、来源路径、改动说明均无书面记录
  4. `.ccc/plans/` 无 `cla-b1-1-migrate.plan.md`，`.ccc/phases/` 无 `cla-b1-1-migrate.phases.json`

- **待改动点**：
  - 创建 `docs/migration-B1.md`，记录 B1 阶段从 qx 迁入了哪些文件、来源路径、改动说明、验收状态
  - 确认三硬门可稳定重复通过
  - 将本 plan 写入 `.ccc/plans/cla-b1-1-migrate.plan.md`，phases 写入 `.ccc/phases/cla-b1-1-migrate.phases.json`

---

## 范围

- **目标**：创建 B1 迁移审计报告（docs/migration-B1.md），确认三硬门稳定通过，补全 .ccc 过程产物
- **只改文件**：
  ```
  docs/migration-B1.md                          # 迁移审计报告（Phase 1）
  .ccc/plans/cla-b1-1-migrate.plan.md           # 本 plan 文件（Phase 1）
  .ccc/phases/cla-b1-1-migrate.phases.json      # 本 task phases（Phase 1）
  ```
- **不改文件**：`src/crawlers/` 下所有文件、`scripts/run_crawler.py`、`tests/`、`README.md`、`VERSION`、`SKILL.md`、`CLAUDE.md`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：创建迁移报告 + 硬门验收文档化

### 做什么

B1 的代码已在 `0e275bb` 落地运行，但未产出迁移审计报告。本 phase 创建 `docs/migration-B1.md`，内容完整记录：

1. B1 阶段从 qx 迁入了哪些文件、来源路径、做了什么改造
2. 三硬门验收命令及实际结果（src 非空 / pytest 绿 / CLI 可跑）
3. 后续可迁入方向概览（如四川价爬虫文件路径标注）

同时将本 plan 存放到 `.ccc/plans/`、phases 存放到 `.ccc/phases/`，完成 CCC 过程闭环。

### 怎么做

1. **创建 `docs/migration-B1.md`**，内容至少包含：
   - 首行 `# Migration Report: B1 — 从 qx 迁入爬虫骨架` + task id `cla-b1--qx--1-vded`
   - 迁入代码清单表（列：本地路径 | qx 来源路径 | 用途 | 改造说明）
   - 验收状态表（三硬门：src 非空 / pytest 绿 / CLI 可跑），附带实际验证命令和 exit 码
   - 未迁入的 qx 爬虫资源概览（如 `crawlers/sichuan_price_adapter/`），标明「后续可迁入」

2. **创建 `.ccc/plans/cla-b1-1-migrate.plan.md`**：
   - 内容与本 plan 相同（即写入当前输出的完整 plan.md）

3. **创建 `.ccc/phases/cla-b1-1-migrate.phases.json`**：
   - 内容为输出的 phases JSONL

4. **运行三硬门验收**并确认结果无误：
   - src 非空：`git ls-files src/crawlers/` 文件数 ≥ 4
   - pytest 绿：`python3 -m pytest tests/test_crawler_demo.py -q --tb=short` → 4 passed
   - CLI 可跑：`python3 scripts/run_crawler.py` → exit 0，stdout 含 `crawl OK`

5. **Stage + commit**（三个文件均 stage）：
   - `git add docs/migration-B1.md .ccc/plans/cla-b1-1-migrate.plan.md .ccc/phases/cla-b1-1-migrate.phases.json`
   - commit message: `docs: B1.1 迁移报告 + 硬门验收闭环 (phase 1/1, cla-b1-1-migrate)`

### 验收清单

- [ ] docs/migration-B1.md 已创建，含 task id cla-b1--qx--1-vded
- [ ] 迁入代码清单表含至少 3 行记录（base.py / demo/ / tests/ 等）
- [ ] 验收状态表三硬门全部标记为 PASS
- [ ] .ccc/plans/cla-b1-1-migrate.plan.md 已创建
- [ ] .ccc/phases/cla-b1-1-migrate.phases.json 已创建
- [ ] commit message 含 `cla-b1-1-migrate`
- [ ] 不修改白名单外的任何文件

### 验收

- 迁移报告存在且标注了 B1 的 task id（参考：`test -f docs/migration-B1.md && grep -q 'cla-b1--qx--1-vded' docs/migration-B1.md`，exit 0）
- CLI 可稳定重复运行（参考：`python3 scripts/run_crawler.py && echo "OK"` → exit 0，stdout 含 `crawl OK`）
- pytest 全绿（参考：`python3 -m pytest tests/test_crawler_demo.py -q --tb=short` → exit 0，stdout 含 `4 passed`）
- src 目录非空（参考：`git ls-files src/crawlers/ | wc -l` → ≥ 4）
- plan 和 phases 已写入 .ccc（参考：`test -f .ccc/plans/cla-b1-1-migrate.plan.md` 且 `test -f .ccc/phases/cla-b1-1-migrate.phases.json`，均 exit 0）
- 唯一 commit message 含 task id（参考：`git log -1 --oneline | grep cla-b1-1-migrate` → exit 0）
- diff 不越白名单（参考：`git diff --name-only HEAD~1..HEAD` 仅含白名单中 3 文件）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 创建 docs/migration-B1.md + 写入 .ccc/plans + .ccc/phases | `docs: B1.1 迁移报告 + 硬门验收闭环 (phase 1/1, cla-b1-1-migrate)` |

---

## 全局验收清单

- [ ] `docs/migration-B1.md` 存在且含 task id `cla-b1--qx--1-vded`
- [ ] 迁入代码清单表完整（≥ 3 行）
- [ ] 三硬门验收状态全部 PASS
- [ ] `python3 scripts/run_crawler.py` exit 0
- [ ] `python3 -m pytest tests/test_crawler_demo.py -q --tb=short` exit 0，含 `4 passed`
- [ ] `git ls-files src/crawlers/ | wc -l` ≥ 4
- [ ] `.ccc/plans/cla-b1-1-migrate.plan.md` 已创建
- [ ] `.ccc/phases/cla-b1-1-migrate.phases.json` 已创建
- [ ] commit message 含 `cla-b1-1-migrate`
- [ ] diff 范围仅限白名单 3 文件
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json phase 数 = 1，与 plan 一致

---

## 验收

- 迁移报告存在且标记了 B1 task id（参考：`test -f docs/migration-B1.md && grep -q 'cla-b1--qx--1-vded' docs/migration-B1.md`）
- CLI demo 爬虫可稳定运行（参考：`python3 scripts/run_crawler.py && echo "OK"`）
- demo 单测全绿（参考：`python3 -m pytest tests/test_crawler_demo.py -q --tb=short`）
- plan 和 phases 文件已写入 .ccc（参考：`test -f .ccc/plans/cla-b1-1-migrate.plan.md && test -f .ccc/phases/cla-b1-1-migrate.phases.json`）
- 唯一 commit 含 task id `cla-b1-1-migrate`（参考：`git log -1 --oneline | grep cla-b1-1-migrate`）
- diff 不越白名单（参考：`git diff --name-only HEAD~1..HEAD` 仅白名单内 3 文件）

---

## 后续步骤

- **B2 方向**：从 qx 迁入 tfydd 适配器或 dekyy 浏览器自动化爬虫
- **四川价爬虫**：参考 qx `crawlers/sichuan_price_adapter/`，按 BaseCrawler 接口包装（已在原 B1 plan 的 Phase 2 规划，可独立开卡）
- **爬虫注册器**：建立 registry 支持按 name 批量调度多个爬虫
- **凭证管理**：建立 `~/.ccc/credentials/` 目录，支持 real 模式的 API 爬虫

## 完成定义（仅 Phase 1）
1. 仅实现 Phase 1 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-b1-1-migrate` 与 `phase=1`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase
