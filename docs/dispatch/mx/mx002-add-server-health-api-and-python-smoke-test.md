# 任务卡 mx002 · add server health api and python smoke test（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

在 `medio-0` 媒体服务器 (Rust Axum 后端) 中实现一个极轻量的 `/api/v1/health` 健康监控接口，并在 Python API 冒烟测试集 `tests/test_probe.py` 中增加对应的端到端测试用例并成功跑通。

## 红线（先看）

1. **绝对禁止**修改或破坏 `medio-0` 中既有的任何业务 API 逻辑和数据库表结构。
2. 仅允许在 `/Users/fan/program/apps/medio-0` 目录下的 `src/backend/core/src/api/routes/mod.rs` 和 `tests/test_probe.py` 中进行白名单修改。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/api/routes/mod.rs` (核心 API 路由层)
- `tests/test_probe.py` (Python 冒烟测试集)

## 步骤

1. 在 Mac2017 实机进入目录 `cd /Users/fan/program/apps/medio-0`。
2. 编辑 `src/backend/core/src/api/routes/mod.rs`，在 `build_routes()` 路由器中注册 `/api/v1/health` 路由：
   - 引入 `axum::routing::get` 及 `axum::Json`。
   - 实现无鉴权直接可访问的 `async fn health_handler() -> Json<serde_json::Value>` 处理器，返回 `{"status": "ok", "version": env!("CARGO_PKG_VERSION")}`。
   - 在 `build_routes()` 中追加 `.route("/api/v1/health", get(health_handler))` 链式注册。
3. 执行编译检查，确保后端能够完美编译通过：
   ```bash
   cargo check -p medio-server
   ```
4. 编辑 `tests/test_probe.py`，在 `TestServerConnectivity` 测试类中追加一个针对健康检查接口的测试用例：
   ```python
   def test_health_endpoint(self, session):
       """GET /health should return 200 with status ok and valid version."""
       resp = session.get(f"{self.BASE_URL}/health", timeout=5)
       assert resp.status_code == 200
       data = resp.json()
       assert data.get("status") == "ok"
       assert "version" in data
   ```
5. 启动测试服务器并运行端到端测试进行验证：
   - 使用测试配置拉起服务器（如后台挂载运行或使用指定测试端口，默认测试端口 3000）：
     ```bash
     cargo run -p medio-server -- --config config-test.toml --port 3000 &
     SERVER_PID=$!
     sleep 2
     ```
   - 激活虚拟环境并执行测试：
     ```bash
     # M2 platform virtual env position: /Users/fan/program/apps/medio-0/.venv or tests/requirements env
     # Run health probe:
     pytest tests/test_probe.py -k test_health_endpoint -v
     ```
   - 验证通过后清理测试服务器进程：
     ```bash
     kill $SERVER_PID
     ```
6. commit+push 到卡内分支 `codex/mx002-add-server-health-api-and-python-smoke-test`（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 通过浏览器或 curl 访问 `http://127.0.0.1:3000/api/v1/health` 能够秒级返回 `{"status":"ok","version":"0.9.0"}` 等 JSON 数据。
2. 运行 `pytest tests/test_probe.py -k test_health_endpoint` 测试用例 100% Passed。
3. `/Users/fan/program/apps/medio-0` 源码工作区保持干净（除了我们修改的 `mod.rs` 和 `test_probe.py` 外，没有其他任何残留修改或未跟踪文件）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 实现说明
- **API 路由及处理器**：在 `src/backend/core/src/api/routes/mod.rs` 中注册了 `/api/v1/health` 路由，并引入 `axum::routing::get` 和 `axum::Json` 实现无鉴权处理器 `health_handler`，秒级返回包含状态 "ok" 及当前版本号 `0.9.0` 的 JSON 数据。
- **冒烟测试用例**：在 `tests/test_probe.py` 中的 `TestServerConnectivity` 类里追加了针对 `/health` 接口的端到端自动化测试用例 `test_health_endpoint`。

### 2. 测试结果
- 执行 `cargo check -p medio-server` 检查编译完美通过。
- 启动测试服务器（使用端口 3000 和 config-test.toml 配置），运行 `pytest tests/test_probe.py -v` 冒烟测试共计 11 个测试用例，100% 成功通过（11 passed）：
  ```
  tests/test_probe.py::TestImports::test_import_aiohttp PASSED             [  9%]
  tests/test_probe.py::TestImports::test_import_requests PASSED            [ 18%]
  tests/test_probe.py::TestImports::test_import_pytest PASSED              [ 27%]
  tests/test_probe.py::TestServerConnectivity::test_rss_subscriptions_endpoint PASSED [ 36%]
  tests/test_probe.py::TestServerConnectivity::test_rss_items_endpoint PASSED [ 45%]
  tests/test_probe.py::TestServerConnectivity::test_rss_tags_endpoint PASSED [ 54%]
  tests/test_probe.py::TestServerConnectivity::test_rss_opml_export PASSED [ 63%]
  tests/test_probe.py::TestServerConnectivity::test_media_videos_endpoint PASSED [ 72%]
  tests/test_probe.py::TestServerConnectivity::test_media_folders_endpoint PASSED [ 81%]
  tests/test_probe.py::TestServerConnectivity::test_search_endpoint PASSED [ 90%]
  tests/test_probe.py::TestServerConnectivity::test_health_endpoint PASSED [100%]

  ============================== 11 passed in 0.41s ==============================
  ```
- 源码工作区除允许修改的文件外保持绝对干净（`.venv` 在验证完毕后已被彻底移除）。

### 3. Push 证据
- 业务仓 (medio-0) 提交至分支 `codex/mx002-add-server-health-api-and-python-smoke-test`：
  Commit Hash: `b3e24280c2fb46315a51fb74fb5999d6dae7424a`

## 机审区

**机审**：Claude Code · 日期：2026-08-07

**机审：通过**

独立取证（非依据回写区自述）：
- diff（`b3e2428`）仅改白名单内 `src/backend/core/src/api/routes/mod.rs` 与 `tests/test_probe.py`，未触碰业务 API 逻辑或 DB 结构；既有 `/search` 端点实测仍 200。
- `cargo check -p medio-server` 独立复验编译通过。
- 实机拉起 `--port 3000` 后 `curl /api/v1/health` → HTTP 200，body `{"status":"ok","version":"0.9.0"}`（验收标准 1）。
- 独立重建 venv 跑 `pytest tests/test_probe.py` 全量 11 passed（含 `test_health_endpoint`，验收标准 2）。
- 业务仓与 CCC worktree 工作树均 clean，无残留（验收标准 3）。
- `## 人工批注` 为空占位，无未落实批注。
- 业务仓补收口（2026-08-07 遗留清理）：medio-0 main b3e2428
