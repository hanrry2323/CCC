# Plan: onboard-clawcinema-runner — 注册 ClawCinema 为 ExternalCLIRunner

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：
  - `app/agents/runner.py` — AgentRunner 注册表（`AGENT_RUNNERS` dict），已含 `ExternalCLIRunner` 类、`register_runner()` / `get_runner()` 函数，以及 qb 的 lazy import 注册模式（lines 414-422）
  - `tests/test_multi_agent.py` — 通过 `register_runner()` 做集成测试（含 `test_register_runner` 示例）
  - `tests/test_qb_runner.py` — qb runner 的独立测试文件，含 dispatch 路径验证
  - `tests/test_runner_registry.py` — **尚不存在**，需新建

- **当前结构要点**：
  - `AGENT_RUNNERS` 当前注册 3 个 key：`"be-dev"`（ClaudeAgentRunner）、`"be-qa"`（ClaudeAgentRunner）、`"be-stub"`（StubAgentRunner），外加 try/except 内的 `"qb"`（QbAgentRunner）
  - `ExternalCLIRunner` 已完整实现（`run()` 方法含 EXECUTE/EVALUATE 阶段 + FileNotFoundError/TimeoutExpired 错误处理）
  - ClawCinema CLI binary 不存在于磁盘（`~/program/clawcinema/` 和 `/Users/apple/bin/claw-cinema` 均无），按 roadmap 期望路径为 `/Users/apple/bin/claw-cinema`，args `["render"]`
  - `tests/test_qb_runner.py` 可作为 `test_runner_registry.py` 的编写参考（注册验证 + dispatch 验证 + 错误路径验证）

- **待改动点**：
  - `app/agents/runner.py:416-422` — 追加 clawcinema 注册入口（同 qb 的 try/except 模式，或直接注册 ExternalCLIRunner 实例）
  - `tests/test_runner_registry.py`（新建）— 注册验证 + dispatch 路径验证 + 非存在 binary 错误处理验证

---

## 范围

- **目标**：注册 ClawCinema 影视墙为 `ExternalCLIRunner`，创建 dispatch 验证测试，确认错误路径处理正确
- **只改文件**：
  - `app/agents/runner.py`
  - `tests/test_runner_registry.py`（新建）
- **不改文件**：
  - `app/agents/__init__.py`
  - `app/core/` 下任何文件
  - `tests/test_multi_agent.py`（保持现有集成测试不受影响）
  - 任何其他文件
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：注册 ClawCinema runner + 创建测试

### 做什么
在 `app/agents/runner.py` 中，在 qb 注册入口后追加 ClawCinema 的 `ExternalCLIRunner` 注册。ClawCinema 项目当前不存在于磁盘，故用 try/except 保证不阻塞主流程（同 qb 模式）。同时创建 `tests/test_runner_registry.py`，覆盖注册验证 + dispatch 路径验证 + 错误路径（binary 不存在时的 FileNotFoundError）验证。

由于 `ExternalCLIRunner` 自身已处理 `FileNotFoundError`（返回 `code: "non-retry"` 的 error message），且无需项目级 import，注册可直接实例化而非依赖模块导入。

### 怎么做

**1. `app/agents/runner.py`** — 在 qb 注册段（line 422 的 `pass` 之后）追加：

```python
# ── V9.S1b clawcinema runner registration (ExternalCLIRunner) ─
try:
    AGENT_RUNNERS["clawcinema"] = ExternalCLIRunner(
        name="clawcinema",
        cli_path="/Users/apple/bin/claw-cinema",
        args=["render"],
    )
except Exception:
    pass
```

位置：紧接在 `# qb_runner 注册失败不应阻塞主流程` 的 `pass` 之后（line 422 → 423 新行），`def register_runner()` 之前（line 424）。

**2. `tests/test_runner_registry.py`（新建）** — 写入完整测试类 `TestClawCinemaRunnerRegistry`：

```python
"""Tests for ClawCinema runner registration in the Agent Runner registry.

V9.S1b: Verifies that:
  - clawcinema is registered in AGENT_RUNNERS
  - get_runner("clawcinema") returns an ExternalCLIRunner instance
  - dispatch with non-existent binary returns non-retry error
  - register_runner() can override the clawcinema runner
"""

from __future__ import annotations

import pytest

from app.agents.runner import AGENT_RUNNERS, ExternalCLIRunner, get_runner, register_runner


class TestClawCinemaRunnerRegistry:
    """ClawCinema runner registration and dispatch path verification."""

    def test_clawcinema_registered(self):
        """clawcinema key must exist in AGENT_RUNNERS."""
        assert "clawcinema" in AGENT_RUNNERS, (
            "clawcinema runner not registered in AGENT_RUNNERS"
        )

    def test_clawcinema_is_external_cli_runner(self):
        """get_runner('clawcinema') must return an ExternalCLIRunner instance."""
        runner = get_runner("clawcinema")
        assert isinstance(runner, ExternalCLIRunner), (
            f"expected ExternalCLIRunner, got {type(runner).__name__}"
        )
        assert runner.name == "clawcinema"

    def test_clawcinema_default_config(self):
        """The default cli_path and args must match roadmap spec."""
        runner = get_runner("clawcinema")
        assert runner.cli_path == "/Users/apple/bin/claw-cinema"
        assert runner.args == ["render"]
        assert runner.timeout == 300  # default

    @pytest.mark.asyncio
    async def test_dispatch_binary_not_found_returns_error(self):
        """Dispatch when binary doesn't exist must return non-retry error."""
        runner = get_runner("clawcinema")
        task = {"id": "test-001", "exec_prompt": "render scene 5", "workspace": "/tmp"}
        errors = []
        async for msg in runner.run(task):
            if msg.type == "error":
                errors.append(msg)
        assert len(errors) >= 1, "expected at least one error message"
        # ExternalCLIRunner raises FileNotFoundError → code "non-retry"
        error_codes = {e.payload.get("code") for e in errors}
        assert "non-retry" in error_codes, (
            f"expected non-retry error code, got {error_codes}"
        )
        # Verify the error message mentions the binary path
        error_msgs = [e.payload.get("message", "") for e in errors]
        assert any("claw-cinema" in m for m in error_msgs), (
            "error message should reference the binary path"
        )

    def test_register_runner_can_override(self):
        """register_runner() must be able to override clawcinema runner."""
        custom = ExternalCLIRunner(name="clawcinema-test", cli_path="/tmp/test-cli")
        register_runner("clawcinema", custom)
        runner = get_runner("clawcinema")
        assert runner.name == "clawcinema-test"
        assert runner.cli_path == "/tmp/test-cli"
        # Restore original for other tests
        register_runner("clawcinema", ExternalCLIRunner(
            name="clawcinema",
            cli_path="/Users/apple/bin/claw-cinema",
            args=["render"],
        ))
```

**不做**：不动 `app/agents/__init__.py`、不动 `app/core/` 下任何文件、不动 `tests/test_multi_agent.py`。

### 验收清单

- [ ] `AGENT_RUNNERS["clawcinema"]` 注册在 `runner.py` qb 注册段之后
- [ ] `get_runner("clawcinema")` 返回 `ExternalCLIRunner` 实例
- [ ] 默认 `cli_path` = `/Users/apple/bin/claw-cinema`，`args` = `["render"]`
- [ ] dispatch 到不存在 binary 返回 `code: "non-retry"` 错误
- [ ] `register_runner()` 可覆盖 clawcinema 注册
- [ ] `test_runner_registry.py` 新建文件中 5 个 test case 全部通过
- [ ] compileall 零错误
- [ ] 现有测试（`test_multi_agent.py`、`test_qb_runner.py`）不受影响
- [ ] diff 范围仅限 `runner.py` + `test_runner_registry.py`

### 验收

- [clawcinema 已注册]（参考：`python3 -c "from app.agents.runner import AGENT_RUNNERS; print('clawcinema' in AGENT_RUNNERS)"` → True）
- [返回 ExternalCLIRunner]（参考：`python3 -c "from app.agents.runner import get_runner, ExternalCLIRunner; r=get_runner('clawcinema'); print(isinstance(r, ExternalCLIRunner))"` → True）
- [默认配置正确]（参考：`python3 -c "from app.agents.runner import get_runner; r=get_runner('clawcinema'); print(r.cli_path, r.args)"` → `/Users/apple/bin/claw-cinema ['render']`）
- [compileall 零错]（参考：`python3 -m compileall -q app/ tests/` → exit code 0）
- [pytest 全部通过]（参考：`uv run pytest tests/test_runner_registry.py -q -x` → passed）
- [现有测试不受影响]（参考：`uv run pytest tests/ -q --ignore=tests/e2e -x` → passed）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | runner.py 注册 clawcinema + 新建 test_runner_registry.py | `feat(agents): register ClawCinema as ExternalCLIRunner + dispatch verification tests (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表（2 文件：1 修改 + 1 新增）
- [ ] 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（1）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

ClawCinema 注册完成后（占位状态），后续步骤：
1. ClawCinema 项目上线后，安装 `/Users/apple/bin/claw-cinema` CLI binary
2. 届时 `try/except` 自动成功注册，无需改代码
3. 如需自定义运行逻辑（非纯 CLI 调用），可参考 `QbAgentRunner` 创建 `ClawCinemaAgentRunner` 子类
4. 同步注册 xianyu runner（Phase 15 `onboard-xianyu-runner`）使用同模式
