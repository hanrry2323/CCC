# CCC 项目审计报告

## 元数据

| 项 | 值 |
|----|-----|
| 日期 | 2026-07-15 |
| 范围 | `scripts/`、`app/`、`lib/`、`src/`、`docs/`、`specs/`、`references/`、`skills/`、`CLAUDE.md`、`README.md`、`STARTUP-BRIEF.md`、`SKILL.md`、`src-tauri/tauri.conf.json`；排除编译产物/node_modules/__pycache__ |
| 方法 | 已知疑点优先 grep → 定点 Read 证据行 → 五维交叉；**只读**（仅创建 `.cursorignore` + 本报告） |
| 覆盖维度 | 架构 / 代码 / 业务流程 / 角色·智能体 / 提示词 |
| 权威版本 | `VERSION` = **v0.30.0**（与部分文档漂移，见 F-VER-*） |

---

## 执行摘要（Top 10）

| # | 严重度 | 一句话 | 位置 |
|---|--------|--------|------|
| 1 | Critical | Chat 默认口令 `claude2026` + 绑定 `0.0.0.0` + 启动打印明文账密 → 局域网可直连代理 Claude | `scripts/chat_server/config.py:10-13`；`ccc-chat-server.py:39` |
| 2 | Critical | Board 文件锁在持锁进程仍存活时可 force-clear → 双写者破坏看板 JSONL | `_board_store.py:308-318`（与注释 276-277 矛盾） |
| 3 | High | `_GLOBAL_OPENCODE_COUNT` 无锁自增/自减，且经 `ThreadPoolExecutor` 并发读写 | `ccc-engine.py:95-96,1167-1174,1272-1284` |
| 4 | High | stale/hang 隔离不释放 opencode 全局槽位 → 计数泄漏直至进程重启 | `ccc-engine.py:2080-2105` vs 递减仅 `1752-1758`/`1581-1584` |
| 5 | High | 多 workspace 靠猴子补丁 `ccc_board.ROOT/BOARD` 切换，并发路径存在跨 workspace 污染面 | `ccc-engine.py:345-353` |
| 6 | High | Tauri `distDir` 指向 `.py`、`beforeDevCommand` 递归调用 `tauri dev` → 桌面端接线错误 | `src-tauri/tauri.conf.json:3-6` |
| 7 | High | 危险命令黑名单仅正则匹配用户末条 prompt，易绕过；CORS `*`+credentials | `config.py:18-20`；`chat.py:38-39`；`app.py:16-17` |
| 8 | High | Dev/并行 phase prompt 未限定「只做当前 phase」，要求「实现所有需求」→ 并行互踩 | `ccc-engine.py:1124-1135`；`ccc-board.py:4535-4544` |
| 9 | Medium | 文档/版本三方漂移：权威 v0.30.0 vs SKILL/BRIEF v0.28.1 vs README 仍写 7 角色定时轮询 | `VERSION`；`SKILL.md:6,205`；`README.md:24-57` |
| 10 | Medium | pytest 失败任务永久留 testing 无自动回收；`complexity=small` 文档称跳过 gate 但 engine 未实现 | `ccc-engine.py:585-594,520-636`；`STARTUP-BRIEF.md:45` |

---

## 发现清单表

| ID | 维度 | 严重度 | 标题 | 位置(file:line) | 证据 | 影响 | 建议修复(一句话) | 工作量 |
|----|------|--------|------|-----------------|------|------|------------------|--------|
| F-SEC-01 | 代码 | Critical | Chat 默认弱口令 + 全网绑定 | `scripts/chat_server/config.py:10-13` | `HOST=0.0.0.0`；`AUTH_PASS` 默认 `claude2026` | 未改 env 时外网/LAN 可 Basic Auth 进 Chat→Claude | 默认绑 `127.0.0.1`；强制设强口令否则拒启 | S [DONE] |
| F-SEC-02 | 代码 | Critical | 启动日志打印明文账密 | `scripts/ccc-chat-server.py:39` | `print(f"账号: {AUTH_USER} / {AUTH_PASS}")` | 终端/launchd 日志泄漏凭据 | 永不打印密码；仅提示「已启用 Basic Auth」 | S [DONE] |
| F-SEC-03 | 代码 | High | 危险指令黑名单可绕过 | `config.py:18-20`；`chat.py:18-19,38-39` | 只拦 `rm -rf`/`sudo` 等；`rm -r -f`、`/bin/rm`、tool 侧命令不查 | agent 可经工具执行危险命令 | 取消正则黑名单幻想；约束工具层 allowlist + 工作目录 jail | M [DONE] |
| F-SEC-04 | 代码 | High | CORS 允许任意 Origin + credentials | `chat_server/app.py:14-19` | `allow_origins=["*"]` + `allow_credentials=True` | 浏览器 CSRF/凭证捎带风险 | 收紧为明确 Origin 列表 | S [DONE] |
| F-SEC-05 | 代码 | Medium | Board 无 token 时本机免鉴权 | `ccc-board-server.py:356-359` | `if not token: if is_local: return True` | 本机其他用户/恶意进程可改看板 | 默认要求 `QX_BOARD_TOKEN` | S [DONE] |
| F-SEC-06 | 代码 | Low | `CLAUDE_BIN` 硬编码用户路径 | `config.py:27` | `"/Users/apple/.local/bin/claude"` | 不可移植；他人环境静默失败 | 仅 `shutil.which`，失败显式报错 | S [DONE] |
| F-CON-01 | 代码 | High | 全局 opencode 计数无锁 | `ccc-engine.py:95-96,1167-1174,1272` | `ThreadPoolExecutor` 内对 `_GLOBAL_OPENCODE_COUNT` 无条件 `+=1`；工程内仅 `_stats_lock` | 超卖并发 / 负反馈漏计 → OOM 或饥饿 | 用 `threading.Lock` 或 `Semaphore` 包读写 | S [DONE] |
| F-CON-02 | 业务流程 | High | quarantine/stale 不释放槽位 | `ccc-engine.py:2080-2105` vs `1752-1758` | `_check_stale` 只 quarantine，无 `_GLOBAL_OPENCODE_COUNT -=`、不删 `active_tasks` | 槽位枯竭，planned 饿死至 Engine 重启 | quarantine/hang 路径统一 `release_slot(task)` | M [DONE] |
| F-CON-03 | 架构 | High | workspace 全局 ROOT 补丁 | `ccc-engine.py:345-353`；`ccc-board.py:59-88` | `_activate_workspace` 写 `ccc_board.ROOT/BOARD` + `_reset_lazy()` | 任一并发读 ROOT 会串 workspace | 废除模块全局；所有 API 显式传 `ws`/`store` | L [DONE] |
| F-LOCK-01 | 代码 | Critical | 存活锁可被强制删除 | `_board_store.py:276-277,308-318,325-330` | 注释称「活 pid 永不强清」；实现 `elapsed>timeout` 即 `unlink` 活锁 | 双 writer 撕裂 JSONL / 丢迁移 | 删除 force-clear 活锁分支；超时只 `return None` | S [DONE] |
| F-LOCK-02 | 架构 | Medium | 双锁协议并存 | `ccc-board.py:142-156` vs `_board_store.py:270-285` | product 用 `fcntl.flock`；board 用 `O_EXCL` | 规则不一致，跨平台/崩溃行为难推 | 统一一种 advisory 协议并文档化 | M [DONE] |
| F-UI-01 | 架构 | High | Tauri 构建接线错误 | `tauri.conf.json:3-6`；`package.json:6-9` | `distDir: "../scripts/ccc-chat-server.py"`；`beforeDevCommand: " npm run tauri dev"` | 桌面打包/dev 循环损坏或无限递归 | `distDir`→前端静态目录；`beforeDevCommand`→启动 chat server | M [DONE] |
| F-VER-01 | 提示词 | Medium | 版本号多源矛盾 | `VERSION`；`SKILL.md:6,205`；`STARTUP-BRIEF.md:1,127`；`Cargo.toml:3`；`tauri.conf.json:10`；`package.json:3` | 权威 `v0.30.0`；SKILL/BRIEF=`v0.28.1`；Tauri/npm=`0.29.0` | agent/人读错契约；发版门禁失效 | 单源 `VERSION` + CI 校验全部文档/包版本 | S [DONE] |
| F-VER-02 | 提示词 | Medium | README 描述已废架构 | `README.md:24-57,62-72` | 仍写「7 launchd plist 周期跑」与角色频率表 | 新人按旧模型部署/排障 | 对齐 Engine 串行 + 2 plist（见 STARTUP-BRIEF） | S [DONE] |
| F-FLOW-01 | 业务流程 | High | pytest fail 永久挂 testing | `ccc-engine.py:585-594` | 「留在 testing 等待人工确认」无 TTL/重试上限 | testing 队列堆积、门禁反复空转 | 失败 N 次 → abnormal + 通知 | S [DONE] |
| F-FLOW-02 | 业务流程 | Medium | small complexity 文档与实现不符 | `STARTUP-BRIEF.md:45`；`SKILL.md:53-54`；`ccc-engine.py:520-636` | Brief 称 small 可跳过 reviewer+tester；gate 无 `complexity` 分支（仅 diff 行数 small） | 期望行为与运行不符；审查成本/安全基线混乱 | 实现 task.complexity 短路或改文档 | S [DONE] |
| F-FLOW-03 | 业务流程 | Medium | Verdict 门禁子串误判 | `ccc-engine.py:599-611` | `"FAIL" in _vcontent` 会匹配 `FALLBACK`/正文提及 FAIL | 误回滚 PASS 任务或误触发 revert | 解析结构化 Verdict 字段，禁裸子串 | S [DONE] |
| F-FLOW-04 | 业务流程 | Medium | 挂起最坏路径仍可达 6h | `_config.py:124`；`ccc-engine.py:2094` | `max_stale_hours=6`；hang 检测 5min 但依赖 CPU≈0 | 活线程 busy-loop 可挡 6h 后才 quarantine | busy/idle 双阈值；缩短 stale 默认 | M [DONE] |
| F-FLOW-05 | 业务流程 | Low | 无跨 task 依赖调度 | `docs/next-upgrade-roadmap.md:49-51` | 文档自陈引擎不感知 task 依赖 | 依赖未就绪 task 空跑失败 | phases depends_on 已有；补 task 级 depends | L [DONE] |
| F-ROLE-01 | 角色流程 | High | 角色 SKILL 自相矛盾（reviewer fallback） | `skills/ccc-reviewer/SKILL.md:26,54` vs `113-123` | 同文件既写「fallback 到 py_compile」又写「已废除，medium/large quarantine」 | agent 可能按旧路径放行不安全 verified | 删除过时职责表行，只留 R-12 | S [DONE] |
| F-ROLE-02 | 角色流程 | Medium | `ccc-board.py` 上帝模块 | `ccc-board.py`（~5113 行） | 7 角色 + lock + prompt + quarantine 同文件 | 边界难审、互串风险高、测试难 | 按角色/store/prompt 拆包 | L [DONE] |
| F-ROLE-03 | 角色流程 | Medium | `app/`/`lib/`/`src/` 与 scripts 双栈 | `app/`、`lib/dead_letter.py`、`src/` | 主路径在 scripts；app/src 薄且弱挂钩 | 维护者不知 SSOT | 标明废弃或接到 Engine | M [DONE] |
| F-ROLE-04 | 角色流程 | Low | auto-tune 只改本地 `MAX_RETRY` 影子 | `ccc-engine.py:65,1795-1806` | `MAX_RETRY = ccc_board.MAX_RETRY` 后本地再赋值 | 调参对 board 重试逻辑无效 | 写回 `ccc_board.MAX_RETRY` 或 cfg | S [DONE] |
| F-PROMPT-01 | 提示词 | High | Phase prompt 无相范围 | `ccc-engine.py:1124-1135`；`ccc-board.py:4535-4544` | 「实现所有需求」+ 全文 plan；并行多 worker 同文 | 并行 phase 改同一文件冲突/重复 commit | prompt 强制 `只做 Phase N` + 白名单切片 | M [DONE] |
| F-PROMPT-02 | 提示词 | Medium | Reviewer 输出格式可被「看似 JSON」绕过 | `ccc-board.py:1800-1808,1868-1902` | 解析失败 → `verdict=fallback` → quarantine（好）；但 prompt 截断 plan/diff | 大变更漏检；截断导致假 PASS/假 FAIL | 提高预算或分块审查；禁止截断关键文件 | M [DONE] |
| F-PROMPT-03 | 提示词 | Medium | CLAUDE/SKILL/README 三套叙事 | `CLAUDE.md`；`SKILL.md`；`README.md` | Engine 串行 vs README 定时；版本号不一致 | prompt 注入互相冲突，红线可被「选读」绕过 | 单一 STARTUP-BRIEF 为 SSOT，其余链到它 | M [DONE] |
| F-PROMPT-04 | 提示词 | Low | phases schema 1.1 vs 1.2 | `SKILL.md:97`；`phase_lint.py:28` | 文档写 1.1；lint 默认 1.2 | product/agent 产出被 lint 拒 | 统一 schema_version 文案与校验 | S [DONE] |
| F-ARCH-01 | 架构 | Medium | Engine 单点 + 内存态 | `ccc-engine.py` KeepAlive 模型；`_hang_retry_counter:208` | 单进程；hang 计数内存字典 | 进程死丢计数；整体不可水平扩展 | 计数持久化；考虑多实例锁 | L [DONE] |
| F-ARCH-02 | 架构 | Medium | 测试缺口：无并发计数/auth 默认加固测 | `tests/scripts/`（~30） | 无 `_GLOBAL_OPENCODE_COUNT` 竞态测；chat 测固化默认口令 | 回归挡不住本次 Critical/High | 补 lock/counter/auth fail-closed 单测 | M [DONE] |
| F-ARCH-03 | 代码 | Low | list_tasks 无锁快照 | `_board_store.py:457-495` | 有意识无锁读；可能与写并发撕裂单行 | 偶发脏读导致错调度 | 读侧校验 JSONL 尾行完整性 | S [DONE] |
---

## 分维度详述

### 1. 架构层

- **模块边界**：核心运行时在 `scripts/ccc-engine.py` + `scripts/ccc-board.py` + `_board_store.py`；`app/`/`lib/`/`src/` 基本旁路，SSOT 不清（F-ROLE-03）。
- **依赖方向**：Engine 动态 `importlib` 加载 `ccc-board.py` 后猴子补丁其全局（F-CON-03）——依赖倒置为「共享可变全局」，扩展多 workspace 并发即风险。
- **全局可变状态**：`_GLOBAL_OPENCODE_COUNT`、`ccc_board.ROOT`、`_hang_retry_counter`、`MAX_RETRY` 本地影子（F-CON-01/03, F-ROLE-04）。
- **并发模型**：主循环串行 tick + phase 级 `ThreadPoolExecutor`（max 2）+ Board `ThreadingHTTPServer`；计数器与 ROOT 补丁未按线程安全设计。
- **单点故障**：单 Engine（launchd KeepAlive）控所有 workspace；Board/Chat 另起进程。Engine 挂则流水线停；计数泄漏则软死锁（F-CON-02）。
- **扩展瓶颈**：全局 opencode 上限 6；无跨机调度；无 task 级依赖（F-FLOW-05）。God-module `ccc-board.py` ~5k 行阻碍演进（F-ROLE-02）。
- **桌面端**：Tauri 配置与前端产物脱节（F-UI-01），Cockpit 路径不可信。

### 2. 代码层

- **线程安全**：并行 phase 启动对 `_GLOBAL_OPENCODE_COUNT` check-then-act 无原子性（F-CON-01）。
- **资源/槽位泄漏**：成功 `+=1` 后若经 stale quarantine 而非 `_handle_task_result`，无对称 `-=1`（F-CON-02）。
- **锁正确性**：`_acquire_lock` 对存活 holder 可强删，与 docstring 冲突（F-LOCK-01）；product 与 store 两套锁（F-LOCK-02）。
- **错误处理**：pytest 失败吞进「人工确认」黑洞（F-FLOW-01）；verdict 用子串匹配（F-FLOW-03）。
- **硬编码秘钥与配置**：Chat 默认口令、打印明文、0.0.0.0、硬编码 Claude 路径（F-SEC-01/02/06）；危险正则可绕过（F-SEC-03）；宽松 CORS（F-SEC-04）。
- **测试缺口**：未覆盖计数竞态与「无默认口令」fail-closed（F-ARCH-02）；chat 测试反而固化 `ccc:claude2026`。

### 3. 业务流程层（创建→分配→执行→完成→回收）

| 阶段 | 闭环？ | 缺口 |
|------|--------|------|
| 创建 | 是 | backlog→product→planned；fallback plan 质量弱 |
| 分配 | 部分 | planned FIFO（已修饿死）；无跨 task depends |
| 执行 | 是 | phase depends_on + retry/backoff；并行 prompt 越界（F-PROMPT-01） |
| 完成 | 部分 | testing→reviewer/tester→verified→kb；小任务策略文档不符（F-FLOW-02） |
| 回收 | 弱 | stale→abnormal；pytest fail 不回收；槽位可不释放（F-FLOW-01/02, F-CON-02） |
| 崩溃恢复 | 部分 | `_load_active_tasks` + `_recover_tasks` 存在；计数与 hang 内存态不完整恢复 |

**挂起/饿死路径**：busy-loop 可达 `max_stale_hours`（6h）；pytest 失败常驻 testing；opencode 槽泄漏后 planned 无法启动（饥饿）。

### 4. 角色 / 智能体流程层

- **多角色**：职责表在 skills 中声明「不互串」；运行时真实执行在 Python，SKILL 过时条款可诱导错误行为（F-ROLE-01）。
- **多 workspace**：`_activate_workspace` 改写模块全局 + lazy 重置；主循环按序 activate，但并行 phase 线程与未来多线程扩展不安全（F-CON-03）。
- **上下文污染**：`~/.ccc/prompts/` 跨任务 prompt 文件；Chat `_get_project_context` 注入到用户 prompt；CORS+认证弱放大跨站污染面。
- **消息/委派协议**：看板列 + `.done`/pid 文件 + events.jsonl；无严格消息 schema 版本门禁（phase 1.1/1.2 漂移 F-PROMPT-04）。
- **委派绕过**：红线 12 靠 prompt 纪律；README 旧入口脚本可能仍引导定时角色跑偏。

### 5. 提示词工程层

- **质量问题**：Dev prompt「实现所有需求」缺 phase 边界（F-PROMPT-01）；Reviewer prompt 截断 plan/diff（F-PROMPT-02）；Reviewer SKILL 新旧 fallback 并存（F-ROLE-01）。
- **自相矛盾**：版本叙事（F-VER-01）、架构叙事 README vs CLAUDE/BRIEF（F-VER-02/F-PROMPT-03）、small 跳过 vs 全量 gate（F-FLOW-02）。
- **约束可绕过**：Chat 黑名单（F-SEC-03）；红线 11 依赖 verdict 文件——引擎有检查但字符串匹配脆弱（F-FLOW-03）；角色「只读」仅靠 SKILL 文字，无 OS 级只读沙箱。
- **正向面**：R-12 quarantine 在代码路径对 medium/large fallback 已落地；STARTUP-BRIEF 相对最接近现状。

---

## 优先级路线图

### P0（必修，可被人利用或丢数据）

| 项 | 依赖 |
|----|------|
| F-SEC-01 + F-SEC-02：Chat 默认绑定/口令/禁打印 | 无 |
| F-LOCK-01：禁止强清存活 O_EXCL 锁 | 无 |
| F-CON-01 + F-CON-02：Semaphore 化槽位 + quarantine 释放 | F-CON-01 先做锁，再接到 quarantine/hang |
| F-UI-01：修 tauri.conf.json 接线 | 需确认前端静态目录路径 |

### P1（重要 bug / 强风险）

| 项 | 依赖 |
|----|------|
| F-CON-03：取消 ROOT 猴子补丁，显式传 workspace | 大 refactor，可先文档限制「禁止 Engine 外并发调 board」作临时措施 |
| F-SEC-03 + F-SEC-04：工具层 allowlist + CORS 收紧 | F-SEC-01 之后 |
| F-PROMPT-01：phase 作用域 prompt | 与并行调度同发 |
| F-FLOW-01 + F-FLOW-03：testing 失败回收 + 结构化 verdict | 无 |
| F-ROLE-01 + F-VER-01/02 + F-PROMPT-03：统一文档/版本 SSOT | 改 VERSION 校验门禁 |
| F-FLOW-02：对齐 small 策略 | 产品决策：跳过 or 不跳过 |

### P2（可选 / 可维护性）

| 项 | 依赖 |
|----|------|
| F-ROLE-02 拆分 ccc-board | 宜在 F-CON-03 后 |
| F-LOCK-02 统一锁协议 | F-LOCK-01 后 |
| F-ARCH-01/02 持久化 hang 计数 + 补测试 | F-CON-01 后 |
| F-FLOW-04/05、F-PROMPT-02/04、F-ARCH-03、F-SEC-05/06、F-ROLE-03/04 | 各自独立 |

---

## 未知项

| # | 内容 | 需要用户补充 |
|---|------|----------------|
| U1 | 生产是否对外暴露 `:8084` Chat / Board | 部署拓扑与防火墙规则 |
| U2 | `QX_BOARD_TOKEN` / `CCC_CHAT_PASS` 是否已在 launchd env 覆盖默认 | 实际 plist/env |
| U3 | Tauri Cockpit 是否仍在使用；期望 frontend 目录 | 产品意图 |
| U4 | `app/`/`src/` 是否 intentional 新架构还是实验残留 | 是否要删/并 |
| U5 | 多 Engine 实例是否有人手动跑过 | 确认 F-CON-03 是否已在实战爆发 |
| U6 | hang 检测误杀率（网络等待型 opencode） | 线上 `engine.log` / `.hung` 样本 |
| U7 | `.ccc/chat/**` 大量 D 状态是否刻意清理 | 与审计无关但影响仓库卫生 |

---

## 附录：已知疑点核查结果

| 疑点 | 结论 |
|------|------|
| `_GLOBAL_OPENCODE_COUNT` 无锁 | **确认** High；且有 ThreadPool 并发写 |
| `_board_store` O_EXCL / .done / stale | O_EXCL **会强清活锁**（Critical）；.done 竞态有注释防护；stale→abnormal **不释放槽** |
| chat config/auth | **确认** Critical；黑名单可绕过；CORS 过宽 |
| `_activate_workspace` 补丁 ROOT | **确认** High |
| 版本漂移 | **确认** 0.30.0 / 0.28.1 / 0.29.0 三档 |
| tauri.conf.json | **确认** distDir/beforeDevCommand 错误 |
| 提示词冲突 | **确认** README/SKILL/reviewer fallback/phase 无范围 |

---

*本报告为只读审计产出。未修改任何业务代码；会话内仅新建 `.cursorignore` 与本 `AUDIT.md`。*
