# cockpit-v0304-multicli 执行报告

## 信息
- Phase: cockpit-v0304-multicli-p1
- 退出码: 0

## 完成内容

### 1. 多 CLI 引擎注册（CLI_ENGINES）
新增 3 个 CLI 引擎条目：
- `claude-p` — Claude Code CLI（print 模式）
- `opencode` — OpenCode CLI（loop/code 模型）
- `cursor` — Cursor CLI（待启用）

### 2. CLI 引擎检测函数 `_detect_cli_engines()`
- 通过 `shutil.which()` 检查 binary 是否存在
- 运行 `<binary> --version` 等探测命令获取版本
- 区分 `ok` / `warn` / `timeout` / `missing` / `error` 5 种状态
- 超时保护（4s timeout）

### 3. 日志文件函数
- `_list_log_files()` — 列出 `.ccc/logs/*.log` 文件，按 mtime 排序
- `_read_log_tail(name, max_bytes)` — 读取日志尾部（默认 16KB，可调），安全过滤（仅接受简单文件名）
- `.ccc/logs/` 实际包含 ccc-exec-launcher / role-*.log / flywheel-scan 等日志

### 4. HTTP API 端点
- `GET /api/cli/engines` → 返回 `{"engines": [...]}`
- `GET /api/logs/list` → 返回 `{"logs": [{name, size_kb, mtime}, ...]}`
- `GET /api/logs/tail?name=X&max=N` → 返回日志尾部内容

### 5. HTML 渲染
新增两个 section：
- **CLI 引擎** — 展示引擎安装状态、版本、路径，附带"复制命令"按钮
- **服务日志** — 日志文件下拉选择 + "查看日志" + "自动刷新"（5s 轮询）

## 验证
```bash
python3 -m py_compile scripts/ccc-cockpit.py  # 通过
PYTHONPATH=scripts python3 -c "import ccc_cockpit; print(ccc_cockpit._detect_cli_engines())"
# → 3 个引擎正确检测

curl http://127.0.0.1:17778/api/cli/engines  # 返回 3 引擎 JSON
curl http://127.0.0.1:17778/api/logs/list    # 返回日志列表
curl http://127.0.0.1:17778/                 # HTML 含 "CLI 引擎" 和 "服务日志" 区域
```

## 验收清单
- [x] 多 CLI 引擎注册 + 检测（claude-p / opencode / cursor）
- [x] 服务日志面板（日志列表 + 尾部查看 + 自动刷新）
- [x] Python 语法检查通过
- [x] API 端点工作正常
- [x] HTML 渲染包含新区域
