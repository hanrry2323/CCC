# Plan: qx-pipe-data-quality-gate — 数据质量门禁（PG 写入前校验 + quarantine）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

项目已有成熟的质量门基础设施（RuleEngine + persist 层 quality_engine 参数），但未接入实际 pipeline，也缺少 quarantine 落表能力。

- **入口/核心文件：**
  - `crawlers/_sdk/persist_pg_v2.py:107` — `write_records_batch()` PG 批量写入，已支持 `quality_engine` 和 `on_quality_fail`（skip/log/raise）
  - `crawlers/_sdk/persist_pg_v2.py:245` — `write_records_stream()` 流式写入，同样支持 quality_engine
  - `crawlers/_sdk/persist.py:57` — SQLite 写入（`write_records()`），同样有 quality_engine 参数
  - `lib/qx_platform/quality.py` — RuleEngine 引擎，6 条内置规则（PricePositive、CodeNonEmpty、NameLength、ApprovalNoFormat、FetchedAtFresh、RawDataJSON）
  - `scripts/data_quality.py` — 旧 SQLite 离线质量审计脚本（读 SQLite 文件跑规则），**不参与 PG pipeline**
  - config/credentials 下有 crawler 凭证

- **当前结构要点：**
  - persist_pg_v2 的 `_INSERT_SQL_TEMPLATE` 硬编码了 `data.products` 表 16 列和 ON CONFLICT 逻辑（`source_id, external_id, fetched_at` 主键）
  - `_normalize_record()` 提取 `code/external_id` 等字段，缺失时返回 None（skip 不写）
  - `_gen_rows()` 在 `quality_engine` 非 None 时过质量门，失败时按 `on_quality_fail` 策略处理
  - 三份 persist 文件（persist.py SQLite / persist_pg.py v1 PG / persist_pg_v2.py v2 PG）独立维护，没有共享 quarantine 逻辑

- **待改动点：**
  - `persist_pg_v2.py` — 新增 `"quarantine"` 策略支持 + 写入 quarantine 表
  - `persist.py` — 同步新增 `"quarantine"` 策略（SQLite 版本）
  - `lib/qx_platform/quality.py` — 可选：增加 `to_quarantine_record()` 方法让 RuleResult 直接序列化为 quarantine 字段
  - 需要 quarantine 表 DDL（PG `data.product_quarantine` + SQLite `_quarantine` 后缀表）

---

## 范围

- **目标**：在爬虫写入 PG/SQLite 前过质量门，失败数据不进入主表而写入 quarantine 隔离表
- **只改文件：**
  - `crawlers/_sdk/persist_pg_v2.py`
  - `crawlers/_sdk/persist.py`
  - `lib/qx_platform/quality.py`（可选增强）
  - `scripts/data_quality.py`（可选，新增 gate 注册入口）
- **不改文件：** `crawlers/_sdk/persist_pg.py`（v1.0 只读）、`dashboard/`、`workers/`、`infra/`、`config/credentials/`
- **执行方式：** `manual`
- **Phase 数：** 2

---

## 改动 1：persist_pg_v2.py + persist.py 新增 `"quarantine"` 策略 + 写入 quarantine 表

### 做什么
`persist_pg_v2.py` 已有 `on_quality_fail="skip"|"log"|"raise"`，缺一个真正**留存坏数据**的选项。新增 `"quarantine"` 策略：质量门未通过的 record 不进入主表 `data.products`，而是写入 `data.product_quarantine`（PG）/ `products_quarantine`（SQLite）隔离表，带上校验失败的原因、原始数据、抓取上下文。

同时 `persist.py`（SQLite 版本）同步新增相同策略，保证一致性。

### 怎么做
1. **`persist_pg_v2.py`:**
   - 第 143 行 `if on_quality_fail not in ("skip", "log", "raise"):` → 改为 `("skip", "log", "raise", "quarantine")`
   - 在 `_gen_rows()` 内部（第 160-173 行），`elif on_quality_fail == "quarantine"` 分支：
     - 不 `continue`，而是在函数外积累 `quarantine_batch: list[tuple]`
     - 每个 quarantine 记录包含：`source_id, external_id, fetched_at, fetch_run_id, code, name, approval_no, price, raw_data, failed_rules (JSON), failed_at, quarantined_by`
   - 新增内部函数 `_ensure_quarantine_table(s)` — 执行 `CREATE TABLE IF NOT EXISTS data.product_quarantine (...)`
   - 新增内部函数 `_flush_quarantine(s, batch)` — 执行 `execute_values` 写入 quarantine
   - 在主 upsert 事务结束后（同一 session），flush quarantine 记录
   - 返回值新增 `"quarantined": int` 字段

2. **`persist.py`:**
   - 第 81 行 `on_quality_fail 校验` → 加 `"quarantine"`
   - 第 92-101 行质量门失败处理 → 新增 `elif on_quality_fail == "quarantine"` 分支
   - 在当前 SQLite DB 创建 `{table}_quarantine` 表（CREATE TABLE IF NOT EXISTS）
   - 写入失败记录 + 失败原因
   - 返回值新增 `quarantined` 计数

3. **`lib/qx_platform/quality.py`:**
   - `RuleResult` 增加 `to_quarantine_json()` 方法，序列化 rule_id/rule_name/severity/field/error_msg 为 JSON 片段

### 验收清单

- [ ] `on_quality_fail="quarantine"` 时，质量门失败的 record 写入 quarantine 表而非主表
- [ ] quarantine 表包含：原始字段 + `failed_rules (JSON)` + `quarantined_at` + `quarantined_by`
- [ ] `on_quality_fail="skip"` 行为不受影响
- [ ] `on_quality_fail="raise"` 行为不受影响
- [ ] `on_quality_fail="quarantine"` 时返回值 `quarantined > 0`
- [ ] quarantine 表自动创建（无需手动跑 migration）
- [ ] SQLite `persist.py` 同步支持 quarantine（内联 `CREATE TABLE IF NOT EXISTS`）

### 验收
- [正常写入不受影响]（参考：`python3 -c "from crawlers._sdk.persist_pg_v2 import write_records_batch; print('OK')"`）
- [quarantine 表可创建]（参考：`python3 -c "
  from crawlers._sdk.persist_pg_v2 import _ensure_quarantine_table, _QUARANTINE_DDL
  print(_QUARANTINE_DDL)
"`）
- [mock 坏数据入 quarantine] 实现后验证（参考：提供 mock record 调用 write_records_batch(records=[{"price": 0, "code": ""...}], quality_engine=RuleEngine(), on_quality_fail="quarantine")）

---

## 改动 2：新增 `scripts/data_quality_gate.py` 作为 pipeline 入口，集成 quality gate

### 做什么
提供一键式脚本 `scripts/data_quality_gate.py`，可被 cron_dispatcher / wrapper 调用，接收 records + source_id，过 RuleEngine 质量门，质量合格数据写入主表、不合格数据入 quarantine。

同时将当前空转的 quality_engine 参数实际接通到管道：让 caller 显式传 `quality_engine=RuleEngine()` 即可启用门禁。

### 怎么做
1. 新增 `scripts/data_quality_gate.py`：
   - CLI：`python3 scripts/data_quality_gate.py --source ds-sichuan --records-file /tmp/batch.json --on-fail quarantine`
   - 内部：`json.load` 读取 records → `RuleEngine().run(records)` → 过滤 + `write_records_batch(quality_engine=None, on_quality_fail="skip")` 写合格数据 → 不合格的 write_records_batch(on_quality_fail="quarantine")
   - 输出 JSON：`{total, written, quarantined, errors, duration_sec}`

2. 修改 `persist_pg_v2.py` 的 `_gen_rows()` 返回结构增加 `quarantined` 计数（改动 1 已包含）

### 验收清单

- [ ] `scripts/data_quality_gate.py --help` 正常输出参数信息
- [ ] 传入 mock 记录，质量门通过的写入主表
- [ ] 传入不合格数据（price=0），进入 quarantine 表
- [ ] 返回值 JSON 字段正确
- [ ] 与现有 `write_records_batch` 调用不冲突（quality_engine=None 时原有逻辑不变）

### 验收
- [--help 正常]（参考：`python3 scripts/data_quality_gate.py --help`）
- [mock 测试]（参考：`python3 scripts/data_quality_gate.py ...` 返回含 written/quarantined 的 JSON）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | persist_pg_v2.py + persist.py + quality.py 新增 quarantine 策略 | `feat(quality): add quarantine strategy to persist SDK — failed records go to data.product_quarantine (phase 1/2)` |
| 2 | 新增 data_quality_gate.py pipeline 入口 | `feat(quality): add scripts/data_quality_gate.py as pipeline entry point for quality gate + quarantine (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查零错误（`python3 -m compileall -q crawlers/_sdk/ lib/qx_platform/`）
- [ ] 全部测试通过（`python3 -m pytest tests/ -q --ignore=tests/e2e`）
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成
