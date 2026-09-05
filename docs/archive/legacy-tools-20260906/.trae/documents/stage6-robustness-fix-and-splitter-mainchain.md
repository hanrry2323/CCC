# 阶段 6：代码健壮性修复 + Splitter 主链路启用（开发计划）

> **状态**：待执行 · 基于 stage5 闭环验证埋点数据
> **基准**：stage5 5/5 released 验证通过，但观察到 4 类待优化问题
> **范围**：rc=247 冷启动 + retry budget 重置 + 自愈遥测 + Splitter 主链路启用

---

## 一、Summary

**基于 stage5 测试埋点观察到的 4 类问题，进行代码健壮性修复（warmup probe / retry budget 重置 / 自愈遥测 / 异常优雅降级）+ Splitter 主链路环境启用（SDK + CLI + token + relay），让 CCC 全流程从"fallback 可用"升级为"主链路可用 + 失败自愈可观测"。**

---

## 二、Current State Analysis（stage5 埋点观察）

### 2.1 已验证可用 ✅

| 项 | stage5 证据 |
|----|------------|
| R-14 stdin 传 prompt | 5/5 opencode 执行成功，无 SIGTERM |
| Fallback 拆卡 + scope 提取 | 5/5 fallback 拆卡成功，scope 正确 |
| Engine 串行调度 | 同仓 1 个 opencode，无资源竞争 |
| 自愈重投 + timeout 递增 | t4/t5 首次 rc=247 → relaunch → 成功 |
| 验收探针 + 浮点容差 | 5/5 验收通过 |

### 2.2 待修复问题 ❌

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| P1 | rc=247 冷启动失败 | t4/t5 首次必失败，浪费 1 轮 retry | opencode 冷启动 >300s，无 warmup，rc=247 无特殊处理 |
| P2 | retry_count 永不重置 | 旧任务 budget 8/8 耗尽后永久死亡 | _task_reopen.py 只重置 review_fail_loops，不重置 retry_count |
| P3 | 自愈日志分散 | 排查需 grep engine.log 多关键词 | 无独立 recover.log，_task_reopen logger 未挂 file handler |
| P4 | Splitter 全走 fallback | 主链路从未跑通 | claude-agent-sdk 未装 + claude CLI 缺失 + token 缺失 |
| P5 | Splitter 异常不降级 | ClaudeCliMissing 让 splitter 直接 failed | _run_fanout 未 catch 异常走 fallback |
| P6 | short_path testing 列遗漏 | testing 列短路径失败不可见 | _handle_short_path_failure 只处理 in_progress/planned |

---

## 三、Proposed Changes（5 个 Work Package）

### WP1：rc=247 冷启动修复（warmup probe + cold_start bucket）

**目标**：消除 opencode 冷启动 rc=247 失败，让首次执行即可成功。

#### WP1.1：新增 warmup probe 函数

**文件**：`scripts/opencode-exec.py`
**位置**：在 `run_opencode` 函数（L199）之前插入

**改动**：
```python
async def _warmup_opencode(opencode_bin: str, model: str, cwd: Path) -> bool:
    """R-WARMUP: opencode 冷启动预热 — 跑极短 prompt 让模型加载/session 初始化。

    带 30s 短超时，失败静默（不阻塞主流程）。
    成功后 opencode 后续启动走热路径，避免 rc=247。
    """
    try:
        warmup_cmd = build_opencode_run_cmd(
            opencode_bin, model, message="ok", cwd=cwd
        )
        proc = await asyncio.create_subprocess_exec(
            *warmup_cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
        )
        await asyncio.wait_for(proc.wait(), timeout=30)
        _log.info("[warmup] ok (rc=%s)", proc.returncode)
        return True
    except (TimeoutError, asyncio.CancelledError):
        _log.warning("[warmup] timeout (30s)，继续主流程")
        try:
            await _kill_process_group(proc.pid, __import__("signal").SIGKILL)
        except Exception:
            pass
        return False
    except Exception as exc:
        _log.warning("[warmup] 失败: %s，继续主流程", exc)
        return False
```

**调用点**：在 `run_opencode` 函数的 `proc = await asyncio.create_subprocess_exec(...)` 之前（L265 附近），当 `_use_stdin and full_prompt` 时调用：
```python
if _use_stdin and full_prompt:
    await _warmup_opencode(opencode_bin, model, cwd)
```

#### WP1.2：cold_start bucket

**文件**：`scripts/_failure_buckets.py`
**位置**：`classify_failure_bucket` 函数（L12-56），在 `dirty_block` 分支之前插入

**改动**：
```python
# R-COLD: opencode 冷启动 rc=247 优先识别
if "rc=247" in low or "cold_start" in low or "cold start" in low:
    return "cold_start"
```

在 `bucket_optimize_hints` 函数中增加：
```python
if bucket == "cold_start":
    return [
        "首次启动超时，下次重试前先 warmup",
        "timeout 抬到 600s+",
        "检查 relay :4002 连接稳定性",
    ]
```

#### WP1.3：rc=247 显式识别

**文件**：`scripts/opencode-exec.py`
**位置**：`run_opencode` 成功路径返回 result 处（L341-350）

**改动**：在 `result = {...}` 之后增加 cold_start 标记：
```python
if proc.returncode == 247:
    result["cold_start"] = True
    _log.warning("[opencode] rc=247 cold-start timeout detected")
```

**文件**：`scripts/opencode-runner.sh`
**位置**：RC 判断处（L76-80 附近）

**改动**：增加 247 分支：
```bash
elif [ $RC -eq 247 ]; then
    python3 -c "import json; json.dump({'error':'opencode cold-start timeout','rc':247,'cold_start':True}, open('$RESULT_FILE','w'))"
```

#### WP1.4：relaunch retry>=1 即放宽 timeout

**文件**：`scripts/board/roles/dev.py`
**位置**：`dev_role_relaunch` 的 bucket-aware 切换（L941-948）

**改动**：将 `retry_count >= 2` 改为 `retry_count >= 1`：
```python
# R-WARMUP: 首次重试即放宽（retry>=1），不再等 retry>=2
if bucket == "timeout" and retry_count >= 1:
    ...
    timeout_s = int(timeout_s * 1.5)
    bucket_applied = True
elif bucket == "cold_start" and retry_count >= 1:
    # cold_start bucket：切短 prompt + warmup + 放宽 timeout
    prompt = _compose_compact_phase_prompt(task_id, cur_phase, plan_content)
    timeout_s = max(timeout_s, 600)
    bucket_applied = True
elif bucket == "reviewer_timeout" and retry_count >= 1:
    ...
```

---

### WP2：retry budget 重置 + 自愈遥测

**目标**：让 retry_count 可重置，让自愈日志可独立排查。

#### WP2.1：reopen 时重置 retry_count

**文件**：`scripts/_task_reopen.py`
**位置**：`reopen_task` 函数的 `reset_fail_loops` 分支（L117-121）

**改动**：在重置 `review_fail_loops` 的同时重置 `retry_count`：
```python
if reset_fail_loops:
    try:
        store.patch_task(task_id, {
            "review_fail_loops": 0,
            "retry_count": 0,  # R-RESET: 同步重置 retry budget
        })
        _log.info("reset retry_count=0 for %s", task_id)
    except Exception as exc:
        _log.warning("reset review_fail_loops/retry_count %s: %s", task_id, exc)
```

#### WP2.2：新增 recover.log 独立日志

**文件**：`scripts/ccc-engine.py`
**位置**：日志配置处（L196 附近，`add_file_handler("engine", ...)` 之后）

**改动**：
```python
add_file_handler("engine.recover", "~/.ccc/logs/recover.log", ...)
```

**文件**：`scripts/engine/_recover_retry_impl.py`、`scripts/engine/failure_router.py`（budget 路径）、`scripts/engine/_results_impl.py`（budget 路径）、`scripts/engine/hang.py`（budget 路径）

**改动**：在这些文件的自愈/budget 关键路径增加独立 logger：
```python
_recover_log = get_logger("engine.recover")
# 在 budget 耗尽、reopen、auto-refeed 关键节点用 _recover_log.info(...)
```

#### WP2.3：_task_reopen.py 日志落盘

**文件**：`scripts/ccc-engine.py`（L196 附近）

**改动**：增加 task_reopen 的 file handler：
```python
add_file_handler("task_reopen", "~/.ccc/logs/reopen.log", ...)
```

#### WP2.4：_handle_short_path_failure 处理 testing 列

**文件**：`scripts/engine/_results_impl.py`
**位置**：`_handle_short_path_failure` 的 move 逻辑（L190-197 附近）

**改动**：将 move 逻辑扩展为包含 testing 列（与 `_handle_acceptance_fail_budget` 的 R-10 对齐）：
```python
if col_now in ("in_progress", "planned", "testing"):  # R-TESTING: 增加 testing
    store.move_task(task_id, col_now, "abnormal")
```

#### WP2.5：.short_path_fails 显式清理

**文件**：`scripts/_task_reopen.py`
**位置**：`_PID_SUFFIXES` 列表（L20-40）

**改动**：增加 `".short_path_fails"` 后缀：
```python
".short_path_fails",  # R-CLEAN: 与 .acceptance_fails 对称
```

#### WP2.6：耗尽关键词统一

**文件**：`scripts/_failure_buckets.py`
**位置**：文件末尾新增导出常量

**改动**：
```python
EXHAUST_MARKERS = (
    "fail_loop_exhausted", "重试耗尽", "次全部失败",
    "retry budget exceeded", "budget 耗尽",
    "acceptance_fail_budget", "max_retry",
    "滞留", "stale_inflight",
    "plan_lint", "phase graph",
)
```

**文件**：`scripts/engine/failure_router.py`
**位置**：`_EXHAUSTED_KEYWORDS`（L143-161）

**改动**：改为从 `_failure_buckets` 导入：
```python
from _failure_buckets import EXHAUST_MARKERS as _EXHAUSTED_KEYWORDS
```

---

### WP3：Splitter 异常优雅降级 + Hub 前置自检

**目标**：让 Splitter 主链路任何异常都优雅降级到 fallback，而非直接 failed。

#### WP3.1：_run_fanout 异常走 fallback

**文件**：`scripts/ccc-intent-splitter.py`
**位置**：`_run_fanout` 函数（L257-315），`sess = run_contract_loop_sync(...)` 调用处（L276 附近）

**改动**：用 try/except 包裹主链路调用：
```python
try:
    sess = run_contract_loop_sync(
        prompt=prompt, workspace=workspace, task_id=epic["id"],
        mode="epic", model="flash",
        validate_fn=_validate_epic,
        gate_fn=_gate_epic,
    )
except Exception as exc:
    _log.warning("splitter 主链路异常 (%s)，走 fallback", exc)
    return _fallback_create_work(
        store, epic, workspace, proposal_id,
        main_chain_error=str(exc)[:200],
    )
if not sess.get("ok"):
    _log.warning("splitter 主链路失败 (%s)，走 fallback", sess.get("error", "")[:80])
    return _fallback_create_work(
        store, epic, workspace, proposal_id,
        main_chain_error=sess.get("error", ""),
    )
```

#### WP3.2：_fallback_create_work 接收 main_chain_error

**文件**：`scripts/ccc-intent-splitter.py`
**位置**：`_fallback_create_work` 函数签名（L318 附近）

**改动**：增加 `main_chain_error: str = ""` 参数，并写入审计结果：
```python
def _fallback_create_work(
    store, epic, workspace, proposal_id,
    main_chain_error: str = "",
) -> dict:
    ...
    return {
        "ok": True,
        "child_ids": [work_id],
        "claude_session_id": "",
        "fallback": True,
        "main_chain_error": main_chain_error,  # R-TRACE: 主链路失败原因
        ...
    }
```

#### WP3.3：Hub 前置自检

**文件**：`scripts/chat_server/services/intent_proposals.py`
**位置**：`trigger_splitter` 函数（L163-205），`subprocess.Popen` 之前

**改动**：增加主链路前置探测，探测失败时写入 result 但仍启动子进程（让 fallback 处理）：
```python
# R-CHECK: 主链路前置探测（不阻塞，仅记录）
main_chain_ready = True
main_chain_error = ""
try:
    import claude_agent_sdk  # noqa: F401
except ImportError:
    main_chain_ready = False
    main_chain_error = "claude-agent-sdk not installed"
try:
    from _claude_cli import resolve_claude_cli
    resolve_claude_cli(require=False)
except Exception as exc:
    main_chain_ready = False
    main_chain_error = f"{main_chain_error}; claude cli: {exc}" if main_chain_error else str(exc)

if not main_chain_ready:
    append_result(
        workspace_root, proposal_id,
        {"status": "warning", "main_chain": "not_ready", "error": main_chain_error},
    )
```

---

### WP4：Splitter 主链路环境启用

**目标**：安装主链路依赖，让 Splitter 从 fallback 升级为主链路拆卡。

#### WP4.1：安装 claude-agent-sdk

**命令**（在 2017 端执行）：
```bash
cd ~/program/CCC
pip3 install -r requirements-hub.txt
# 验证
python3 -c "from claude_agent_sdk import ClaudeSDKClient; print('ok')"
```

#### WP4.2：部署 claude CLI

**命令**（在 2017 端执行）：
```bash
# 方案 A：npm 全局安装
npm install -g @anthropic-ai/claude-code
# 验证
which claude && claude --version

# 或方案 B：设 CCC_CLAUDE_BIN 指向已有二进制
# export CCC_CLAUDE_BIN=/path/to/claude
```

**配置**：确保 Hub launchd plist 的 PATH 含 `~/.npm-global/bin`（`_sanitized_env` 已通过 `claude_path_prefixes` 尽力补，但 launchd 启动时需确认）。

#### WP4.3：配置 anthropic token

**命令**（在 2017 端执行）：
```bash
# 从 ~/.claude/settings.json 读取 token 写到 ~/.ccc/anthropic-auth-token
python3 -c "
import json, os
from pathlib import Path
src = Path.home() / '.claude' / 'settings.json'
dst = Path.home() / '.ccc' / 'anthropic-auth-token'
if src.exists():
    data = json.loads(src.read_text())
    token = data.get('ANTHROPIC_AUTH_TOKEN', '')
    if token:
        dst.write_text(token)
        os.chmod(dst, 0o600)
        print(f'token written to {dst}')
    else:
        print('no ANTHROPIC_AUTH_TOKEN in settings.json')
else:
    print(f'{src} not found')
"
```

#### WP4.4：验证 relay:4000

**命令**（在 2017 端执行）：
```bash
# 检查 relay 进程
ps aux | grep -i relay | grep -v grep
# 检查 :4000 端口
lsof -iTCP:4000 -sTCP:LISTEN
# 探活
curl -s http://127.0.0.1:4000/health 2>/dev/null | head -5
```

若 relay 未运行，启动：
```bash
launchctl load ~/Library/LaunchAgents/com.ccc.relay.2017.plist 2>/dev/null
# 或手动启动
cd ~/program/CCC && python3 scripts/ccc-relay-2017.py &
```

#### WP4.5：验证主链路端到端

**命令**（在 2017 端执行）：
```bash
cd ~/program/CCC
# 验证主链路前置条件
python3 -c "
import claude_agent_sdk; print('SDK: ok')
from _claude_cli import resolve_claude_cli; print('CLI:', resolve_claude_cli(require=True))
from pathlib import Path; print('Token:', Path.home() / '.ccc' / 'anthropic-auth-token' exists)
"
# 提交一个 smoke 方案验证主链路
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb --wait
# 检查 result.jsonl 中 fallback 字段
cat /Users/fan/program/apps/qb/.ccc/intent-proposals/prop-*.result.jsonl | python3 -m json.tool
# 预期：fallback: false, claude_session_id 非空
```

---

### WP5：其他健壮性修复

#### WP5.1：fallback scope 扩展

**文件**：`scripts/ccc-intent-splitter.py`
**位置**：`_extract_scope_from_md`（L210-232）和 `_extract_paths_from_acceptance`（L235-254）

**改动**：扩展正则匹配的文件扩展名：
```python
# 当前只识别 .py|.md|.sh|.json|.yaml|.yml|.txt|.toml
# 扩展为：增加 .ts|.js|.go|.rs|.java|.c|.cpp|.h|.vue|.css|.html
_EXT_RE = re.compile(
    r'[A-Za-z0-9_./\-]+\.(?:py|md|sh|json|yaml|yml|txt|toml|ts|js|go|rs|java|c|cpp|h|vue|css|html)'
)
```

#### WP5.2：fallback 跳过冗余 _attach_skill_version

**文件**：`scripts/ccc-intent-splitter.py`
**位置**：`main` 函数中 `_attach_skill_version` 调用处（L537 附近）

**改动**：当 fallback 为 True 时跳过冗余调用：
```python
fr = _run_fanout(...)
# R-DEDUP: fallback 子卡 note 已自带 skill_ref/prompt_ref，跳过冗余 attach
if not fr.get("fallback"):
    _attach_skill_version(store, epic["id"], fr.get("child_ids", []))
```

---

## 四、Assumptions & Decisions

### Assumptions
1. 2017 端 Python 3.12 环境可安装 claude-agent-sdk（pip 可用）
2. npm 全局安装 claude CLI 可行（或已有 claude 二进制）
3. `~/.claude/settings.json` 中存在有效的 `ANTHROPIC_AUTH_TOKEN`
4. CCC Relay :4000 可启动（plist 存在）
5. 2017 端代码已含 R-1~R-14 全部修复（stage5 已验证）

### Decisions
1. **warmup probe 策略**：用户选择 warmup probe（而非仅 timeout 下限），需在 opencode-exec.py 新增 `_warmup_opencode` 函数
2. **retry_count 重置时机**：在 `_task_reopen.py` 的 `reset_fail_loops` 分支同步重置（而非新增独立参数），保持 reopen 语义一致
3. **Splitter 异常降级**：用 try/except 包裹 `run_contract_loop_sync`，异常时走 fallback 而非 failed
4. **自愈日志**：新增 `recover.log` + `reopen.log` 两个独立文件，不改动现有 engine.log 结构
5. **WP4 依赖外部环境**：SDK/CLI/token 安装可能失败，WP1-WP3 代码修复不依赖 WP4 完成

---

## 五、Verification Steps

### 5.1 WP1-WP3 代码修复验证（不依赖 WP4）

```bash
# 1. 单元测试
cd ~/program/CCC
pytest tests/ -x -k "failure_bucket or task_reopen or recover or splitter"

# 2. 清理 stage5 数据
python3 -c "
# 清理 qb board 中的 prop-2026* 任务 + retry budget
...
"

# 3. 重新提交 5 个 stage5 任务
for f in docs/intent-proposals/stage5-t{1,2,3,4,5}-*.md; do
  python3 scripts/ccc-submit-proposal.py \"$f\" --project qb
  sleep 2
done

# 4. 验证 t4/t5 首次执行不再 rc=247（warmup 生效）
# 预期：5/5 首次即成功，0 次 relaunch
tail -f ~/.ccc/logs/ccc-engine.log | grep -E "rc=247|warmup|relaunch"

# 5. 验证自愈日志独立可查
cat ~/.ccc/logs/recover.log | tail -20
cat ~/.ccc/logs/reopen.log | tail -20
```

### 5.2 WP4 主链路启用验证

```bash
# 1. 验证前置条件
python3 -c "import claude_agent_sdk; print('SDK ok')"
which claude && claude --version
test -f ~/.ccc/anthropic-auth-token && echo "Token ok"
curl -s http://127.0.0.1:4000/health

# 2. 提交 smoke 方案，验证主链路
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb --wait

# 3. 检查 result.jsonl
# 预期：fallback: false, claude_session_id 非空
cat /Users/fan/program/apps/qb/.ccc/intent-proposals/prop-*.result.jsonl | python3 -m json.tool
```

### 5.3 全链路闭环验证

```bash
# 提交 5 个任务，全程监控
for f in docs/intent-proposals/stage5-t{1,2,3,4,5}-*.md; do
  python3 scripts/ccc-submit-proposal.py \"$f\" --project qb
  sleep 2
done

# 监控 board 状态
watch -n 10 'ssh mac2017 "cd ~/program/CCC && python3 -c \"
import sys; sys.path.insert(0,\\\"scripts\\\")
from _board_store import FileBoardStore
from pathlib import Path
s = FileBoardStore(Path(\\\"/Users/fan/program/apps/qb\\\"))
for col in [\\\"released\\\",\\\"in_progress\\\",\\\"planned\\\",\\\"abnormal\\\"]:
    ts = [t for t in s.list_tasks(col) if \\\"prop-2026\\\" in t.get(\\\"id\\\",\\\"\\\")]
    print(f\\\"[{col}] {len(ts)}\\\")
\""'

# 验收标准：
# 1. 5/5 released（0 abnormal）
# 2. t4/t5 首次即成功（0 relaunch）— warmup 生效
# 3. recover.log + reopen.log 有内容
# 4. result.jsonl 中 fallback=false（主链路启用后）
```

### 5.4 回归验证

```bash
# 全量测试
pytest tests/ -x

# Engine 日志无 ERROR
grep -c "ERROR" ~/.ccc/logs/ccc-engine.log
```

---

## 六、执行顺序

```
WP1 (rc=247 warmup) ──┐
WP2 (budget+遥测) ────┼─→ 5.1 代码修复验证 ──→ 5.3 全链路验证
WP3 (Splitter降级) ───┘
                                           WP4 (主链路启用) ──→ 5.2 主链路验证
WP5 (其他健壮性) ─────→ 随 WP1-3 一起验证
```

WP1-WP3 + WP5 可并行开发，WP4 依赖外部环境操作可独立进行。
