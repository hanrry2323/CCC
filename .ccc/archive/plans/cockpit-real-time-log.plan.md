# Plan: cockpit-real-time-log — Cockpit 显示 Engine 实时日志

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-cockpit.py`（1249 行单文件，`CockpitHandler` HTTP 处理器 + 内联 HTML 渲染）
- **当前结构要点**：
  1. 4 个路由：`/`（HTML 全页）→ `render_html(data)` / `/api/alive`（JSON 探针） / `/api/board`（看板摘要） / `/api/kb/search`（知识库代理）
  2. HTML 渲染在 `render_html()`（L697-1136）——纯内联 Python f-string + `<script>` 字符串变量（L855-1024），无模板引擎
  3. 客户端轮询：`checkAlerts()` 每 15 秒 + `fetchAlive()` 每 30 秒，均调 `/api/alive`
  4. Engine 日志：`~/.ccc/logs/engine.log`（`TimedRotatingFileHandler`，每日轮转、保留 7 天）
  5. Cockpit 目前**零日志相关功能**——不读、不 tail、不展示任何日志文件
- **待改动点**：`scripts/ccc-cockpit.py`——新增 tail 工具函数 + API 端点 + 渲染面板 + JS 轮询

---

## 范围

- **目标**：Cockpit 仪表盘在"项目"和"页脚"之间新增日志面板，tail Engine 日志最后 20 行，每 10 秒自动刷新
- **只改文件**：`["scripts/ccc-cockpit.py"]`
- **不改文件**：`["scripts/_logger.py", "scripts/ccc-engine.py", "scripts/ccc-board.py", "scripts/_config.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：新增日志 tail API + 面板 HTML + JS 轮询

### 做什么

在 Cockpit 仪表盘中新增一个 Engine 实时日志面板：
1. 后端新增 `GET /api/logs` 端点，返回 `~/.ccc/logs/engine.log` 最后 20 行（JSON 格式）
2. HTML 在"项目"表格下方、"页脚"上方插入一个日志面板区域（带文件路径标题和日志内容容器）
3. JS 新增 `fetchLogs()` 轮询函数，页面加载后立即执行，之后每 10 秒自动刷新
4. 日志面板采用终端风格深色背景（#1d1d1f + #e0e0e0 文字），最大高度 400px 可滚动
5. 日志文件不存在或为空时显示友好提示，不报错

### 怎么做

**1a. `scripts/ccc-cockpit.py`** — 在 `parse_infra()` 函数后（约 L50）新增 `tail_file()` 工具函数：

```python
def tail_file(filepath: Path, n: int = 20) -> list[str]:
    """Read the last n lines from a file efficiently."""
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    # Take last n, avoid negative index when file has fewer lines
    return lines[-n:] if len(lines) >= n else lines
```

**1b. `scripts/ccc-cockpit.py`** — 在 `_render_board_section()` 之后（约 L695）、`render_html()` 之前新增 `_render_log_panel()` 渲染函数：

```python
def _render_log_panel() -> str:
    """Render the engine log viewer panel (placeholder, populated by JS)."""
    return (
        '<div class="sec-title">Engine 实时日志</div>'
        f'<div id="log-panel" style="background:{THEME["surface"]};border:1px solid {THEME["border"]};border-radius:var(--radius-md);padding:12px;margin-bottom:8px">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:11px;color:#86868b;text-transform:uppercase;letter-spacing:.04em">'
        '<span>~/.ccc/logs/engine.log</span>'
        '<span id="log-ts"></span>'
        "</div>"
        '<pre id="log-content" style="margin:0;font-family:ui-monospace,monospace;font-size:12px;line-height:1.6;max-height:400px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;background:#1d1d1f;color:#e0e0e0;padding:12px;border-radius:4px">加载中…</pre>'
        "</div>"
    )
```

**1c. `scripts/ccc-cockpit.py`** — 在 `render_html()` 模板中，`</tbody></table></div>`（项目表格结束，L1122 行）与 `<div class="foot"`（页脚，L1124 行）之间插入日志面板：

```python
    # 替换 L1122-L1124 之间为:
    </tbody></table></div>

    {_render_log_panel()}

    <div class="foot" ...
```

**1d. `scripts/ccc-cockpit.py`** — 在 `script_html` 字符串（L855-1024）中新增 `fetchLogs()` 函数和定时器。具体位置在 `function portFilter()` 之后（L985）、`(function() { ... })()` 自执行之前（L1005），追加：

```javascript
function fetchLogs() {
    fetch('/api/logs')
    .then(function(res) { if (!res.ok) { throw new Error('HTTP ' + res.status); } return res.json(); })
    .then(function(data) {
        var content = document.getElementById('log-content');
        var ts = document.getElementById('log-ts');
        if (!content) { return; }
        if (!data.exists || data.lines.length === 0) {
            content.innerHTML = '<span style="color:#86868b">日志文件不存在或为空</span>';
            if (ts) { ts.textContent = ''; }
            return;
        }
        content.innerHTML = data.lines.map(function(l) {
            return l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }).join('');
        if (ts) { ts.textContent = data.updated || ''; }
        content.scrollTop = content.scrollHeight;
    })
    .catch(function(err) { console.error('Failed to fetch logs:', err); });
}
```

并在现有定时器区域（L1018-1023）追加日志轮询启动：

```javascript
  setInterval(checkAlerts, 15000);
  checkAlerts();
  setTimeout(function() {
    fetchAlive();
    setInterval(fetchAlive, 30000);
  }, 2000);
  setTimeout(function() {              // 新增
    fetchLogs();
    setInterval(fetchLogs, 10000);
  }, 500);
```

**1e. `scripts/ccc-cockpit.py`** — 在 `do_GET()` 中 `/api/kb/search` 分支结束后（L1232）、404 回退之前（L1233）新增日志 API 路由：

```python
        elif path == "/api/logs":
            log_path = Path.home() / ".ccc" / "logs" / "engine.log"
            lines = tail_file(log_path, 20)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "lines": lines,
                    "file": str(log_path),
                    "exists": log_path.exists(),
                    "updated": datetime.now().strftime("%H:%M:%S"),
                }).encode("utf-8")
            )
```

### 验收清单

- [ ] `tail_file(Path, n=20)` 函数存在，文件不存在时返回 `[]`，不抛异常
- [ ] `GET /api/logs` 返回 JSON `{"lines": [...], "file": "...", "exists": bool, "updated": "HH:MM:SS"}`
- [ ] HTML 页面在"项目"表格下方、"页脚"上方有日志面板区域
- [ ] 日志面板带文件路径标题（~/.ccc/logs/engine.log）和自动刷新时间戳
- [ ] 日志内容用深色终端风格背景 + `<pre>` 等宽字体显示
- [ ] 最大高度 400px，内容超出时可滚动
- [ ] JS `fetchLogs()` 在页面加载 500ms 后执行，之后每 10 秒轮询
- [ ] 日志文件不存在或为空时显示友好文本，不闪红/报错
- [ ] HTML 字符转义处理（& → &amp;，< → &lt;，> → &gt;）
- [ ] 每次刷新后自动滚到底部（`scrollTop = scrollHeight`）

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-cockpit.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/ccc-cockpit.py').read())"` → 无异常
- [函数存在] `grep -n "def tail_file" scripts/ccc-cockpit.py` → 匹配
- [函数存在] `grep -n "def _render_log_panel" scripts/ccc-cockpit.py` → 匹配
- [路由存在] `grep -n "/api/logs" scripts/ccc-cockpit.py` → `do_GET()` 内匹配
- [路由返回 JSON] `grep -A5 '"application/json"' scripts/ccc-cockpit.py` → `/api/logs` 分支使用 JSON Content-Type
- [HTML 面板注入] `grep -n "_render_log_panel" scripts/ccc-cockpit.py` → 在 `render_html()` 被调用（>=2 处：定义 + 调用）
- [JS 函数存在] `grep -n "function fetchLogs" scripts/ccc-cockpit.py` → `script_html` 内匹配
- [定时器存在] `grep -n "setInterval.*fetchLogs" scripts/ccc-cockpit.py` → 10000 间隔
- [HTML 转义] `grep -n "replace.*&amp;" scripts/ccc-cockpit.py` → fetchLogs 内有转义处理
- [滚动到底] `grep -n "scrollHeight" scripts/ccc-cockpit.py` → fetchLogs 内有 scrollTop 赋值
- [日志为空处理] `grep -n "日志文件不存在" scripts/ccc-cockpit.py` → 有 fallback 文本
- [日志文件路径] `grep -n "engine.log" scripts/ccc-cockpit.py` → `/api/logs` 路由用 `Path.home() / ".ccc" / "logs" / "engine.log"`
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新增 tail_file() 工具 + /api/logs 端点 + 日志面板 HTML + JS 轮询 | `feat(cockpit): Engine 实时日志面板（tail 20 行，10s 自动刷新）(phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-cockpit.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-cockpit.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] 新端点 /api/logs 返回正确 JSON 结构
- [ ] 日志面板在浏览器中可见，10s 自动刷新，深色终端风格
- [ ] 日志文件不存在时优雅降级（显示"日志文件不存在或为空"）
- [ ] HTML 转义确保安全性（XSS 防护）

---

## 后续步骤

完成后：
- 可通过 Cockpit 仪表盘实时观察 Engine 工作日志，无需 SSH 或终端 tail
- 后续可考虑增加日志级别过滤（只显示 ERROR/WARN）、或通过 `?lines=50` 参数控制行数
- Engine 日志路径可考虑在 `_config.py` 中集中定义，避免硬编码