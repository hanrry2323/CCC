# P3 完成报告 · v2.0 环境声明式（env-manifest + 测试命令声明化）

> 日期：2026-09-07 · 指令：`/Users/fan/.ccc/instructions/2026-09-07-p3-env-manifest.md`
> 目标仓：`/Users/fan/program/CCC` · 交付头部：见本报告末尾

## 结论

P3 全部改动落地并验证：**全量 pytest 1459 passed（基线 1447，净 +12）+ 2 skipped，ruff 净**。
环境依赖由「执行体现场解决、每张卡重新踩坑」改为「派发前声明化校验 + 缺失 FAIL_FAST 拦截」；
测试命令由「test-evidence 解析卡文本 + eval」改为「优先 env-manifest `test_entry` 以 argv 数组执行」。

## 改动清单（4 项，逐模块一波 commit+push）

### 1. env-manifest 声明文件
- 新建 `docs/projects/xy/env-manifest.json`：
  - `python_bin=.venv/bin/python`，`pytest_bin=.venv/bin/pytest`，`ruff_bin=.venv/bin/ruff`，
    `test_entry=.venv/bin/pytest tests/ -q`，`test_paths=["tests/"]`，`worktree_venv_source=.venv`。
  - 按 xianyu 业务仓（`/Users/fan/program/apps/xianyu`）只读核实填写：
    `.venv` 为真实目录（含 pytest 9.0.3 / ruff 0.16.1 / Python 3.12）；`.venv-hub` 不存在 → ruff 在 `.venv/bin`。
    P2 已前置 symlink 修复，本文件声明的是「验证入口」而非「创建入口」。

### 2. engine 派发前 fail-fast 校验
- 新建 `server/engine/env_manifest.py`：`load_manifest / manifest_path / validate_manifest`
  ——只读，不创建/修复/硬编码业务仓路径。校验以 symlink 展开后真实存在为准。
- `server/engine/main.py::_ensure_business_worktree`：挂载 `.venv` symlink 后，按
  `docs/projects/<prefix>/env-manifest.json` 校验 `python_bin`/`pytest_bin`/`ruff_bin`；
  缺失 = 派发前拒绝（FAIL_FAST，不拉起执行体，不现场修复），worktree 失败计数上浮，
  `audit_ledger.record_action("env_manifest_missing", …, failure_class="infra")` 落账。
- manifest 文件不存在 → 默认回退（`.venv/bin/pytest` + `.venv/bin/ruff`）只落 WARN 不拦截。

### 3. 测试命令声明化（test-evidence 告别 eval 解析卡文本）
- `scripts/test-evidence.sh`：命令来源优先级改为
  **env-manifest `test_entry`（shlex 拆分 argv 数组，不 eval）> 卡 `## 门禁` 文本解析（旧路径）**。
- from 前缀经卡路径 `docs/dispatch/<prefix>/` 推导 → `docs/projects/<prefix>/env-manifest.json`；
  `CCC_PROJECTS_DIR` 环境变量可覆盖（测试隔离）。
- 执行方式：argv 数组 `"${_ARGV[@]}"` 于 workdir 内执行，stdout/stderr/exit_code 照旧落证据日志。
- xy060 已关闭不重跑；后续新卡自然使用。

### 4. 测试
- 新增 `server/tests/test_env_manifest.py`（12 用例，tmp 模拟不碰真实业务仓）：
  - manifest 存在且 bin 齐 → pass；
  - manifest 缺失 → 默认回退，回退路径缺失仅 WARN 不拦截；
  - manifest 存在但 bin 路径无效 → FAIL_FAST 拒绝（`env_manifest_missing`），engine 集成双测。
- `tests/test_test_evidence.py` 扩 5 用例：`test_entry` 优先级/失败透传/空 entry 回退/缺 manifest 回退/非前缀卡忽略。

## 验证记录

| 项 | 结果 |
|---|---|
| 全量 pytest | **1459 passed, 2 skipped**（基线 1447+2，净 +12） |
| ruff check server/ tests/ | **All checks passed** |
| test-evidence argv 真实路径手动验证 | source=env_manifest，`./bins/run-tests.sh --flag 'quoted arg'` 引号参数完整（引用原样），卡文本回退不触发 |
| 真实 xy manifest 解析 | `entry=.venv/bin/pytest tests/ -q` 正确拾取并以 symlink .venv 执行（缺少 tests/ → pytest rc=4，透传正确） |
| /health | 200（重启前后） |

## 红线核对

- ✅ 不改 xianyu 业务仓（只读核实，零写入）
- ✅ 不改已关闭卡（xy060 不重跑）
- ✅ 不绕过 test-evidence（本项目改造其 argv 路径，eval 仅保留于无 manifest 回退场景）
- ✅ 不删任何现有测试（全量 1459 全绿）
- ✅ env-manifest 为新增可选文件（不存在 = 默认回退，不强制所有项目立即配备）

## 交付头部

```
P3-ENV-MANIFEST-DONE 89f8cacf6 46644
```