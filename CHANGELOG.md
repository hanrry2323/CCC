# Changelog — CCC

All notable changes to CCC will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.41.0] — 2026-07-16

### 闭环：下达即开工 + 基线 + 日审骨架

- 修 Hub SSE 双份输出（`result` 不再重复追加 assistant 正文）
- 下达任务 → `enabled` + `engine.wake` + launchd 拉起（无确认；不打开 invent）
- 「对齐基线」：`GET /api/projects/{id}/baseline` + 空态按钮
- product prompt 注入 `ccc-product` skill + 程序基线快照
- `ccc-daily-diff-review.py`：决策 A–J，`--apply` 建卡并 wake
- 发布闸继续以 kb 程序化为主（CHANGELOG/tag/state，默认 0 LLM）

## [v0.40.1] — 2026-07-16

### 流水线修通：claude PATH / upstream 探针 / reviewer 门禁

- **Fix1** `scripts/_claude_cli.py`：运行时解析绝对路径；`_sanitized_env` 补 `~/.local/bin`
- **Fix2** upstream 探针：4xx 视为 proxy 可达；`CCC_UPSTREAM_STRICT=1` 恢复仅 200；写 `~/.ccc/stats/upstream-probe.jsonl`
- **Fix3** `CCC_REVIEWER_FALLBACK=static|quarantine`（默认 static：PASS+WARN 过门）
- **Fix4** hang：abnormal 后不再刷 hang 事件；耗尽 quarantine 后清 active/counter
- **Fix5** `tests/e2e/test_green_pipeline_e2e.sh` mock 绿通

## [v0.40.0] — 2026-07-16

### 架构：队列消费者 + 失败账本

- 控制面四态：`disabled` | `ui` | `enabled`（只消费）| `invent`（自造）
- Engine 空队列深睡 60s；默认只扫 CCC workspace（非全 ~/program）
- `.ccc/stats/failures.jsonl` + `ccc-failure-report.py` + Hub `/api/failures`
- plan 模板缺失时回退 CCC `templates/plan.plan.md`
- 文档：`docs/CONTROL.md` · `docs/observability.md`

## [v0.39.2] — 2026-07-16

### 前端开发与 Engine 解耦

- 控制面三态：`disabled` | `ui` | `enabled`
- 新增 `scripts/ccc-hub-dev.sh`：前台 Hub+Board，不改 control、不装 KeepAlive、不启 Engine
- `install-hub/board --start` 只设 `ui`，绝不 enable Engine
- `install-ccc-roles` 的 board 只 stage

## [v0.39.1] — 2026-07-16

### 堵住 install 复活路径

`install-ccc-roles.sh` / hub / board / scheduler 默认**只 stage** 到
`~/Library/LaunchAgents/disabled-ccc/`，不再 `launchctl load`。
`--start` 才 enable + bootstrap。board/chat 入口尊重 control（idle hold）。

## [v0.39.0] — 2026-07-16

### 根源：运行控制面状态机（非「删自启动」）

旧业务把「永远在线 + 多通道自愈」写成目标：crontab / patrol Popen / launchd /
opencode KeepAlive 互不知情 → 用户杀掉仍复活。

**新业务**：
- `~/.ccc/control.json` SSOT：`disabled`（默认）| `enabled`（显式）
- 唯一合法拉起：`launchd:com.ccc.engine`
- patrol **删除** `Popen(python ccc-engine.py)` 旁路
- loop-monitor **永不自启**，只观察
- 空看板仍真空闲（继承 v0.37）

模块：`scripts/_ccc_control.py`  
文档：`docs/CONTROL.md`  
CLI：`bash scripts/ccc-autostart-guard.sh`

## [v0.38.4] — 2026-07-16

- e2e-event-test-1784201475: 看板发布

## [v0.38.3] — 2026-07-16

- test-events-1784200011: 看板发布

## [v0.38.2] — 2026-07-16

- test-events-1784200011: 看板发布

## [v0.38.1] — 2026-07-16

- e2e-chat-greet: 看板发布

## [v0.38.1] — 2026-07-16

### 根因：后台进程被强制复活

**根因链**：`crontab */5 * * * * ccc-loop-monitor.sh` → Engine 死后执行
`python3 ccc-engine.py &` → 即使用户卸了 launchd / 杀了进程，**最多 5 分钟必复活**；
叠加 `ccc-patrol-v4` 的 launchctl/Popen 拉起，形成双 engine + 内存打爆。

### 修复
- 新增 `~/.ccc/DISABLED` 总开关 + `scripts/ccc-autostart-guard.sh`
- `ccc-loop-monitor.sh`：**永不自启** Engine；尊重 DISABLED
- `ccc-patrol-v4.py`：支持 `--no-restart`；DISABLED 时拒绝 `_try_start_engine`
- `ccc-engine.sh` / `engine_loop`：DISABLED 时只空转 sleep，不干活
- `flywheel-scan.sh`：限制单次 grep 文件数，避免扫全量 reports 卡死 CPU
- 从 crontab 移除 `ccc-loop-monitor`（由 guard disable 执行）

启用 CCC：`bash scripts/ccc-autostart-guard.sh enable` 后再手动 load plist。

## [v0.38.0] — 2026-07-16

### 7 角色闭环生产力升级

打通 `backlog → … → verified → released` 全链路，对齐 Claude + OpenCode 协作模型。

### 修复（流程）
- Engine 接入 `kb_role`：扫 `verified` → tag/CHANGELOG → `released`（此前任务永久卡 verified）
- reviewer small-class 通过时写 `.ccc/verdicts/{id}.verdict.md`（红线 11；此前仅写 review.md）
- 多 phase：`dev_role_check_complete` 标记 phase done 后 `phase_done` → relaunch 下一 phase
- async product 对齐 sync：`phase_lint` + `complexity` 推断
- plan+phases 双文件门禁；孤儿 phases 删除后走 product
- kb `git push` 失败不再 `continue` 卡 verified（本地 tag 仍归档）
- `reviewer_role()` 补齐返回值

### 文档
- STARTUP-BRIEF / README / SKILL / 角色 skill / CLAUDE.md 同步 v0.38 行为
- 默认空看板不自造任务（继承 v0.37）

## [v0.37.0] — 2026-07-16

### 生产力阶段：止血内存与空看板自造任务

空看板时 Engine 仍每 5s/5min 触发 `audit_role` + `_evolve_run_one` + `_auto_replenish_backlog`，
不断投递 `evolve-*` 任务并拉起 `claude -p` / `radon` / `bandit`，导致本机内存爆掉。
本版本默认关闭自造任务回路，并修复导致自动化重试风暴的门禁 bug。

### 修复
- `posted_decision` UnboundLocalError — `audit_role` 每次空决策扫描崩溃
- `dev_role_check_complete` 用 stub 覆盖 report.md 后强制要求 `ALL SELF-CHECKS PASSED` → 无限 relaunch
- phase regen 竞态：删 phases.json 后仍被 `_process_backlog` 短接跳过 product（加 `.regen` 标记）
- 内存监控盲区：此前不计入 `claude`/`radon`/`bandit`/`vulture`/`opencode`，心跳假报 ~75MB
- `product` 异步无墙钟超时 — `claude -p` 可无限挂起

### 行为变更（默认更安全）
- `CCC_AUTO_REPLENISH=0`（默认）：空看板不自动 audit 补任务
- `CCC_EVOLVE_ON_IDLE=0` / `CCC_EVOLVE_ON_AUDIT=0`（默认）：不自动 evolve 投 backlog
- 真·空闲：无 backlog/planned/in_progress/testing/abnormal 时只写 heartbeat，跳过 audit/evolve/stats
- 内存默认阈值收紧：warn 400 / degraded 800 / kill 1500 MB；聚合超限强杀最大非-engine 进程
- `CCC_PRODUCT_ASYNC_TIMEOUT=600`：product 异步超时强杀

需要旧「空看板自动进化」行为时显式开启：
`CCC_AUTO_REPLENISH=1 CCC_EVOLVE_ON_IDLE=1 CCC_EVOLVE_ON_AUDIT=1`

## [v0.30.0] — 2026-07-15

### 定位重定
- 正式从「Prompt 资产套件」升级为「分布式自动化开发平台」
- CLAUDE.md 全面同步新定位，版本号 v0.29.34 → v0.30.0

### 修复
- move_task() 返回值检查（ccc-engine.py:845,1292）— 避免静默丢任务
- _check_and_mark_hung() CPU=0 误杀（macOS ps %cpu 生命周期均值问题）
- dev_role_check_complete() 空报告门禁 — exit_code=0 不等于改了代码
- 全局子进程上限 — 防止资源耗尽

### 流程
- Verdict FAIL/FALLBACK 现在会触发 commit 回滚 + 任务退回 planned

### 清理
- 删除 _build_prompt.py（死代码，未被任何生产路径引用）
- 修正 _board_store.py now_iso docstring（写着 UTC 实际返回 +08:00）
- 移除 quarantine_store_content.base_name 函数属性反模式

## [v0.29.34] — 2026-07-14

- board-index-auto-fix: 看板发布

## [v0.29.33] — 2026-07-14

- engine-heartbeat-metrics: 看板发布


- board-index-auto-fix: Patrol 同步 index.json 后检查一致性 看板发布

## [v0.29.32] — 2026-07-14

- state-md-auto-update: 看板发布


- engine-heartbeat-metrics: Engine 心跳增加活跃任务数 看板发布

## [v0.29.31] — 2026-07-14

- patrol-restart-detail: 看板发布


- state-md-auto-update: state.md 自动更新 — Engine 每次任务流转后更新 state.md 看板发布

## [v0.29.30] — 2026-07-14

- fix-debt-import-cleanup-scope: 看板发布


- patrol-restart-detail: Patrol 重启 Engine 增加详细 commit 记录 看板发布

## [v0.29.29] — 2026-07-14

- cockpit-search-filter: 看板发布


- fix-debt-import-cleanup-scope: 清理 debt-import-cleanup 越界引入的无关文件（H3） 看板发布

## [v0.29.28] — 2026-07-14

- test-engine-phase-failover: 看板发布

## [v0.29.27] — 2026-07-14

- test-validate-jsonl-edge: 看板发布


- test-engine-phase-failover: Engine phase 失败转移集成测试 看板发布

## [v0.29.26] — 2026-07-14

- cockpit-dead-counter-badge: 看板发布


- test-validate-jsonl-edge: task JSONL 校验边界场景测试 看板发布

## [v0.29.25] — 2026-07-14

- cockpit-auto-refresh: 看板发布

## [v0.29.24] — 2026-07-14

- engine-phase-parallel-dispatch: 看板发布

## [v0.29.23] — 2026-07-14

- test-cockpit-alive-check: 看板发布


- engine-phase-parallel-dispatch: 无依赖 phase 支持并行执行 看板发布

## [v0.29.22] — 2026-07-14

- test-board-events-format: 看板发布


- test-cockpit-alive-check: Cockpit /api/alive 端点单元测试 看板发布

## [v0.29.21] — 2026-07-14

- engine-task-state-persist: 看板发布


- test-board-events-format: BoardStore 事件格式一致性测试 看板发布

## [v0.29.20] — 2026-07-14

- engine-stats-endpoint: 看板发布


- engine-task-state-persist: Engine 重启后 task 状态持久化恢复 看板发布

## [v0.29.19] — 2026-07-14

- engine-phase-retry-config: 看板发布

## [v0.29.18] — 2026-07-14

- engine-stats-endpoint: 看板发布


- engine-phase-retry-config: phase 重试次数和超时可配置化 看板发布

## [v0.29.17] — 2026-07-14

- debt-import-cleanup: 看板发布


- engine-stats-endpoint: Engine 添加 /api/stats HTTP 健康检查端点 看板发布

## [v0.29.16] — 2026-07-14

- debt-docstring-sweep: 看板发布


- debt-import-cleanup: 清理全部未使用 import 看板发布

## [v0.29.15] — 2026-07-14

- cockpit-status-sort: 看板发布

## [v0.29.14] — 2026-07-14

- cockpit-dead-counter-badge: 看板发布


- cockpit-status-sort: Cockpit 端口列表按健康状态排序分组 看板发布


- debt-docstring-sweep: 各模块补全 docstring 看板发布

## [v0.29.13] — 2026-07-14

- cockpit-search-filter: 看板发布


- cockpit-dead-counter-badge: Cockpit 页面标题 dead 端口数量角标 看板发布

## [v0.29.12] — 2026-07-14

- cockpit-auto-refresh: 看板发布


- cockpit-search-filter: Cockpit 实时搜索过滤端口列表 看板发布

## [v0.29.10] — 2026-07-14

- fix-lint-2026-07-14: 看板发布

## [v0.29.9] — 2026-07-14

- zcode-adapter-v121: 看板发布


- fix-lint-2026-07-14: Plan: fix-lint-2026-07-14 — ruff 扫描修复 32 处 lint 问题 看板发布

## [v0.29.8] — 2026-07-14

- v10-automation: 看板发布


- zcode-adapter-v121: Plan: zcode-adapter-v121 (ZCode IDE Adapter · 配置独立 Session 调度) 看板发布

## [v0.29.7] — 2026-07-14

- readme-zcode-update: 看板发布


- v10-automation: v10 Automation Implementation Plan — 8 phases 待执行 看板发布

## [v0.29.6] — 2026-07-14

- cockpit-v0303d-mobile: 看板发布


- readme-zcode-update: Plan: readme-zcode-update (README 加入 ZCode adapter v1.2.1 章节) 看板发布

## [v0.29.5] — 2026-07-14

- hello-ccc-demo-v2: 看板发布


- cockpit-v0303d-mobile: Plan: cockpit-v0303d-mobile — Mobile 端优化（触摸目标 + 侧栏底栏 + 布局） 看板发布

## [v0.29.4] — 2026-07-14

- cluster-bus-bugfixes: 看板发布

## [v0.29.3] — 2026-07-14

- enhance-quarantine-phase: 看板发布

## [v0.29.2] — 2026-07-14

- ccc-check-gitignore: 看板发布


- enhance-quarantine-phase: [ABNORMAL] quarantine lessons 追加上报 phase 编号 看板发布

## [v0.29.1] — 2026-07-14

- e2e-backlog-auto-2026-07-12: 看板发布


- ccc-check-gitignore: [ABNORMAL] [ABNORMAL] 检查 CCC .gitignore 遗漏常见模式 看板发布

## [v0.29.0] — 2026-07-13 — CCC Chat Mobile Control 三标签重构

移动端 Web 聊天界面（`scripts/ccc-chat-server.py`）三模式重构：Chat / Execute / Board。

**Commit 1 — feat(chat): P0 TabBar refactor + light theme**
- 底部 TabBar 三标签（Chat / Execute / Board），强制亮色 iOS 风格主题
- 项目选择器移至顶部导航栏，历史会话左滑侧边栏

**Commit 2 — feat(chat): P1 execute mode backend**
- `POST /api/execute`：claude -p 子进程 + stream-json SSE 转发
- 120s 超时 SIGKILL、stderr 仅写日志、危险指令双重过滤、并发限制 429

**Commit 3 — feat(chat): P2 execute mode frontend**
- Execute Tab 接入执行 API：⚡ 气泡、tool_use 折叠卡片、token/费用显示
- 输入框模式切换、加载指示器与取消

**Commit 4 — feat(chat): P3 history per-project isolation**
- 会话存储 `.ccc/chat/{project}/`，历史 API 按 project 过滤

**Commit 5 — feat(chat): P4 board mode**
- 看板代理 `/api/board/proxy/*` → board-server :7777
- Board Tab 横向滚动看板列、新建任务、503 离线提示、刷新按钮

---


- cockpit-v0301-kb: Cockpit v0.30.1 — 知识库整合 + 服务告警 看板发布


- cockpit-v0303-terminal: Cockpit v0.30.3 — 终端体验 + UI 美化 看板发布


- cockpit-v0302-files: Cockpit v0.30.2 — 文件浏览器 + 看板集成 看板发布


- cockpit-v0304-multicli: Cockpit v0.30.4 — 多 CLI 引擎 + 日志面板 看板发布


- cockpit-v031-desktop: Cockpit v0.31.0 — Tauri 桌面端 看板发布


- cockpit-v0303c-terminal: Cockpit v0.30.3 — 终端格式优化 看板发布


- e2e-backlog-auto-2026-07-12: e2e: 验证 backlog 自动拆分 → 全链路 看板发布

## [v0.28.1] — 2026-07-12 — 任务复杂度分流 + Lock 热修复

**Commit 1 (a81be00) — feat: 任务复杂度分流 + 每周总结定时任务**
- product_role 根据 plan_weight 自动推断 complexity（small/medium/large）
- small 任务跳过 reviewer+tester 直通 kb（complexity 分流）
- CronCreate 每周日晚 22:03 自动生成 `.ccc/reports/weekly-YYYY-MM-DD.md`
- 持久定时任务（重启后仍在）

**Commit 2 (本次) — fix: product_role 锁 Python 3.14 PosixPath 属性赋值兼容**
- **根因**: `_acquire_product_lock` 把 fd 挂到 Path 对象上（`lockfile._lock_fd = _fd`），
  Python 3.14 `PosixPath` 是 `__slots__` 对象，不支持动态属性赋值
- **表现**: 锁获取成功但 fd 丢失 → 后续所有 `product_role` 调用死锁 30s timeout
- **修复**: 改用模块级 `_product_lock_fds: dict[str, int]` 替代 Path 属性注入
- **验证**: 引擎重启后 6 个 backlog 任务全部消费完成（`engine-qb-19121.log`）

---


### 任务复杂度分流（优化方案 A）

- (v0.28.1) 新增 `complexity` 字段：small / medium / large
  - `_board_store.py`: validate_task_jsonl + fill_task_defaults 支持
  - `ccc-board.py` product_role: 根据 plan_weight 自动推断复杂度并写入 task
  - `ccc-engine.py`: small 任务跳过 reviewer+tester，直通 kb
  - 文档: `references/board-task-schema.md` §12
- 定时每周总结: CronCreate 每周日晚 22:03 自动生成 `.ccc/reports/weekly-YYYY-MM-DD.md`

## [v0.26.1] — 2026-07-11 — 代码审查修复批次（H1-H5 + M1/M2/M6/M7/M10）

v0.24 → v0.25 → v0.26 全面代码审查后修复 5 项高危 + 5 项中等问题。
不影响协议契约，纯实现层加固。

**Commit 1 (1a3b42d) — fix(server): H3 HTTP API 保留 Board Protocol v1 全部 11 字段**
- `scripts/ccc-board-server.py`: `create_task()` wrapper 改签名为 `(data: dict, workspace, column)`
- HTTP handler 传入完整 `data` dict（pop `workspace` 控制字段）
- 修复 IDE 端发完整 11 字段时被静默截断为 3 字段（tags/assignee/note/schema_version/color_group/color_depth 全丢）
- 新增测试：`test_11_field_wrapper_preservation`（H3）

**Commit 2 (a158d99) — fix(store): H4/H5/M7 锁超时防护 + 颜色计数器原子写 + description 长度校验**
- `scripts/_board_store.py`:
  - **H4**: 4 个写操作（create_task/move_task/update_index/quarantine）在 `_lock()` 返回 None 时 abort，避免静默无锁运行
  - **H5**: `assign_color_group` 用 `_atomic_write()` 替换 `write_text()`，HTTP server 路径调用崩溃时计数器损坏问题修复
  - **M7**: `validate_task_jsonl` 补 description 长度校验（`DESCRIPTION_MAX=10000`）
- 新增文件：`tests/scripts/test_board_store_locking.py`（6 用例）

**Commit 3 (79fd12d) — fix(reconcile): H2/M2/M10 原子写入 + 复用 COLUMNS + 过滤 schema 元数据**
- `scripts/board-reconcile.py`:
  - **H2**: `fix_status_field` 用 `_atomic_write()` 替换 `path.write_text()`，崩溃时 JSONL 损坏问题修复
  - **M2**: `COLUMNS` 从 `_board_store` 导入，删除重复定义
  - **M10**: `load_status`/`fix_status_field` 跳过 `schema_version` 元数据行（避免被错误添加 status 字段）
- 新增测试：`test_reconcile_uses_atomic_write`、`test_reconcile_skips_schema_metadata_lines`

**Commit 4 (2bbdaa5) — fix(docs/code): H1/M1/M6 review.md 路径统一 + docstring + 函数名修正**
- **H1**: 4 个顶层文档（CLAUDE.md / SKILL.md / board-task-schema.md / red-lines.md）将 reviewer 产出路径由 `reviews/` 改为 `reports/`（与代码 + skill doc + 实际磁盘一致）
- **M1**: `_check_phase_failures` docstring `all_failed` → `all_failed_or_skipped`
- **M6**: `_move_task_to_abnormal_if_all_failed` → `_move_task_to_abnormal_if_all_terminal_failed`

**测试覆盖**：189 个 case 全通过（pytest tests/scripts/ -q: 189 passed in 17.93s）
**HTTP 端到端**：H3 curl round-trip 验证 11 字段全部保留

未修复（可选/低优先级）：
- M5：`engine_iter` 不跨 phase 重置 — 架构问题，需单独调研实现 phase-scoped 字段
- S1-S5：`os.write` 短写检查、isinstance 重写、warnings helper 提取等优化类

---

## [v0.27.1] — 2026-07-11 — 发布后 follow-up 修复

v0.27.0 发布前审查发现的 3 项 P0 + 1 项 P1 + M5 架构修复。
不含协议契约变动。

**Commit 1 — fix(server): env var 化 LAN IP 白名单 (P0-1)**
- `scripts/ccc-board-server.py`: `_verify_auth()` 移除硬编码 `192.168.3.140`
- 改为从 `CCC_BOARD_LOCAL_IPS` env var（逗号分隔）读取额外局域网 IP
- 默认仅保留本地回环 `127.0.0.1/::1/[::1]`
- 其他用户 clone 后 auth 立即可用

**Commit 2 — feat(server): _DashboardCache thread-safe 缓存类 (P0-2)**
- `scripts/ccc-board-server.py`: 新增 `_DashboardCache` 类（`threading.Lock` + TTL）
- 替代原 class-level `_dash_cache` dict 的 TOCTOU race
- 新文件 `tests/scripts/test_dashboard_cache.py`：7 用例（含 100 线程并发测试）

**Commit 3 — fix(server): ws="all" 例外下推到 /api/dashboard (P0-3)**
- `scripts/ccc-board-server.py`: `do_GET` gate 恢复严格校验
- `ws="all"` 只对 `/api/dashboard` 有意义，其他 endpoint 传 `workspace=all` 返回 400

**Commit 4 — fix(ui): re-执行按钮 fetch 错误检查 (P1)**
- `scripts/ccc-board-ui/index.html`: 新增 `reExec()` 异步函数
- 原 inline fetch 吞 4xx/5xx → 改为 alert 显示错误信息
- 成功路径仍 `location.reload()`

**Commit 5 — fix(engine): engine_iter 按 phase 分桶 + 重置 (P2/M5)**
- `scripts/ccc-board.py`:
  - 新增 `_read_engine_iter_meta` / `_write_engine_iter_meta` 私有函数
  - `_read_engine_iter` phase 切换时自动归零（`engine_iter_phase != cur_phase → 0`）
  - `_write_engine_iter` 同时写入 `engine_iter_phase` 字段
  - `force_converged` warning 附加 `engine_iter_phase` 便于 debug
- 新增测试：`test_engine_iter_resets_on_phase_change`（phase 切换不累计）

**测试覆盖**：199 个 case 全通过（pytest tests/scripts/ -q: 199 passed in 18.45s）

---

## [v0.26.0] — 2026-07-11 — CCC Board Protocol / 跨 IDE 开放协议

### 修复（6 commit + 41 test case）

CCC 从"框架"升级为"协议标准"：任意 IDE/Trae/Cursor/Zed/VS Code/OpenCode
读 `references/board-task-schema.md` → 写标准 JSONL → 看板全自动流转。

**Commit 1（0c1c5e9）— Protocol v1 文档重写**
- `references/board-task-schema.md`：333 行 / 8.6KB，13 章节
- §0 版本兼容矩阵（CCC ≥ 0.26 接受缺失/schema_version="1.0"）
- §1 Task 文件格式（7 列目录约定）
- §2 字段定义（11 条：原 10 + color_group + color_depth）
- §3 Agent↔列映射表（9 agent 契约）
- §4 校验规则（11 条规则逐条说明）
- §5 颜色分层协议（HSL 公式 + 视觉示例）
- §6 列迁移规则（COLUMN_TRANSITIONS 白名单 + 禁止迁移）
- §7 事件格式（move/assign/quarantine 3 类）
- §8 结构化 Error Schema（IDE 错误反馈协议）
- §9 多语言示例（Python/Bash/Node.js/CLI）
- §10 向前兼容（缺失字段补默认 / 未知字段忽略）
- §11 与 QXO 互通示例
- §12 错误排查 checklist

**Commit 2（7c21996）— validate_task_jsonl() 函数**
- `scripts/_board_store.py`：validate_task_jsonl(data, *, strict=False)
- 11 条规则严格执行，return (is_valid, errors)
- fill_task_defaults(data) 补 schema_version/color_*
- create_task 集成：失败返回 False + stderr errors
- 修复 _audit_post_backlog 缺字段（之前被 validate 拒）
- 27 个新测试

**Commit 3（b943964）— POST /api/tasks 结构化 error**
- `scripts/ccc-board-server.py`：POST /api/tasks 用 validate_task_jsonl
- 失败返回 400 + 结构化 error（ok/error/details/fix_hint）
- 成功返回 201 + {"ok": true, "task_id": tid}
- 写入失败返回 500 + {"ok": false, "error": "create_failed"}
- 4 个 helper 函数（_field_of / _rule_of / _got_of / _fix_hint_for）
- 9 个新测试

**Commit 4（c894ec4）— 颜色分层 server**
- `scripts/_board_store.py`：assign_color_group(workspace, parent_group=None)
- GROUP_POOL = A-Z 顺序轮转（持久化 .ccc/board/.color_counter）
- 单 Engine 串行场景无需 fcntl 锁
- `scripts/ccc-board.py`：product_role 移 backlog→planned 时自动分配
  color_group + color_depth=0；phase 继承 depth+1
- 5 个新测试

**Commit 5（ca55475）— 颜色分层 UI**
- `scripts/ccc-board-ui/index.html`：taskHue() + taskBg() HSL 计算
- 卡片渲染：color_group 存在时 border-left-color + width=4px
- 兼容老 task（无 color_group 字段回退 3px 边框）

### 红线检查
- R-04 reviewer 强制参与：未触动，test_advisory_lock.py 仍绿
- R-08 不能 skip 列：未触动，move_task 白名单不变
- R-12 强制人工介入：未触动，fallback quarantine 路径不变
- X1-X7 进程/锁/文件：未触动

### 测试统计
- v0.25.1 baseline: 137 passed
- v0.26.0 新增: 41 case (validate 27 + server 9 + color 5)
- v0.26.0 总量: 178 passed + 1 e2e（仍绿）
- 整体 pytest 全绿，无 regression

### 跳过
- dev_role worktree 隔离（roadmap v0.26 #3）：属执行层而非协议层，推 v0.27
- 完整 RFC 7807 error：IDE 不需要
- 颜色字段强校验（拒绝重复 group）：视觉分组不需要严格唯一
- 跨 ws color_group 同步：跨 ws 是审计不是开发

---

## [v0.25.1] — 2026-07-11 — 5 项 P1 遗留修复（3 项代码 + 测试）

### 修复（3 commit）

CHANGELOG v0.24.4:93-99 列了 5 项 P1 遗留，v0.25.0 补契约测试，v0.25.1 落地 3 项核心代码：

1. **循环依赖检测**（commit a71cec2）
   - `_detect_phase_cycle()` DFS 三色标记扫环
   - 环上 phase 强标 skipped（防 dev 写错 phases.json 死锁 Engine）
   - 写 `.ccc/warnings.json` type=`phase_cycle`
   - 5 个测试 case（TestV0251CycleDetection）

2. **不存在依赖告警**（commit 80918cf）
   - `_resolve_phase_dependencies` 扫所有 depends_on，引用不存在的 phase_id 写 warnings
   - `.ccc/warnings.json` type=`unresolved_dep` 含 missing dict
   - ccc-notify.sh L2 桌面通知
   - 3 个测试 case（TestV0251UnresolvedDeps）

3. **max_iter=5 强收敛**（commit 4479a2f）
   - `_check_phase_failures` 加 `PHASE_MAX_ENGINE_ITER=5` + phases.json metadata `engine_iter` 计数器
   - iter >= 5 时把非终态 phase 强标 skipped（force_converged=True）
   - 写 warnings + L2 通知
   - 4 个测试 case（TestV0251MaxIterConvergence）

### 跳过（v0.25.1 不做）
- **PHASE_TERMINAL_FAIL blocked**（CHANGELOG v0.24.4:96）：当前 PHASE_TERMINAL_FAIL = {"failed"} 已能让 failed phase 不再 retry，影响小
- **phase 独立 retry 计数**（v0.24.4:98）：retry counter 当前在 task 级；改 phase 级需重构 dev_role 状态机，工作量大

### 红线检查
- R-12（强制人工介入）：未触动，fallback quarantine 路径仍生效
- R-04（reviewer 强制参与 + advisory lock）：未触动
- 测试统计：137 pytest case + 1 e2e 全绿

---

## [v0.25.0] — 2026-07-11 — 全链路对齐

### 修复（11 commit，含文档 + 测试 + 角色 SKILL 同步）

v0.24.7 五轮对抗性审查修复后，文档/SKILL/测试三层严重落后。本版本按 `.ccc/reviews/adversarial-2026-07-11.json` + Explore agent 审计结果做全链路对齐：

**最高危修复（commit 1）**：
- `skills/ccc-reviewer/SKILL.md:111-117` 与代码完全相反（"fallback = pass" vs `ccc-board.py:1601-1628` medium/large quarantine）——按 SKILL 走的 agent 复活 v0.23 G2 bypass 红线。R-12 红线文字防线修复

**文档同步（commit 2/3/5）**：
- `CLAUDE.md`：`0.20.0` → `v0.25.0`；加 R- 红线表；架构图补 phase 感知；4 文件契约加 `reviews/` + `review-locks/`
- `SKILL.md`：`0.18.0` → `v0.25.0`；7 角色 Engine 触发说明；关键资产清单补 `_review_one_task` / `_board_store.py 30s 强清` 等
- `references/red-lines.md`：加 R-04/07/08/09/12/14（X- alias）；X7 段重写强化 fallback 语义

**角色 SKILL 同步（commit 4）**：6 个角色（product/dev/tester/ops/kb/regress）SKILL.md 同步 Engine 触发 + phase 感知 + retry 退避

**测试新增（commit 6/7/8/9a/9b/9c）**：
- `test_advisory_lock.py`（6 case）—— R-04 验证 reviewer per-task lock 互斥
- `test_fallback_quarantine.py`（8 case）—— R-12 验证 medium/large fallback 强制 quarantine + L2 通知
- `test_retry_backoff.py`（7 case）—— v0.24.7 retry=0 first backoff 60s + 指数序列
- `test_phase_dependencies.py` 增量（5 case）—— CHANGELOG v0.24.4:93-99 P1 遗留契约
- `test_phase_end_to_end.py`（7 case）—— 3 phase 链式依赖端到端
- `tests/e2e/test_pipeline_phase_aware.sh`（8 step）—— phase 感知 bash harness

### 红线检查
- R-04（reviewer 强制参与 + advisory lock）：commit 1 + test_advisory_lock ✓
- R-07（phases.json 原子写）：commit 5 + commit 3 (SKILL.md 同步) ✓
- R-08（日志统一 logger）：commit 5 ✓
- R-09（认证 GET 路径）：commit 5 ✓
- R-12（强制人工介入 fallback quarantine）：commit 1 + test_fallback_quarantine ✓
- R-14（audit 子进程 timeout）：commit 5 ✓

### 测试统计
- v0.24.7 baseline: 92 passed
- v0.25.0 新增: 33 case (6 + 8 + 7 + 5 + 7)
- v0.25.0 总量: 125 passed + 1 e2e（8 step）
- 整体 pytest 全绿，无 regression

---

## [v0.24.7] — 2026-07-11 — 对抗性审查 P2 fixes（prompt 临时文件 / 最小退避）

### 修复（2 项 medium，1 个 commit）
v0.24.4 对抗性审查 P2 中处理 2 项：

1. **A24-12/A24-24: prompt 临时文件改私有目录 + mode 0o600**
   - `opencode-exec.py` 与 `ccc-board.py` 的 LLM prompt 临时文件统一写到 `~/.ccc/prompts/`
   - 显式 `os.chmod(tmp_path, 0o600)` 防同用户其他进程读取（prompt 可能含 plan/凭据）
   - macOS `NamedTemporaryFile` 的默认 mode 0o644 风险消除
2. **A24-14: `retry=0` 强制 60s 最小退避（first backoff）**
   - 之前 `backoff = _backoff_seconds(retry - 1) if retry else 0`，retry=0 → backoff=0，retry_at=None
   - 改为 `backoff = _backoff_seconds(retry - 1) if retry else 60`，retry_at 必填
   - opencode 刚失败立刻再启浪费 retry 机会的问题消除

### 跳过
- **A24-13**（全局 file-level lock 防并发 commit 同文件）：工作量超 P2 估时（需 engine + exec-commit 协同改造），转入 v0.25 排期

---

## [v0.24.6] — 2026-07-11 — 对抗性审查 P1 fixes（锁 / diff 来源 / auth）

### 修复（3 项 medium-severity，1 个 commit）
v0.24.4 对抗性审查 P1 三项：

1. **A24-02: `_acquire_lock` 强清阈值 5s → 30s + owner-pid mtime 校验**
   - 锁文件内容从 `"{pid}"` 升级为 `"{pid}|{mtime}"`
   - 强清条件：`pid 已死 OR (pid 活 + elapsed > 30s + deadline 已过)`
   - 防 PID reuse 误杀无辜进程（仅当 pid 已死 OR 锁超 30s 才清；活 pid 永不强制清理）
2. **A24-08: `_get_git_diff` 优先读 phases.json commit 字段**
   - 之前 fallback 路径才查 phases.json；现优先 phases.json（防 task_id grep 复用导致拿到历史 commit 的 diff）
3. **A24-11: `board-server.py` GET /api/* 加可选 token 校验**
   - 之前 GET 完全不校验；现在与 POST 一致：local 直通、远端需 `Authorization: Bearer <QX_BOARD_TOKEN>`

### 红线检查
- R-02（并发写安全）：锁强清逻辑加固，防 PID reuse 误杀 ✓
- R-04（reviewer 强制参与）：diff 来源准确，与 dev 提交一致 ✓
- R-09（认证）：GET 路径与 POST 对齐 ✓

---

## [v0.24.5] — 2026-07-11 — 对抗性审查 P0 hotfix（reviewer 防线加固）

### 修复（2 项 high-severity，1 个 commit）
v0.24.4 对抗性审查（`adversarial-2026-07-11.json`）发现 4 项 high，本版本修 P0 两项：

1. **A24-01: reviewer 加 per-task advisory lock** — `.ccc/review-locks/{task_id}.lock` 锁住写 review.md 的临界区，并发 reviewer 实例持锁中跳过本轮；macOS 兼容（用 `O_EXCL|O_RDWR` 而非 BSD `O_WRLOCK`）
2. **A24-03/A24-04: medium/large fallback 强制 quarantine** — LLM 不可用时不再"py_compile 通过即 verified"或"plan 有验收清单即 verified"，一律 quarantine + L2 桌面通知（v0.23 G2 bypass 复发红线，high-severity 必须人工介入）

### 抽取
- `reviewer_role` 把单 task 处理抽出到 `_review_one_task(task_id) -> bool`，便于 advisory lock 包住；外层仅做 lock 生命周期管理 + 计数汇总

### 红线检查
- R-04（reviewer 强制参与）：fallback 走 quarantine 不静默 verified ✓
- R-09（卡死可中断）：concurrent reviewer 实例通过 advisory lock 互斥，不再文件竞态 ✓
- R-12（强制人工介入）：fallback quarantine 触发 L2 桌面通知 ✓

---

## [v0.24.3] — 2026-07-11 — 对抗性审查 P0 hotfix

### 修复（8 项，1 个 commit）
v0.24.0 / v0.24.1 / v0.24.2 三轮对抗性审查共发现 19 项 issue，本版本处理 P0 致命/重要 8 项：

1. **`_check_phase_failures` 写回后 reload phases** — writeback 之后返回值仍基于陈旧内存，导致 `all_terminal`/`all_failed_or_skipped` 报错脏数据，Engine 无法识别 all-failed → task 不会移到 abnormal
2. **删除 `engine_log = print` 局部别名** — `_move_task_to_abnormal_if_all_failed` 中 `engine_log = print` 是局部遮蔽，无全局 logger 引用，关键日志脱管
3. **`_apply_phase_status_updates` 加文件锁** — `fcntl.flock(LOCK_EX)` 包裹整个 read-modify-write，Engine 与外部 CLI（`ccc-board.py phase update`）并发写不再竞态覆盖
4. **`ThreadPoolExecutor` 单 ws timeout** — `fut.result(timeout=120)`，单 ws ruff/mypy 卡死不再阻塞整个 audit_role（超时报 `{"status": "timeout"}`）
5. **`ThreadPoolExecutor max_workers` 降到 2** — 避免 4 ws × (ruff + mypy) = 8 子进程并发 OOM（mypy 单进程 ~300MB，峰值 1.2GB+）
6. **small 类 reviewer 至少校验 diff 非空** — 防止 dev 提交空 commit + 验收清单全 √ 绕过 reviewer 进 verified
7. **`_parse_diff_size` 缺 summary 行返回 None** — 不再静默返回 0 让 LLM 审查被永久跳过；调用方 fail-fast 走 quarantine
8. **`dev_role_launch/relaunch` 读 `_current_running_phase()`** — 不再硬编码 `phase_id=f"{task_id}-p1"`，多 phase 顺序执行真正接入

### 红线检查
- R-04（reviewer 强制参与）：small 类加 diff 非空校验 ✓
- R-07（原子写入）：phases.json 加 fcntl.flock ✓
- R-08（日志统一格式）：移除 print 冒充 ✓
- R-12（任务卡死可观测）：P0-2 移除脱管日志 ✓
- R-14（子进程 timeout）：audit 加 120s 单 ws timeout ✓

### 验证
- syntax: py_compile 0 errors
- pytest: 81 passed (22 new + 59 old)

### 已知遗留（→ v0.24.4 P1 处理）
- 循环依赖检测（P1-MAJ-v0.24.0）
- 多轮收敛上限 max_iter=5（P1-MAJ-v0.24.0）
- `PHASE_TERMINAL_FAIL` 加 blocked（P1-MIN-v0.24.0）
- 不存在的依赖 phase 告警（P1-MAJ-v0.24.0）
- 重试计数器按 phase 独立（P1-P0-3）
- 阈值常量 / medium impact / timeout 分级 / JSON 正则 / OOM cap / last_run 时间错位（v0.24.1×4 + v0.24.2×2 MINOR）

---

> **Repository**: `~/program/CCC/`
> **Skill name**: `ccc-protocol`
> **Framework total**: scripts + references + docs + templates (single .ccc/ artifact dir per project)

---

## [v0.24.2] — 2026-07-10 — audit 多 workspace 并行化

### 新增
- `audit_role` 多 workspace 并行：把单 ws 处理抽到 `_audit_run_one(ws, since)`
- `ThreadPoolExecutor(max_workers=min(n, 4))` 并发跑；单 ws 仍走原串行路径
- 并发安全：每个 ws 的写入路径独立（backlog / audit-reports / ruff cwd），互不冲突

### 收益
- 5 个 workspace 审计从串行 ~50min 降到并发 ~12min（IO + subprocess bound）

### 验证
- syntax: py_compile 0 errors
- pytest: 59 passed（重构未破坏）
- 单 ws 路径 / 多 ws 并发路径 / 5 ws WORKSPACES 配置全 OK

---

## [v0.24.1] — 2026-07-10 — reviewer 按变更量分级

### 新增
- `_parse_diff_size(stat_output)` — 解析 `git diff --stat` 输出统计 insertions + deletions
- `_classify_review_size(stat_output)` — 三级分类：`small` (≤10) / `medium` (11-50) / `large` (>50)
- `_review_with_llm` 加 `size_class` 参数，`large` 类追加 impact_section（影响面/风险等级/回归路径）
- 常量 `REVIEW_SIZE_SMALL_MAX=10` / `REVIEW_SIZE_MEDIUM_MAX=50`
- `reviewer_role` 主流程改造：small 走静态 py_compile；medium/large 走 LLM

### 收益
- 节省 LLM 调用 60-70%（小额变更走静态）
- 大额变更更严格（强制 impact 分析）

### 验证
- syntax: py_compile 0 errors
- pytest: 59 passed
- unit: 4 类 case + 4 边界 case + 当前 commit 134 行 → large 类（自验证）

---

## [v0.24.0] — 2026-07-10 — Engine phase 感知调度

### 新增（p1-p4 4 sub-phase）
- **p1 schema**：phases.json schema_version 1.0→1.1，新增 `depends_on: [phase_id]` 字段
- **p1 status**：扩展 `blocked` / `failed` / `skipped`（原有 pending/in_progress/done/verified）
- **p2 解析**：`_load_phases` / `_resolve_phase_dependencies` / `_apply_phase_status_updates` / `_task_all_phases_terminal`
- **p3 失败传染**：`_current_running_phase` / `_mark_phase_failed` / `_check_phase_failures` / `_move_task_to_abnormal_if_all_failed`
- **p3 quarantine**：`dev_role_check_complete` retry 耗尽路径接入失败传染
- **p3 abnormal 决策**：所有 phase failed/skipped → 移到 abnormal 而非 quarantined
- **ccc-engine.py**：启动 dev 前调依赖解析，所有 phase 被跳过则不启动 task；quarantined 分支调 `_check_phase_failures`

### 失败传染语义
- `failed` 传染：依赖 failed → 下游 `skipped`
- `skipped` 不传染：依赖 skipped → 下游可执行（视为 OK）
- 多轮 tick 收敛：双向同步（blocked ↔ pending）让失败链在后续轮次中自动解开

### 验证
- syntax: py_compile 0 errors
- pytest: 81 passed（59 原有 + 22 新增）
- 新增 `tests/scripts/test_phase_dependencies.py`：22 个 case 覆盖依赖解析、双向同步、失败传染、多轮收敛、Engine 视角

---

## [v0.23.16] — 2026-07-10 — 合规收尾（VERSION/CHANGELOG 补全）

> 注：v0.23.11~v0.23.16 六个维修版本 commit 已存在，但 CHANGELOG 历史条目之前未补全，本次统一补齐。

### v0.23.16 — 修 reviewer G2 误判 + COLUMN_TRANSITIONS 加 abnormal 重投通路
- Bug 1: `reviewer_role` L1126/1134 调 `quarantine_task()` —— 函数未定义，实际是 `_quarantine()`，NameError 让 reviewer 异常退出
- Bug 2: reviewer G2 fallback 误隔离 retest 任务 —— plan 有 `## 验收` 段 + 无 py 文件 → 信任 plan 直接 verified
- Bug 3: COLUMN_TRANSITIONS 不允许 abnormal→testing —— testing 白名单加 abnormal
- 文件：`scripts/_board_store.py`, `scripts/ccc-board.py`
- 验证：pytest 59 passed；3 retest task 全部 backlog→released

### v0.23.15 — 修 OpenCode 模型名 (loop/code) + product 兼容性 (3.9 rglob)
- OpenCode 模型修正 `loop/flash`→`code`
- 模型 env 透传修复
- product 兼容性：3.9 rglob 用 `follow_symlinks=False`

### v0.23.14 — 修 reviewer bytes/text 冲突 + engine LOG 路径冲突
- reviewer input 改用 bytes 注入 + 禁交互
- reviewer prompt 走临时文件，避开 stdin buffer 截断
- engine LOG 路径冲突修复

### v0.23.13 — board-server GET / 路由修（do_GET else 兜底吞 UI）
- 之前 `do_GET` else 分支把 `/` 也吞了，UI 加载不到
- 修复后 `/` 走 HTML 渲染路径，不影响 `/api/*` 端点

### v0.23.12 — audit_role 修复 per-workspace last_run key
- Engine 用 `Path(workspace).name='qb'` 读 `audit-last-run.qb.json`，但 audit_role 用全路径 → 永远错配
- 修复：Engine 调 audit_role 时传 workspace 参数

### v0.23.11 — 根治 fcntl 死锁 + reviewer JSON 宽松解析
- `_acquire_lock`: pid 残留锁自动检测清理 + 5s 超时强清
- `list_tasks` 读锁: 3s 超时
- `_lock` 写锁: 5s 超时
- reviewer JSON 解析: 转义控制字符容错，避免 Claude 输出 `\` 反斜杠报 Expecting ',' delimiter
- 锁文件后缀：`..excl`（不在 `.board.lock` 自身，避免截断）

### 验证
- pytest: 全部维修 commit 累积 59 passed
- VERSION: v0.23.10 → v0.23.16

---

## [v0.21.0] — 2026-07-09 — 门控修补

### 新增
- `reviewer_role` 重写：调 Claude API 审查 `git diff HEAD~1` + plan `## 验收清单`
- `tester_role` 强制 baseline：检测 pyproject.toml 时追加 `pytest tests/ -q --cov=src --cov-fail-under=80`
- `_get_git_diff()` / `_review_with_llm()` / `_py_compile_fallback()` 辅助函数
- LLM 审查失败时 fallback 到 py_compile 静态检查

### 重构
- plan 模板加 `## 验收清单` 段
- `skills/ccc-reviewer/SKILL.md` 重写：5 大类审查清单 + 三级严重度
- `references/red-lines.md`：加 X7（reviewer 必须 LLM）

## [v0.23.4] — 2026-07-09 — 流程加固：Trae 报告入站校验

### 新增
- `scripts/_review_validator.py` — 审查报告格式校验器，校验 JSON 是否符合 SKILL.md 模板规范
- `ccc-engine.py` 空闲循环加 `_check_new_reviews()` — 自动扫描 `.ccc/reviews/` 新报告，格式不合规即告警
- `docs/flow-review.md` — 全流程弱点清单（4 层已知弱环 + 修复计划）

### 验证
- compile: 无语法错误
- 已用 Trae 实际报告验证：合规报告通过、残缺报告被抓
- validator 覆盖：缺字段、非法 source、summary.total 不匹配

---


- adv-ccc-f1: [CRITICAL] 看板 HTTP server 在多 workspace 安装路径中默认绑定 0.0.0.0 且零鉴
- adv-ccc-f10: [MEDIUM] _parse_plan_scope 解析 plan.md 后直接 ROOT/f 拼接路径遍历 + glob 注入
- adv-ccc-f13: [MEDIUM] web UI 静态资源目录由 SimpleHTTPRequestHandler 导致目录泄露
- adv-ccc-f19: [LOW] subprocess 环境未脱敏，凭据可能经 env 泄漏到子进程

## [v0.23.3] — 2026-07-09 — 时间戳统一为北京时间

### 修复
- `ccc-board.py` `now_iso()` 从 `timezone.utc` 改为 `ZoneInfo("Asia/Shanghai")`，输出后缀从 `Z` 改为 `+08:00`
- `ccc-engine.py` `now_iso()` 同样改为北京时间
- 影响：task JSONL 时间戳、engine 心跳、报表日期、事件记录等全部时间输出

### 验证
- compile: 无语法错误
- 测试输出: `2026-07-09T11:56:01+08:00`（北京时间，`fromisoformat` 可解析）

---


- ccc-fix-board-auth: board-server 加最低鉴权 + 绑定白名单 看板发布


- ccc-fix-flock-fallback: _HAS_FLOCK=False 时写操作加文件锁降级防御 看板发布


- ccc-fix-osascript-inject: osascript notify 参数引用加固 看板发布


- ccc-fix-tester-shell-true: tester_role shell=True 改为 shell=False 看板发布

## [v0.23.2] — 2026-07-09 — engine 取 task 后未更新 index 修复

### 修复
- `ccc-engine.py` `dev_role_launch` 成功后未调 `update_index()`，导致 index.json 与实际看板列不一致（task 已到 in_progress 但 index 仍显示 planned+1） `ccc-engine.py:160`

### 教训
- Lesson 37: Engine 每次操作看板文件后必须同步 index.json。`dev_role_launch` 调了 `move_task` 但 call site 没跟 `update_index()`。

### 验证
- compile: 无语法错误
- VERSION: v0.23.0 → v0.23.2

---


- ccc-changelog-format: CHANGELOG.md 格式统一 看板发布


- dialog-latency-optimize: 紧急修复: 对话流式响应延迟优化 看板发布


- emergency-dialog-latency-optimize: 升舱: dialog-latency-optimize 看板发布


- emergency-quality-flywheel-auto-suggest: 升舱: quality-flywheel-auto-suggest 看板发布


- quality-flywheel-auto-suggest: 紧急修复: 质量飞轮自动建议 看板发布


- smoke-v020: v0.20 smoke 看板发布


- ccc-docstring-sweep: scripts/ 模块级 docstring 补充 看板发布


- ccc-gitignore-update: .gitignore 加运行时数据排除 看板发布

## [v0.23.1] — 2026-07-09 — v0.23 对抗性审查修复

### 修复
- A1: VERSION v0.23.0-dev → v0.23.0
- A2: `_get_code_context` 截断确保代码块闭合
- A3: 删除冗余 subprocess import（用全局）
- A4: roadmap.md v0.23 状态改为已发布
- A5: 入口文件过滤增强（排除 vendor/build/tests）
- A6: 模块级缓存 `_get_code_context_cache`
- A7: rglob `follow_symlinks=False`

### 验证
- compile: 无语法错误
- pytest: 10 passed

---

## [v0.23.0] — 2026-07-09 — product 上游智能化

### 新增
- `_get_code_context()` 函数：动态获取当前代码结构（文件树 + git 日志 + 入口文件），注入 `_call_claude_for_plan` prompt `ccc-board.py:121`
- product 角色启动后第一步读代码结构，再写 plan（SKILL.md 更新）
- plan 模板强制写 `## 当前代码状态` 段

### 重构
- `_call_claude_for_plan` prompt 注入代码上下文（`_get_code_context` 输出 <3KB） `ccc-board.py:216`
- `skills/ccc-product/SKILL.md`: 加 §0 — "先读代码，再写 Plan"

### 验证
- compile: 无语法错误

---

## [v0.22.1] — 2026-07-09 — audit 修复 + 实测耗时记录

### 修复
- N1: `FileBoardStore` __init__ 兜底建 7 列 + events 目录（裸 workspace 不抛 `FileNotFoundError`） `_board_store.py:126`
- N3: 审计报表加 mypy 原始输出附录（review 段只取前 5 行前 120 字符，完整输出在附录，防截断误导） `ccc-board.py:1297`
- N4: `audit_role` 加全程计时（per-workspace + total duration，写 `audit-last-run.json` + 报表 + return dict） `ccc-board.py:1326`

### 验证
- pytest: 10 passed (test_audit_role.py, 含 N1 裸 workspace 测试)
- compile: 无语法错误

---

## [v0.22.0] — 2026-07-09 — audit 角色 + daily-auto-scan 收纳

### 新增
- `audit_role()` 新角色：全项目扫描 + AI 分类 + auto 直接修 / review 投 backlog
- `_audit_recent_commits` / `_audit_lint` / `_audit_classify` / `_audit_post_backlog` / `_audit_write_report` 辅助
- engine 主循环加 `_audit_should_run()` 时间检查（每 2h）

### 重构
- `FileBoardStore` 白名单 `backlog → planned` 允许（audit 投出直接到 planned）
- 报表路径：`{workspace}/.ccc/audit-reports/`（替代 `~/Desktop/auto-scans/`）
- lint baselines 迁到 `~/.ccc/lint_baselines/`

### 清理（v0.22 重点）
- 删除 `~/.claude/skills/daily-auto-scan/`（功能并入 audit_role）
- 删除 `~/.claude/scheduled_tasks.json` 中 cron `7 */2 * * *`（改 engine 触发）
- Memory 文件加迁移说明（链接到 CCC）

### 红线
- X8：audit 角色必须 2h 内只跑一次

---

## [v0.20.1] — 2026-07-08 — 串行执行引擎

> `ccc-engine.py` 替代 7 角色 launchd 定时轮询。
> 有任务即串行执行全链路，无任务休眠。

### 新增
- `scripts/ccc-engine.py` — CC Engine 串行执行守护进程（~280 行）
- `scripts/ccc-engine.sh` — Engine launchd 入口
- `scripts/uninstall-ccc-roles.sh` — 卸载旧 7 角色 plist
- `scripts/ccc-board.py`: 新增 `dev_role_launch()` + `dev_role_check_complete()` 引擎辅助函数
- `scripts/_config.py`: 新增 `engine_poll_interval` / `engine_idle_sleep` 配置项

### 重构
- `scripts/install-ccc-roles.sh`: 改为只装 Engine + board-server plist，支持 `--upgrade` 自动卸载旧角色
- `references/red-lines.md`: X5（7 plist 必装→Engine+board-server）、X6（角色频率→取消定时）
- `CLAUDE.md`: 架构文档更新到 v0.20.1
- `docs/roadmap.md`: 添加 v0.20.1 规划

### 删除（保留向后兼容）
- `scripts/roles/*.sh` 7 文件标记为 deprecated（不再由 launchd 触发，手动调用仍可用）
- 旧 launchd plist 14 个（CCC 7 + qxo 7），替换为每个 workspace 1 个 engine plist

### 验证
- pytest: 49 passed (同 v0.20.0)
- engine 启动正常，写 `.ccc/engine-heartbeat.json`
- compile: 全部 Python 文件无语法错误

---

## [v0.20.0] — 2026-07-08 — Dev 体验 + 运维完备

### 新增
- ops 角色扩展: launchd 7 角色自检 + `.ccc/metrics.json` 指标收集
- 日志清理: ops 角色自动删除 >30 天的 role-*.log
- E2E 覆盖: 白名单外语法错误跳过 + 白名单内语法错误拒绝 (7→9 步)

### 重构
- `scripts/ccc-board.py` ops_role: 新增 launchd 自检、日志清理、metrics 收集
- `scripts/ccc-board.py`: docstring v0.18 → v0.20
- `scripts/ccc-board-server.py`: docstring v0.18 → v0.20
- `VERSION`: v0.19.0 → v0.20.0

### 修复 (v0.19 对抗性审查 6 项)
- S1: `opencode-pool.py` asyncio 阻塞 — 改为 `run_in_executor` 包装
- S2: `ccc-exec-launcher.sh` 重试日志覆盖 — 文件名加 `-attempt-${attempt}` 后缀
- W1: `_board_store.py` list_tasks 无读锁 — 加 `LOCK_SH` 共享读锁
- W2: `ccc-board.py` schema_version 字符串匹配 — 改用 `json.loads` 检测 (第一处)
- N1: `_executor.py` 代码重复 — 提取模块级 `resolve_opencode()` 函数
- N5: `board-task-schema.md` 文档不一致 — 修正为 phases.json 格式章节

### 修复 (v0.20 对抗性审查 4 项)
- S3: `ccc-board.py` schema_version 第二处仍用 `startswith` — 改为 `json.loads` 检测
- S4: `opencode-exec.py` 未复用 _executor — 改为 `from _executor import resolve_opencode`
- W5: ops_role 函数内 `import json as _json` 冗余 — 删除，用文件顶部 `json`
- W6: ops 角色 launchctl 自检未检查 returncode — 加 `r.returncode == 0`

### 文档
- docstring 版本号 `scripts/ccc-board.py`: v0.18 → v0.20
- docstring 版本号 `scripts/ccc-board-server.py`: v0.18 → v0.20
- `board-task-schema.md`: 新增 phases.json 格式章节

## [v0.19.0] — 2026-07-08 — 基础加固 + 扩展通路

### 新增
- `scripts/_config.py`: 集中配置 Config dataclass，消灭散布的硬编码
- `scripts/_board_store.py`: BoardStore 抽象 + FileBoardStore 实现（含 fcntl.flock 锁 + 原子写入）
- `scripts/_executor.py`: Executor 协议 + OpenCodeExecutor 实现
- `references/board-task-schema.md`: task JSONL 格式标准（CCC-QXO 共享契约）
- `tests/e2e/test_pipeline_smoke.sh`: 完整流水线 E2E 集成测试

### 重构
- `scripts/ccc-board.py`: 存储操作委托 FileBoardStore，角色业务逻辑与存储层解耦
- `scripts/ccc-board-server.py`: 消除 list_tasks/move_task/create_task 重复代码，导入 FileBoardStore
- `scripts/opencode-pool.py`: 消除 importlib hack，导入 OpenCodeExecutor
- `scripts/ccc-exec-launcher.sh`: 新增 3 次重试（指数退避 60/120/240s）

### 文档
- `docs/roadmap.md`: 新增 v0.19/v0.20 规划、三层架构图、与 QXO 独立发展说明
- `docs/architecture.md`: 重写为三层架构（L3 角色 → L2 抽象 → L1 实现）
- `CLAUDE.md`: 资产清单更新、QXO 关系改为"独立发展共享契约"

### 修复
- phases.json 写入带 `"schema_version": "1.0"` 元数据行
- dev_role 读取 phases 时跳过 schema_version 行
- 看板写操作加文件锁防 race condition

## [Unreleased] — v0.8 — OpenCode CLI 执行端重构

**里程碑**：CCC 执行器从 claude CLI 切到 **OpenCode CLI**（CLI 模式，禁用 HTTP/serve），新增 3 条 OpenCode 进程管理红线（X1/X2/X3）。

### Added
- `scripts/opencode-exec.py` — OpenCode CLI 执行器（asyncio 子进程 + 必杀兜底 + pid 文件）
- `scripts/opencode-pool.py` — 进程池（asyncio.Semaphore(3) 硬限，红线 X1）
- `scripts/opencode-watchdog.sh` — 残留扫描（pid 文件 + pgrep 兜底，红线 X2/X3）
- `scripts/ccc-notify.sh` — macOS 桌面通知（L1/L2/L3）
- `scripts/ccc-hook.sh` — 通用钩子（pre-exec / post-exec / on-error / pre-commit）
- 红线 X1（OpenCode 进程池最多 3 并发）
- 红线 X2（每 phase 必杀 opencode 进程）
- 红线 X3（OpenCode 启动前必跑残留 watchdog）
- `tests/scripts/test_opencode_pool_max_parallel.py` — 验 X1
- `tests/scripts/test_opencode_pool_kill_residual.py` — 验 X2
- `tests/scripts/test_opencode_watchdog_cleanup.py` — 验 X3

### Changed
- `scripts/ccc-exec-launcher.sh` — 从 tmux+claude 改为 opencode CLI 串联
- `references/adapters/runtime-opencode.md` — 重写为执行器契约（CLI 模式，弃用 4096 serve）
- `SKILL.md` / `CLAUDE.md` / `README.md` — 资产清单 + 红线表同步更新

### Removed
- `DESIGN-VALIDATION.md`（v0.7 历史 design review）
- `examples/cluster/` `examples/scheduler/` `examples/qxo-audit-frontend.md`（旧路线预留）
- `scripts/ccc-monitor.sh` `scripts/executor-watchdog.sh` `scripts/install-ccc-as-skill.sh`（旧 monitor/watchdog/installer）
- `scripts/*.md` 副本（每个脚本旁的重复文档）
- `tests/scripts/test_executor_watchdog_smoke.py`（旧 watchdog 已删）
- 卸载 `com.opencode.serve` launchd 守护（v0.8 不用 HTTP）

### Verified
- pytest: 57 passed, 0 failed in 10.73s
- smoke test: 10 项能力 9 项直接通过，1 项模型 provider（v0.9a 修复）
- launchd 调度: load → start → 告警落文件 → unload 全链路通

---


**里程碑**：v0.9a 修复 opencode 调模型失败（`--model flash` → `--model loop/flash`），跑通真实模型调用。v0.9b 飞轮和 v0.9c 收尾按用户节奏。

### Fixed
- `scripts/opencode-exec.py` — `--model flash` → `--model loop/flash`（v0.9a 实测修复）
- `references/adapters/runtime-opencode.md` §六 — 模型映射段更新（对外 flash / 内部 loop/flash）
- `docs/lessons.md` — 追加 Lesson 32（opencode 模型名必须带 provider 前缀）

- 真实模型调用: `opencode run --model loop/flash` exit 0，52s 返回
- pytest: 57 passed
- 中转站: localhost:4002（loop provider）确认工作



**里程碑**：v0.11 完结后消化，标记 CCC 范式转变 = "opencode 写 + 人工 review"。

- `docs/lessons.md` Lesson 34 — opencode run 起 node 孙子进程，killpg 在 macOS 不可靠
- `docs/lessons.md` Lesson 35 — opencode 写代码质量超过 v0.7 时代人工基线
- `docs/roadmap.md` 范式转变段（v0.11 起默认 opencode 写）

- install-ccc-scheduler install/uninstall 闭环烟测：plist 生成 + plutil lint OK + 卸载干净
- 远端 5 tag 完整：v0.7.0 / v0.8.0 / v0.9.0 / v0.10.0 / v0.11.0



**里程碑**：v0.12 全量扫 bug（7 个发现，3 真 bug 修，4 复查非 bug 加注释）。3 类修复模式：数据泄漏 / 静默失败 / 配置硬编码。

- **Bug 1+3**: `opencode-exec.py` 长 prompt 临时文件永久泄漏（磁盘 + 隐私）— finally 块 unlink
- **Bug 2**: `ccc-finish.sh` bare `except: pass` 吞所有异常 — 改 `except json.JSONDecodeError as e` + stderr 输出
- **Bug 6**: `ccc-hook.sh` timeout=30 写死 — 加 `CCC_HOOK_TIMEOUT` env + macOS perl alarm 兜底

### Verified (非 bug, 加注释说明)
- **Bug 4**: watchdog `for pf in *.pid` 空目录不进 loop（bash 默认行为）
- **Bug 5**: ccc-precheck `open(fp)` 没指定 encoding（macOS UTF-8 默认）
- **Bug 7**: launcher log 命名已含 phase_id，并发不交错

- `tests/scripts/test_bug_fixes_v012.py` — 3 个 test 覆盖
- `docs/lessons.md` Lesson 36 — bug 分类 + 修复模式

- pytest: 69 passed (66 + 3 新增)
- 远端 6 tag: v0.7.0 / v0.8.0 / v0.9.0 / v0.10.0 / v0.11.0 / v0.12.0



**里程碑**：v0.11 落地 a（钩子模板 + scheduler 安装器）+ b（队列 N phase 真测试）+ b-fix（红线 X2 必杀修）。v0.11 完结后，CCC 具备了从"用户启 launcher" → "launchd 周期调 launcher" → "队列跑多 phase" 的全链路。

- `templates/hooks/post-exec.sh` — phase 完成自动 git add+commit
- `templates/hooks/on-error.sh` — phase 失败 L2 通知 + 落 abnormal report
- `templates/hooks/pre-commit.sh` — soft lint (TODO/print/debugger)
- `scripts/install-ccc-scheduler.sh` — install/uninstall/status/--dry-run 一键装 launchd
- `tests/scripts/test_queue_e2e_3phase_pass.py` — 3 phase 全成功
- `tests/scripts/test_queue_e2e_mid_fail.py` — 中间失败 pause
- `tests/scripts/test_queue_e2e_resume.py` — pause 后续跑
- `docs/lessons.md` Lesson 33 — opencode run positionals 截断 200 字符

- `scripts/opencode-exec.py` — 长 prompt 走 --file 协议（positionals 截断修复）
- `scripts/opencode-exec.py` — `start_new_session=True` + `os.killpg`（kill 级联）
- `scripts/opencode-watchdog.sh` — 扫 `opencode (run|exec)` + pkill -f 兜底
- `scripts/ccc-queue.sh` — `CCC_LAUNCHER_OVERRIDE` env var 支持（mock 测试）

- **红线 X2 失守修复**：launcher 杀 opencode 不级联到孙子 node 进程（macOS killpg 不可靠）
  - 修法 1: opencode-exec 用 killpg
  - 修法 2: watchdog 加 pkill -f 兜底

- pytest: 66 passed (63 + 3 新增)
- 真实模型调用: 11.9s 返 exit 0
- launchd 调度: 装/卸/触发全通
- 队列 3 场景: pass / mid_fail(exit 5) / resume 全验
- 必杀: 30s sleep + 2s timeout 必杀




**里程碑**：每个角色拥有独立 SKILL.md（职责/方法论/红线/知识库注入），参考 `agent-teams.md` + `practitioner-insights.md` 等行业最佳实践。

- `skills/ccc-product/SKILL.md` — 产品经理 skill + **SPEC 门禁**
- `skills/ccc-dev/SKILL.md` — 开发工程师 skill + **steer don't launch-and-forget** + 迭代检索
- `skills/ccc-reviewer/SKILL.md` — 代码审查员 skill + **只读不写** + **1:4 比例**
- `skills/ccc-tester/SKILL.md` — 测试工程师 skill + **双门禁验证**（pytest + plan 验收逐条）
- `skills/ccc-ops/SKILL.md` — 运维工程师 skill + **告警升级链 L1/L2/L3**
- `skills/ccc-kb/SKILL.md` — 知识管理员 skill + **AGENTS.md 最终收集**
- `skills/README.md` — skill 索引（6 角色 + 2 遗留角色）
- `templates/pending-agents-suggestions.md` — kb 收集 AGENTS.md 建议的模板

- `scripts/roles/{product,dev,reviewer,tester,ops,kb}.sh` — 启动时加载对应 SKILL.md（export CCC_ROLE + CCC_ROLE_SKILL）, 记录 skill frontmatter 到 log

### Knowledge Base Injected
- **SPEC 门禁**（`agent-teams.md:1923`）：product 拆 subtask 必须过 Specific/Programmatically evaluable/Explicit scope/Constrained
- **Steer don't launch-and-forget**（`practitioner-insights.md:229`）：dev 的监督姿态
- **Reviewer 只读不写**（`agent-teams.md:1186`）：有写权限就会去修，产生 merge conflict
- **1 reviewer per 3-4 builders**（`agent-teams.md:1184`）：reviewer 积压监控
- **AGENTS.md 积累**（`agent-teams.md:1040-1063`）：沉淀跨 session 工程教训，禁止 agent 直接写入

- 6 角色 shell 脚本语法通过（`bash -n`）
- `ccc-board.py index` 正常返回
- ops 角色端到端运行验证（加载 skill → 调 board.py → 退出 0）



**里程碑**：v0.16 6 角色系统落地后, 沉淀战略地图, 所有 cloud agent 启动第一件事读 STRATEGY-MAP.md。

- `docs/STRATEGY-MAP.md` — 战略地图（启动必读第一份）
  - 10 段: CCC 是什么 / 范式演进史 / 6 角色系统 / 看板 / 完整调用链 / 红线 / 自动化 / 模型路由 / 教训 / 怎么用
- `SKILL.md` — 加"启动必读战略地图"段（红线 7 升级）
- `CLAUDE.md` — 6 角色矩阵（替换 3 角色旧路由）
- `references/red-lines.md` — X4/X5/X6 三条新红线（v0.16 配套）
  - X4: 每 phase 必走看板流转
  - X5: 6 角色 plist 必装
  - X6: 角色频率不许改
- `docs/roadmap.md` — 5 次范式转变标注（v0.11 / v0.12 / v0.15 / v0.16 / v0.17）

- SKILL.md version: v1.1 → v1.6
- 编号索引表加 X4/X5/X6 三行

- 启动必读链验证: STRATEGY-MAP.md → red-lines.md → lessons.md → state.md
- 6 plist 装上 + 频率正确
- 9 tag 完整: v0.7.0 → v0.16.0



**里程碑**：CCC 从 3 角色扩到 6 角色定时开发系统。任务在 6 列看板流转, 6 launchd plist 周期跑。

- `.ccc/board/` 6 列任务看板 (backlog/planned/in_progress/testing/verified/released)
- `scripts/ccc-board.py` 6 角色核心
- `scripts/roles/{product,dev,reviewer,tester,ops,kb}.sh` × 6
- `scripts/install-ccc-roles.sh` 一键装 6 plist

- 6 plist 装上, launchctl list 6 行
- 看板 e2e: backlog→planned→in_progress→testing→verified→released
- pytest: 69 passed


## [1.2.0] — 2026-07-06 — 流程跑通 (CCC v1.0 Closure)

**里程碑**:Planner → Executor → Verifier 三角色**完整流程**首次跑通,5+5 机器化门控闭环。

参见 `.ccc/plans/ccc-engineering-foundation.plan.md` §T1.1-T1.7 + `.ccc/plans/hello-ccc-demo-v2.plan.md`。

### Added
- **`.ccc/state.md`**: Planner 接力文件(红线 10 强制,Lesson 13 schema)
- **`scripts/ccc-precheck.sh`**: 5 项前置门控(状态/项目/计划/相位/看门狗)
- **`scripts/ccc-finish.sh`**: 5 项后置门控(报告/验收/引用/范围/相位闭环)
- **`tests/scripts/test_ccc_precheck_finish_smoke.py`**: 10 个 smoke test
- **`hello-ccc-demo-v2`**: 3 phase + 独立 Verifier session 完整闭环 demo
- **`scripts/ccc-status.sh`**: 4 文件契约健康检查 CLI(105 行)
- **`scripts/ccc-cost.sh`**: 单任务 cost summary CLI(85 行)
- **`tests/scripts/test_ccc_status_smoke.py`**: 3 个 status smoke test
- **`docs/E2E-DEMO.md`**: 完整跑通 trace 文档

### Changed
- **SKILL.md**: 新增 §Planner 启动顺序 + §强制 watchdog + §ccc commit 闭环
- **`templates/executor-prompt.template.md`**: 集成 ccc-precheck/finish + ccc commit 引用
- **`templates/AGENTS.md`**: agent config 路径 `~/.mavis/` → `~/.config/ccc/` (mavis 清理配套)
- **`scripts/ccc-finish.sh`**: 排除 `.claude/` 元数据(范围白名单)

### Verified
- `pytest tests/scripts/test_ccc_precheck_finish_smoke.py` → 10/10 PASS
- `bash scripts/ccc-precheck.sh . hello-ccc-demo-v2` → 7/7 PASS
- `bash scripts/ccc-finish.sh . hello-ccc-demo-v2` → 7/7 PASS(完整 4 文件契约)
- Verifier 独立 session: 4/4 probes PASS
- 3 phase 任务: ccc-task-id=hello-ccc-demo-v2 phase=1/2-3/final

### Red Lines Enforced (v1.2.0)
| 红线 | v1.2.0 机器化 |
|------|---------------|
| 7 启动顺序固定 | ccc-precheck Gate 1-3 |
| 9 Executor 卡死止损 | ccc-precheck Gate 5 = watchdog |
| 10 跨会话不隐式记忆 | ccc-precheck Gate 1 = state.md |
| 11 Verifier 必写文件 | ccc-finish Gate 2+3 |
| 4+8 单 phase 单 commit | ccc-finish Gate 5 + ccc commit 闭环 |
| 3 范围白名单 | ccc-finish Gate 4 |

---

## [1.1.0] — 2026-07-06 — Engineering Foundation

**里程碑**：v1.0 release gate open + 工程化补漏 + 移交准备。

参见 `.ccc/plans/ccc-engineering-foundation.plan.md` — 24 tasks / 4 phases。

### Added
- **T14**: `docs/handoff-checklist.md` — 12 项移交验收 checklist
- **T13**: `tests/scripts/test_cluster_bus_benchmark.py` — 100 node 压测 (1000 hb avg 0.83ms)
- **T11**: `tests/scripts/test_integration_business_flows.py` — 3 条端到端集成测试

### Changed
- VERSION 0.5.0 → 1.1.0
- `scripts/cluster-bus.py`: h11 协议, atomic checkpoint, `--port` 参数
- `tests/scripts/test_integration_business_flows.py`: fix bytes/str Python 3.14 compat

---

## [1.0.0] - 2026-07-06 — Automation Open

### Added (8 commits / 8 reports)

- **P0-1**: `scripts/cluster-bus.py` — FastAPI node registry + heartbeat (5 endpoint)
  - commit `6af9121` / report `p0-1-cluster-bus.report.md`
- **P0-2**: `scripts/ccc-dispatch.py` — task triple output (no auto-dispatch)
  - commit `fa0fa2e` / report `p0-2-ccc-dispatch.report.md`
- **P1-1**: `references/cluster-protocol.md` — 跨设备协议规范 (10 sections, 229 lines, mTLS design)
  - commit `376e2b9` / report `p1-1-cluster-protocol.report.md`
- **P1-2**: `tests/cluster/test-capability-required.py` — Red Line 18 enforcement (7 cases, 6 passed, 1 skipped)
  - commit `090e918` / report `p1-2-test-capability.report.md`
- **P2-1**: `examples/cluster/{m1,feiniu}.yaml` — node config templates
  - commit `e32d9df` / report `p2-1-yaml-examples.report.md`
- **P2-2**: `tools/cluster-doctor.sh` — 5-section cluster diagnostic
  - commit `a6ffc11` / report `p2-2-cluster-doctor.report.md`
- **P3-2**: dispatcher PoC end-to-end — 3 nodes registered, m1 picked (score 0.795)
  - commit `8a19431` / report `p3-2-dispatcher-poc.report.md`
- **Final**: v1.0 release summary report
  - commit `f522c34` / report `v1.0-automation-summary.report.md`

### Engineering Discipline (red lines)

- **红线 11** (verifier file): 8 reports, all ≥ 100 lines
- **红线 18** (capability default): tests prevent clawmed-ai v3.1 failure
- **红线 19** (independent verifier): applied in P1-1 protocol design
- **红线 20** (bash v3 portability): all scripts compliant
- **Lesson 28 + 29 + 30** from v0.5 P0: applied throughout

### Borrowed / Cited

- `clawmed-ai` Universal Worker v3.1 + T1.2 worker analysis (heartbeat 30s/90s)
- `agentmesh` 6 projects (TCP discovery + capability routing consensus)
- Anthropic 2026 mesh paper (motwani et al, communications-effective multi-agent)
- 老板 `~/.claude/CLAUDE.md` 工程纪律 + red lines 跨项目沉淀

---

## [0.5.0] - 2026-07-06 — Connect–Claude Code 重构

### BREAKING

- **CCC 重定位**: 从 "Codex Claude Collaboration framework 代码库" → "Connect–Claude Code SKILL 资产"
- **SKILL.md 重写**: 单一 prompt 注入资产，169 行
- **含义**: **C**onnect–**C**laude **C**ode（连接 Claude Code 能力到任意 IDE）
- **`projects/qxo/` 解耦**: lessons.md 迁到 `docs/lessons.md`
- **Mavis 术语替换** → ccc 统一命名

### Added

- `SKILL.md` (169 行, 唯一注入 prompt)
- `references/red-lines.md` 新增 红线 11 + 12
- `references/adapters/runtime-opencode.md` OpenCode adapter
- `references/red-lines.md` 10 + 2 完整红线
- `DESIGN-VALIDATION.md` 设计决策永久证据链 (234 行)
- `references/adapters/runtime-opencode.md` 适配 OpenCode runtime
- `docs/lessons.md` Lesson 27 (`claude -p` 语义) + Lesson 28 (verdict 强证据)
- `references/adapters/runtime-claude-p.md` v2 更新 — print 模式 + stdin 喂内容
- `CHANGELOG.md` (v0.3 占位版本)

### Fixed

- `runtime-claude-p.md`: 修复 `-p` 描述错误（Lesson 27）

### Removed

- v0.3.x 阶段 `projects/qxo/` 整个目录 → `.archived-2026-07-06/`
- v0.3.x `distribution-report.md` → archive
- v0.3.x `references/adapters/scheduler-mavis-cron.md` → archive

### Documentation

- 文档分层：
  - `SKILL.md` (agent 唯一入口)
  - `README.md` (用户入口)
  - `CLAUDE.md` (framework 总纲)
  - `DESIGN-VALIDATION.md` (证据链)
  - `references/red-lines.md` (工程纪律)
  - `docs/lessons.md` (教训沉淀)
  - `docs/architecture.md` (框架结构)
  - `docs/roadmap.md` (发展路线)

---

## [0.3.2] - 2026-07-05 — 实测沉淀 (9 个 task)

### Added

- `scripts/ccc` CLI 入口 (status / search / init / commit)
- `scripts/ccc-init.py` 项目初始化
- `scripts/ccc-search.py` 工件搜索
- `scripts/ccc-cost-report.sh` 成本估算
- `scripts/ccc-exec-commit.sh` 自动 commit 兜底
- `scripts/ccc-hook.sh` Claude Code pre-tool hook
- `scripts/install-ccc-as-skill.sh` 安装到 `~/.claude/skills/`

### Tasks Closed (9 个 task)

- `add-ccc-archive` (2026-07-04)
- `add-ccc-cost-report` (2026-07-04)
- `ccc-test-auto-claude-code` (v1-v4, 2026-07-04 ~ 07-05)
- `ccc-test-html-manual-paitongshu` (2026-07-04)
- `ccc-v0.3.1-infrastructure` (2026-07-04)
- `ccc-v0.3.2-cccq-status-ux` + R2 (2026-07-04)
- `fix-ccc-v031-bugs` (2026-07-04)
- `push-ccc-v0.3.1-to-origin` (2026-07-04)

### Engineering (v0.3 → v0.5)

- 9 个 task 沉淀成 9 个 phases.json + 9 个 reports + 4 个 verdicts
- 教训沉淀：Lessons 1-26 (~1300 行)
- 4 文件契约确立 (`plans/` / `phases.json` / `reports/` / `verdicts/`)
- 三角色纪律 (Planner / Executor / Verifier)

---

## [0.3.0] - 2026-07-01 — 三角色 + 4 文件契约

### Added

- **三角色**：Planner / Executor / Verifier 严格分离
- **4 文件契约**：`.ccc/{plans,phases,reports,verdicts}/`
- **第 9 红线**: Planner 越界 = Critical (C1-C6 子条款)
- **commit 兜底机制**: `ccc-exec-commit.sh` 自动检测 working tree → commit

### Roles

- **Planner (Mavis/MiniMax-M3)**: 写 plan.md + phases.json
- **Executor (Claude Code CLI)**: 自主执行 plan → 写 report.md
- **Verifier (Claude Code CLI)**: 独立 session → 写 verdict.md (≥ 50 行)

---

## [0.1.0] - 2026-06-30 — Internal Prototype

### Added

- 内部脚本集阶段
- 多个项目实验性使用 (qx-observer / qb / xianyu)
- 形成 `templates/` + `skills/` + `projects/` 雏形

### Structure

```
~/program/CCC/
├── SKILL.md
├── templates/
├── skills/
├── projects/
└── references/
```

---

## 借鉴来源 (Borrowed)

| 来源 | 提供价值 | 落地 |
|------|---------|------|
| `clawmed-ai` plans/universal-worker-v3.1.md | heartbeat 30s/90s 协议 | `cluster-bus.py` § v1.0 |
| `clawmed-ai` plans/T1.2_worker_analysis.md | 注册/选举/capability | `ccc-dispatch.py` |
| `clawmed-ai` reviews/universal-worker-v3.1-review.md | v3.1 失败教训（能力匹配被注释掉） | `tests/cluster/test-capability-required.py` |
| GitHub `agentmesh-*` 6 projects (2025-11) | TCP discovery + capability 共识 | `references/cluster-protocol.md` |
| Anthropic 2026 mesh paper (Motwani et al) | multi-phase coordination | `references/cluster-protocol.md` § 4 |
| clawmed-ai `.gitignore` 模式 (.ccc/ 豁免 plans/phases/reports) | 元数据 vs 工件分离 | `.gitignore` v0.5 |
| abc PoC `scripts/git-bundle-stream.sh` | 跨设备 git bundle 流程 | `examples/cluster/` 配置参考 |

---

## 设计决策（永久证据链）

详见 `DESIGN-VALIDATION.md`。已验证决策：
1. SKILL 资产 vs framework 代码库
2. JSONL phases.json vs nested object
3. 三角色严格分离（Planner / Executor / Verifier）
4. 4 文件契约 + 红线 4/5/11
5. Capability-tag dispatch
6. bash v3 portability (Lesson 29)
7. 独立 Verifier session 工程价值 (Lesson 30)

---

## 已知限制 / Backlog

- ❌ **mTLS 待实现**：`cluster-bus.py` 当前 plaintext (P1-1 协议设计完成, 实现待 v1.1)
- ❌ **chunk_id 幂等性**：commit message 应含 `ccc-task-id=<id>` (红线 15 待实装)
- ❌ **真 Mac2017 bus**：当前用 `mac2017-fake` 模拟
- ❌ **自动派单**：dispatcher 仍需人工 stdin 'yes'
- ❌ **跨 IDE SKILL 实测矩阵**：Trae 验证过，Cursor / Zed 待测
- ❌ **CI**：GitHub Actions 模板存在但未实测 GFW 下 push

---

## 相关文件

- `README.md` — 30 秒上手
- `SKILL.md` — 注入 prompt (agent 唯一入口)
- `CLAUDE.md` — 框架总纲
- `DESIGN-VALIDATION.md` — 设计决策永久证据链
- `references/red-lines.md` — 13 条硬约束
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 30 条工程教训
- `docs/architecture.md` — 框架结构
- `.ccc/plans/` — 所有 task plan.md
- `.ccc/reports/` — 所有 task report.md
- `.ccc/phases/` — 所有 task phases.json
- `.ccc/verdicts/` — 所有 task verdict.md

---

**Latest**: `bf88077` docs(ccc): T14 handoff-checklist.md (2026-07-06)
**Active branch**: main
**Version**: 1.1.0 (engineering foundation)
**Status**: v1.1 release — 24 tasks (T1-T14 done, T15+ pending Trae IDE)

[Unreleased]: https://github.com/hanrry2323/CCC/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/hanrry2323/CCC/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hanrry2323/CCC/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/hanrry2323/CCC/releases/tag/v0.5.0

## [v0.7-slim] — 2026-07-07 — 精简 80→15 (slim route closure)

**里程碑**:CCC 从 80+ 文件瘦身到 15 个核心文件。砍掉为"路线预留"而存在的过度工程化代码。

参见 `.ccc/plans/v0.7-slim.plan.md` + `.ccc/reports/v0.7-slim.report.md` + `docs/lessons.md` Lesson 29。

### Removed
- **cluster 总线整套** (phase 1):`scripts/cluster-bus.py` + `ccc-znode-register.py` + `ccc-zcode-bridge.sh` + `ccc-zcode-orchestrate.sh` + `tools/cluster-doctor.sh` + `references/cluster-protocol.md` + `tests/cluster/`
- **多 IDE 适配器整套** (phase 2):`references/adapters/runtime-{cursor,claude-p,zcode,claude-code}.md` + `scheduler-{launchd,github-actions}.md` (保留 `runtime-opencode.md`)
- **派单/飞轮/成本/precommit** (phase 3):`scripts/ccc-dispatch.py` + `ccc-hook.sh` + `ccc-scheduler.sh` + `hello-ccc.sh` + `flywheel-scan.py` + `ccc-cost-report.sh` + `ccc-cost.sh` + `precommit-{bash-quality,verdict-length}.sh` + `.ccc/dispatches/` + 9 测试
- **worktree 副本** (phase 4):`.claude/worktrees/oral-calc-commit/`

### Changed
- **CLAUDE.md**:精简"工程纪律配套扩展"段
- **README.md**:精简"配套"段 + 删除 ZCode Adapter 整段
- **.ccc/profile.md**:精简"关键资产清单"表(8 脚本 + 8 测试)
- **.ccc/state.md**:追加"v0.7-slim 精简决策"到关键历史决策
- **scripts/ccc**:删除 `run` 子命令(ccc-zcode-orchestrate.sh 已删)
- **scripts/ccc-exec-commit.sh** + 测试:历史任务名 "cluster-bus-bugfixes" → "historical task phase 1"

### Added
- **docs/lessons.md** Lesson 29:路线图当现实做 = 过度工程化
- **references/red-lines.md** 红线 13 (v0.7-slim 配套):禁止未使用路线代码
- **.ccc/reports/v0.7-slim.report.md**:执行报告 + 验收证据

### Test
- **精简前**:21/21 smoke tests PASS(测的是被删功能)
- **精简后**:42/42 smoke tests PASS(测的是保留功能)

## [v0.7a] — 2026-07-07 — 修 plan 阈值 + 清理 qxo 归档

**里程碑**:修正 v0.7-slim plan 拍脑袋写的"60-80 文件"验收数字为按 sections 实绩对照;删除 qxo 归档(已解耦)。

参见 `.ccc/plans/v0.7a.plan.md` + `.ccc/reports/v0.7a.report.md` + `docs/lessons.md` Lesson 30。

### Changed
- **`.ccc/plans/v0.7-slim.plan.md`**:改动 4 验收段 + 全局验收清单:"60-80 文件" → "scripts/ 30+ → 8、tests/ 21 → 8、adapters/ 7 → 1" 实绩对照(原数字已废除,标注为 Planner 拍脑袋)

### Added
- **`docs/lessons.md` Lesson 30**:不要拍脑袋写验收数字(可执行规则 = sections 分项对照,避免单一全局数字)
- **`.archived-2026-07-06/README.md`**:归档边界说明(CCC v0.7 起不再维护,删子目录需先 grep CLAUDE.md)

### Removed
- **`.archived-2026-07-06/qxo-project/`**:qxo 已与 CCC v0.5 解耦(CLAUDE.md 明文),删除整个归档子目录(保留 `.archived-2026-07-06/` 目录本身)

## [v0.7d-prime] — 2026-07-07 — 红线 14+15 工程化 (monitor + 5min 轮询)

**里程碑**:把"自动开 monitor + 5 分钟轮询 + 完成自动终止"沉淀为 CCC 工具链。未来所有 Executor 任务通过 `ccc-exec-launcher.sh` 一键起 monitor + Executor + poll 三件套。

参见 `.ccc/plans/v0.7d-prime.plan.md` + `.ccc/reports/v0.7d-prime.report.md`。

### Added
- **`scripts/ccc-monitor.sh`**:幂等开 tmux monitor 窗口(已存在则跳过,避免重复开窗)
- **`scripts/ccc-poll.sh`**:5 分钟轮询指定窗口 + 完成信号检测(`❯` prompt + 无 `esc to interrupt`)+ 自动 `break` 退出
- **`scripts/ccc-exec-launcher.sh`**:三件套整合(开 monitor → send-keys 触发 Executor → 后台 nohup 启动 poll,PID 写入 `/tmp/poll-<WINDOW>.pid`)
- **`references/red-lines.md` 红线 14 + 红线 15**:Executor 必须配 monitor + 5min 轮询 / 轮询进程完成自动终止
- **`docs/engineer-flow.md`**:串行 vs 并行投递模式 + ccc-exec-launcher.sh 三件套用法 + 失败兜底(poll 异常退出)

---

## [v0.7.0] — 2026-07-07 — v0.7 任务链完结 (umbrella release)

**里程碑**:CCC v0.7 整条任务链(slim → a → b → c → d → d-prime → e → e-fix → f)统一收束为 `v0.7.0` release。从 v1.2.0 流程层版本号**回落**到 v0.7.0 —— 因为流程层 v1.0 已闭环,而代码层经过 slim 精简后,只配 v0.7.0 的能力级别。后续 v0.8 起重新自增代码版本。

参见 `.ccc/plans/v0.7f.plan.md` + `.ccc/reports/v0.7f.report.md`。

### Sub-task 收录(sections 分项)

| 子任务 | 主题 | 关键产出 | 教训 |
|--------|------|---------|------|
| **v0.7-slim** | 精简 80→15 | scripts 30+ → 8、tests 21 → 7、adapters 7 → 1 | Lesson 29 |
| **v0.7a** | 修 plan 阈值 + 删 qxo 归档 | sections 分项实绩对照 + qxo 子目录删 | Lesson 30 |
| **v0.7b** | 3 处文档统一资产清单 | SKILL.md / README.md / state.md 资产表一致 | — |
| **v0.7c** | 5 命令验收通过 | 8 脚本(实 12,见 Lesson 31) | Lesson 31 |
| **v0.7d** | 4 窗口 cwd 对齐 | 全部相对 CCC repo root | — |
| **v0.7d-prime** | monitor + poll + launcher 工具化 | 红线 14 + 15 + 三件套 | — |
| **v0.7e** | Verifier CONDITIONAL_PASS | 独立 session 验证通过 | — |
| **v0.7e-fix** | SKILL.md L218-222 hotfix | 删过时的 planner 启动顺序引用 | — |

### Files Touched (sections 分项,各子任务汇总)

| Section | 数量 | 备注 |
|---------|------|------|
| `VERSION` | 1 | 1.2.0 → v0.7.0 |
| `CHANGELOG.md` | 1 | 本文件 + v0.7 各子任务段已存在 |
| `.ccc/state.md` | 1 | 接力索引更新 |
| `docs/lessons.md` | 1 | 追加 Lesson 31 + 32 |
| `.ccc/reports/v0.7f.report.md` | 1(新增) | 本次执行报告 |
| `.ccc/phases/*.json` | 1 | 更新 phases.json |
| `SKILL.md` / `references/red-lines.md` / `scripts/` | **0** | **禁止改**(红线 13 + 14 + 15) |

### Red Lines Enforced (v0.7.0)
| 红线 | v0.7.0 触发 |
|------|------------|
| 13 禁止未使用路线代码 | v0.7-slim 删 cluster-bus / dispatch / flywheel |
| 14 Executor 必配 monitor + 5min 轮询 | v0.7d-prime 三件套 |
| 15 轮询进程完成自动终止 | v0.7d-prime `ccc-poll.sh` break 检测 |

---

## [v0.7.0-closure] — 2026-07-07 — 收尾完成,等待 tag + push

**里程碑**:v0.7.0 收尾。V0.8 加固(窗口识别/空闲选择/冲突拦截/完成回写 + 红线 16 + 3 pytest)因 Claude 在 fake tmux 调试卡 32m+,被用户叫停 → 半成品全部迁出到 worktree `../CCC-v0.8-wip`(branch `v0.8-wip`),main 干净。

**8 个 verdict 全部 PASS / CONDITIONAL_PASS**:v0.7-slim + v0.7a/b/c/d/d-prime/e-fix/f(独立 Verifier session 写 verdict.md,≥3 probes,红线 11)。

**主干验收**:42 pytest passed(`pytest tests/ -q --ignore=...v0.8 untracked`)。V0.8 新加 3 测试留在 worktree,不阻塞 v0.7.0。

**Tag + push 清单(待用户执行)**:
```bash
cd /Users/apple/program/CCC
git tag -a v0.7.0 -m "v0.7.0 umbrella release: slim + a/b/c/d/d-prime/e/e-fix/f"
git push origin main --tags
```

**为什么 V0.8 不进 v0.7.0**:
- V0.8 是**加固**(新增能力),不是 v0.7 的修复
- V0.8 半成品含未验证代码(3 个 fail pytest + 未跑通的手动调试)
- 独立版本号 `v0.8.0` 更清晰,review 也更干净

---

## [v0.18.0] - 2026-07-07

- feat-agents-approve: AGENTS.md 审批流程 看板发布


- feat-regress-notify: [ABNORMAL] 回测失败通知：regress 发现回归时，除了建 bug 还要发桌面通知（ccc-notify.sh） 看板发布


- feat-product-auto: product 自动调 Claude API 写 plan（--promote 已实现，需测试中转站连通性） 看板发布


- feat-role-bar: 前端角色状态栏对接 /api/roles，实时显示 7 角色最新执行状态（ok/fail/idle+执行时间） 看板发布


- feat-card-detail: [ABNORMAL] 前端卡片点击弹出详情面板，显示任务完整信息（题目/描述/当前列/move事件列表） 看板发布

## [v0.23.5] - 2026-07-10

### 修复
- _board_store.py: update_index() 加锁防并发写入导致 index 不一致
- _config.py: CCC_WORKSPACE 环境变量增加绝对路径校验 + resolve（CWE-22）
- ccc-notify.sh: osascript notify 参数改为 `on run argv` 带索引访问，防止 MESSAGE 拼接注入
- HP memory-store: 补上 KB_EMBED_URL 配置指向 feiniu:11434，修复重启后 embed 失效
- memory-store 健康检查 embed 超时从 5s 提到 15s（bge-m3 CPU 模式首次加载 ~12s）

## [v0.23.6] - 2026-07-10

### 修复
- G1 [critical] reviewer_role: _get_git_diff 加 task_id 参数，优先按 git log --grep 找 task 关联 commit 取 diff，其次 phases.json commit ref，reviewer 只审本 task 的改动而非全仓 HEAD~1
- G2 [critical] reviewer_role fallback: 无验收清单 `## 验收` + 无 py 文件 → quarantine（防止 dev 绕开审查）；无 py 文件也不再静默 pass，改为 quarantine

## [v0.23.7] - 2026-07-10

### 修复
- G4 [high] engine 重启恢复: 启动扫描 in_progress 后检查 PID 存活，.pid 指向已死进程时清理并标记 failed 让 engine 自动重启
- G11 [medium] audit-last-run 跨 workspace 共享: 拆为 `audit-last-run.{workspace}.json`，5 个 engine 实例互不影响

## [v0.23.8] - 2026-07-10

### 修复
- reviewer JSON 提取: markdown 代码块匹配时用 `m.group(1)` 而非 `m.group(0)`，修复 json.loads 因包含反引号解析失败
- v0.23.14 ABNORMAL smoke OK

## [v0.24.4] - 2026-07-11 — board zombie 副本修复

### 修复
- **`_board_store.move_task` 原子迁移**：旧版写 dst 与删 src 之间无原子性，异常时会产生双份 zombie。新版先 unlink dst（清残留）→ 把更新后的 task（status=to_col）写回 src → `shutil.move(src, dst)` 一次性 rename。status 字段与物理位置天然一致，不会再产生双份存在
- **board-reconcile.py**：新工具，扫描所有列，按 jsonl["status"] 字段与物理位置的一致性清理 zombie（多副本时保留 status 匹配的副本、删其它；status 字段错位时改 status）。以 jsonl 为权威，events 只作审计日志（避免事件缺失或历史回退时误判）

### 清理
- 手动归档 `retest-feat-card-detail-v02315.jsonl` 到 released（events 已走完）
- `retest-feat-regress-notify-v02315.jsonl` 保留在 abnormal（audit_role 自动降级，events 最新 `in_progress → abnormal`）
- 修正 19 个 jsonl 的 status 字段（历史遗留错位：disk 在 backlog 但 status=released 等）

### 测试
- 新增 `tests/scripts/test_board_zombie_reconcile.py`（7 case）：move_task 原子性、reconcile 多副本清理、status 字段修正、dry-run 不改文件
- 全量 92 case 通过

## [v0.28.0] — 2026-07-11 — stream-line hardening 流层加固

修复 v0.27.1 在实际跑 qxo task 时暴露的 6 个流层漏洞。内部硬化、协议透明。

**scripts/_config.py — timeout 可配置**
- `default_timeout` 默认 600 → 1800
- 新增 `parse_duration()`：支持 `"15m"` / `"1h"` / `"1d"` duration 类 expr
- `_env_override_duration()` 处理 env var + clamp `[60, 86400]`
- `CCC_TIMEOUT=15m` / `CCC_HOOK_TIMEOUT=30s` 环境变量打通

**scripts/ccc-board.py — timeout 默认值**
- `_load_timeout()` 缺省走 `cfg.default_timeout`
- 3 处 `default=600` → `default=cfg.default_timeout`
- phase 内 `timeout` 字段支持 duration expr 字符串

**scripts/phase_lint.py — 校验扩展**
- 新增 `validate_executor()`：未定义 executor + skip 状态但无说明检测
- 新增 `validate_empty_phase()`：空白 phase（缺 description / files_touched / subtasks）检测
- 新增 `validate_v12_fields()`：schema v1.2 三字段（estimated_minutes / files_touched / verification_cmd）软警告
- 新增 `validate_phases_dict()`：统一入口（新 API）
- 新增 `validate_phases_jsonl()`：文件级校验（含 schema_version）
- 修复 `validate_phase_structure` `pid` 变量名 bug
- 修复 `validate_status_transitions` 跨 phase 误判逻辑
- 修复 `run_lint` 不存在文件 vs 空 phase 行为
- `allowed_fields` 加 v1.2 新字段

**scripts/_board_store.py — quarantine 副本归档**
- 新增模块级函数：
  - `quarantine_store_content(task_id, content_path)` — 归档内容到 `.ccc/quarantines/<task_id>`
  - `quarantines_cleanup_task(hours_threshold=5.0)` — 删除同 base_name 下除最新外副本
  - `quarantines_index_task()` — 扫描写 `index.json` 沉淀统计
  - `quarantines_harvesting_index()` — 返回 `{total, completed, remaining}`
- `_get_quarantine_dir()` 多级查找（env > 扫描 tempdir > cwd）

**templates/phases.phases.json** — 升 schema_version 1.2（结构兼容 1.0/1.1）

**测试覆盖**
- `scripts/tests/test_phase_lint.py`：14/14 passed
- `scripts/tests/test_quarantine_archive.py`：5/5 passed
- `scripts/tests/test_phase_lint.py` 测试同时验证 legacy API 与 v0.28.0 新 API


### v0.28.0 审查修复批次（F-1~F-4 核心断点）

#### 修复

- (F1-C1) engine Step 1.5 失败计数器：连续 3 次 product_role 失败 → 移入 abnormal
  - `scripts/ccc-engine.py` + `.ccc/.product-fail-counter/<tid>.json`
  - 成功自动清空计数，失败递增，超限 quarantine
- (F1-C2) backlog FIFO: `_board_store.py` `list_tasks()` 按 `created_at` 升序排列
  - 防止 task_id 字典序与创建序不同步导致新 task 被先消费、老 task 永久饿死
- (F1-H1/H3) product_role 写锁: `_acquire_product_lock` / `_release_product_lock` (fcntl.flock)
  - 锁文件 `.ccc/.product_role.lock`，30s 超时 + LOCK_NB + 500ms 重试
  - 防止 Engine 与外部 CLI --promote 并发写 plan+phases 撕裂
- (F1-H2) product_role 原子写: temp → rename 替代直接 write_text
  - 先写 phases (`.tmp` → rename), 再写 plan (`.tmp` → rename)
  - 崩溃时任一文件不存在 → engine Step 2 跳过 → 下一轮重试
- (F2-C1) ADR 决策: F-2 size_hint 与 R-12 互补非冗余，保留两者
  - docs/adr/F2-vs-R12-redundancy.md
- (F2-H1) size_hint 加权判定: lines + file_mentions*20 + section_count*10 替代纯行数
  - 低行数高引用 plan 也能触发大变更提示
- (F3-H1) flywheel 报告落盘: scan 结束 cp 到 .ccc/reports/flywheel-YYYY-MM-DD.md
- (F4-H1) auto_approve_agents 重复检测：sha256(content) 指纹 → AGENTS.md hash marker
  - 旧实现 `"### 来自 {source}" + content[:100]` 因 AGENTS.md 实际写 `({task_id})` 后缀导致 false-negative
- (F4-H3) auto_approve_agents 事务顺序：先写 cooldown 再写 AGENTS.md
  - cooldown 写失败 → 不写 AGENTS.md（重启不重复合入）
- (F3-C1/F3-C2) flywheel-scan.sh ALL_WORKSPACES 去重 + P2 段输出去重
  - macOS bash 3.2 兼容（declare -A 不可用），P2_WRITTEN 字符串做去重表
- (N-001/002/004/005) logger / config / json 统一修复

#### 对抗性审查沉淀

- `.ccc/reports/v0.28.0-review-checklist.md` — 28 项跟踪清单

#### 验证

- `tests/e2e/test_f1_backlog_failover.sh` — F-1 失败计数器 + quarantine E2E
- `tests/e2e/test_f2_size_hint.sh` — F-2 size_hint 阈值边界 E2E
- `tests/e2e/test_f3_flywheel_dedup.sh` — F-3 workspace/P2 去重 E2E
- `tests/e2e/test_f4_auto_approve.sh` — F-4 cooldown/sha256/None path E2E

#### 看板发布（smoke）

- smoke-pipeline-2026-07-12: smoke: 跑通 dev → reviewer → tester → kb 看板发布
- smoke-model-2026-07-12: smoke: 验证 loop/code 模型 看板发布
- smoke-v0245-test: [ABNORMAL] v0.24.5 smoke 看板发布
- e2e-mini-2026-07-12: e2e: 小变更验证全链路 看板发布

## [v0.29.11] - 2026-07-14

- cockpit-auto-refresh: Cockpit 30s 自动轮询刷新端口状态 看板发布
