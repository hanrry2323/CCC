# 任务卡 xy059 · xianyu html-preview CLI——HTML 场景本地预览命令（DSH 执行）

> 关联：xy-plan-008 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-24

## 基准文件（先看）

- 业务仓导航：`/Users/fan/program/apps/xianyu/AGENTS.md`（uv 工作流：`uv run pytest tests/ -q`）
- 方案出处：`docs/projects/xy/plans/008-high-expression-v2.md` 方案内容块 2「模板库规模化 + html-preview」
- 现有场景渲染器：`src/xianyu/html_scene/renderer.py`（输入即 HTML 场景文件）

## 目标

新增 CLI 子命令 `xianyu html-preview <task_id>`：定位该任务的 HTML 场景产物并在本地起临时 HTTP 服务供浏览器预览，补齐 xy-plan-008 块 2 的预览入口。只读操作，不触碰生产管线与产出文件。

## 实现

白名单仅下列两文件：

1. `src/xianyu/cli.py`（追加子命令，风格对齐现有 `thumbnail` 命令）：
   - `html-preview(task_id: str, port: int = 8765, open_browser: bool = False)`；
   - 模块级纯函数 `_find_scene_html(task_id: str) -> Path | None`：在 `video-pipeline/output/<task_id>/` 下按文件名排序 glob 首个 `*.html`；目录或文件不存在 → 返回 None；
   - 找到 → 以场景所在目录为根起 `http.server` 线程（ThreadingHTTPServer，绑定 127.0.0.1），打印可点 URL `http://127.0.0.1:<port>/<html文件名>`；`--open` 时 `webbrowser.open`；Ctrl-C 优雅退出码 0；
   - 未找到 → rich console 明确报错（含已尝试路径）并以 `typer.Exit(code=1)` 退出。
2. `tests/test_cli.py`（追加，遵循文件内既有 CliRunner 用例风格）：
   - `test_html_preview_find_scene_html_tmpdir`：tmp_path 构造 `output/t1/a.html`，monkeypatch cwd 或注入根路径，断言命中；
   - `test_html_preview_missing_task_exits_nonzero`：CliRunner 调用不存在任务，断言 exit_code != 0 且输出含「未找到」类提示；
   - `test_html_preview_serves_url`：mock 服务线程（不真绑端口），断言打印的 URL 形如 `http://127.0.0.1:<port>/a.html`。
   - 新用例命名一律以 `test_html_preview_` 开头（门禁按 `-k html_preview` 收集）。

注：业务仓 worktree 若缺虚拟环境，先执行 `uv sync` 再跑测试（README 标准 uv 工作流）。

## 红线（先看）

1. 白名单外零触碰；禁直推 main；只读预览，禁止改写 output/ 任何产出。
2. 禁写机审区/验收区/置已关闭。
3. 不引入新第三方依赖（仅标准库 http.server/webbrowser + 既有 typer/rich）。

## 范围

- `src/xianyu/cli.py`
- `tests/test_cli.py`

## 步骤

1. Read 本卡全文 + `src/xianyu/cli.py`（thumbnail 命令段）+ `tests/test_cli.py`（既有风格）+ `src/xianyu/html_scene/renderer.py`（理解场景文件语义）。
2. 实现 `_find_scene_html` + `html-preview` 子命令 + 三条测试；自测：
   - `uv run pytest tests/test_cli.py -k html_preview -q` 全绿；
   - `uv run ruff check src/xianyu/cli.py tests/test_cli.py` 无新增告警；
   - 手工冒烟：对任一含 HTML 的真实任务目录起服务，curl URL 200。
3. commit+push 到分支 `codex/xy059-html-preview-cli`（勿直推 main）；push 前 fetch+rebase origin/main。
4. 卡头改「已回写」并填回写区（实现说明/测试结果/commit hash 与 push 证据）；维护区四问逐项填写——勾选符必须落在问题行的方括号内（如 [是]/[否]），说明行写一句实情（docgate 机械校验该格式）。
5. 停手，等机审与环节② 合入。

## 验收标准

1. 门禁测试命令真实退出码=0（wrapper 截获证据日志为准）。
2. `xianyu html-preview 不存在的任务` 退出码非零且报错含尝试路径；存在场景时打印可访问 URL（手工冒烟 curl 200）。
3. 分支相对 main 的 diff 仅触白名单两文件；无新依赖。
4. 卡头=已回写；维护区四问勾选落位问题行方括号、说明非占位。

## 门禁

测试：cd /Users/fan/program/apps/.ccc-wt/xy/xy059 2>/dev/null || cd /Users/fan/program/apps/xianyu; uv run pytest tests/test_cli.py -k html_preview -q

## 回写区

（执行体回写）

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：
