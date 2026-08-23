# 任务卡 xy059 · xianyu html-preview CLI——HTML 场景本地预览命令（DSH 执行）

> 关联：xy-plan-008 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-08-24

## 基准文件（先看）

- 业务仓导航：`/Users/fan/program/apps/xianyu/AGENTS.md`（uv 工作流：`uv run pytest tests/ -q`）
- 方案出处：`docs/projects/xy/plans/008-high-expression-v2.md` 方案内容块 2「模板库规模化 + html-preview」
- 现有场景渲染器：`src/xianyu/html_scene/renderer.py`（输入即 HTML 场景文件）

## 目标

新增 CLI 子命令 `xianyu html-preview <task_id>`：定位该任务的 HTML 场景产物并在本地起临时 HTTP 服务供浏览器预览，补齐 xy-plan-008 块 2 的预览入口。只读操作，不触碰生产管线与产出文件。

## 实现

白名单仅下列两文件：

1. `src/xianyu/cli.py`（追加子命令，风格对齐现有 thumbnail 命令）：
   - 模块级纯函数 `_find_scene_html(task_id: str) -> Path | None`：在 `video-pipeline/output/<task_id>/` 下按文件名排序 glob 首个 `*.html`；目录或文件不存在返回 None；
   - 子命令 `html-preview(task_id: str, port: int = 8765, open_browser: bool = False)`：命中则以场景所在目录为根起 ThreadingHTTPServer（绑定 127.0.0.1），打印 URL `http://127.0.0.1:<port>/<html文件名>`；`--open` 时 webbrowser.open；Ctrl-C 退出码 0；
   - 未命中 → rich console 明确报错（含已尝试路径）并以 typer.Exit(code=1) 退出。
2. `tests/test_cli.py`（追加，遵循文件内既有 CliRunner 用例风格）：
   - `test_html_preview_find_scene_html_tmpdir`：tmp_path 构造 output/t1/a.html 断言命中；
   - `test_html_preview_missing_task_exits_nonzero`：不存在任务 exit_code!=0 且输出含路径提示；
   - `test_html_preview_serves_url`：mock 服务线程不真绑端口，断言打印 URL 形如 http://127.0.0.1:<port>/a.html；
   - 新用例命名一律 test_html_preview_ 开头（门禁按 -k html_preview 收集）。

注：业务仓 worktree 若缺虚拟环境，先 uv sync 再跑测试（README 标准 uv 工作流）。

## 红线（先看）

1. 白名单外零触碰；禁直推 main；只读预览，禁止改写 output/ 任何产出。
2. 禁写机审区/验收区/置已关闭。
3. 不引入新第三方依赖（仅标准库 http.server/webbrowser + 既有 typer/rich）。

## 范围

- src/xianyu/cli.py
- tests/test_cli.py

## 步骤

1. Read 本卡全文 + src/xianyu/cli.py（thumbnail 段）+ tests/test_cli.py（既有风格）+ src/xianyu/html_scene/renderer.py。
2. 实现 _find_scene_html + html-preview 子命令 + 三条测试；自测：
   - uv run pytest tests/test_cli.py -k html_preview -q 全绿；
   - uv run ruff check src/xianyu/cli.py tests/test_cli.py 无新增告警；
   - 手工冒烟：对任一含 HTML 的任务目录起服务 curl 200。
3. commit+push 到分支 codex/xy059-html-preview-cli（勿直推 main）；push 前 fetch+rebase origin/main。
4. 卡头改「已回写」并填回写区（实现说明/测试结果/commit hash 与 push 证据）；维护区四问逐项填写——勾选符必须落在问题行的方括号内（如 [是]/[否]），说明行写一句实情（docgate 机械校验该格式）。
5. 停手，等机审与环节② 合入。

## 验收标准

1. 门禁测试命令真实退出码=0（wrapper 截获证据日志为准）。
2. xianyu html-preview 不存在的任务退出码非零且报错含尝试路径；存在场景时打印可访问 URL（手工冒烟 curl 200）。
3. 分支相对 main 的 diff 仅触白名单两文件；无新依赖。
4. 卡头=已回写；维护区四问勾选落位问题行方括号、说明非占位。

## 门禁

测试：cd /Users/fan/program/apps/.ccc-wt/xy/xy059 2>/dev/null || cd /Users/fan/program/apps/xianyu; uv run pytest tests/test_cli.py -k html_preview -q

## 回写区

**执行体**：DSH · 日期：2026-08-24

### 1. 实现说明

- `src/xianyu/cli.py` 新增模块级纯函数 `_find_scene_html(task_id: str) -> Path | None`：在 `video-pipeline/output/<task_id>/`（相对 cwd，与卡面路径一致）下按文件名排序取首个 `*.html`；目录不存在或无 HTML 文件返回 None。
- 新增子命令 `xianyu html-preview <task_id>`（`--port/-p` 默认 8765、`--open/--no-open` 默认不开）：命中后以场景所在目录为根、绑定 127.0.0.1 起 `ThreadingHTTPServer`（标准库 `SimpleHTTPRequestHandler(directory=...)`，纯只读），打印 URL `http://127.0.0.1:<port>/<html文件名>`；`--open` 时 `webbrowser.open(url)`；Ctrl-C 捕获 KeyboardInterrupt 退出码 0；未命中 rich 报错含已尝试完整路径并以 `typer.Exit(code=1)` 退出；端口被占（OSError）同样归一为退出码 1。仅标准库 http.server/webbrowser/functools + 既有 typer/rich，零新依赖。
- `tests/test_cli.py` 按既有 CliRunner 风格追加 3 条用例：tmp_path 构造 `output/t1/{b,a}.html` 断言按文件名序命中 a.html；不存在任务断言 exit_code!=0 且输出含尝试路径（去空白后匹配，防 rich 长路径折行）；mock `http.server.ThreadingHTTPServer` 断言打印 URL 形如 `http://127.0.0.1:8123/a.html`、绑定地址为 ("127.0.0.1", 8123) 且 serve_forever/server_close 各调用一次——不真绑端口。

### 2. 测试结果

- 门禁命令（卡内原文）：`uv run pytest tests/test_cli.py -k html_preview -q` → **3 passed, 10 deselected**
- ruff：`uv run ruff check src/xianyu/cli.py tests/test_cli.py` → All checks passed
- 回归：`uv run pytest tests/test_cli.py -q --no-cov` → **13 passed**（存量 10 + 新增 3）
- 手工冒烟（真 CLI 真端口，/tmp 下构造 `video-pipeline/output/t1/a.html`）：HTTP GET `http://127.0.0.1:8931/a.html` → **200** 且响应体一致；对服务进程发 SIGINT → 退出码 **0**；`html-preview ghost-task` → 退出码 **1** 且输出含尝试路径 `/tmp/xy059_smoke/video-pipeline/output/ghost-task`

### 3. push 证据

- 业务仓 commit：`beab445`（feat(xy059): add html-preview CLI to preview task HTML scenes locally），已推送 `origin/codex/xy059-html-preview-cli`（push 前 fetch+rebase origin/main，up to date）；`git diff --name-only origin/main..HEAD` 仅白名单两文件。

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 xy-plan-008 推进为「部分执行」，关联卡补 xy059（本卡落地块 2 的 html-preview 入口）。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无。标准库直加 typer 子命令并复用既有 CliRunner 测试模式，未遇新型踩坑。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：否。仅 cli.py 增量子命令与对应测试，项目结构/技术栈/路径无变化。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：否。属 xy-plan-008 既定块内推进，近况与下一步不变。
