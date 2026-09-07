# P1 加固批完成报告 · v2.0 审计链与 infra 自检

> 日期：2026-09-08（指令日期：2026-09-07）· 指令：`/Users/fan/.ccc/instructions/2026-09-07-p1-hardening.md`
> 目标仓：`/Users/fan/program/CCC`

## 结论

5 项 P1 缺陷已修复，逐项提交并推送到 `origin/main`。全量测试与静态检查通过。

## 修复清单

1. **`scripts/cc-auditor.sh` 预清旧 verdict**
   - Claude 审计循环启动前清除 `${WORK_ID}-audit-verdict.json/.md`。
   - 清理失败不阻断，防止上一轮 PASS/REJECT 被本轮复用。

2. **`cc-auditor.sh` 协议兜底分类**
   - LLM 未产出合法 JSON 的兜底 JSON reason 为：
     `protocol：JSON verdict 缺失或非法（claude 未产出合法 verdict）`。
   - 维护区/测试真实性门禁仍写合法的非 protocol REJECT，保持业务打回语义。
   - `audit_verdict.py` / `_read_audit_verdict` 的 `protocol：` 前缀判定保持有效。

3. **`phase2.audit_card` 最终 ERROR 分类**
   - 记录最后一轮 rc 与 protocol 状态。
   - 只有最后一轮确属 verdict 协议非法且不是 CLI/超时类 rc 才标记 `protocol=True`。
   - rc 124/126/127 归 `infra`，进入冷却与自检路径，不消耗 protocol 预算。

4. **合法 REJECT 的 rc=0 兼容**
   - 合法、非 protocol 的 REJECT verdict 在 rc=0 或 rc=2 时均直接返回 REJECT 打回。
   - 仅 protocol 或无合法 verdict 继续走协议/infra 重试路径。

5. **`failure_class.run_infra_selfcheck` 异常安全**
   - `log_dir` 与 `writable` 提前初始化。
   - `_audit_log_dir` 或 mkdir 异常时返回 `verdict_dir_writable.writable=False`，不再抛 `UnboundLocalError`。

## 定向验证

- rc=127 auditor → `infra=True`, `protocol=False`：通过。
- rc=0 + 非法 verdict → `protocol=True`：通过。
- rc=0 + 合法 REJECT → 一次返回 REJECT，不重试：通过。
- `_audit_log_dir` 抛异常 → `path=""`, `writable=False`, `all_ok=False`：通过。

## 全量验证

| 检查 | 结果 |
|---|---|
| `.venv-hub/bin/pytest server/tests/` | **1477 passed, 1 skipped** |
| `.venv-hub/bin/ruff check server/` | **All checks passed** |
| `bash -n scripts/cc-auditor.sh` | **通过** |
| 旧语义 grep 复核 | **无残留匹配** |
| 工作树 | **clean** |

## 提交清单

```text
8085319fa fix(auditor): clear stale verdict artifacts before audit
2dbccbd84 fix(auditor): classify missing verdict as protocol failure
0644681a2 fix(phase2): classify final audit ERROR by last attempt's failure
52708a600 fix(phase2): reject valid audit verdict regardless of wrapper rc
7cccf47b0 fix(infra): keep self-check results on log-dir errors
```

## 红线核验

- 未改 xianyu 业务仓；未改已关闭卡。
- 未修改 `CardStateStore` CAS/锁语义。
- 未削弱 fail-closed；非法 verdict 仍不产生业务打回。
- 新测试只使用临时目录与 mock，不碰真实资源。

## 部署验证

报告提交后重启 engine，并独立核验新 PID 与 `/health` HTTP 200；结果见最终输出。
