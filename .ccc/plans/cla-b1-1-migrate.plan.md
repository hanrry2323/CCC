# CCC 执行任务: cla-b1-1-migrate

## 当前 Phase（强制）
- **只做 Phase 2**，不得实现其他 phase 的需求
- 不得修改不属于本 phase 白名单的文件
- 完成定义仅对本 phase 生效；其他 phase 留给后续调度
- 你是执行器（弱模型友好）：按清单改文件，不要重写 plan，不要发明新需求

## 文件白名单 scope（硬约束）
只允许修改下列路径；改其他文件视为失败：
- `docs/migration-B1.md`
- `.ccc/plans/cla-b1-1-migrate.plan.md`
- `.ccc/phases/cla-b1-1-migrate.phases.json`

## Plan（全文供参考；执行范围仍以本 phase 为准）

# Plan: cla:B1.1 — 真正迁入爬虫骨架（B1 空发布回炉）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

B1（cla-b1--qx--1-vded）于 `c8c3d31` 完成 demo 爬虫代码迁入，但被标记为假通过：仅有 demo 单源、四川价爬虫骨架未合入、无迁移报告与过程产物。当前仓库存在四川价爬虫代码和测试文件，但尚未提交且 tests 不通过。

- **入口/核心文件**：
  - `scripts/run_crawler.py` — CLI 入口，已修改包含 `from crawlers.sichuan.sichuan_crawler import SichuanCrawler` 并注册 `{"demo": DemoCrawler, "sichuan": SichuanCrawler}`，**未提交**
  - `src/crawlers/base.py` — BaseCrawler 抽象基类，声明 4 个抽象方法：`_load_credential`、`login`、`crawl`、`extract`
  - `src/crawlers/demo/demo_crawler.py` — DemoCrawler（已提交），正确实现了全部 4 个抽象方法
  - `src/crawlers/sichuan/sichuan_crawler.py` — 四川价爬虫适配器，**未提交**；缺失 `extract()` 抽象方法实现
  - `tests/test_crawler_demo.py` — Demo 爬虫 4 单测（已提交，全部通过）
  - `tests/test_crawler_sichuan.py` — 四川价爬虫 5 单测，**未提交**；因 `SichuanCrawler` 无法实例化导致 4/5 失败

- **当前结构要点**：
  1. **Demo 骨架已就位**：`src/crawlers/demo/` + `src/crawlers/base.py` + `__init__.py` — 已提交于 B1
  2. **四川价爬虫代码已写好但未提交**：`src/crawlers/sichuan/`（`sichuan_crawler.py` + `__init__.py`）及 `tests/test_crawler_sichuan.py` 在 untracked 区
  3. **SichuanCrawler 缺 `extract()` 方法**（`_extract_price_records` 定义了提取逻辑但方法名未对齐抽象接口），导致 `crawler = SichuanCrawler()` 时 `TypeError: Can't instantiate abstract class`
  4. **`scripts/run_crawler.py` 已含 Sichuan 引用**但修改未提交
  5. **已有两笔重复 B1.1 commit**（`e586399`、`a22a6f2`），创建了 `docs/migration-B1.md` 和 `.ccc/` 过程文件，但未处理爬虫代码

- **待改动点**：
  - 给 `SichuanCrawler` 添加 `extract()` 方法以通过基类实例化检查
  - 确认 `crawl()` 和 `extract()` 职责分离，确保 `run()` 完整链路（load → login → crawl → extract）可跑
  - 确认 sichuan + demo 两套单测全部通过
  - 提交 sichuan 爬虫代码 + run_crawler.py 修改 + 更新的测试
  - 覆盖或更新 `docs/migration-B1.md` 以完整记录 B1→B1.1 全量迁移清单

---

## 范围

- **目标**：修复 SichuanCrawler 使其完整实现 BaseCrawler 接口，提交四川价爬虫代码（src + tests + CLI 注册），完成三硬门验收
- **只改文件**：
  ```
  src/crawlers/sichuan/sichuan_crawler.py     # 修复 extract() 抽象方法（Phase 1）
  tests/test_crawler_sichuan.py               # 按修复后的爬虫调整验收（Phase 1）
  scripts/run_crawler.py                      # 注册 sichuan 爬虫（已改，需提交）（Phase 1）
  docs/migration-B1.md                        # 迁移报告，记录 B1→B1.1 全量迁移（Phase 2）
  .ccc/plans/cla-b1-1-migrate.plan.md         # 本 plan 覆盖（Phase 2）
  .ccc/phases/cla-b1-1-migrate.phases.json    # 本 phases 覆盖（Phase 2）
  ```
- **不改文件**：`src/crawlers/base.py`、`src/crawlers/demo/`、`tests/test_crawler_demo.py`、`src/util_obs4.py`、`tests/test_obs4_util.py`、`VERSION`、`SKILL.md`、`CLAUDE.md`、`README.md`
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：四川价爬虫适配修复 + 代码提交 + 硬门验收

### 做什么

B1 遗留的 sichuan 爬虫代码未提交且 `SichuanCrawler` 不能实例化（缺 `extract()` 抽象方法）。本 phase 修复接口一致性，确认 `run()` 全链路可跑，提交代码，并验证三硬门。

**「真正迁入」的核心**：`src/crawlers/sichuan/` 成为可实例化、可运行、单测全绿的一等公民。

### 怎么做

1. **修复 `sichuan_crawler.py`**：添加 `extract(self, raw)` 方法（@override）。参考 `_extract_price_records` 已有的映射逻辑，将其作为 `extract()` 的实现体。确保 `crawl()` 返回原始数据（dry-run 或 API 响应），`extract()` 完成归一化输出。

2. **修复 `test_crawler_sichuan.py`（如需要）**：若 dry-run `crawl()` 的数据结构调整为「原始格式」（即 `name`/`price` 而非 `product_name`/`reference_price`），则对应更新字段名断言。保持测试数量 ≥ 5 且覆盖 `crawl()`、`extract()`、`_load_credential()`、`login()`、`run()` 五条路径。

3. **运行全站测试**：
   - `pytest tests/test_crawler_demo.py -q --tb=short` → 4 passed
   - `pytest tests/test_crawler_sichuan.py -q --tb=short` → 5+ passed（含新增 `test_run`）
   - **禁止留失败测试**

4. **验证 CLI 双爬虫可跑**：
   - `python3 scripts/run_crawler.py --name demo` → exit 0
   - `python3 scripts/run_crawler.py --name sichuan` → exit 0

5. **Stage + commit**（只有 code 相关文件，不含 docs/.ccc）：
   - `git add src/crawlers/sichuan/ tests/test_crawler_sichuan.py scripts/run_crawler.py`
   - commit message: `feat(crawler): 四川价爬虫适配 — 迁入完整 BaseCrawler 实现 (phase 1/2, cla-b1-1-migrate)`

### 验收清单

- [ ] SichuanCrawler 实现了 `extract()` 方法
- [ ] `python3 -c "from crawlers.sichuan.sichuan_crawler import SichuanCrawler; c = SichuanCrawler(); print('OK')"` 不报错
- [ ] demo crawler 4 单测全绿
- [ ] sichuan crawler 5+ 单测全绿
- [ ] `python3 scripts/run_crawler.py --name demo` exit 0
- [ ] `python3 scripts/run_crawler.py --name sichuan` exit 0
- [ ] 提交只包含白名单 Phase 1 文件（sichuan/、test、run_crawler.py）

### 验收

- 四川价爬虫可实例化（参考：`python3 -c "from crawlers.sichuan.sichuan_crawler import SichuanCrawler; SichuanCrawler()"` → exit 0）
- demo 单测全绿（参考：`python3 -m pytest tests/test_crawler_demo.py -q --tb=short` → `4 passed`）
- sichuan 单测全绿（参考：`python3 -m pytest tests/test_crawler_sichuan.py -q --tb=short` → exit 0，≥ 5 passed）
- CLI 双爬虫可跑（参考：`python3 scripts/run_crawler.py --name demo && python3 scripts/run_crawler.py --name sichuan` → exit 0×2）
- commit message 含 `phase 1/2` + `cla-b1-1-migrate`（参考：`git log -1 --oneline | grep 'cla-b1-1-migrate.*phase 1/2'` → exit 0）
- diff 不越 Phase 1 白名单（参考：`git diff --name-only HEAD~1..HEAD | grep -vE '^(src/crawlers/sichuan/|tests/test_crawler_sichuan\.py|scripts/run_crawler\.py$)'` → exit 1）

---

## 改动 2（Phase 2）：迁移报告 + .ccc 过程文件

### 做什么

代码迁移完成后补全书面审计。创建/覆盖 `docs/migration-B1.md` 记录 B1→B1.1 全量迁移明细，覆盖 `.ccc/plans/` 和 `.ccc/phases/` 过程文件完成 CCC 闭环。

### 怎么做

1. **创建/覆盖 `docs/migration-B1.md`**，内容至少包含：
   - 首行 `# Migration Report: B1 → B1.1 — 爬虫骨架完整迁入` + task id `cla-b1-1-migrate`
   - 迁入代码清单表两段：
     - **B1 段**（`c8c3d31`）：demo 爬虫（base.py、demo_crawler.py、tests、CLI 注册）
     - **B1.1 段**（Phase 1 commit）：sichuan 爬虫（sichuan_crawler.py + tests + CLI 注册）
   - 验收状态表：三硬门（src 非空 / pytest 全绿 / CLI 双爬虫可跑）
   - 来源标注：sichuan 爬虫的原始来源（qx `crawlers/sichuan_price_adapter/`）

2. **覆盖 `.ccc/plans/cla-b1-1-migrate.plan.md`**：
   - 内容与本 plan 相同

3. **覆盖 `.ccc/phases/cla-b1-1-migrate.phases.json`**：
   - 内容为本 plan 输出的 phases JSONL（2 phases）

4. **运行三硬门验收**确认：
   - src 非空：`git ls-files src/crawlers/` ≥ 8 文件
   - pytest 全绿：demo (4) + sichuan (5+)
   - CLI 双爬虫可跑

5. **Stage + commit**（docs + .ccc 文件）：
   - `git add docs/migration-B1.md .ccc/plans/cla-b1-1-migrate.plan.md .ccc/phases/cla-b1-1-migrate.phases.json`
   - commit message: `docs: B1→B1.1 迁移报告 + 硬门验收闭环 (phase 2/2, cla-b1-1-migrate)`

### 验收清单

- [ ] docs/migration-B1.md 存在，含 B1、B1.1 两段迁入清单
- [ ] 验收状态表三硬门全部 PASS
- [ ] .ccc/plans/cla-b1-1-migrate.plan.md 已覆盖
- [ ] .ccc/phases/cla-b1-1-migrate.phases.json 已覆盖（2 phases）
- [ ] pytest demo + sichuan 全部 9+ 测试通过
- [ ] commit message 含 `phase 2/2` + `cla-b1-1-migrate`

### 验收

- 迁移报告含 B1.1 task id（参考：`grep -q 'cla-b1-1-migrate' docs/migration-B1.md` → exit 0）
- 双爬虫单测全绿（参考：`python3 -m pytest tests/ -q --tb=short` → ≥ 9 passed）
- CLI 双模式可跑（参考：`python3 scripts/run_crawler.py --name sichuan && echo "OK"` → stdout 含 `crawl OK` 或等价标识）
- plan 和 phases 已写入 .ccc（参考：`test -f .ccc/plans/cla-b1-1-migrate.plan.md && test -f .ccc/phases/cla-b1-1-migrate.phases.json` → exit 0）
- 两笔独立 commit 各含对应 phase 编号（参考：`git log --oneline -2` 看两笔 message 含 `phase 1/2`、`phase 2/2`）

---

## 验收

- 四川价爬虫可实例化：`python3 -c "from crawlers.sichuan.sichuan_crawler import SichuanCrawler; SichuanCrawler()"` → exit 0
- 全站测试 9+ passed：`python3 -m pytest tests/ -q --tb=short` → exit 0，`passed` 计数 ≥ 9
- 双爬虫 CLI 可用：`python3 scripts/run_crawler.py --name demo && python3 scripts/run_crawler.py --name sichuan` → exit 0 × 2
- 迁移报告含 B1.1 task id：`grep -q 'cla-b1-1-migrate' docs/migration-B1.md` → exit 0
- .ccc 过程文件就位：`test -f .ccc/plans/cla-b1-1-migrate.plan.md && test -f .ccc/phases/cla-b1-1-migrate.phases.json` → exit 0
- 两笔独立 commit，phase 编号正确：`git log --oneline -2` → 含 `phase 1/2` 和 `phase 2/2`，均含 `cla-b1-1-migrate`

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 四川价爬虫适配修复 + tests + CLI 注册 | `feat(crawler): 四川价爬虫适配 — 迁入完整 BaseCrawler 实现 (phase 1/2, cla-b1-1-migrate)` |
| 2 | 迁移报告 + .ccc 过程文件 | `docs: B1→B1.1 迁移报告 + 硬门验收闭环 (phase 2/2, cla-b1-1-migrate)` |

---

## 全局验收清单

- [ ] SichuanCrawler 可实例化（extract() 已实现）
- [ ] `python3 -m pytest tests/ -q --tb=short` → 全部通过
- [ ] `python3 scripts/run_crawler.py --name demo` → exit 0
- [ ] `python3 scripts/run_crawler.py --name sichuan` → exit 0
- [ ] `docs/migration-B1.md` 存在且含 B1、B1.1 两段迁移记录 + task id
- [ ] `.ccc/plans/cla-b1-1-migrate.plan.md` 已更新
- [ ] `.ccc/phases/cla-b1-1-migrate.phases.json` 已更新（2 phases）
- [ ] Phase 1 commit 限 `src/crawlers/sichuan/`、`tests/test_crawler_sichuan.py`、`scripts/run_crawler.py`
- [ ] Phase 2 commit 限 `docs/migration-B1.md`、`.ccc/plans/`、`.ccc/phases/`
- [ ] diff 范围不越各自白名单

---

## 后续步骤

- **B2 方向**：从 qx 迁入 tfydd 适配器或 dekyy 浏览器自动化爬虫
- **爬虫注册器**：建立 registry 支持按 name 批量调度多个爬虫
- **凭证管理**：建立 `~/.ccc/credentials/` 目录，支持 real 模式的 API 爬虫
- **历史清理**：B1.1 现有两笔重复 commit（`e586399`、`a22a6f2`）可在 Phase 2 后用 `git rebase -i` 合并或标注为 superseded

---

## Phase 完成定义

### Phase 1
1. 修复 SichuanCrawler `extract()` 抽象方法
2. 修复/调整测试使之全部通过
3. 运行全站 9+ 测试全绿
4. 提交一个 commit（message 含 `phase 1/2` + `cla-b1-1-migrate`）
5. 不超出 Phase 1 scope

### Phase 2
1. 创建/覆盖 docs/migration-B1.md（两段迁移审计）
2. 覆盖 .ccc/plans 和 .ccc/phases
3. 运行三硬门验收确认
4. 确保 commit message 含 `phase 2/2`
5. 不超出 Phase 2 scope

## 完成定义（仅 Phase 2）
1. 仅实现 Phase 2 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-b1-1-migrate` 与 `phase=2`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase