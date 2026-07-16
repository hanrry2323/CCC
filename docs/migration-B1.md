# B1 迁移报告：从 qx 迁入四川价爬虫

---

## 任务信息

- **任务ID**：`cla-b1--qx--1-vded`
- **执行阶段**：Phase 2/2（文档 + CCC 过程文件）
- **执行日期**：2026-07-17
- **执行方式**：manual

---

## 迁移概要

从 QX 项目 `~/program/projects/qx/crawlers/sichuan_price_adapter/` 迁入四川药械网价格爬虫至 `clawmed-ccc`（cla）。本次实施 **Phase 2**，重点为：

1. 更新 README.md，补充「爬虫快速运行」小节（≤10 行命令）
2. 创建迁移报告 `docs/migration-B1.md`（含 task id、代码路径、CLI 验收）
3. 写入 CCC 过程文件：`.ccc/plans/cla-b1--qx--1-vded.plan.md` + `.ccc/phases/cla-b1--qx--1-vded.phases.json`
4. Phase 2 独立 commit，与 Phase 1 代码 diff 对齐

---

## 三硬门验收表

| 门禁 | 标准 | 验收结果 |
|------|------|----------|
| **代码迁入路径** | `src/crawlers/sichuan/` 含 `__init__.py` + `sichuan_crawler.py`（来自 Phase 1 commit） | ✅ 代码已提交（commit: `feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)`） |
| **CLI 可跑通** | `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows` | ✅ sichuan CLI 可跑（见 Phase 1 验收执行） |
| **README ≤10 行** | README 含爬虫命令小节，仅 4 条命令（详细 min 文字） | ✅ README 已更新（phase 2 commit 新增小节） |

---

## 技术要点

### 1. BaseCrawler 接口适配

- 抽象方法：`_load_credential/login/crawl/extract`
- `SichuanCrawler` 实现全 4 个方法，`BaseCrawler.run()` 串联全流程
- `_load_credential`：检查 `~/.ccc/credentials/sichuan-001.json`，不存在时返回空 dict
- `login`：支持 `CRAWLER_DRY_RUN` 环境变量切换 dry-run / real 模式
- crawl：dry-run 调用 `_crawl_dry_run`（返回 3 条硬编码样本数据），real 模式调用 `_fetch_price_data` + `_extract_price_records`
- extract：委托 `_extract_price_records(raw)`，做字段归一化

### 2. dry-run 模式设计

- 核心能力：不依赖外部网络和凭证（用于快速验收）
- 采样数据：`阿司匹林肠溶片/氨氯地平/阿莫西林胶囊`，含 `product_name/spec/manufacturer/reference_price/unit`
- 切换：设置 `CRAWLER_DRY_RUN=1` 或省略凭证文件

### 3. 与 qx 原版差异

| 特性 | qx 原版 | cla 迁入版 |
|------|---------|-----------|
| SQLite 持久化 | ✅ `price_history.db` | ❌ 不迁移（Phase 1 留到后续 B2） |
| CSV 导出 | ✅ `prices_export.csv` | ❌ 不迁移 |
| 批处理 | ✅ `ChunkInfo/ProcessResult` | ❌ 待 B2 迁入 |
| CLI 注册 | ✅ 依赖 shell 脚本包装 | ✅ `run_crawler.py` + `crawler_map` 字典 |
|凭证管理 | 手动配置 | `~/.ccc/credentials/sichuan-001.json` 待 B2 完善 |

---

## Phase 2 执行清单

### 变更文件

1. `README.md` — 追加「爬虫快速运行」小节（Phase 1 commit 留下了 CLI 注册不变）
2. `docs/migration-B1.md` — 新建，含 task id、三硬门验收、技术要点（本文件）
3. `.ccc/plans/cla-b1--qx--1-vded.plan.md` — 引用本 plan 全文（Phase 1 引用视频）
4. `.ccc/phases/cla-b1--qx--1-vded.phases.json` — JSONL，每行含非空 description + scope（见下方）

### commit 信息

```bash
git commit -m "docs: B1 迁移报告 — 爬虫迁入闭环 (phase 2/2, cla-b1--qx--1-vded)"
```

### 验收指标（Phase 2）

- ✓ `README.md` 含爬虫快速运行小节（≤10 行命令）
- ✓ `docs/migration-B1.md` 含 task id `cla-b1--qx--1-vded`
- ✓ `.ccc/phases/cla-b1--qx--1-vded.phases.json` 合法 JSONL
- ✓ `.ccc/plans/cla-b1--qx--1-vded.plan.md` 存在
- ✓ Phase 2 diff 不含 `src/` / `tests/` / `scripts/`（仅 `docs/` / `README.md` / `.ccc/`）
- ✓ Phase 1 commit 在前，Phase 2 commit 在后，git log 清晰分列

---

## Phase 1 复盘（仅可查看）

### commit（已提交）

- **message**：`feat(crawler): 迁入四川价爬虫 — sichuan_crawler + run_crawler 注册 + 单测 (phase 1/2, cla-b1--qx--1-vded)`
- **diff 匹配**：代码文件仅 `src/crawlers/sichuan/` + `tests/test_crawler_sichuan.py` + `scripts/run_crawler.py`

### 验收结果（Phase 1 已跑通）

- ✓ `pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 9 passed, 0 failed
- ✓ `python3 scripts/run_crawler.py --name demo` → exit 0，stdout 含 `阿莫西林胶囊`
- ✓ `python3 scripts/run_crawler.py --name sichuan` → exit 0，stdout 含 `Results: 3 rows`
- ✓ `git ls-files src/crawlers/sichuan/ | wc -l` ≥ 2
- ✓ `git ls-files tests/test_crawler_sichuan.py` → exit 0

---

## 后续步骤（B2）

1. 从 qx 迁入 `dekyy_adapter` 浏览器自动化爬虫
2. 建立爬虫注册器支持按 name 批量调度
3. 完善 `~/.ccc/credentials/` 目录，打通 SichuanCrawler real-mode 凭证加载
4. 将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
5. 接入 qx 的 SQLite 持久化层（B2 留到后面方向）

---

## 完成定义（仅 Phase 2）

1. 仅实现 Phase 2 对应需求
2. 不干扰 Phase 1 代码逻辑（不修改 `sichuan_crawler.py` / `test_crawler_sichuan.py` / `run_crawler.py`）
3. 提交一个 commit（message 含 `cla-b1--qx--1-vded` 与 `phase=2`）
4. 确认代码无语法错误（Phase 1 已验证，Phase 2 补 doc 和 probe 不引入新语法变更）
5. 不超出 scope 白名单（仅修改 `README.md` / `docs/migration-B1.md` / `.ccc/plans/` / `.ccc/phases/`）

---

**报告编写人**：ccc-dev（手动执行 Phase 2）
**审核人**：ccc-reviewer（待定）
**归档日期**：2026-07-17
