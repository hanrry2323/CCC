# Verdict — cluster-bus-bugfixes

> Plan: .ccc/plans/cluster-bus-bugfixes.plan.md
> Report: .ccc/reports/cluster-bus-bugfixes.report.md
> Verifier session: 见 `.ccc/plans/cluster-bus-bugfixes-verifier-session-id.txt`
> Executor session: 见 `.ccc/plans/cluster-bus-bugfixes-executor-session-id.txt`
> 验收日期: 2026-07-06

---

## ISOLATION_OK

红线 6 验证: Executor session UUID ≠ Verifier session UUID，session 隔离通过。

```
EXEC=$(cat .ccc/plans/cluster-bus-bugfixes-executor-session-id.txt)
MY=$(cat .ccc/plans/cluster-bus-bugfixes-verifier-session-id.txt)
[ "$EXEC" != "$MY" ] && echo "ISOLATION_OK" || echo "ISOLATION_FAIL"
# → ISOLATION_OK
```

---

## VERDICT: CONDITIONAL_PASS

3/4 probe 通过 + 1 项 Probe 1(JSONL 格式保护)发现新漂移问题。

---

## Probe 1 — JSONL bug

- 结果: **FAIL（格式漂移）**
- 证据:
  - 输入(JSONL, 无缩进、单行):
    ```
    {"phase":1,"status":"pending","files":["a.txt"],"commit":null,"commit_message":"t"}
    {"phase":2,"status":"pending","files":["b.txt"],"commit":null,"commit_message":"t"}
    ```
  - `bash scripts/ccc-exec-commit.sh /tmp/vfy-test ccc-vfy` 跑完写回的 phases.json:
    ```
    {"phase": 1, "status": "pending", "files": ["a.txt"], "commit": null, "commit_message": "t"}
    {"phase": 2, "status": "pending", "files": ["b.txt"], "commit": null, "commit_message": "t"}
    ```
  - **变化**: `{"phase":1,` → `{"phase": 1,`（多了空格）。JSONL 解析修复（不再 `Extra data`），但 `_write_phases` 写回走 `json.dumps(p, ensure_ascii=False)` 默认分隔符，与原行格式不字节相等，破坏 diff 紧凑性。
- 严重度: LOW（功能通了，diff 噪音上升）

## Probe 2 — GC 机制

- 结果: **PASS**
- 证据:
  - `scripts/cluster-bus.py:237` 实现 `gc_threshold_s = HEARTBEAT_TTL_SECONDS * 10`（= 900s = 15 min）
  - `scripts/cluster-bus.py:243-246` 删除 age > 阈值的 stale 节点
  - `scripts/cluster-bus.py:248` 启动时打印 `GC removed {n} stale nodes on startup`
  - 注: 常量名是 `gc_threshold_s` 而不是 `GC_THRESHOLD`，但 plan 要求"加 GC 机制"未指定常量名，功能等价通过

## Probe 3 — include_stale

- 结果: **PASS**
- 证据:
  - `scripts/ccc-dispatch.py:94` `def fetch_active_nodes(... include_stale: bool = True)` 默认 True
  - `scripts/ccc-dispatch.py:103-104` `if include_stale: url += "?include_stale=true"`
  - `scripts/cluster-bus.py:150,157,159,163,181` 5 处 include_stale 处理（含别名兼容）
  - cluster-bus 接受 `?include_stale=true` 别名并与 `active_only` 兼容

## Probe 4 — sidecar task_id

- 结果: **PASS（机制 OK）**
- 证据:
  - `scripts/ccc-exec-commit.sh:98-113` 实现 sidecar 写入路径
  - 实测: `/tmp/vfy-test/.ccc/phases/ccc-vfy.phases.json.task_id` 已生成（37 字节 UUID 文件落地）
  - 注: CCC 主项目 `.ccc/phases/` 下暂无 `.task_id` sidecar，是因为原 3 个 phase 都 `status=pending`，未触发 commit 完成路径 → 不是 bug，机制可用未触发

---

## 总结

- **3/4 probe 通过**（Probe 2/3/4 通过, Probe 1 发现格式漂移）
- 修复范围合规（仅 `scripts/cluster-bus.py` + `scripts/ccc-dispatch.py` + `scripts/ccc-exec-commit.sh`），未越界
- 红线 6（session 隔离）通过
- 最终 **VERDICT: CONDITIONAL_PASS**

### 后续行动（建议 Planner 决定）
- Probe 1 是 LOW 严重度（diff 噪音），非阻塞
- 若需闭环：在下个 phase 让 Executor 微调 `ccc-exec-commit.sh` `_write_phases`，对 `jsonl` 分支用 `separators=(',', ':')` 保持紧凑
- 若用户接受当前 diff 噪音，可直接 close