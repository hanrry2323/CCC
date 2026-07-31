# 阶段 4：组件盘点表

> 扫描范围：`scripts/` 下所有 `.py` 和 `.sh` 文件（按功能分组）
> 基准：`docs/product/ccc-new-architecture-overview.md`（新架构四层分工）
> 扫描日期：2026-07-31
> 目的：识别 改造 / 新增 / 冗余 / 标史 / 保留 五类组件，为阶段 5 落地 plan 提供依据

---

## 新架构对齐速查

| 层 | 承担者 | 硬边界 |
|----|--------|--------|
| ① 谈方案 | 人 + IDE | 不拆卡，只写方案文件 |
| ② 拆意图链 | **Claude 后台程序**（2017·无记忆） | 从 Skill/Prompt 库组装软链接；不创造新 Skill |
| ③ 标准化 | Engine（NG） | `transfer_gate` 校验 + 入 backlog + wake；**不解析 Skill 内容** |
| ④ 闭环驱动 | Engine 流水线 | fanout → OpenCode → 验收 → released |

**新增字段**：`skill_ref` / `prompt_ref` / `prompt_inline`
**删除字段**：`executor_intent` 校验逻辑（枚举式职能锁定退役）

---

## 组件清单

### 1. Engine 核心

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| ccc-engine.py | scripts/ccc-engine.py | 多 workspace 并行执行引擎主循环；调度 product/dev/reviewer/tester | ③ 标准化 + ④ 闭环驱动 | 改造 | 强化"不解析 Skill 内容"边界；透传 `skill_ref`/`prompt_ref` 到执行器；删除内部对 `executor_intent` 的二次判断 |
| ccc-engine.sh | scripts/ccc-engine.sh | launchd 常驻入口；control.json 门禁 + relay env | ③ 入口 | 保留 | 无需改动 |
| engine/loop.py | scripts/engine/loop.py | engine poll 主循环（attach 到 ccc_engine） | ④ 驱动 | 保留 | 实现在 `_loop_impl.py` |
| engine/gates.py | scripts/engine/gates.py | testing/verified 列门禁；verify 单入口 | ④ 验收门禁 | 保留 | 不解析 Skill；门禁逻辑不变 |
| engine/dispatch.py | scripts/engine/dispatch.py | 角色调度；phase marker；try_launch_planned | ④ 调度 | 保留 | dev 角色启动逻辑不变 |
| engine/backlog.py | scripts/engine/backlog.py | epic refresh + process_backlog | ③ 入队 | 保留 | 实现在 `_backlog_impl.py` |
| engine/launch.py | scripts/engine/launch.py | dev/reviewer/tester 异步启动 | ④ 启动 | 保留 | — |
| engine/recover.py | scripts/engine/recover.py | 异常恢复 / relaunch | ④ 恢复 | 保留 | — |
| engine/results.py | scripts/engine/results.py | phase 结果落盘 + 闭环推进 | ④ 闭环 | 保留 | — |
| engine/health.py | scripts/engine/health.py | engine 健康探活 | ④ 观测 | 保留 | — |
| engine/heartbeat.py | scripts/engine/heartbeat.py | engine 心跳 | ④ 观测 | 保留 | — |
| engine/observability.py | scripts/engine/observability.py | 观测指标 | ④ 观测 | 保留 | — |
| engine/workspace.py | scripts/engine/workspace.py | workspace scope / store 取数 | ③/④ 共用 | 保留 | — |
| engine/slots.py | scripts/engine/slots.py | OpenCode 全局并发槽 | ④ 并发控制 | 保留 | — |
| engine/verify_gate.py | scripts/engine/verify_gate.py | verify 门禁入口 | ④ 验收 | 保留 | — |
| engine/compat_board.py | scripts/engine/compat_board.py | board 兼容层 | ③ board 适配 | 保留 | — |
| engine/min_pipeline.py | scripts/engine/min_pipeline.py | 最小流水线开关 | ④ 流水线 | 保留 | — |
| engine/tick.py | scripts/engine/tick.py | tick 调度 | ④ 调度 | 保留 | — |
| engine/upstream.py | scripts/engine/upstream.py | 上游信号 | ④ 观测 | 保留 | — |
| engine/failure_router.py | scripts/engine/failure_router.py | 失败路由 | ④ 恢复 | 保留 | — |
| engine/hang.py / hang_support.py | scripts/engine/hang*.py | 卡死检测 | ④ 恢复 | 保留 | — |
| engine/restart_log.py | scripts/engine/restart_log.py | 重启日志 | ④ 观测 | 保留 | — |
| engine/task_registry.py | scripts/engine/task_registry.py | 任务登记 | ④ 登记 | 保留 | — |
| engine/stats_server.py | scripts/engine/stats_server.py | stats HTTP :7776 | ④ 观测 | 保留 | — |
| engine/discover.py | scripts/engine/discover.py | workspace 发现 | ③ 发现 | 保留 | — |
| engine/notify.py | scripts/engine/notify.py | 通知 | ④ 通知 | 保留 | — |
| engine/process.py | scripts/engine/process.py | 进程工具 | ④ 工具 | 保留 | — |
| engine/active_tasks.py | scripts/engine/active_tasks.py | 活跃任务表 | ④ 跟踪 | 保留 | — |
| engine/cli.py | scripts/engine/cli.py | engine CLI 子命令 | ④ 工具 | 保留 | — |
| board/roles/__init__.py | scripts/board/roles/__init__.py | 角色入口聚合 | ④ 角色入口 | 保留 | — |
| board/roles/dev.py | scripts/board/roles/dev.py | dev 角色（OpenCode 写码） | ④ 写码执行 | 保留 | 角色锁 opencode；不改 |
| board/roles/reviewer.py | scripts/board/roles/reviewer.py | reviewer 角色（Claude 语义审查） | ④ 副闸 | 保留 | — |
| board/roles/tester.py | scripts/board/roles/tester.py | tester 角色（pytest） | ④ 验收 | 保留 | — |
| board/roles/verify.py | scripts/board/roles/verify.py | verify 统一入口 | ④ 验收 | 保留 | — |
| board/roles/ops.py | scripts/board/roles/ops.py | ops 角色 | ④ 运维 | 保留 | — |
| board/roles/kb.py | scripts/board/roles/kb.py | kb 角色（git tag） | ④ 归档 | 保留 | — |
| board/roles/audit.py | scripts/board/roles/audit.py | audit 角色 | ④ 审计 | 保留 | — |
| board/roles/regress.py | scripts/board/roles/regress.py | regress 角色（回测） | ④ 回测 | 保留 | — |
| board/roles/product.py | scripts/board/roles/product.py | product 角色：扫 backlog → Claude 拆 epic 为 work 子卡 | ② 拆卡（旧实现） | **标史** | 新架构下"扫 backlog 自动拆卡"由 `ccc-intent-splitter.py`（消费方案文件）取代；本文件保留为史径，主路径切走；`_product_fanout` 拆卡函数可被新 splitter 复用 |
| board/roles/dev_salvage.py | scripts/board/roles/dev_salvage.py | dev 抢救 | ④ 恢复 | 保留 | — |
| board/roles/repair.py | scripts/board/roles/repair.py | 修复 | ④ 恢复 | 保留 | — |
| board/roles/script_seed.py | scripts/board/roles/script_seed.py | 脚本种子 | ④ 工具 | 保留 | — |
| board/roles/common.py | scripts/board/roles/common.py | 角色公共工具 | ④ 工具 | 保留 | — |

### 2. Hub/Board 服务

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| ccc-chat-server.py | scripts/ccc-chat-server.py | CCC Hub v2 入口（uvicorn） | ③ Hub 入口 | 保留 | 无需改动 |
| chat_server/app.py | scripts/chat_server/app.py | FastAPI app 装配；CORS / 静态 / lifespan | ③ Hub 装配 | 改造 | 注册新 router 端点（proposal）；其余不变 |
| chat_server/config.py | scripts/chat_server/config.py | Hub 配置 | ③ 配置 | 保留 | — |
| chat_server/auth.py | scripts/chat_server/auth.py | 鉴权 | ③ 鉴权 | 保留 | — |
| chat_server/models.py | scripts/chat_server/models.py | 数据模型 | ③ 模型 | 保留 | — |
| chat_server/hub_voice.py | scripts/chat_server/hub_voice.py | Hub 语音 prompt（含旧叙事载体） | ③ UX | **改造（P0）** | L171 模板 `"executor_intent": "opencode"` 删除/改新字段；L178 文案 `executor_intent: python` 删除；其他旧叙事 prompt 文案（自动投链等）留阶段 5 统一改 |
| chat_server/routers/desktop.py | scripts/chat_server/routers/desktop.py | Desktop API：threads / transfer / repair / proposals / flow | ③ 方案入口 + 转任务 | **改造（P0）** | 新增 `POST /api/desktop/proposal`（接收 M1 方案文件）+ `GET /api/desktop/proposal/<id>/result`（查拆卡结果）；现有 `/proposals` + `/proposals/{id}/adopt` 保留为 inbox 采纳路径；**清理 14 处 `executor_intent` 引用**（L638/712/720/742/751/758/824/848/944/947/957/969/1041/1073，含 `resolve_executor_intent` 调用与 `executor_intent=bug` 默认值，统一替换为 skill_ref/prompt_ref） |
| chat_server/routers/board.py | scripts/chat_server/routers/board.py | board 代理 | ③ board | 保留 | — |
| chat_server/routers/sessions.py | scripts/chat_server/routers/sessions.py | 会话路由 | ③ 会话 | 保留 | — |
| chat_server/routers/files.py | scripts/chat_server/routers/files.py | 文件路由 | ③ 文件 | 保留 | — |
| chat_server/routers/projects.py | scripts/chat_server/routers/projects.py | 项目路由 | ③ 项目 | 保留 | — |
| chat_server/routers/ops.py | scripts/chat_server/routers/ops.py | ops 路由 | ③ ops | 保留 | — |
| chat_server/routers/lens.py | scripts/chat_server/routers/lens.py | lens 路由 | ③ lens | 保留 | — |
| chat_server/routers/mind.py | scripts/chat_server/routers/mind.py | mind 路由 | ③ mind | 保留 | — |
| chat_server/routers/agent_proxy.py | scripts/chat_server/routers/agent_proxy.py | agent 代理 | ③ 代理 | 保留 | — |
| ccc-board-server.py | scripts/ccc-board-server.py | Board HTTP :7775（REST API + UI 重定向到 Hub） | ③ Board 服务 | 保留 | UI 已并入 Hub，本服务仅 REST |
| chat_server/services/board_client.py | scripts/chat_server/services/board_client.py | Hub → Board 代理客户端 | ③ 客户端 | 保留 | — |
| chat_server/services/flow_events.py | scripts/chat_server/services/flow_events.py | flow 事件 | ③ 事件 | **改造（P1）** | L551 含 `executor_intent` 字段读取，需替换为 skill_ref/prompt_ref |
| chat_server/services/session_store.py | scripts/chat_server/services/session_store.py | 会话存储 | ③ 存储 | 保留 | — |
| chat_server/services/board_repair.py | scripts/chat_server/services/board_repair.py | board 修复 | ③ 修复 | 保留 | — |
| chat_server/services/repair_queue.py | scripts/chat_server/services/repair_queue.py | 修复队列 | ③ 队列 | 保留 | — |
| chat_server/services/hub_lens.py | scripts/chat_server/services/hub_lens.py | hub lens | ③ lens | 保留 | — |
| chat_server/services/hub_agent_tools.py | scripts/chat_server/services/hub_agent_tools.py | hub agent 工具 | ③ 工具 | 保留 | — |

### 3. Claude 集成

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| _product_session.py | scripts/_product_session.py | Product Sessionful Contract Loop：Claude SDK 会话内 generate→lint→再生成；解析 ---PLAN---/---PHASES--- | ② 拆卡基础设施 | **改造** | 新架构 `ccc-intent-splitter.py` 复用本模块的 `run_contract_loop_sync` + `parse_work_artifacts`；改造为消费方案文件 → 输出意图卡链（带 `skill_ref`/`prompt_ref`） |
| ccc-product-session.py | scripts/ccc-product-session.py | product session 异步 runner（写 .product.out/.done 标记） | ② runner | **改造** | 适配为 `ccc-intent-splitter` 的执行入口；或保留为 product role 史径 runner，新 splitter 单独建 runner |
| _claude_cli.py | scripts/_claude_cli.py | 解析 Claude CLI 绝对路径；loop-code 私有配置家 | ② CLI 解析 | 保留 | 新 splitter 复用本模块解析 Claude CLI |
| ccc-agent-sidecar.py | scripts/ccc-agent-sidecar.py | Desktop 本机 sidecar：127.0.0.1:7788 → ClaudeSDKClient → relay | ① 对话面 | 保留 | M1 对话面，不在 2017 Engine 调度；新架构下 IDE 谈方案仍走此通道 |
| ccc-agent-sidecar.sh | scripts/ccc-agent-sidecar.sh | sidecar 启动脚本 | ① 启动 | 保留 | — |
| chat_server/services/claude_session.py | scripts/chat_server/services/claude_session.py | Hub ClaudeSDKClient 持续会话管理 | ① 对话面 | 保留 | — |
| chat_server/services/claude_client.py | scripts/chat_server/services/claude_client.py | Hub Claude helpers | ① 对话面 | 保留 | — |
| chat_server/services/claude_history.py | scripts/chat_server/services/claude_history.py | Claude 历史 | ① 对话面 | 保留 | — |
| chat_server/services/agent_mind.py | scripts/chat_server/services/agent_mind.py | L1 心智（observed + decided） | ① 心智 | 保留 | — |
| chat_server/services/project_brain.py | scripts/chat_server/services/project_brain.py | 项目脑包编译 | ① 脑包 | 保留 | — |
| _role_lock.py | scripts/_role_lock.py | 角色↔执行器硬锁（product→claude-code 等） | ④ 角色锁 | 改造 | 新增 `intent-splitter` 角色锁条目（→ claude-code）；现有 product 锁可保留为史径 |
| _role_tool.py | scripts/_role_tool.py | 角色工具 | ④ 工具 | 保留 | — |
| _product_fanout.py | scripts/_product_fanout.py | Epic → work 扇出：Claude 拆大卡为 N 张 work（含 `build_fanout_prompt` / `parse_fanout_output` / `apply_fanout`） | ② 拆卡核心 | **改造** | 拆卡 SOP 是新 `ccc-intent-splitter` 的可直接复用资产；改造点：删 `_epic_default_executor` / `executor_intent` 读取（541/548/550 行），子卡注入 `skill_ref`/`prompt_ref` |
| _product_fail_counter.py | scripts/_product_fail_counter.py | product 失败计数 | ② 失败计数 | 保留 | — |
| _evolve.py | scripts/_evolve.py | evolve（已禁用 invent） | — | 保留 | invent 永久禁用 |
| _capability_evolver.py | scripts/_capability_evolver.py | 失败模式记录 | ④ 学习 | 保留 | — |
| _failure_learning.py | scripts/_failure_learning.py | 失败学习 | ④ 学习 | 保留 | — |
| _failure_ledger.py | scripts/_failure_ledger.py | 失败台账 | ④ 台账 | 保留 | — |
| _failure_buckets.py | scripts/_failure_buckets.py | 失败分桶（含 `executor_intent` 文案） | ④ 分桶 | 改造 | 第 101 行文案删除 `executor_intent` 引用 |
| _lessons.py | scripts/_lessons.py | lessons | ④ 学习 | 保留 | — |

### 4. OpenCode 执行器

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| opencode-exec.py | scripts/opencode-exec.py | OpenCode CLI 单 phase 执行器 | ④ 写码执行 | 保留 | 不变；新架构 OpenCode 仍是写码执行器 |
| opencode-pool.py | scripts/opencode-pool.py | OpenCode 进程池（max 3 并发） | ④ 并发控制 | 保留 | — |
| opencode-watchdog.sh | scripts/opencode-watchdog.sh | OpenCode 残留进程扫描清理 | ④ 清理 | 保留 | — |
| ccc-exec-launcher.sh | scripts/ccc-exec-launcher.sh | 单 phase 启动入口（watchdog→钩子→opencode-exec） | ④ 启动 | 保留 | — |
| opencode-runner.sh | scripts/opencode-runner.sh | opencode runner | ④ 启动 | 保留 | — |
| _executor.py | scripts/_executor.py | Executor 抽象 + OpenCodeExecutor 实现 + resolve_opencode | ④ 执行器抽象 | 保留 | — |
| _opencode_quality_gate.py | scripts/_opencode_quality_gate.py | opencode 质量门 | ④ 质量门 | 保留 | — |
| _opencode_reap.py | scripts/_opencode_reap.py | opencode reap | ④ 清理 | 保留 | — |
| executors/registry.py | scripts/executors/registry.py | 执行器注册 | ④ 注册 | 保留 | — |
| _diff_check.py | scripts/_diff_check.py | diff 检查 | ④ 检查 | 保留 | — |
| _task_commit.py | scripts/_task_commit.py | 任务 commit | ④ commit | 保留 | — |
| _acceptance_gate.py | scripts/_acceptance_gate.py | 验收门 | ④ 验收 | 保留 | — |
| _acceptance_strength.py | scripts/_acceptance_strength.py | 验收强度 | ④ 验收 | 保留 | — |
| _review_validator.py | scripts/_review_validator.py | review 校验 | ④ 校验 | 保留 | — |

### 5. Transfer/Gate

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| chat_server/services/transfer_gate.py | scripts/chat_server/services/transfer_gate.py | 转任务门禁：校验 title/goal/acceptance/pipeline/feasibility/`executor_intent`/probe | ③ 标准化门禁 | **改造（核心）** | 删 `VALID_EXECUTOR_INTENTS` 枚举校验（13/119-126/320/758/891 行 `resolve_executor_intent`）；新增 `skill_ref`/`prompt_ref` 必填校验（缺失→`missing_skill_ref`/`missing_prompt_ref`）；`prompt_inline` 可选 |
| _intent_probe.py | scripts/_intent_probe.py | 意图探针解析（acceptance 命令 allowlist） | ③ 探针校验 | 保留 | 探针逻辑不变；skill_ref 不影响探针 |
| _board_garbage.py | scripts/_board_garbage.py | 垃圾戳记识别 | ③ 卫生 | 保留 | — |
| _plan_adopt.py | scripts/_plan_adopt.py | 收养已有 plan（避免白烧 product LLM） | ③ plan 适配 | 保留 | 新架构方案文件路径不同，但收养逻辑可复用 |
| chat_server/services/intent_promote.py | scripts/chat_server/services/intent_promote.py | L1 planned → gate → backlog epic + wake Engine | ③ 推进入队 | 改造 | 第 125 行 `"executor_intent": "opencode"` 默认值替换为 `skill_ref`/`prompt_ref` 默认值 |
| chat_server/services/transfer_outbox_flush.py | scripts/chat_server/services/transfer_outbox_flush.py | M1 transfer outbox 后台冲刷（sidecar 周期 POST Hub） | ①→③ 通道 | **改造（P1）** | L374 `"executor_intent": item.get("executor_intent") or "opencode"` 默认值替换为 skill_ref/prompt_ref；其余可复用为方案文件投递通道 |
| chat_server/services/proposals.py | scripts/chat_server/services/proposals.py | inbox 提案服务（`list_proposals`/`get_proposal`/`proposal_to_transfer_body`） | ③ 提案服务 | **改造** | 删 `executor_intent` 字段（77/105 行），加 `skill_ref`/`prompt_ref`/`prompt_inline` 字段透传；现有 inbox/adopted 机制可复用为方案文件存储 |
| _engine_wake.py | scripts/_engine_wake.py | 下任务 → 强制 enabled + 唤醒 Engine | ③ 唤醒 | 保留 | — |

### 6. Board 存储

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| _board_store.py | scripts/_board_store.py | BoardStore 抽象 + FileBoardStore 实现；列定义/原子写 | ③ 存储 | 保留 | 列结构不变 |
| board/store.py | scripts/board/store.py | store 对外别名 | ③ 存储 | 保留 | — |
| board/store_ops.py | scripts/board/store_ops.py | store 操作实现 | ③ 存储 | 保留 | — |
| board/context.py | scripts/board/context.py | workspace 上下文 | ③ 上下文 | 保留 | — |
| board/lock.py | scripts/board/lock.py | 命名锁 | ③ 锁 | 保留 | — |
| board/phase.py | scripts/board/phase.py | phase 加载/依赖/状态 | ③ phase | 保留 | — |
| board/slots.py | scripts/board/slots.py | board slots | ③ slots | 保留 | — |
| _workspace_registry.py | scripts/_workspace_registry.py | Engine 可消费 workspace 登记（~/.ccc/workspaces.json） | ③ 登记 | 保留 | orch 分离已落地 |
| _workspace_isolation.py | scripts/_workspace_isolation.py | 看板仓与 CCC 仓硬隔离；require_cwd | ③ 隔离 | 保留 | — |
| _board_visibility.py | scripts/_board_visibility.py | board 可见性 | ③ 可见性 | 保留 | — |
| _board_garbage.py | scripts/_board_garbage.py | 垃圾识别（同 5） | ③ 卫生 | 保留 | — |
| _project_baseline.py | scripts/_project_baseline.py | 项目基线 | ③ 基线 | 保留 | — |
| _git_trackable.py | scripts/_git_trackable.py | git 可追踪 | ③ git | 保留 | — |
| _jsonl_rotate.py | scripts/_jsonl_rotate.py | jsonl 轮转 | ③ 轮转 | 保留 | — |
| _task_reopen.py | scripts/_task_reopen.py | 任务重开 | ④ 重开 | 保留 | — |

### 7. 工具/配置

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| _config.py | scripts/_config.py | 集中配置（Config dataclass + parse_duration） | 全局配置 | 保留 | — |
| _logger.py | scripts/_logger.py | 统一 logger | 全局日志 | 保留 | — |
| _ccc_control.py | scripts/_ccc_control.py | 控制面（disabled/ui/enabled；invent 永久禁用） | 全局控制 | 保留 | — |
| _utils.py | scripts/_utils.py | 工具（now_iso / sanitize_id / relay 探活） | 全局工具 | 保留 | — |
| _exceptions.py | scripts/_exceptions.py | 异常定义 | 全局异常 | 保留 | — |
| _secret_redact.py | scripts/_secret_redact.py | 密钥脱敏 | 全局安全 | 保留 | — |
| _result_json.py | scripts/_result_json.py | 结果 JSON | 全局工具 | 保留 | — |
| _stats_aggregator.py | scripts/_stats_aggregator.py | stats 聚合 | ④ 观测 | 保留 | — |
| _cost_telemetry.py | scripts/_cost_telemetry.py | 成本遥测 | ④ 观测 | 保留 | — |
| _host_resources.py | scripts/_host_resources.py | 主机资源 | ④ 观测 | 保留 | — |
| _webhook.py | scripts/_webhook.py | webhook | ④ 通知 | 保留 | — |
| ccc-dual-host-check.sh | scripts/ccc-dual-host-check.sh | 双机检查 | 全局检查 | 保留 | — |
| ccc-sync-after-push.sh | scripts/ccc-sync-after-push.sh | push 后同步 | 全局同步 | 保留 | — |
| ccc-status.sh | scripts/ccc-status.sh | 状态 | 全局状态 | 保留 | — |
| ccc-self-check.sh | scripts/ccc-self-check.sh | 自检 | 全局自检 | 保留 | — |
| ccc-hook.sh | scripts/ccc-hook.sh | hook | 全局 hook | 保留 | — |
| ccc-notify.sh | scripts/ccc-notify.sh | 通知 | 全局通知 | 保留 | — |
| ccc-fleet.sh | scripts/ccc-fleet.sh | fleet | 全局 fleet | 保留 | — |
| ccc-log-rotate.sh | scripts/ccc-log-rotate.sh | 日志轮转 | 全局日志 | 保留 | — |
| ccc-loop-monitor.sh | scripts/ccc-loop-monitor.sh | loop 监控 | 全局监控 | 保留 | — |
| ccc-opencode-gc.sh | scripts/ccc-opencode-gc.sh | opencode GC | ④ GC | 保留 | — |
| ccc-autostart-guard.sh | scripts/ccc-autostart-guard.sh | 自启守卫 | 全局守卫 | 保留 | — |
| ccc-relay-flash-watchdog.sh | scripts/ccc-relay-flash-watchdog.sh | relay flash 看门狗 | 全局看门狗 | 保留 | — |
| ccc-hub-probe.sh | scripts/ccc-hub-probe.sh | hub 探活 | 全局探活 | 保留 | — |
| ccc-hub-dev.sh | scripts/ccc-hub-dev.sh | hub 开发脚本 | 全局开发 | 保留 | — |
| ccc-tauri-dev.sh | scripts/ccc-tauri-dev.sh | tauri 开发 | 全局开发 | 保留 | — |
| ccc-exec-commit.sh | scripts/ccc-exec-commit.sh | exec commit | ④ commit | 保留 | — |
| ccc-ingest-ci-failure.sh | scripts/ccc-ingest-ci-failure.sh | CI 失败摄入 | ④ 摄入 | 保留 | — |
| ccc-reviewer-bg.sh | scripts/ccc-reviewer-bg.sh | reviewer 后台 | ④ 后台 | 保留 | — |
| ccc-init.py | scripts/ccc-init.py | 初始化 | 全局初始化 | 保留 | — |
| ccc-board.py | scripts/ccc-board.py | board CLI | ③ CLI | 保留 | — |
| ccc-search.py | scripts/ccc-search.py | 搜索 | 全局搜索 | 保留 | — |
| ccc-mind-update.py | scripts/ccc-mind-update.py | mind 更新 | ① mind | 保留 | — |
| ccc-hub-agent-mcp.py | scripts/ccc-hub-agent-mcp.py | hub agent MCP | ③ MCP | 保留 | — |
| ccc-hub-lens.py | scripts/ccc-hub-lens.py | hub lens | ③ lens | 保留 | — |
| ccc-capacity-probe.py | scripts/ccc-capacity-probe.py | 容量探针 | ④ 观测 | 保留 | — |
| ccc-pipeline-status.py | scripts/ccc-pipeline-status.py | 流水线状态 | ④ 状态 | 保留 | — |
| ccc-patrol-v4.py | scripts/ccc-patrol-v4.py | patrol v4 | ④ patrol | 保留 | — |
| ccc-authority-patrol.py | scripts/ccc-authority-patrol.py | authority patrol | ④ patrol | 保留 | — |
| ccc-security-analyzer.py | scripts/ccc-security-analyzer.py | 安全分析 | 全局安全 | 保留 | — |
| ccc-health-analyzer.py | scripts/ccc-health-analyzer.py | 健康分析 | ④ 观测 | 保留 | — |
| ccc-failure-report.py | scripts/ccc-failure-report.py | 失败报告 | ④ 报告 | 保留 | — |
| ccc-daily-diff-review.py | scripts/ccc-daily-diff-review.py | 日 diff review | ④ review | 保留 | — |
| ccc-daily-docs-review.py | scripts/ccc-daily-docs-review.py | 日 docs review | ④ review | 保留 | — |
| ccc-desktop-stability-report.py | scripts/ccc-desktop-stability-report.py | desktop 稳定性报告 | ① 报告 | 保留 | — |
| ccc-stress-matrix.py | scripts/ccc-stress-matrix.py | 压测矩阵（SceneConfig dataclass + 场景生成） | 全局压测 | **改造（P1）** | 9 处 `executor_intent` 引用：L71 dataclass 默认值 `executor_intent: str = "opencode"` + L166/185/202/255/344/379/447 七处 `executor_intent="python"` 场景配置 + L487 dict 构建；统一替换为 skill_ref/prompt_ref |
| ccc-stress-*.py / .sh | scripts/ccc-stress-*.{py,sh}（除 ccc-stress-matrix.py） | 压测 | 全局压测 | 保留 | — |
| ccc-clean-abnormal.py | scripts/ccc-clean-abnormal.py | 清 abnormal | ④ 清理 | 保留 | — |
| ccc-workspace-doctor.py | scripts/ccc-workspace-doctor.py | workspace doctor | ③ doctor | 保留 | — |
| ccc-skill-cleanup.py | scripts/ccc-skill-cleanup.py | skill 卫生（dry-run / --apply） | ② skill 卫生 | 保留 | references/skills 软链接清理可复用 |
| board-reconcile.py | scripts/board-reconcile.py | board 对账 | ③ 对账 | 保留 | — |
| phase_lint.py | scripts/phase_lint.py | phase lint | ③ lint | 保留 | — |
| human_status.py | scripts/human_status.py | 人类可读状态 | 全局工具 | 保留 | — |
| check-version-sync.py | scripts/check-version-sync.py | 版本同步检查 | 全局检查 | 保留 | — |
| verify-ccc-hub.py | scripts/verify-ccc-hub.py | hub 验证 | 全局验证 | 保留 | — |
| migrate-desktop-conversation-bind.py | scripts/migrate-desktop-conversation-bind.py | desktop 会话绑定迁移 | 全局迁移 | 保留 | — |
| gen-tauri-icons.py | scripts/gen-tauri-icons.py | tauri 图标生成 | 全局工具 | 保留 | — |
| _ccc_hygiene.py | scripts/_ccc_hygiene.py | CCC 卫生 | 全局卫生 | 保留 | — |
| _ccc_launchd.sh | scripts/_ccc_launchd.sh | launchd 工具 | 全局 launchd | 保留 | — |
| _smoke_remote.sh | scripts/_smoke_remote.sh | 远程冒烟 | 全局冒烟 | 保留 | — |
| _ops_probe.py | scripts/_ops_probe.py | ops 探针 | ④ ops | 保留 | — |
| install-*.sh | scripts/install-*.sh | 各类安装脚本 | 全局安装 | 保留 | — |
| smoke-*.sh | scripts/smoke-*.sh | 各类冒烟脚本 | 全局冒烟 | 改造 | 含 `executor_intent` 字段的 smoke 脚本（smoke-ccc-demo-released/reliability/soak、smoke-dual-port-remote）更新为 `skill_ref`/`prompt_ref` |
| precommit-*.sh | scripts/precommit-*.sh | precommit 钩子 | 全局钩子 | 保留 | — |
| ccc-board-ui/ | scripts/ccc-board-ui/ | 旧 board UI（重定向到 Hub） | — | 保留 | 仅重定向 |
| git-hooks/ccc-post-push | scripts/git-hooks/ccc-post-push | post-push 钩子 | 全局钩子 | 保留 | — |
| roles/*.sh | scripts/roles/*.sh | 旧角色 shell 入口 | — | 保留 | 兼容 |
| _ccc_launchd.sh | scripts/_ccc_launchd.sh | launchd | 全局 | 保留 | — |

### 8. Skill 相关

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| _skills_catalog.py | scripts/_skills_catalog.py | 轻量 Skill 目录扫描（Hub 转任务卡 chips 用，软偏好） | ② Skill 目录 | **改造** | 扩展为扫描 `references/skills/` + `references/prompts/`；提供 `skill_ref`/`prompt_ref` 路径校验 API（供 transfer_gate 调用） |
| board/prompt.py | scripts/board/prompt.py | phase/role prompt 拼装（`build_dev_phase_prompt`，含 skill_hints 注入） | ④ prompt 拼装 | **改造** | 新增 `skill_ref`/`prompt_ref` 解析：从 references 库加载 Skill/Prompt 内容注入到执行器 prompt；`prompt_inline` 直接拼接 |
| references/skills/ | references/skills/ | Skill 库（已建：code-review / write-code） | ② Skill 库 | 保留 + 持续扩充 | 新增职能 = 加目录；已落地 |
| references/prompts/ | references/prompts/ | Prompt 库（已建：code-review-prompt.md） | ② Prompt 库 | 保留 + 持续扩充 | 新增 Prompt = 加文件；已落地 |
| skills/ | skills/ | 现有角色 Skill（ccc-product/dev/reviewer/tester/ops/kb/regress/audit） | ④ 角色 Skill | 保留 | Engine 角色用，与新 references/skills 并存 |
| .cursor/skills/ | .cursor/skills/ | cursor skill（ccc-stress-kpi / ccc-verify） | — | 保留 | IDE 端工具，不影响 |
| install-ccc-as-skill.sh | scripts/install-ccc-as-skill.sh | CCC 安装为 skill | 全局安装 | 保留 | — |
| install-ccc-roles.sh | scripts/install-ccc-roles.sh | 角色安装 | 全局安装 | 保留 | — |
| uninstall-ccc-roles.sh | scripts/uninstall-ccc-roles.sh | 角色卸载 | 全局卸载 | 保留 | — |

### 9. 测试文件（scripts/tests/test_*.py）

> 范围扩展：原扫描范围（`.py` / `.sh`）未覆盖 `tests/` 子目录，本节补齐。**正文不修改，仅在清单标注**，待阶段 5 与正文字段同步改造。

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| test_ccc_hygiene.py | scripts/tests/test_ccc_hygiene.py | CCC 卫生测试 | ④ 测试 | **改造（P1）** | L26 `{"transfer_gate": {"pipeline": "ops", "executor_intent": "python"}}` 1 处引用，待 transfer_gate 字段改造后同步更新 |
| test_ccc_transfer_samples.py | scripts/tests/test_ccc_transfer_samples.py | transfer 样本测试（多个 ccc-transfer 块样本） | ④ 测试 | **改造（P1）** | 11 处 `executor_intent` 引用（L25/33/41/49/57/65/73/81/89/97/130），覆盖 opencode/python/cli 三种枚举值；样本块字段需整体替换为 skill_ref/prompt_ref |
| test_desktop_transfer_gate.py | scripts/tests/test_desktop_transfer_gate.py | desktop transfer 门禁测试 | ④ 测试 | **改造（P1）** | 12 处引用（L26/49/71/94/129/144/152/168/190/206/225/249），含 L152 `assert transfer_gate.resolve_executor_intent(body) == "python"` 直接断言退役函数，需删除该断言并改为 skill_ref 校验 |
| test_desktop_api.py | scripts/tests/test_desktop_api.py | desktop API 测试 | ④ 测试 | **改造（P1）** | 3 处引用（L152/205/261），均为 `"executor_intent": "opencode"` 默认值，同步替换 |
| test_min_pipeline.py | scripts/tests/test_min_pipeline.py | 最小流水线测试 | ④ 测试 | **改造（P1）** | L68 1 处 `"executor_intent": "opencode"`，同步替换 |

**小计**：5 个测试文件，28 处 `executor_intent` 引用。改造依赖 ① transfer_gate.py 字段定稿后统一更新。

### 10. 前端 JS（范围扩展）

> 范围扩展：原扫描范围（`.py` / `.sh`）未覆盖前端 JS，本节补齐。**正文不修改，仅在清单标注**，待阶段 5 与后端字段同步改造。

| 组件 | 路径 | 当前职责 | 新架构下角色 | 处理建议 | 备注 |
|------|------|----------|-------------|----------|------|
| dispatchCard.js | scripts/chat_server/frontend/js/components/dispatchCard.js | 派发卡片渲染（解析 ccc-transfer 块为 UI 卡片） | ③ 前端渲染 | **改造（P2）** | L341 `executor_intent: parsed.executor_intent \|\| 'opencode'` 1 处字段读取，需替换为 skill_ref/prompt_ref 渲染 |
| dispatchFormat.js | scripts/chat_server/frontend/js/components/dispatchFormat.js | 派发格式化（ccc-transfer 块解析/序列化） | ③ 前端格式化 | **改造（P2）** | 3 处引用：L30 注释列举字段、L65 `executor_intent: String(obj.executor_intent \|\| 'opencode')...` 解析、L116 默认值 `'opencode'`；格式化器需同步新字段 |
| quickPrompts.js | scripts/chat_server/frontend/js/components/quickPrompts.js | 快捷 prompt 模板 | ③ 前端模板 | **改造（P2）** | L72 `'4. 卫生卡 executor_intent=python。\n\n'` 1 处文案，需删除/替换为新字段提示 |

**小计**：3 个前端 JS 文件，5 处 `executor_intent` 引用。改造依赖后端字段定稿，且需与 dispatchCard/dispatchFormat 渲染逻辑联动。

---

## 新增组件清单（新架构需要但当前不存在）

| 组件 | 路径 | 职责 | 优先级 | 备注 |
|------|------|------|--------|------|
| ccc-submit-proposal.py | scripts/ccc-submit-proposal.py | M1 端 CLI：读方案文件 → POST `Hub /api/desktop/proposal` | P0 | 新建；M1 IDE 谈完方案后调用；可复用 `transfer_outbox_flush` 的 HTTP 投递模式 |
| ccc-intent-splitter.py | scripts/ccc-intent-splitter.py | 2017 端 Claude 后台程序：消费方案文件 → 从 Skill/Prompt 库组装软链接 → 拆卡产出意图卡链 → 飞轮推下一 L1 | P0 | 新建；**核心复用** `_product_session.run_contract_loop_sync` + `_product_fanout.build_fanout_prompt/parse_fanout_output/apply_fanout`；输出带 `skill_ref`/`prompt_ref`/`prompt_inline` 的意图卡 |
| Hub 端点 POST /api/desktop/proposal | chat_server/routers/desktop.py | 接收 M1 方案文件 → 落盘到业务仓 `.ccc/intent-proposals/` → 触发 2017 拆卡 → 返回 proposal_id | P0 | 在现有 desktop router 新增；可复用 inbox proposals 存储机制 |
| Hub 端点 GET /api/desktop/proposal/<id>/result | chat_server/routers/desktop.py | 查询拆卡结果（意图卡链 + 入队状态） | P0 | 在现有 desktop router 新增 |
| 意图卡 schema 扩展 | references/intent-card-sop.md + transfer_gate.py | 新增 `skill_ref`/`prompt_ref`/`prompt_inline` 字段定义 | P0 | schema 文档 + 校验代码同步 |
| references/skills/ 扩充 | references/skills/ | 新增 dev-write / review / test 等职能 Skill | P1 | 持续扩充，不阻塞主路径 |
| references/prompts/ 扩充 | references/prompts/ | 新增 dev-prompt / review-prompt 等 | P1 | 持续扩充 |

---

## 冗余组件清单（新架构下不再需要）

| 组件/逻辑 | 路径 | 原职责 | 冗余原因 | 处理 |
|----------|------|--------|----------|------|
| `VALID_EXECUTOR_INTENTS` 枚举 | chat_server/services/transfer_gate.py:13-15 | 校验 `executor_intent` ∈ {opencode/python/ollama/cli/auto} | 新架构用 `skill_ref`/`prompt_ref` 软链接替代枚举式职能锁定 | 删除 |
| `executor_intent` 校验块 | chat_server/services/transfer_gate.py:119-126 | 拒绝未知执行面 | 同上 | 删除 |
| `resolve_executor_intent` 函数 | chat_server/services/transfer_gate.py:891-893 | 解析 executor_intent | 同上 | 删除 |
| `executor_intent` 字段读取 | chat_server/services/transfer_gate.py:320, 758, 770 | gate 内多处读取 | 同上 | 删除 |
| `executor_intent` 字段 | chat_server/services/proposals.py:77, 105 | inbox 提案字段 | 同上 | 删除（替换为 skill_ref/prompt_ref） |
| `_epic_default_executor` / `executor_intent` 读取 | _product_fanout.py:529, 541, 548, 550 | epic 默认执行器推断 | 新架构由 splitter 从 Skill 库组装 | 删除 |
| `executor_intent` 默认值 | chat_server/services/intent_promote.py:125 | 默认 "opencode" | 同上 | 删除（替换为 skill_ref 默认） |
| `executor_intent` 文案 | _failure_buckets.py:101 | 失败提示文案 | 同上 | 删除引用 |
| `executor_intent` 模板字段 | chat_server/hub_voice.py:171, 178 | Hub 语音 prompt 契约块模板 + 文案 | 同上（旧叙事载体） | 删除/替换为 skill_ref/prompt_ref |
| `executor_intent` 引用（14 处） | chat_server/routers/desktop.py:638,712,720,742,751,758,824,848,944,947,957,969,1041,1073 | Desktop API 转任务体构建 + resolve_executor_intent 调用 | 同上 | 删除/替换为 skill_ref/prompt_ref |
| `executor_intent` 字段读取 | chat_server/services/flow_events.py:551 | flow 事件字段 | 同上 | 删除/替换 |
| `executor_intent` 默认值 | chat_server/services/transfer_outbox_flush.py:374 | outbox 冲刷默认 "opencode" | 同上 | 删除/替换 |
| `executor_intent` 引用（9 处） | scripts/ccc-stress-matrix.py:71,166,185,202,255,344,379,447,487 | 压测 SceneConfig dataclass + 场景配置 | 同上 | 删除/替换 |
| `executor_intent` 引用（28 处） | scripts/tests/test_*.py（5 个文件） | 测试样本块字段 + resolve_executor_intent 断言 | 同上 | 删除/替换（含删除 L152 退役函数断言） |
| `executor_intent` 引用（5 处） | scripts/chat_server/frontend/js/components/*.js（3 个文件） | 前端卡片渲染 + 格式化 + 快捷 prompt | 同上 | 删除/替换 |
| board/roles/product.py `product_role` 主路径 | board/roles/product.py:283-440 | 扫 backlog → Claude 拆 epic 为 work 子卡 | 新架构由 `ccc-intent-splitter.py`（消费方案文件）取代；旧路径"扫 backlog 自动拆卡"违反"Engine 不拆卡"边界 | **标史**（保留代码，主路径切走） |

---

## 改造工作量评估

| 类别 | 数量 | 说明 |
|------|------|------|
| **保留** | ~116 | Engine 核心 / OpenCode 执行器 / Board 存储 / 工具配置 / 大部分 Hub 服务 / Claude 集成基础设施（原 ~120 中 flow_events / transfer_outbox_flush / hub_voice / ccc-stress-matrix 转为改造） |
| **改造** | **22** | 原 13 项 + 新增 4 项主代码（hub_voice.py / flow_events.py / transfer_outbox_flush.py / ccc-stress-matrix.py）+ 测试文件 5 项（scripts/tests/test_*.py）+ 前端 JS 3 项（dispatchCard.js / dispatchFormat.js / quickPrompts.js）+ smoke 脚本若干 |
| **新增** | **5** | ccc-submit-proposal.py、ccc-intent-splitter.py、Hub 2 个新端点、意图卡 schema 扩展（+ Skill/Prompt 库持续扩充） |
| **冗余（删除）** | **~69 处** | 原 9 处 + 新增 60 处 `executor_intent` 引用（hub_voice.py 2 + desktop.py 14 + flow_events.py 1 + transfer_outbox_flush.py 1 + ccc-stress-matrix.py 9 + tests 28 + frontend JS 5） |
| **标史** | **1** | board/roles/product.py 的 `product_role` 主路径（保留代码，主路径切到 ccc-intent-splitter） |

### 改造优先级排序

| 序 | 组件 | 改造点 | 优先级 | 依赖 |
|----|------|--------|--------|------|
| ① | chat_server/services/transfer_gate.py | 删 executor_intent 校验 + 加 skill_ref/prompt_ref 校验 | P0 | 意图卡 schema 定稿 |
| ② | ccc-intent-splitter.py（新建） | 复用 _product_session + _product_fanout 拆卡 | P0 | ① + Skill 库 |
| ③ | ccc-submit-proposal.py（新建） | M1 端 CLI | P0 | ④ |
| ④ | chat_server/routers/desktop.py | 新增 /api/desktop/proposal + result 端点 | P0 | ① |
| ⑤ | _product_fanout.py | 删 executor_intent 读取 + 子卡注入 skill_ref | P0 | ① |
| ⑥ | chat_server/services/proposals.py | 删 executor_intent 字段 + 加新字段 | P1 | ① |
| ⑦ | chat_server/services/intent_promote.py | 默认值替换 | P1 | ① |
| ⑧ | _skills_catalog.py | 扩展扫描 references/ + 路径校验 API | P1 | Skill 库扩充 |
| ⑨ | board/prompt.py | skill_ref/prompt_ref 解析注入 | P1 | ⑧ |
| ⑩ | ccc-engine.py | 透传 skill_ref + 边界强化 | P1 | ① |
| ⑪ | _product_session.py / ccc-product-session.py | 适配方案消费 → 拆卡 | P1 | ② |
| ⑫ | _role_lock.py | 新增 intent-splitter 角色锁 | P2 | ② |
| ⑬ | _failure_buckets.py + smoke 脚本 | 文案/字段更新 | P2 | ① |
| ⑭ | chat_server/hub_voice.py | 删 L171 模板 executor_intent + L178 文案（旧叙事 prompt 载体） | P0 | ① |
| ⑮ | chat_server/routers/desktop.py（14 处清理） | 清理 14 处 executor_intent 引用 + resolve_executor_intent 调用 | P0 | ① |
| ⑯ | chat_server/services/flow_events.py | L551 字段替换 | P1 | ① |
| ⑰ | chat_server/services/transfer_outbox_flush.py | L374 默认值替换 | P1 | ① |
| ⑱ | scripts/ccc-stress-matrix.py | 9 处 executor_intent 替换（dataclass + 场景配置） | P1 | ① |
| ⑲ | scripts/tests/test_*.py（5 个文件） | 28 处引用同步更新 + 删 resolve_executor_intent 断言 | P1 | ① |
| ⑳ | scripts/chat_server/frontend/js/components/*.js（3 个文件） | 5 处引用同步更新（渲染 + 格式化 + 模板） | P2 | ① + 后端字段定稿 |

---

## 关键发现

1. **`executor_intent` 是新架构退役的核心字段**：全仓 ~88 处引用（原盘点仅识别 30 处，遗漏 58 处），分布如下：
   - `transfer_gate.py`（6 处）、`proposals.py`（2 处）、`_product_fanout.py`（4 处）、`intent_promote.py`（1 处）、`_failure_buckets.py`（1 处）—— 原盘点已识别
   - `hub_voice.py`（2 处，L171/L178，旧叙事 prompt 载体）—— **遗漏补齐**
   - `desktop.py`（14 处，含 resolve_executor_intent 调用与 bug 默认值）—— **遗漏补齐**
   - `flow_events.py`（1 处，L551）—— **误判保留，已纠正为改造**
   - `transfer_outbox_flush.py`（1 处，L374）—— **误判保留，已纠正为改造**
   - `ccc-stress-matrix.py`（9 处，dataclass + 场景配置）—— **误判保留，已纠正为改造**
   - `scripts/tests/test_*.py`（5 文件 28 处，含 L152 退役函数断言）—— **范围扩展补齐**
   - `frontend/js/components/*.js`（3 文件 5 处）—— **范围扩展补齐**
   - smoke 脚本（原 17 处归并在此类，部分已计入 smoke-*.sh）

2. **`ccc-intent-splitter.py` 不是从零新建**：`_product_session.py`（contract loop）+ `_product_fanout.py`（拆卡 SOP）+ `ccc-product-session.py`（runner）三件套已构成完整拆卡基础设施，新 splitter 主要是包装为"消费方案文件"入口 + 注入 `skill_ref`/`prompt_ref`。

3. **Skill/Prompt 库已落地**：`references/skills/`（code-review / write-code）+ `references/prompts/`（code-review-prompt.md）已存在，新架构的物理形态已具备，仅需持续扩充。

4. **Hub 端点改造点集中**：`chat_server/routers/desktop.py` 已有 `/proposals` + `/proposals/{id}/adopt` inbox 机制，新 `/api/desktop/proposal` 端点可复用存储 + 鉴权，新增"触发 2017 拆卡"环节。

5. **board/roles/product.py 是唯一"标史"候选**：其"扫 backlog 自动拆卡"主路径违反新架构"Engine 不拆卡"边界，但代码资产（fanout 逻辑）可被新 splitter 复用，故标史保留而非删除。

6. **OpenCode 执行器全保留**：新架构明确"OpenCode 写码执行器（不变）"，`opencode-exec.py` / `opencode-pool.py` / `opencode-watchdog.sh` / `ccc-exec-launcher.sh` 全部保留。

7. **Engine 核心大部分保留**：`engine/` 目录 26 个模块全部保留，仅 `ccc-engine.py` 主入口需轻量改造（透传 skill_ref + 边界强化）。
