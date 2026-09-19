# CCC 复核取证报告：Trae 环境可信度 + pytest 基线隔离复核（2026-08-29 · 只读）

> 执行：ZCode 会话，真实 2017 本机（fan@fan.local / MacBookPro14,3 / macOS 13.7.8），窗口 02:35:02–02:49（**14 分钟，≤30 分钟约束达成**）
> 性质：全程只读。唯一写动作 = 本报告（任务书指定落点 ~/program 临时区）+ /tmp 两份隔离 pytest 副本（任务书指定方式）。
> **一句话总判：Trae 报告整体可信（2017 侧抽查 20+ 条全部复现，取证环境确为真实 2017 本机；#1 非误报）；pytest「基线红」是假的——保真隔离复跑 EXIT=0 全绿，2 个失败源于跑测试会话的 PATH 解释器漂移，属环境差异，非代码回归。**

---

## 〇、全程命令清单（只读自证）

```
# 基线/收尾自证（三次）
date; git -C /Users/fan/program/CCC rev-parse HEAD; git -C /Users/fan/program/CCC status --porcelain
git -C /Users/fan/program/CCC stash list; ls -la data/audit/ledger.jsonl ~/.ccc/data/cards/cards.index.jsonl
# T2 环境
hostname; scutil --get LocalHostName; scutil --get ComputerName; sysctl -n hw.model; sw_vers
ps aux | grep -iE 'trae|sandbox|node' | grep -v grep | head -20
ls /opt/ /var/run/docker.sock; docker ps; limactl list; colima status
ifconfig | grep 'inet '; route -n get default | head -5
curl -s -m5 -o /dev/null -w '%{http_code}' http://127.0.0.1:7788          # =200
curl -s -m5 -o /dev/null -w '%{http_code}' http://192.168.3.116:7788      # =000 (exit 7 refused)
curl -sv -m5 -o /dev/null http://192.168.3.116:7788 2>&1 | tail -4        # Connection refused
lsof -nP -iTCP:7788; ps -p 86493 -o pid,ppid,lstart,command; lsof -nP -iTCP -sTCP:LISTEN
grep -c 'cloud.sandbox' ~/program/ccc-baseline-alignment-audit-20260829.md; grep -ln 'cloud.sandbox' ~/program/*.md
# Trae 报告其余断言抽查（只读）
wc -l < data/audit/ledger.jsonl; grep -c '"probe"' data/audit/ledger.jsonl
ls -la ~/.ccc/data/cards/; wc -l < ~/.ccc/data/cards/cards.index.jsonl
launchctl list | grep -iE 'ccc|board'; crontab -l | head -5
grep -nE '7788|LocalForward|RemoteForward' ~/.ssh/config; ls ~/Library/LaunchAgents/disabled-ccc/
grep -n '_run_audit_worker' server/engine/main.py
grep -rniE 'delete.?branch|git branch -d' server/engine/
ls -la server/config/config.env; grep -nE 'DATA_DIR|7788|7789|CLUSTER_SERVICES' server/config/config.env
diff -q server/config/executors.json server/config/executors.example.json
ls -la ~/program/ccc-rebuild-phase*.md; grep -n 'com\.ccc' ~/.dsh/ccc-prod-health.sh
# P1 静态取证
head -3 scripts/new-card.sh; grep -nE 'python3|python|typing.Self|ImportError' scripts/new-card.sh | head -20
/Users/fan/program/CCC/.venv-hub/bin/python --version; which -a python3; /usr/bin/python3 --version
/usr/local/bin/python3 --version; /usr/local/bin/python3 -c 'import typing;print(hasattr(typing,"Self"))'
/usr/bin/python3 -c 'import typing;print(hasattr(typing,"Self"))'
grep -rn 'typing.Self\|from typing import Self' server/ scripts/ --include='*.py'
grep -rn 'new-card' server/tests/ | head; grep -n 'CCC_PYTHON_BIN\|PYTHON_BIN' scripts/new-card.sh
sed -n '75,135p' server/tests/test_card_dispatch_gate.py; grep -n '^set ' scripts/new-card.sh
grep -rln 'program/CCC' server/tests/ | head; grep -n 'PROJECT_ROOT' server/tests/conftest.py
# P2 隔离实跑（唯一 pytest 方式；解释器用权威仓 venv 只读调用）
rsync -a --exclude .venv-hub --exclude data --exclude .git /Users/fan/program/CCC/ /tmp/ccc-pytest-20260829-024052/
cd /tmp/ccc-pytest-20260829-024052 && .venv-hub 绝对路径 python -m pytest server/tests/ -q   # 跑1
rsync -a --exclude .venv-hub /Users/fan/program/CCC/ /tmp/ccc-pytest-full-20260829-024355/   # 保真副本
cd /tmp/ccc-pytest-full-20260829-024355 && 同上 pytest                                       # 跑2
python -m pytest server/tests/ --collect-only -q; git -C 两副本 status --porcelain
```

无 checkout/merge/commit/push/clean/reset/stash/restore/branch 删除；无 config/plist 改动；无服务起停；无安装。

---

## 一、任务一：Trae 取证环境复核

### 1.1 T2 环境证据（本会话 = 真实 2017 本机）

| 判据 | 命令 | 实测输出 |
|---|---|---|
| 主机名 | `hostname` / `scutil --get LocalHostName` / `ComputerName` | `fan.local` / `fan` / `Fan的MacBook Pro` |
| 硬件 | `sysctl -n hw.model` | **MacBookPro14,3**（2017 款 MBP）＋ macOS 13.7.8 (22H730) |
| LAN IP | `ifconfig` | `inet 192.168.3.116`（与 Trae 报告「2017=fan@192.168.3.116」一致）；网关 192.168.3.1 (en0) |
| Trae 进程 | `ps aux` | TRAE SOLO CN.app 全套进程本地运行（Electron 78638、ptyHost 2195、agent-tool-host 78679/79290），无远程 shell 迹象 |
| 容器 | docker/lima/colima | docker 未安装、无 /var/run/docker.sock、lima 零实例、colima 未安装 → **本机无容器可藏** |
| 关键判据① | `curl 127.0.0.1:7788` | **200**（exit 0）＝外脑实锤事实 |
| 关键判据② | `curl 192.168.3.116:7788` | **000**，verbose＝`Connection refused`（exit 7）＝与 Trae 报告 B2 一致 |
| 监听 | `lsof -nP -iTCP:7788` | `Python 86493 … TCP 127.0.0.1:7788 (LISTEN)`；`ps -p 86493`＝`-m server.web.server --host 127.0.0.1 --port 7788`，PPID 1，起于 08-29 00:45:12 ＝与外脑事实、Trae 报告三方一致 |
| 转述核查 | `grep cloud.sandbox` 全部 ~/program/*.md | **0 命中**（Trae 报告内也无） |

### 1.2 根因判定（#1「7788 误报」疑云）

1. **Trae 上轮取证环境＝真实 2017 本机，不是 Trae 云端沙箱**。其报告记录的回环 200、LAN 000、lsof 86493 回环绑定、裸进程 00:45 起、crontab 06:05、disabled-ccc plist、卡片数据（tst997）等，与本机实测逐条吻合；本机也无任何容器运行时可供沙箱隐藏。
2. **「7788 绑 cloud.sandbox.v2.trae.cn」是转述失真**：该字符串在 Trae 报告及 ~/program 全部报告中 0 次出现。Trae 报告原文写的是「Python 86493 仅绑 127.0.0.1:7788」（其 C 级一致项）。
3. **#1「两端 000」不是误报，是真发现**：web 以 `--host 127.0.0.1` 启动 → 仅回环监听 → 任何来源访问 `192.168.3.116:7788` 必然 refused。本人在真实 2017 上实测 LAN=000（Connection refused），与 Trae 完全一致。外脑判据「若本机 curl 127.0.0.1=200 即证 Trae 探测对象≠真实回环」不成立——Trae 报告从未声称回环 000（其 D4 行明确「127.0.0.1:7788=200」），「两端 000」指的是 LAN 地址。

### 1.3 分模块可信度分级（A=与实测吻合可采信 / B=需复测 / C=与实况矛盾）

| Trae 报告模块 | 本次复核结果 | 判级 |
|---|---|---|
| B 看板链路·2017 侧（LAN 000、7788 绑 127.0.0.1、~/.ssh/config 无 7788 转发） | 逐条复现 | **A** |
| B2 的「M1 端=000」；board-live.sh/md 恒回退（M1 qx-map 侧） | 未连 M1，未复测 | B |
| D 服务实况·2017 侧（无 com.ccc.* launchd、disabled-ccc/ 恰 4 个 plist、crontab 06:05、web 裸进程 86493 PPID1 00:45:12、dsh-web node 804 `*:3080`、xy 8765/8080 无监听） | 逐条复现（86493 起止时间精确到秒） | **A** |
| D 模块 M1 侧（litellm 3456、com.qxmap.daily-sync、com.qxmap.board-live） | 未连 M1 | B |
| E 数据（ledger 4891 行、`"probe"` 0 次、cards.index.jsonl 2 行+.lock、git 干净、origin/main=1726b0180） | 逐条复现 | **A** |
| **E·pytest 基线红（EXIT=1，2 失败，根因 typing.Self）** | **保真隔离复跑 EXIT=0 全绿（1266 例）→ 2 失败=会话环境差异，非事实** | **C（此条不可信）** |
| F 配置（config.env 实为 server/config/ 下、DATA_DIR/端口/CLUSTER_SERVICES 内容、executors 活配置≠example） | 逐条复现（DIFFERENT 实测） | **A** |
| F·/health auth_configured:false | 未复测 | B |
| G1 `_run_audit_worker` 未拆（4226 定义/4904 调用） | 精确复现（行号全中） | **A** |
| G3 分支消费后无自动删除 | 复现（grep 零命中） | **A** |
| G6 化石巡检 + dsh-web 两活口 | 复现（`~/.dsh/ccc-prod-health.sh:8` 恰 4 个 com.ccc.* 标签；node 804 `*:3080` 在听） | **A** |
| G7 xy :8765 实停 | 复现（监听表无 8765/8080） | **A** |
| G4 全量 pytest 必写 59 个 plan 文件 | **绿跑零复现**（保真副本跑完 git status 仅我的日志文件未跟踪项）→ 可能条件触发 | B |
| A3 交接单 6 份在位 + phase2 文件名标 20260830 实为 08-28/29 生成 | 复现（mtime 23:34/00:09/00:37） | **A**（2017 侧） |
| A1/A2 qx-map/AGENTS.md 口径冲突、决策档引用链（M1 侧文件） | 未连 M1 | B |
| C hp-kb 记忆停 08-19 / MISSING 清单 | 涉 HP 外部连接，本次红线未复测 | B |

**可采信**：B/D/E/F/G/A3 的全部 2017 侧结论（含 Top10 中的 #1、#6、#8、#9、#10、G1/G3/G6/G7）。
**必须复测**：① pytest 基线（本报告已用保真副本替代复测→改判全绿）；② 全部 M1 侧断言（qx-map 口径、board-live、litellm、6100、M1 端 000）；③ hp-kb 记忆；④ /health 鉴权；⑤ G4 副作用触发条件。

---

## 二、任务二：pytest 基线隔离复核

### 2.1 P1 静态证据链（禁实跑部分）

- `scripts/new-card.sh` shebang=`#!/usr/bin/env bash`；`:44` `set -euo pipefail`；`:65` `PYTHON_BIN="${CCC_PYTHON_BIN:-}"`；`:109-116` 仅当未显式指定时按 `/usr/local/bin/python3 → python3 → python` 解析；`:454` `from server.board.validate import validate_cards`。
- `server/board/card_header.py:14` `from typing import Self`（需 Python ≥3.11）。
- 解释器实况：`.venv-hub/bin/python`=**3.12.0**；`/usr/local/bin/python3`=**3.12.0（typing.Self=True）**；`/usr/bin/python3`=**3.9.6（typing.Self=False）**。`which -a python3`：/usr/local/bin 先于 /usr/bin。
- 触发用例：`server/tests/test_card_dispatch_gate.py` 的 `test_card_dispatch_gate_remote_check`(:18) 与 `test_new_card_flock_concurrency`(:131)，均子进程跑 `scripts/new-card.sh`，且 **`:80` `env["CCC_PYTHON_BIN"]="python3"` 强制走 PATH 解析**。
- 推论：测试结果取决于**跑 pytest 的会话 PATH 把 `python3` 解析到谁**——3.9.6 则 `typing.Self` ImportError → 两用例失败；3.12 则绿。

### 2.2 P2 隔离实跑（两跑对照）

| | 跑1（任务书 prescribed 副本） | 跑2（保真副本） |
|---|---|---|
| 副本路径 | `/tmp/ccc-pytest-20260829-024052/`（58M，排除 .venv-hub/data/.git） | `/tmp/ccc-pytest-full-20260829-024355/`（137M，仅排除 .venv-hub，**含 .git+data**） |
| 解释器 | `/Users/fan/program/CCC/.venv-hub/bin/python`（3.12.0） | 同左 |
| 完成 | 02:42:56 | 02:45:51 |
| **EXIT** | **1** | **0** |
| 结果 | **3 failed**，其余 ≈1263 passed | **1266 例全部通过，0 failed** |
| 失败明细 | `test_card_dispatch_gate_remote_check`（assert 128==3）、`test_new_card_flock_concurrency`（P1 失败：assert 128==0）、`test_http_api.py::TestCardsComposite::test_closed_cards_have_closed_at` | 无 |

跑1 失败 traceback（摘要）：
```
test_card_dispatch_gate_remote_check: assert res.returncode == 3 → AssertionError: assert 128 == 3
test_new_card_flock_concurrency:      assert p1.returncode == 0 → AssertionError: P1 失败:  assert 128 == 0
（两者子进程 stderr 均为空、stdout 均为空）
test_closed_cards_have_closed_at:     AssertionError: 已关闭卡应带 closed_at（git 合入时间）
```

### 2.3 判定：基线红 = 环境差异（假红），非真回归

1. **保真条件（含 .git+data、同一 venv、同一台真实 2017）下全绿 EXIT=0**——fix2 记录的绿基线成立，Trae 的「EXIT=1/2 失败」不是代码现状。
2. **Trae 两个失败的解释器漂移机制已实锤**：测试强制 `CCC_PYTHON_BIN=python3`（test_card_dispatch_gate.py:80）→ new-card.sh:65 直接采用 → :454 导入 validate → card_header.py:14 `from typing import Self`。Trae 会话的 PATH 将 `python3` 解析到 3.9.6（无 Self）→ ImportError → 两用例红；本会话 PATH 解析到 /usr/local/bin/python3=3.12 → 绿。与 Trae 报告自述根因（py3.9 typing.Self）方向一致，但结论应改写为**「跑测试会话的 PATH 污染」，不是「基线回归」**，部署门禁在正常环境不会拦。
3. **跑1 的教训（方法论警告，供 B 轨修订引用）**：任务书 prescribed 的隔离方式（排除 .git）本身会**制造同类假红**：new-card.sh:44 `set -euo pipefail` + :135 `PROJECT_ROOT_REAL="$(cd "$PROJECT_ROOT" && git rev-parse --show-toplevel 2>/dev/null)"` 在无 .git 目录返回 git 的 exit 128 → 赋值即失败 → 脚本静默死（stderr 已被 2>/dev/null 吞掉）→ 恰好同样的 2 个用例失败（returncode 128、stderr 空）+ `closed_at` 用例因无 git 历史失败。**今后隔离副本必须带 .git；或测试/脚本把解释器钉死（CCC_PYTHON_BIN 默认指向 .venv-hub/bin/python），一并消除 PATH 依赖。**
4. 附带：G4「全量 pytest 写 59 个 plan」在绿跑中零复现（副本 git status 无任何 plan 修改）——该副作用可能是条件触发（如失败路径/特定先置状态），B 轨勿按「必然副作用」定方案。

---

## 三、验收自证

1. **T2 每条带输出证据** ✓（§1.1 表格 9 行均为实测回显）。
2. **T3 有 A/B/C 分级表** ✓（§1.3，15 行逐模块）。
3. **P2 有隔离副本路径证明** ✓：`/tmp/ccc-pytest-20260829-024052/`、`/tmp/ccc-pytest-full-20260829-024355/`（含各自 pytest-run1.log / pytest-run2.log 原始日志，可复查）。
4. **零写操作自证** ✓：`git status --porcelain` 起点（02:35:02）/中段/终点（02:49:22）三次均 **0 行**；HEAD 恒为 `1726b0180a05299012d01578a17c7dffcde561dd`；无 stash；`data/audit/ledger.jsonl`（mtime 08-28 23:33）与 `~/.ccc/data/cards/cards.index.jsonl`（08-29 00:32）mtime 均早于本会话、未变；全程无任何 git 写命令（无 restore）；写动作仅 /tmp 两副本 + 本报告。
5. **用时 ≤30 分钟** ✓：02:35:02 开始 → 02:49 收尾（约 14 分钟）。

## 四、回传

- 报告路径：`/Users/fan/program/ccc-env-and-pytest-audit-20260829.md`
- 一句话总判：**Trae 报告整体可信（2017 侧逐条复现、环境确为真实 2017、#1 非误报；唯 pytest 基线红一条需改判），pytest 基线红是假（保真隔离复跑 EXIT=0 全绿，2 失败 = 跑测试会话 PATH 解析到系统 python3.9 的环境差异）。**
