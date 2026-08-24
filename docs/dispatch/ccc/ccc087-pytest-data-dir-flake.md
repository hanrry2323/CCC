# 任务卡 ccc087 · pytest 单实例锁夹具去共享——消 test_once_smoke 偶发失败（DSH 执行）

> 关联：环节②交接(2026-08-25)问题3 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

server/tests/test_engine_main.py _write_env 默认 DATA_DIR=/tmp/ccc2/data 为同文件多测试共享，engine.lock 偶发 BlockingIOError/SystemExit(2) 造成 test_once_smoke 间歇失败。改夹具为每测试唯一 DATA_DIR。

## 红线

- 白名单：server/tests/test_engine_main.py（必要时 conftest.py）。
- 不改单实例锁生产逻辑。

## 步骤

1. _write_env 默认值改为基于 tmp_path 的唯一目录（保留 overrides 覆盖能力，供锁竞争专项测试显式传同路径）。
2. 自测：连续全量 server/tests ×3，0 次 test_once_smoke 及相关锁类 flake。

## 验收标准

- [x] 连续三轮全量 pytest 零该 flake（附三轮尾部输出）
- [x] 显式传同 DATA_DIR 的锁竞争测试（如有）仍有效

## 回写要求

- 回写区附三轮输出与 diff；维护区四问如实。

## 人工批注

（留空）

## 回写区

**实现说明**（2026-08-25 · DSH 执行体）

- 根因：`_write_env` 默认 `DATA_DIR=/tmp/ccc2/data` 为生产共享路径；`server/engine/main.py` `main()` 入口无条件调 `_acquire_engine_single_instance(DATA_DIR)`（main.py:4441），对 `DATA_DIR/engine.lock` 做 `flock(LOCK_EX|LOCK_NB)`（main.py:241），本机真实 engine/watchdog 持锁时测试进程拿锁失败 → `SystemExit(2)`（main.py:245）。另 LOG_DIR 同指共享 `/tmp/ccc2/logs`，一并去共享。
- 改动：仅改 `server/tests/test_engine_main.py` `_write_env` 默认值为 `tmp_path/'data'`、`tmp_path/'logs'`（pytest tmp_path 每测试唯一）；`overrides.get(...)` 覆盖能力保留，生产单实例锁逻辑零改动。conftest.py 未需改动。

**diff**（commit 48c70ceae）

```diff
--- a/server/tests/test_engine_main.py
+++ b/server/tests/test_engine_main.py
@@ -39,12 +39,16 @@ REGISTRY_PATH = PROJECT_ROOT / "server" / "config" / "executors.example.json"
 def _write_env(tmp_path: Path, registry_path: Path | str, **overrides: str) -> str:
     """写一份可用的 config.env（测试夹具；字面值仅属测试数据）。"""
+    # ccc087：DATA_DIR/LOG_DIR 默认落 tmp_path 唯一目录——默认值曾指向 /tmp/ccc2/{data,logs}
+    # 共享路径，与本机真实 engine 跨进程争 DATA_DIR/engine.lock 单实例锁，
+    # 造成 test_once_smoke 偶发 BlockingIOError/SystemExit(2)。锁竞争专项测试
+    # 仍可经 overrides 显式传同一路径。
     lines = [
         "ENGINE_PORT=8101",
         "BOARD_PORT=8102",
         "WEB_PORT=8103",
-        f"DATA_DIR={overrides.get('DATA_DIR', '/tmp/ccc2/data')}",
-        f"LOG_DIR={overrides.get('LOG_DIR', '/tmp/ccc2/logs')}",
+        f"DATA_DIR={overrides.get('DATA_DIR', str(tmp_path / 'data'))}",
+        f"LOG_DIR={overrides.get('LOG_DIR', str(tmp_path / 'logs'))}",
```

**自测结果**

1. 单文件：`python3 -m pytest server/tests/test_engine_main.py -q --tb=short` → 119 用例全过（junitxml 计数 total=119 failures=0）；`python3 -m ruff check server/tests/test_engine_main.py` → All checks passed。
2. 连续三轮全量 `python3 -m pytest server/tests -q --tb=short`（日志 /tmp/ccc087-evidence/round{1,2,3}.log），三轮尾部输出：

```text
== ROUND 1 tail ==
FAILED server/tests/test_brain_stream.py::TestStreamClaude::test_success_flow
FAILED server/tests/test_brain_stream.py::TestStreamClaude::test_thinking_flag_default_enabled
FAILED server/tests/test_brain_stream.py::TestStreamClaude::test_thinking_flag_disabled_via_env
FAILED server/tests/test_brain_stream.py::TestStreamBrainEvents::test_not_configured_yields_error_503
FAILED server/tests/test_http_api.py::TestConversation::test_conversation_not_configured_503
FAILED server/tests/test_http_api.py::TestConversation::test_conversation_stream_not_configured_sse_error
== ROUND 2 tail ==（同 ROUND 1）
== ROUND 3 tail ==（同 ROUND 1）
```

- 三轮 grep 锁类关键词 `test_once_smoke|BlockingIOError|engine\.lock|SystemExit\(2\)|单实例锁|test_engine_main.*FAILED` → **0 命中 ×3**，验收标准第 1 条达成。
- 三轮各 11 个 FAILED 全部属 brain/http 环境性既有失败（依赖本机 CCC_BRAIN_* 配置）：junitxml 权威计数 verify 轮 tests=1175 failures=11 errors=0；stash 基线对照（未含本卡改动全量跑）tests=1175 failures=11，失败集合与本卡改动后**完全一致**（差集为空）→ 非本卡引入，与 ccc079 Lesson 57 已记录的 conversation 族环境性失败同源。
- 验收标准第 2 条：仓内现无显式传同 DATA_DIR 的锁竞争专项测试（rg 无 `_acquire_engine_single_instance|engine.lock` 测试引用，「如有」不触发）；实测夹具覆盖能力保留：内联调用 `_write_env(tmp, reg)` 得 `DATA_DIR=<tmp>/data`（每测试唯一），`_write_env(tmp, reg, DATA_DIR='/tmp/ccc2/data')` 显式传同路径生效 → CHECK-PASS。

**push 证据**

- 分支 `codex/ccc087-pytest-data-dir-flake`，commit `48c70ceae` fix(tests): ccc087 test_engine_main 夹具 DATA_DIR/LOG_DIR 去共享——消单实例锁 flake（1 file changed, 6 insertions(+), 2 deletions(-)）
- push 输出：`To github.com:hanrry2323/CCC.git  * [new branch] codex/ccc087-pytest-data-dir-flake -> codex/ccc087-pytest-data-dir-flake`
- 卡回写随本分支后续提交入库。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：本卡无关联方案编号（「关联」为环节②交接问题3），无可同步的方案状态与关联卡。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：「测试夹具禁默认写共享生产路径」要点已固化于 _write_env 夹具注释与回写区；docs/lessons.md 不在本卡白名单故未单独沉淀；同类隐患 test_engine_scheduler.py `_write_env` 仍指 /tmp/ccc2/data（该文件不在白名单未改），建议另卡处理。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：纯测试夹具默认值修复，未动项目结构、技术栈与路径。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：单点 flake 修复，无新增线路或近况变化。
