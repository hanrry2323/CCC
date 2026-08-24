# 调查报告 · mx/roadmap 周期写入者定位（ccc074）

> 卡：ccc074 · 日期：2026-08-24 · 执行体：DSH · 性质：只读取证 + 动态复现，未实施修复

## 结论

写入者**不是单一进程，而是同一条写入代码路径的两个触发面**；污染内容与留档 patch 字节级同源（同一 blob 对 `a1abcb5a4..d9462a1bc`），已动态复现坐实：

1. **主链（测试面 · worktree 污染元凶）**：`server/tests/test_observer.py::test_run_observer_output`（`server/tests/test_observer.py:94-115`）隔离不完整——只 mock 了三个 loader，但 `run_observer` 内部的 `scan_findings(cfg, PROJECT_ROOT)` 吃**真实仓库根**、`write_roadmap_draft` **未被 mock**。任何 checkout 里跑全量 pytest（各卡门禁普遍要求），该测试就会对**所在 checkout** 的 `docs/projects/mx/roadmap.md` 追加 Loop 巡查草案行。ccc068 当日按卡要求多轮「全量 pytest」，与其留档 patch 三次出现（04:29 / 05:01 / 05:27）吻合。
2. **辅链（生产调度面 · 主仓污染源）**：launchd `com.ccc.scheduler` 常驻进程（实测 PID 31668，PPID=1，cwd=`/Users/fan/program/CCC`）每 60s 一轮调度，`loop-observer` 任务在阈值满足时走**同一条** `run_observer → write_roadmap_draft → create_draft → _write_roadmap` 链写主仓同文件（12:32:46 实跑日志命中与 patch 逐字相同的发现）。
3. **反复复现的机制**：根因数据条件未消除——已提交版本 `docs/projects/mx/roadmap.md:64-66` 中里程碑 M8 声明「进行中」，但其 4 个关联方案（mx-plan-005~008）实际全部已完成（12:32 实跑发现原文：「实际完成率 100%（4/4 方案 → 已完成）」）。只要该条件在，任何一次 pytest/巡逻都会把被 revert 掉的草案行**重新写回**，形成「清了又脏」。

## 写入者命令行与父链（实测）

### A. 生产调度链（写主仓）

```text
launchd (PPID=1, label=com.ccc.scheduler, KeepAlive=1, RunAtLoad=1)
└─ PID 31668  Sat Aug 22 11:40:12 2026 起
   /Library/Frameworks/Python.framework/Versions/3.12/.../Python -m server.engine.scheduler --config /Users/fan/program/CCC/server/config/config.env
   cwd = /Users/fan/program/CCC   （lsof 实测）
```

- plist：`~/Library/LaunchAgents/com.ccc.scheduler.plist`；调度循环间隔 60s（`server/engine/scheduler.py:31 DEFAULT_INTERVAL_SECONDS=60`，进程未传 `--interval`，config.env 未覆盖）。
- 任务注册：`server/engine/scheduler.py:268-271` 将 `run_observer` 注册为 `loop-observer` 只读任务（名不符实：其内部有草案池**写**副作用）。

### B. 测试链（写任意所在 checkout —— worktree 污染路径）

```text
执行体 wrapper / 门禁步骤（如 ccc068 步骤3「全量 pytest」）
└─ <python> -m pytest server/tests/...
   └─ test_run_observer_output (server/tests/test_observer.py:94)
      └─ run_observer (server/engine/observer.py:715)
```

pytest 以 checkout 为 rootdir，`import server.*` 解析到**该 checkout 的副本**，而路径基准全部基于 `__file__`：

- `server/board/roadmap.py:26-28`：`_repo_root() = Path(__file__).resolve().parents[2]`
- `server/engine/observer.py:40`：`PROJECT_ROOT = Path(__file__).resolve().parents[2]`

因此测试进程内的写入必然落在**运行 pytest 的那个 checkout**（worktree 或主仓），与 cwd 无关。

次要入口（本轮未见触发证据，仅登记）：Web API `POST create_draft`（`server/web/server.py:2814`）与 DSH 草案端点（`:3652-3666`）可经 HTTP 触发同链写入，取决于 web 进程加载自哪个 checkout。

## 触发周期（实测）

| 触发面 | 周期 | 依据 |
|---|---|---|
| engine scheduler 巡逻 | 每 60s 判一次阈值；满足才实跑 | `scheduler.py:206-213` 循环 + `observer.py:90-124 should_run`（24h 过期 / 新 HEAD commit / cards.index.jsonl mtime·size 变化即触发） |
| pytest 全量 | 每次按卡门禁全量跑即触发（`OBSERVER_FORCE=true` 强制实跑） | `test_observer.py:99 cfg={'DATA_DIR': tmp, 'OBSERVER_FORCE': 'true'}` + `should_run:91-92` force 分支 |
| 留档节奏旁证 | patch1→3 间隔约 30min（04:29/05:01/05:27），patch4(06:01) 为空 | `/tmp/ccc068-stray-mx-roadmap.patch*` mtime；与 ccc068 多轮验证电池节奏吻合（相关性推断，无逐次时间戳日志，如实标注） |

## 写入内容生成点（file:line 全链）

```text
test_run_observer_output            server/tests/test_observer.py:94-115   ← 隔离缺口（未 mock scan_findings / write_roadmap_draft / _auto_fix_deterministic）
run_observer                        server/engine/observer.py:715
├─ scan_findings(cfg, PROJECT_ROOT) observer.py:756                            ← 吃真实仓库根，扫出真实 M8 不一致
├─ write_roadmap_draft(...)         observer.py:757-764（调用点 :762）          ← PRIME-DIRECTIVE §6.3 注释：发现自动回草案池
│  └─ title="[治理债][Loop巡查] {description}"  observer.py:1598
│     └─ create_draft(project, title)           observer.py:1609（未传 source）
│        ├─ 去重：exact-title 相等              server/board/roadmap.py:614-616
│        └─ _write_roadmap(...)                 server/board/roadmap.py:618-624
│           └─ 整文件重序列化 + 头部日期 date.today()  roadmap.py:307-315      ← 「更新：2026-08-19→08-24」来源
└─ _auto_fix_deterministic(findings, PROJECT_ROOT) observer.py:777             ← 同类越权面：subprocess auto-fix-plan-progress.py(:694-703) 重算里程碑进度
```

diff 三处变化的对应关系：头部日期行（`_write_roadmap` 重写）、历史行 `[治理债][Loop巡查]`→`[治理债] [Loop巡查]`（parse→serialize 回环把旧行 source token 拆分重排）、新增 M8 草案行（本次发现）。

## 动态复现实证（本卡自测核心）

一次性 detached worktree（`git worktree add --detach /tmp/ccc074-repro HEAD`，已清理）内单跑嫌疑测试：

```text
$ cd /tmp/ccc074-repro && git status --porcelain -- docs/projects/mx/roadmap.md   # 空（干净）
$ python -m pytest server/tests/test_observer.py::test_run_observer_output -q     # 1 passed
$ git status --porcelain -- docs/projects/mx/roadmap.md
 M docs/projects/mx/roadmap.md          # +3/-2
$ git diff …  # blob 对 a1abcb5a4..d9462a1bc —— 与 /tmp/ccc068-stray-mx-roadmap.patch* 字节级一致
```

复现后现场已还原并移除临时 worktree；主仓现存脏文件（mtime 08-24 06:09:27）为**既有证据**，按红线未触碰。

## 是否属预期设计

**半预期**。「巡查发现 → 自动回线路图草案池」是设计意图（`observer.py:757` 注释明引 PRIME-DIRECTIVE §6.3；`write_roadmap_draft` docstring 同旨），生产调度面写主仓属设计内行为。但两点**超出预期**：(1) 该写路径经模块级常量泄漏进**单元测试**，使全量 pytest 成为对任意 checkout 的隐式写入器，直接违反「测试不写生产文件」约定（同文件其他测试均以 tmp_path+mock 隔离，唯此一处失守）；(2) `_write_roadmap` 对整个文件的整篇重排会顺手改写历史行样式，放大了每次写入的 diff 面积。另注：`loop-observer` 在任务表注册为 `TASK_TYPE_READONLY` 但实际有写副作用，命名与类型标注失真。

## 治理建议（三选一：改道 ✅ / 停止 ❌ / 加锁 ❌）

**选「改道」**，理由与最小切口：

1. **治本（测试隔离，必做，一行级）**：`test_run_observer_output` 补 mock——`patch('server.engine.observer.scan_findings', return_value=[])`（或把 `PROJECT_ROOT` patch 到 tmp_path），并同样罩住 `_auto_fix_deterministic`。完成后全量 pytest 不再具备写仓能力。
2. **改道（写权限收口到生产上下文）**：给 `write_roadmap_draft` 加环境闸（如仅 `CCC_ALLOW_ROADMAP_WRITE=1` 由 launchd 生产环境注入时放行，默认拒写并记日志）。保留 PRIME-DIRECTIVE §6.3 治理闭环，同时让任何非生产 checkout（worktree/测试/web 开发实例）天然无写权。不建议一刀切「停止」：会拆掉巡查→草案池的产品闭环；也不选「加锁」：`_write_roadmap` 已有 fcntl 锁（`roadmap.py:307-310`），锁解决并发不解决越权写入面。
3. **根因数据收口（消触发源）**：将 M8 状态改判「已完成」（4/4 方案已完成是扫描实证），或修复 `_auto_fix_deterministic`→`sync_milestone_progress` 本应完成的自动重算（12:32 实跑仍在报 M8 进行中，说明该修复链当前未生效，需另查——不在本卡范围内实施）。数据条件不消，任何残留写路径仍会再写。
4. **顺带修正**：`loop-observer` 任务类型标注与实际副作用不符，建议改名或在注册处注明含草案池写副作用，避免下一个排查者被「readonly」误导。

## 未定项（防幻觉声明）

- 主仓最后一次写入（08-24 06:09:27）无法做进程级归因：scheduler 日志（`~/.logs`→`/Users/fan/.ccc/logs/scheduler.stderr.log`）无时间戳，当日可确认的唯一实跑巡逻在 12:32。候选=主仓内一次全量 pytest 或一次未留痕的生产巡逻，两者代码路径相同、写入结果等价，不影响结论。
- ccc068 三次 patch 与其三轮验证的一一对应为节奏相关性推断（其卡步骤 3 要求多环境×多变体全量 pytest），非逐次日志实证。
