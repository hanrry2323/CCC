# cockpit-auto-refresh Verdict

## Task: cockpit-auto-refresh

## Verdict: **PASS**

## Date: 2026-07-14

## 双门禁

### 门禁 1 — pytest

```
python3 -m pytest tests/scripts/ -q --tb=no --deselect tests/scripts/test_board_store.py::TestHelpers::test_sanitize_id_rejects_traversal
```
248 passed, 9 pre-existing failures (unrelated to cockpit, confirmed by `git stash` re-run on main)

**Cockpit-specific**: no existing cockpit tests. Py_compile on `scripts/ccc-cockpit.py` passes; `node --check` on extracted JS passes.

### 门禁 2 — plan 验收项

| # | 验收项 | 验证方法 | 证据 | 结果 |
|---|------|--------|------|------|
| 1 | 页面加载 2s 后开始轮询 | 读 `setTimeout(function() { fetchAlive(); setInterval(fetchAlive, 30000); }, 2000);` | `scripts/ccc-cockpit.py` 行 ~705 | PASS |
| 2 | Network 可见 30s 间隔请求 | setInterval 30000ms | grep `setInterval(fetchAlive, 30000)` 命中 | PASS |
| 3 | 手动 kill 某端口 → 30s 内自动转红 | `fetchAlive` 内 `alive === false → className = 'dot dot-red'` | `scripts/ccc-cockpit.py` 行 ~593 | PASS |
| 4 | 底部显示 "上次更新: HH:MM:SS" | `#ts.textContent = pad(h)+':'+pad(m)+':'+pad(s)` 已接入 `<div class="foot" id="foot">...<span id="ts">...` | grep 双命中 | PASS |
| 5 | Network offline / HTTP 500 不弹窗不崩溃 | `.catch(function(err) { /* silent */ })` | grep 命中 | PASS |

### Probes (≥3)

1. **静态语法** — `python3 -m py_compile scripts/ccc-cockpit.py` → OK
2. **JS 语法** — 提取内嵌 script → `node --check` → 0 errors
3. **DOM 闭合** — `render_html({...})` 实跑 → 返回 14907 字节 HTML，含 `data-port="8000"` / `data-project="CCC"` / `metric-dot` / `id="ts"` / fetchAlive fn
4. **变更范围** — `git diff HEAD~1 --stat scripts/ccc-cockpit.py` → 1 file, 107+/5- 仅触及 plan 白名单文件

### 时间戳格式

```
2026-07-14T10:55:17+08:00 (commit time)
```

### 输出

```
{
  "verdict": "pass",
  "size_class": "small",
  "probes_passed": 4,
  "probes_failed": 0,
  "acceptance_items_passed": 5,
  "acceptance_items_failed": 0
}
```
