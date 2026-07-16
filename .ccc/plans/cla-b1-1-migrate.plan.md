# Plan: cla:B1.1 — 真正迁入爬虫骨架（B1 空发布回炉）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

HEAD `5663a2b` 已包含 SichuanCrawler 全套可运行骨架和测试，代码本身已不阻塞 B1.1。但配套文件（README 运行指引、migration 报告）未提交，CCC 过程文件（plan.md + phases.json）内容指向旧 HEAD `cfcd0c4` 且 phases 格式缺 `timeout/commit/notes` 字段。当前盘查要点：

- **入口/核心文件**：
  - `src/crawlers/sichuan/sichuan_crawler.py` — **committed**（HEAD `5663a2b`），SichuanCrawler 实现，含 dry-run/real 模式、凭证加载、字段映射
  - `src/crawlers/sichuan/__init__.py` — **committed**，包声明
  - `tests/test_crawler_sichuan.py` — **committed**，5 条单测
  - `scripts/run_crawler.py` — **committed**，已注册 `"sichuan": SichuanCrawler`
  - `README.md` — **modified（uncommitted）**，已写入「爬虫快速运行」4 条命令
  - `docs/migration-B1.md` — **modified（uncommitted）**，已写入完整迁移报告（三硬门验收表、与 qx 差异表、完成定义）
  - `.ccc/plans/cla-b1-1-migrate.plan.md` — **committed，内容已过时**（引用不存在的 `cfcd0c4`）
  - `.ccc/phases/cla-b1-1-migrate.phases.json` — **committed，缺 timeout/commit/notes 字段**

- **当前结构要点**：
  1. SichuanCrawler 实现 4 个抽象方法 + `run()` 全管线串联，10 条测试全绿
  2. CLI 双注册（`demo` + `sichuan`），`python3 scripts/run_crawler.py --name sichuan` exit 0
  3. 代码已在 HEAD 中，缺少的是文档提交和过程文件合规化
  4. 旧 phases.json 含 2 个 phase（Phase 1 错标 completed 但 scope 文件从未被该 phase commit）

- **待改动点**：
  - `README.md` — stage + commit 已写的爬虫运行命令段落
  - `docs/migration-B1.md` — stage + commit 已写的迁移报告
  - `.ccc/plans/cla-b1-1-migrate.plan.md` — 覆写为本 plan 正文
  - `.ccc/phases/cla-b1-1-migrate.phases.json` — 覆写为 1-phase 规范 JSONL（含 timeout/commit/notes）

---

## 范围

- **目标**：为 B1.1 收尾——commit 剩余文档、重写 CCC 过程文件为 SPEC 合规格式、全量验证三硬门
- **只改文件**：
  ```
  README.md
  docs/migration-B1.md
  .ccc/plans/cla-b1-1-migrate.plan.md
  .ccc/phases/cla-b1-1-migrate.phases.json
  ```
- **不改文件**：`src/`、`tests/`、`scripts/`、`VERSION`、`CLAUDE.md`、`SKILL.md`、`reports/`、`docs/OBS1.md`、`.ccc/board/`、`.ccc/ops/`
- **执行方式**：`manual`
- **Phase 数**：1

---

## Phase 1：文档提交 + CCC 过程文件 SPEC 合规化

### 改动内容

1. Stage `README.md` 和 `docs/migration-B1.md`（已完成的文档写作）
2. 覆写 `.ccc/plans/cla-b1-1-migrate.plan.md` 为本 plan 正文
3. 覆写 `.ccc/phases/cla-b1-1-migrate.phases.json` 为 conform JSONL（1 行，含 timeout/commit/notes）
4. 生成并 stage 与 commit

### 验收清单

- [ ] 4 文件已 stage
- [ ] commit message 含 `phase 1/1` + `cla-b1-1-migrate`
- [ ] final HEAD 含 SichuanCrawler + README + migration 报告 +合规过程文件
- [ ] phases JSONL 合法
- [ ] diff 仅白名单 4 文件

### 验收命令

- `python3 -m py_compile scripts/run_crawler.py`
- `python3 -m pytest tests/test_crawler_demo.py tests/test_crawler_sichuan.py -q --tb=short` → 10 passed
- `python3 scripts/run_crawler.py` → exit 0
- `python3 scripts/run_crawler.py --name sichuan` → exit 0
- `git ls-files src/crawlers/ | wc -l` ≥ 6
- `grep -q '爬虫快速运行' README.md`
- `grep 'cla-b1-1-migrate' docs/migration-B1.md`
- `.ccc/phases/cla-b1-1-migrate.phases.json` 合法 JSONL
- `git log -1 | grep "phase 1/1"`

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | README + migration 报告 + CCC 过程文件 | `docs: B1.1 正式闭环 — README 爬虫命令 + migration 报告 + CCC 过程文件 (phase 1/1, cla-b1-1-migrate)` |

---

## 全局验收（可选，作为氛围校验）

- 编译检查：`python3 -m py_compile scripts/run_crawler.py` → exit 0
- 测试全绿：10 passed
- CLI demo 可跑
- phases JSONL 合法
- commit 含 cla-b1-1-migrate

---

## 后续步骤

- B2：从 qx 迁入 dekyy 浏览器自动化爬虫或 tfydd 适配器
- 凭证管理：打通 real-mode 依赖的 `~/.ccc/credentials/`
- OBS 自检集成：将爬虫烟雾测纳入 `scripts/ccc-self-check.sh`
- 看板刷新：完成一张 verified/released 卡片

---

## PHASES（JSONL）

{"phase": 1, "status": "completed", "description": "文档提交 + CCC 过程文件 SPEC 合规化", "scope": ["README.md", "docs/migration-B1.md", ".ccc/plans/cla-b1-1-migrate.plan.md", ".ccc/phases/cla-b1-1-migrate.phases.json"], "subtasks": ["README 爬虫运行指引提交", "migration-B1 报告提交", "CCC 过程文件 SPEC 合规化", "JSONL 验证", "commit"], "timeout": 600, "commit": true, "notes": "SichuanCrawler 代码已在 HEAD；仅提交文档与过程文件完成闭环。"}
