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

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

### 1 范围核对（base `738cac95e` → HEAD `f411c6ccd`，分支 `codex/ccc087-pytest-data-dir-flake`）

- `48c70ceae` 仅改 `server/tests/test_engine_main.py`（1 file, +6/−2）——白名单内；conftest.py 未动，符合「必要时」才动的卡面约定。
- `f411c6ccd` 仅改本卡文件（回写）。两提交均显式 add 单文件，无 `git add -A`。
- 未触验收区/机审区既有内容/已关闭状态；未改单实例锁生产逻辑（diff 零生产文件）。

### 2 对抗式核查证据（全部本席独立复现）

| # | 核查项 | 命令/位置 | 结果 |
|---|---|---|---|
| a | 根因引证真实 | `sed -n '235,250p' server/engine/main.py`、`sed -n '4435,4448p'` | `flock(LOCK_EX\|LOCK_NB)` 失败 `SystemExit(2)`（:241-245）；`main()` 无条件调 `_acquire_engine_single_instance(DATA_DIR)`（:4441）——与回写区引证逐字相符 |
| b | 修复命中目标 | `test_engine_main.py:133,136` | `test_once_smoke` → `_write_env(tmp_path, reg)` 无 overrides，走新 tmp_path 默认值 ✓ |
| c | 覆盖能力保留 | diff 第 50-51 行 `overrides.get('DATA_DIR', …)` | 显式传参通路未删 ✓ |
| d | 锁竞争专项测试「如有」 | `grep -rn "_acquire_engine_single_instance\|engine\.lock" server/tests/` | 仅命中注释行，「不触发」声明属实 ✓ |
| e | 三轮零锁类 flake | `grep -Ec 'test_once_smoke\|BlockingIOError\|engine\.lock\|SystemExit\(2\)\|单实例锁' /tmp/ccc087-evidence/round{1,2,3}.log` | **0 ×3**，复现成立 ✓ |
| f | 三轮完整性 | round{1,2,3}.log 各含 `[100%]` 终点、FAILED=11 | 三轮均跑完全量 ✓ |
| g | 防伪造 | `md5` 六份工件互异；baseline.xml≠verify.xml | 等长系巧合（耗时位数相同），无复制伪造 ✓ |
| h | 失败集合基线对照 | python 解析 verify.xml/baseline.xml | 双方 tests=1175 failures=11，失败集合差集**双向为空** → 11 个失败非本卡引入 ✓ |
| i | push 事实 | `git for-each-ref refs/remotes/origin` | `origin/codex/ccc087-pytest-data-dir-flake`=`f411c6ccd`=本地 HEAD ✓ |
| j | 引用工件抽查 | `docs/lessons.md:2358` | Lesson 57 存在且确载 conversation 族环境性失败（CCC_BRAIN_BASE_URL 依赖），回写区交叉引用属实 ✓ |

### 3 发现（均不阻断）

1. 【瑕疵·记录】round{1,2,3}.log 缺 pytest 最终计数行（`N failed, M passed in …`）；但 `[100%]` 终点 + FAILED 集合与 baseline 完全一致 + verify/baseline junitxml 权威计数交叉印证，实质结论不受影响。疑为运行器截尾，后续留证建议保留完整尾部。
2. 【残留隐患·范围外】同模式共享默认值仍在：`test_engine_scheduler.py:54-56` `_write_env` 仍硬编码 `/tmp/ccc2/{data,logs}`（执行体已在维护区 Q2 如实披露并建议另卡，本席确认属实）；另 ENGINE_PORT/BOARD_PORT/WEB_PORT 固定 8101/8102/8103 共享，若本机真实服务占用同端口仍可能偶发冲突（本席补充，建议随 scheduler 另卡一并评估）。均在白名单外，不在本卡处置。

### 4 severity 三级评分

影响面 1（仅测试夹具默认值，生产零触及）+ 改动深度 1（单文件 4 行实质变更）+ 红线邻近 1（不涉生产锁逻辑/安全/数据）= **3 分 → 轻**；无任一维度高危，不强升。

### 5 维护区四问核对（P1-b 机械判据）

四问均为合规单选：[否]/[无]/[否]/[否]，各附一句实情说明，无模板占位。抽查声明：Q1「关联为交接问题3 非方案编号」✓；Q2「lessons.md 不在白名单」✓、「scheduler 残留」✓（grep 属实）；Q3/Q4 与 diff 事实一致 ✓。**维护区通过**。

### 6 结论

机审：通过（被审 f411c6ccd7ff）
