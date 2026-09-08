# 批D执行报告 · 硬编码抽配置（行为等价重构）2026-09-04

> 指令：`/Users/fan/.ccc/instructions/2026-09-04-align-batchD.md`
> 执行窗口：CCC 产线修复窗口 · 全程 `/Users/fan/program/CCC`（权威仓）
> 性质：硬编码抽配置；**行为等价**（默认值=现值，生产行为零变化）；项6 为明确的观测面行为变更（OpenCode 探测退役）
> 开工基线 `b01164b14` → 收尾 head `3d408b00f`（6 笔 commit，逐笔 push）
> 门禁：全量 `pytest server/tests/` **1385 passed** + `ruff check server/` 净

## 一、改动清单（对指令逐项）

| 项 | 文件 | 改前 | 改后取值路径 | 行为 |
|----|------|------|--------------|------|
| 1 | `server/engine/dsh_gateway.py:30-31` | 模块常量 `ANTHROPIC_BASE_URL=http://127.0.0.1:3456/v1/messages`、`ANTHROPIC_MODEL=Code` | env `DSH_PROBE_URL`/`DSH_PROBE_MODEL` → config.env（loader OPTIONAL_KEYS 已有）→ 回退常量 | 等价（config.env 现值=常量） |
| 2 | `server/web/wall.py:553` | `f"http://127.0.0.1:3080/api/{method}"` | `os.environ.get("CCC_DSH_WEB_URL", "http://127.0.0.1:3080/api/")` | 等价（env 缺省=现值） |
| 3 | `server/web/server.py`（KNOWN_SERVICES ×2 + PORTALS 三处内嵌表） | 双份 KNOWN_SERVICES + PORTALS 内嵌 | 新建 `server/config/ops-nodes.json` 单一来源 + `server/config/ops_nodes.py` 加载函数（文件缺失/损坏回落内嵌默认表=现值） | 结构等价（`/ops/summary` 相关端点结构不变，ops 定向测试绿） |
| 4 | `server/engine/scheduler.py:332-336` | `/Users/fan`、`fan@192.168.3.116`、`/Users/fan/.dsh/run_patrol.sh` | env `CCC_M2_DEPLOY_HOME`/`CCC_SSH_TARGET`/`CCC_PATROL_SCRIPT`（默认=现值） | 等价 |
| 5 | `server/board/registry.py:255` | `startswith("/Users/fan/program/")` | env `CCC_WORKTREE_ROOT_PREFIX`（默认=现值） | 等价 |
| 6 | `server/engine/observer.py:1228-1262,1466,1489,1577` | 巡查探测 `~/.config/opencode/opencode.json` + `opencode_mcp_enabled` 字段 | 探测段移除；字段从 mcp 指标字典移除；报告/摘要保留「OpenCode 通道：已退役（2026-09-02 通道退役）」说明 | **观测面行为变更**（按指令），定向测试同步 |
| 7 | `scripts/dsh-auditor.sh` / `scripts/dsh-executor.sh` | — | 批C 已 `$HOME`/`_SELF` 化；本批复核两脚本**零残余**绝对路径/IP/`user@host`（grep 实证） | 无需改动 |

## 二、commit 列表（6 笔，均已 push origin main）

| commit | 项 | 说明 |
|--------|-----|------|
| `8ac01f38f` | 1 | refactor(config): single-source gateway channel via DSH_PROBE_* keys |
| `16ef7a7df` | 2 | refactor(config): DSH web RPC base URL via CCC_DSH_WEB_URL env |
| `9b4915cc5` | 3 | refactor(config): single-source ops nodes table via ops-nodes.json |
| `ad8f3abed` | 4 | refactor(config): scheduler DSH patrol trigger via CCC_* env keys |
| `b0063fc97` | 5 | refactor(config): registry worktree root prefix via CCC_WORKTREE_ROOT_PREFIX |
| `3d408b00f` | 6 | refactor(observer): retire OpenCode MCP probe |

## 三、loader.py 键白名单（红线）履行

新增配置键无 —— 项1 复用既有 `DSH_PROBE_URL`/`DSH_PROBE_MODEL`（OPTIONAL_KEYS 已有）；
项2/4/5 走 `os.environ.get` 运行时取 env，不经 loader，不涉及白名单。
loader 白名单未新增键（无需同步 OPTIONAL_KEYS）。

## 四、验证

- 定向：`test_dsh_gateway.py` 14 绿；`test_engine_scheduler.py` 12 绿；`test_project_registry.py` 11 绿；
  `test_observer.py`（含 2 条退役回归：`'opencode_mcp_enabled' not in metrics` + 不探测 OpenCode 路径）34 绿；
  `test_http_api.py -k ops` 17 绿。
- 取值路径实证（项1）：env←config.env←常量三条路径均解析出 `http://127.0.0.1:3456/v1/messages · Code`（脚本核验）。
- 项2 实证：默认 `http://127.0.0.1:3080/api/status`、env 覆盖 `http://192.168.3.116:3080/api/status`（stub urlopen 截获）。
- 项3 实证：`load_known_services()`/`load_portals()` 结构与旧内嵌表逐项相等。
- 全量：`pytest server/tests/ -q` → **1385 passed**；`ruff check server/` → **All checks passed**。

## 五、引擎重启记录

- 改前 pid：`11901`
- `launchctl kickstart -k gui/$(id -u)/com.ccc.engine` → 新 pid：**`78771`**（启动 2026-09-05 03:12:29）
- 心跳：新进程段（log 行 144644 起）持续 `heartbeat: {"mode": "loop", ...}` 正常。
- phase2：`consume_once` 每个循环轮调用；新进程段无 `phase2 消费异常`/Traceback（无待消费卡，summary 全零不落日志）。
- 实测项6 已上线：新进程生成的 `observation-2026-09-05.md` 含「**OpenCode 通道：已退役（2026-09-02 通道退役）**」，不再含 `opencode_mcp_enabled`。

## 六、边界与说明

- 项6 是**观测面行为变更**（指令明示）：报告丢弃 OpenCode 配置状态实时探测，改退役常亮说明；消费方（结论判定、`--once` 摘要）同步改用仅 Claude Code 配置。报告消费方无外部引用（仅 archived backlog 历史值，不改）。
- 项7 复核为「批C 已覆盖、无残余」——本批零代码改动项。
- 引擎内部 scheduler 巡检（loop-observer 等）在新进程段运行正常。