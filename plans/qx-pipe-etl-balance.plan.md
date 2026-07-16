# Plan: qx-pipe-etl-balance — ETL 余额对账增强（WeCom 告警 + pipeline 自动接入）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

已有 `scripts/verify_etl_balance.py`（256 行，ops-006 Phase 1 产出），支持 3 个 source 的行数 + 随机 hash 校验。但同时存在 3 个缺口：**无 WeCom 告警**（仅 POST 到未实际部署的 `/api/alerts`）、**无历史日志**、**未接入 ETL pipeline**（须手动执行）。

- **入口/核心文件：**
  - `scripts/verify_etl_balance.py` — 对账主逻辑，已有 `verify_source()` / `run_etl_balance()` / `_send_alert()`
  - `scripts/cron_dispatcher.py:496-507` — 爬虫步骤完成后的 post-crawl hook 调用点，紧邻计划新增的 balance hook
  - `dashboard/server/wecom/alert.js` — WeCom 告警 CLI（`node alert.js <workflow_id> <error_msg> [run_id]`，3 次重试 + fallback 落盘）
  - `scripts/pipeline_hooks.py` — 负责 drug matching 后置钩子，已有 `run_post_crawl_hook()`；新增的 balance 钩子放在此处或 cron_dispatcher 中

- **当前结构要点：**
  - `verify_etl_balance.py` 的 `verify_source()` 返回结构化 dict，`run_etl_balance()` 是 import 入口但仅包裹 `verify_source`（单 source）
  - `_send_alert()` 只 POST 到 `http://127.0.0.1:8080/api/alerts`，无 WeCom 通道；函数签名 `failures: list[dict]` 传给 body 但实际调用方为 `main()` 里的 `--alert` 模式
  - 爬虫完成后 `cron_dispatcher.py` 依次执行：step → hook（drug matching）→ log → 失败时 WeCom 告警
  - 无 `logs/etl-balance/` 目录或持久化接口

- **待改动点：**
  - `scripts/verify_etl_balance.py` — 加 WeCom 告警通道 + 持久日志 + `run_etl_balance()` 增强为多源聚合
  - `scripts/pipeline_hooks.py` — 新增 `run_balance_hook()` 函数，复用 `_SOURCE_CONFIGS` 的 source 映射
  - `scripts/cron_dispatcher.py:496-507` — 在 drug matching hook 之后接入 balance hook

---

## 范围

- **目标**：每次 ETL 跑完自动进行 SQLite ↔ PG 余额校验，发现不一致时触达 WeCom 告警，并有持久化日志追溯
- **只改文件：**
  - `scripts/verify_etl_balance.py`
  - `scripts/pipeline_hooks.py`
  - `scripts/cron_dispatcher.py`
- **不改文件：** `v1.0` 只读目录（`crawlers/` 下适配器源码不动）、`config/` 下凭证、`dashboard/` 源码、`lib/` 核心库、`tests/` 现有测试
- **执行方式：** `manual`
- **Phase 数：** 2

---

## 改动 1：增强 verify_etl_balance.py — WeCom 告警 + 持久日志 + 多源聚合

### 做什么
`verify_etl_balance.py` 当前支持 3 个 source 的行数 + 哈希对账，但告警只发到未兜底的 HTTP API，也没有留存审计日志。改造后：

1. **WeCom 告警** — 当 `--alert` 模式下发现不一致时，除了原有的 HTTP POST，额外调用 `node dashboard/server/wecom/alert.js` 发送企微消息，与 `cron_dispatcher.py` 现用的告警通道统一
2. **持久 JSONL 日志** — 每次运行结果追加到 `logs/etl-balance/YYYY-MM-DD.jsonl`，每行一个 source 对账结果，含完整字段和 timestamp
3. **`run_etl_balance()` 增强** — 现为单 source 包裹函数，改为支持多 source 聚合返回，让外部调用一次拿到所有 source 结果
4. **CLI 增强** — `--log-dir` 选项指定日志目录，`--wecom-workflow` 指定 WeCom 告警中显示的 workflow 名（便于区分是哪个 ETL 触发的）

### 怎么做
1. **`verify_etl_balance.py`:**
   - 新增导入 `import subprocess` / `import shlex`
   - `_WECOM_ALERT_JS` 常量：`_PROJECT_ROOT / "dashboard" / "server" / "wecom" / "alert.js"`
   - 新增 `_send_wecom_alert(workflow_id: str, error_msg: str, run_id: str = "")`：
     - 检查 `_WECOM_ALERT_JS` 存在
     - `subprocess.run(["node", str(_WECOM_ALERT_JS), workflow_id, error_msg, run_id])`
     - 失败时写入 `logs/wecom_alert_fallback.log`（现有 alert.js 的 fallback 逻辑补充）
   - 新增 `_append_balance_log(results: list[dict], log_dir: str)`：
     - 确保 `log_dir/` 存在
     - 每行 JSON：`{timestamp, source, ok, sqlite_count, pg_count, delta, hash_sq, hash_pg, row_hash_ok, evidence}`
     - 文件名 `{log_dir}/YYYY-MM-DD.jsonl`，append 模式
   - 修改 `run_etl_balance()` 签名：`def run_etl_balance(sources: list[str], sample_size: int = 10, alert: bool = False, log_dir: str = "") -> dict`
     - 接受 source 列表，遍历调 `verify_source()`
     - 如果 `alert=True`，对失败 source 调 WeCom 告警（走 `_send_wecom_alert`）
     - 如果 `log_dir` 非空，调 `_append_balance_log()`
     - 返回聚合结果：`{all_ok, sources: [...], summary: {total, failed}, timestamp, duration_ms}`
   - 修改 `main()` CLI：
     - 新增 `--log-dir` 默认值 `"logs/etl-balance/"`
     - 新增 `--wecom-workflow` 指定 workflow 名
     - `--alert` 模式下走增强后的 `_send_wecom_alert()`
     - 保留原 `--json` 输出

2. **不修改** 现有函数签名兼容性，`run_etl_balance(source_id: str, sample_size: int = 10)` 的单 source 签名保留为向后兼容 wrapper，内部转发到新签名。

### 验收清单

- [ ] `--alert` 模式下发现不一致时，WeCom 消息送达（参考：手动断开 PG 模拟 mismatch）
- [ ] `logs/etl-balance/YYYY-MM-DD.jsonl` 文件生成，格式正确 JSONL
- [ ] `run_etl_balance()` 返回聚合 dict 含 `all_ok` / `sources[]`
- [ ] 旧单 source 签名兼容，不破坏已有调用方
- [ ] `--log-dir` 指定目录不存在时自动创建
- [ ] WeCom 告警 CLI 调用失败时不影响主流程（不抛异常）

### 验收
- [JSONL 日志]（参考：`python3 scripts/verify_etl_balance.py --source all --log-dir /tmp/etl-test && cat /tmp/etl-test/$(date +%Y-%m-%d).jsonl`）
- [告警不退化]（参考：`python3 scripts/verify_etl_balance.py --source sichuan --alert` 正常输出）

---

## 改动 2：接入 pipeline — cron_dispatcher.py 后置钩子

### 做什么
在 `cron_dispatcher.py` 的爬虫步骤完成之后、dashboard 日志投递之前，自动触发 balance 校验。成果：每次 ETL 跑完无需人工介入，自动知晓 SQLite ↔ PG 是否对齐。

具体调用点：`cron_dispatcher.py:496-507`（drug matching hook 之后）。对每个成功的爬虫 worker 步骤，按 source 映射执行 ETL balance。

### 怎么做
1. **`scripts/pipeline_hooks.py`** — 新增 `run_balance_hook(worker_id: str) -> dict`：
   - 复用 `_map_worker_to_source(worker_id)`（已有，将 `worker-sichuan` → `sichuan`）
   - 映射 source 到 `ds-{source}` 格式
   - 调 `verify_etl_balance.run_etl_balance(sources=[f"ds-{source}"], sample_size=10, log_dir="logs/etl-balance/")`
   - 返回 `{"source": source, "all_ok": bool, "delta": int, "evidence": str, "log_file": str}`

2. **`scripts/cron_dispatcher.py`** — 在 drug matching hook 之后（line ~504-507），新增 balance hook：
   ```python
   # v2.2: ETL balance hook
   try:
       from scripts.pipeline_hooks import run_balance_hook
       balance_result = run_balance_hook(result["worker_id"])
       _log_line(step_log, logging.INFO,
                 f"hook_etl_balance worker={result['worker_id']} "
                 f"source={balance_result.get('source')} "
                 f"ok={balance_result.get('all_ok')} "
                 f"delta={balance_result.get('delta')}")
       if not balance_result.get("all_ok"):
           # WeCom alert already sent by run_balance_hook if mismatch
           _log_line(step_log, logging.WARNING,
                     f"hook_etl_balance_mismatch worker={result['worker_id']} "
                     f"evidence={balance_result.get('evidence')}")
   except Exception as e:
       _log_line(step_log, logging.WARNING,
                 f"hook_etl_balance_error worker={result['worker_id']} err={e}")
   ```

3. **日志兼容** — `cron_dispatcher.py` 已有 `_log_line()` 和 logger，balance hook 的日志复用同一基础设施。

### 验收清单

- [ ] 爬虫 worker 成功后自动触发 balance 校验
- [ ] 校验结果写入 `logs/etl-balance/` 日志文件
- [ ] 校验不一致时打印 WARNING 日志到 `cron_dispatcher` 日志
- [ ] balance 校验失败（如 PG 不可用）不阻止 workflow 继续执行（catch Exception）
- [ ] 非爬虫 worker（如 nmpa-scanner）不触发 balance hook
- [ ] `run_balance_hook` import 失败时静默绕过（防御式 import）

### 验收
- [自动触发]（参考：运行 workflow 后确认 `logs/etl-balance/` 有日志行）
- [异常不阻塞]（参考：手动断 PG 后跑 workflow，workflow 主线正常完成 + 有 WARNING 日志）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | verify_etl_balance.py 增强：WeCom 告警 + 持久 JSONL 日志 + run_etl_balance 多源聚合 | `feat(etl): enhance verify_etl_balance.py with WeCom alert, persistent JSONL logging, multi-source aggregation (phase 1/2)` |
| 2 | pipeline_hooks.py + cron_dispatcher.py 接入自动 ETL balance 后置钩子 | `feat(etl): integrate auto ETL balance hook after worker steps in cron_dispatcher (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查零错误（`python3 -m compileall -q scripts/`）
- [ ] 全部测试通过（`python3 -m pytest tests/ -q --ignore=tests/e2e`）
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 交付后运行一次全部 source 的 balance 校验，确认 baseline
2. 观察下 1-2 个 ETL 周期确认告警通路正常
