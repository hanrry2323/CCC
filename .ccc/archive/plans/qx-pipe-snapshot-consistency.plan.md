# Plan: qx-pipe-snapshot-consistency — 快照一致性校验

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

`workers/snapshot_refresh.py` 是独立的 MV 刷新脚本，执行后只记录行数到 `meta.worker_heartbeats`（id/worker_id/status/recorded_at），没有对 MV 数据做任何一致性校验。日志输出仅 `logging.info` 打一行 `"REFRESH ok: %d rows in %d ms"`，无持久化校验记录。

- **入口/核心文件：**
  - `workers/snapshot_refresh.py`（114 行）— 刷新 `data.mv_drug_price_latest` 物化视图。`refresh_mv()` 返回 `{ok, rows, duration_ms}`。`main()` 调 `refresh_mv()` 后只打日志，exit 0/1
  - `alembic/versions/0025_create_mv_drug_price_latest.py` — MV 定义：`SELECT DISTINCT ON (drug_key, source_id) drug_key, source_id, avg_price, snapshot_date FROM data.drug_price_snapshot WHERE snapshot_date >= CURRENT_DATE - INTERVAL '90 days' ORDER BY drug_key, source_id, snapshot_date DESC`
  - `lib/qx_platform/db.py` — 提供 `engine()`, `session_scope()`, `advisory_xact_lock()`, `try_advisory_xact_lock()`
  - `logs/` — 目录已存在，已有 `cron_dispatcher-*.log`，当前无 `snapshot-verify.log`

- **当前结构要点：**
  - `snapshot_refresh.py:56-58` — `try_advisory_xact_lock(LOCK_KEY)` 拿锁，拿不到直接返回 `{ok: false, reason: "advisory_lock_held"}`（非阻塞）
  - `snapshot_refresh.py:67-68` — `REFRESH MATERIALIZED VIEW CONCURRENTLY` 执行后只 count 行数，无 hash/校验
  - `snapshot_refresh.py:80-91` — heartbeat 写 `meta.worker_heartbeats`，schema 只有 `(id, worker_id, status, recorded_at)` — 不含行数/哈希等校验字段
  - MV 列：`drug_key, source_id, avg_price, snapshot_date` — 四个字段，可做 `md5(string_agg(...))` 哈希检验完整性
  - `data.drug_price_snapshot` 源表有 `id, snapshot_date, source_id, drug_key, avg_price, min_price, max_price, sample_count`，可在 MV 外做独立行数校验

- **待改动点：**
  - `workers/snapshot_verify.py` — **新建**。封装行数校验 + MD5 内容哈希，输出结构化结果
  - `workers/snapshot_refresh.py` — REFRESH 成功后调用 verify 函数，结果写入 `logs/snapshot-verify.log`
  - 无需改动 `lib/qx_platform/`、`alembic/`、`alembic/versions/`

---

## 范围

- **目标**：`snapshot_refresh.py` 执行完成后自动校验 MV 行数 + 内容哈希，结果写入 `logs/snapshot-verify.log`
- **只改文件：**
  - `workers/snapshot_verify.py`（新增）
  - `workers/snapshot_refresh.py`
- **不改文件：** `lib/qx_platform/`、`alembic/`、`alembic/versions/`、`scripts/`、`config/`、`infra/`、`dashboard/`
- **执行方式：** `manual`
- **Phase 数：** 2

---

## 改动 1：新增 workers/snapshot_verify.py — MV 一致性校验模块

### 做什么
创建一个可独立调用也可被 import 的校验模块。对 `data.mv_drug_price_latest` 做两重校验：

1. **行数校验**：MV 行数 > 0，且与源表 `data.drug_price_snapshot` 90 天窗口内 distinct (drug_key, source_id) 配对数的差值在阈值内（默认允许 5% 偏差，硬下限 0 行）
2. **内容哈希**：`SELECT md5(string_agg(mv_row_hash, ',' ORDER BY drug_key, source_id))` 计算全量 MV 内容的确定性 MD5 哈希，支持与前次结果比对判断数据是否发生变化

输出为 `LogRecord` 对象（Python dict/list 序列化 + 可读文本），同时具备：
- Python import 用法：`from workers.snapshot_verify import verify_snapshot; result = verify_snapshot()`
- CLI 用法：`python workers/snapshot_verify.py [-o logs/snapshot-verify.log]`
- 结果结构：`{"ok": bool, "mv_rows": int, "source_pairs": int, "row_delta": int, "row_delta_pct": float, "row_match": bool, "mv_hash": str, "hash": str, "prev_hash": str|None, "hash_changed": bool|None, "duration_ms": int, "errors": [str]}`

### 怎么做
1. **新建 `workers/snapshot_verify.py`**，遵循 `snapshot_refresh.py` 的同目录约定（`ROOT` = `os.path.dirname(__file__)/..`, `sys.path` insert ROOT 和 `lib/`）：
   ```python
   """snapshot_verify.py — MV 行数 + 内容哈希校验
    
   与 snapshot_refresh.py 配对使用：
      python workers/snapshot_refresh.py && python workers/snapshot_verify.py -o logs/snapshot-verify.log
   也可被 import 集成：
      from workers.snapshot_verify import verify_snapshot
      result = verify_snapshot()
      result['ok']  # True/False
   """
   ```

2. **核心函数 `verify_snapshot()`**：
   - 参数：`(dry_run=False, sample_pct=None)`（sample_pct 保留扩展，暂不用）
   - 用 `engine()` connect，SQLAlchemy raw SQL
   - 步骤：
     a. `SELECT count(*) FROM data.mv_drug_price_latest` → `mv_rows`
     b. `SELECT count(DISTINCT (drug_key, source_id)) FROM data.drug_price_snapshot WHERE snapshot_date >= CURRENT_DATE - INTERVAL '90 days'` → `source_pairs`
     c. 计算 `row_delta = abs(mv_rows - source_pairs)`，`row_delta_pct = row_delta / max(source_pairs, 1) * 100`
     d. `row_match = row_delta_pct <= 5.0`（允许 5% 偏差——MV 去重后行数 <= 源表 distinct 对，因为 DISTINCT ON 只取每个 pair 最新行）
     e. 内容哈希：`SELECT md5(string_agg(COALESCE(drug_key,'')||'|'||COALESCE(source_id,'')||'|'||COALESCE(avg_price::text,'')||'|'||snapshot_date::text, ',' ORDER BY drug_key, source_id)) FROM data.mv_drug_price_latest` → `mv_hash`
     f. 读前次哈希（`persistent_state` 文件 `logs/.snapshot-last-hash` — 纯文本存最后一次成功校验的 hash）
     g. `hash_changed = prev_hash is not None and mv_hash != prev_hash`（哈希变了说明 MV 内容有更新）

3. **主函数 `main()`**：
   - `-o`/`--output FILE` — 指定输出文件（默认 `logs/snapshot-verify.log`）
   - `--dry` — 不连 PG，输出假数据（用于测试 CLI 逻辑）
   - 输出格式：
     - **追加一行到 output file**（如 `logs/snapshot-verify.log`），格式为 `YYYY-MM-DD HH:MM:SS,+08:00 [VERIFY] {json}` — 每校验一行 JSON，便于程序解析
     - **同时打 stdout** `logging.info("verify: %s", json.dumps(result))` 方便控制台观察

4. **状态文件**：校验成功后写入 `logs/.snapshot-last-hash`（纯文本，只存 `mv_hash` 值）。下次校验时读入作为 `prev_hash`。

5. **退出码**：全部通过 0；row_match 失败 1；PG 连接失败 2

### 验收清单

- [ ] `python workers/snapshot_verify.py -o logs/snapshot-verify.log` 正常执行
- [ ] 输出文件 `logs/snapshot-verify.log` 创建成功，每行含 JSON 负载
- [ ] `mv_rows > 0`（生产环境有数据时）
- [ ] `row_match` 校验通过（允许 5% 偏差）
- [ ] `mv_hash` 是非空 32 位 MD5 字符串
- [ ] `prev_hash` 在第二次运行时非 None（`.snapshot-last-hash` 已写入）
- [ ] `hash_changed` 在数据有变化时输出 True/False
- [ ] `from workers.snapshot_verify import verify_snapshot` 可 import，返回结构化 dict
- [ ] exit code 0 正常，PG 不可达时 exit code 2

### 验收
- [日志文件]（参考：`python workers/snapshot_verify.py -o logs/snapshot-verify.log; cat logs/snapshot-verify.log`）
- [import 可用]（参考：`python3 -c "from workers.snapshot_verify import verify_snapshot; r = verify_snapshot(); print(r['ok'], r['mv_rows'], r['mv_hash'][:8])"`）
- [状态持久化]（参考：`cat logs/.snapshot-last-hash` 应与上次校验的 mv_hash 一致）

---

## 改动 2：集成到 snapshot_refresh.py — REFRESH 后自动校验

### 做什么
`snapshot_refresh.py` REFRESH MV 成功后，不再止步于打一行 log + 写 heartbeat，而是自动调 `verify_snapshot()` 做行数 + 内容校验，结果写入 `logs/snapshot-verify.log`。校验失败时：
- 写 error log
- 不影响 exit code（REFRESH 本身成功了，校验是辅助信息，不阻断主流程）

### 怎么做
1. **`workers/snapshot_refresh.py`** 第 37 行 import 区域新增：
   ```python
   from workers.snapshot_verify import verify_snapshot
   ```

2. **第 93 行 `log.info("REFRESH ok: %d rows in %d ms", rows, duration_ms)` 之后**，在 `refresh_mv()` 函数返回前新增：
   ```python
   if result.get("ok") and not result.get("dry"):
       try:
           verify = verify_snapshot()
           verify_log = os.path.join(ROOT, "logs", "snapshot-verify.log")
           os.makedirs(os.path.dirname(verify_log), exist_ok=True)
           with open(verify_log, "a") as f:
               f.write(f"{__import__('datetime').datetime.now().isoformat()} [VERIFY] {json.dumps(verify, ensure_ascii=False)}\n")
           if not verify.get("ok"):
               log.warning("snapshot_verify: row_match=%s hash_changed=%s delta=%d",
                   verify.get("row_match"), verify.get("hash_changed"), verify.get("row_delta", -1))
           else:
               log.info("snapshot_verify: ok rows=%d hash=%s", verify["mv_rows"], verify["mv_hash"][:12])
       except Exception as e:
           log.warning("snapshot_verify failed (non-fatal): %s", e)
   ```

3. **当前 `return {"ok": True, "rows": rows, "duration_ms": duration_ms}`**（第 93 行）保持不变 — verify 结果不进 refresh_mv 返回值，只在日志和文件中记录。

4. **`main()` 中也保持不动** — verify 作为 refresh_mv 内部副作用，main 不需要知道。

5. **第 97 行附近 `parser.add_argument`** 新增 `--verify` flag（默认 True）：`--no-verify` 跳过校验。`refresh_mv()` 新增 `verify=True` 参数。这是兜底开关，以免校验本身出现问题阻塞排查时无法跳过。

### 验收清单

- [ ] REFRESH 成功后 `logs/snapshot-verify.log` 自动追加校验记录
- [ ] REFRESH 失败时（`ok=False`）不触发校验
- [ ] `--dry` 模式下不触发校验
- [ ] `--no-verify` 跳过校验
- [ ] 校验失败（如 row_match=False）不影响 exit code（REFRESH 成功 = exit 0）
- [ ] 校验模块 import 错误时优雅降级（log warning），不阻断 REFRESH 主流程
- [ ] `snapshot-verify.log` 每行是合法 JSON
- [ ] `.snapshot-last-hash` 在每次校验成功后更新

### 验收
- [自动追加]（参考：`python workers/snapshot_refresh.py; cat logs/snapshot-verify.log | tail -3`）
- [dry 跳过]（参考：`python workers/snapshot_refresh.py --dry; cat logs/snapshot-verify.log | tail -1` → 不应新增行）
- [no-verify 跳过]（参考：`python workers/snapshot_refresh.py --no-verify; cat logs/snapshot-verify.log | tail -1` → 不应新增行）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新增 workers/snapshot_verify.py — MV 行数 + MD5 哈希校验，输出到 logs/snapshot-verify.log | `feat(snapshot): add snapshot_verify.py — row count and MD5 hash consistency check for mv_drug_price_latest (phase 1/2)` |
| 2 | snapshot_refresh.py REFRESH 成功后自动调用 verify_snapshot()，结果追加写入 logs/snapshot-verify.log，新增 --no-verify 开关 | `feat(snapshot): integrate automatic verification into snapshot_refresh.py after each REFRESH (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查零错误（`python3 -m compileall -q workers/snapshot_verify.py workers/snapshot_refresh.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/ -q --ignore=tests/e2e`）
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 稳定运行后可将 `snapshot-verify.log` 接入 Dashboard `/api/health/*` 端点，暴露最近一次校验状态
2. 可在 `meta.worker_heartbeats` 增加 `rows`、`mv_hash` 等字段，替代 `logs/.snapshot-last-hash` 状态文件，实现更可靠的状态追踪
3. 考虑在 PM2 `ecosystem.config.cjs` 为 `qx-snapshot-refresh` 加 `--no-verify` 选项以跳过校验阶段（性能敏感场景）
