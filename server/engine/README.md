# engine/ — 薄驱动核心

> 施工卡：T2（骨架）+ T32（真实派发闭环）+ T39（按卡头执行体绑定派发）· 依赖：`config/`（已就绪）· 被依赖：`web/`、`deploy/`、`tests/`

## 职责

- 读取 `config/executors.json`（契约 §7 注册表），决定任务派发给谁。
- 发单：把待办任务变为可执行 work；派发：按卡头执行体绑定优先（T39）+ 注册表「分类」选择自动拉起（可后台 CLI）或挂起等人（手动 GUI）。
- **真实派发**（T32）：`subprocess.Popen` 拉起可后台 CLI 执行体，stdout/stderr 重定向到 `{EXECUTOR_LOG_DIR}/{work_id}.log`，按 `EXECUTOR_TIMEOUT_SECONDS` 超时收单。
- 收单：按退出码判定 → 0 = 已回写；非 0 / 超时 / 启动失败 = 打回（附问题清单）。
- 状态更新写入看板接口（`store.py`），T3 前用内存实现。

## 关键约定

- **Engine 负责真实派发/收单**：`engine/` 不含任何具体工具逻辑；工具名只存在于注册表配置；按注册表配置真实拉起可后台 CLI 执行体、采集结果、按契约状态机收单并驱动看板。
- 派发规则（T39 卡头绑定优先 → 契约 §7 → §2）：
  - 卡头「执行体：X」命中注册表行 → 按该 binding 的分类决策：`可后台 CLI` → AUTO；`手动 GUI` → MANUAL（即便角色含 CLI 行也不自动拉起，修复 T38 插曲）；`—` → NONE；
  - 卡未指定执行体 / binding 未命中 → 回退 `decide(role)`（现行为不变）。
- 状态机 = **契约 §2 五态**：`待分派 → 执行中 → 已回写 → 已关闭`；失败路径 `执行中/已回写 → 打回（附问题清单）`，人工处理后 `打回 → 待分派` 重新派发；终态 `已关闭`。**非法状态转移一律抛 `IllegalTransitionError`。**
- 零硬编码：执行体命令/参数模板/工作目录全部走注册表；超时/日志目录走 `config.env`。代码不出现工具名字面量。
- 现役模型出口统一经 M1 中转 `127.0.0.1:3456 → LiteLLM → Code`；`server/relay/` 与 6100/6102 为退役历史路径，engine 不直连上游。

## 实现

| 文件 | 职责 |
|------|------|
| `task.py` | `Work` 数据结构（含 `card_path` / `executor`）+ 契约 §2 状态机（合法/非法转移） |
| `dispatch.py` | 注册表读取（§7 字段/分类/命令校验）+ `decide()` 角色决策 + `decide_work()` 卡头绑定优先决策（T39）+ `build_command()` 命令构造 |
| `store.py` | 看板对接接口 `BoardStore` + 内存实现 `InMemoryBoardStore`（T3 前占位）；`FileBoardStore` 解析卡头执行体填充 `Work.executor` |
| `main.py` | 入口：`--config` → `load_config`；`--once` 单次扫描+真实派发+收单；持续模式循环+心跳+催单；`run_once` 决策走 `decide_work` |
| `scheduler.py` | 通用定时任务框架：只读巡检 + 变更类走卡（不绕过 Engine） |
| `cluster.py` | 集群节点状态采集（只读巡检） |

## 派发管道（T32 真实派发闭环 + T39 绑定优先）

```text
run_once(registry, store, cfg)
  ├─ 扫描「待分派」work
  ├─ decide_work(work, registry) → AUTO / MANUAL / NONE（T39：卡头 executor 优先，回退 decide(role)）
  ├─ AUTO：
  │   ├─ work.transition(执行中) → store.save
  │   ├─ entry = registry.cli_entry_for_role(role)   # role 已由 store 从 executor 反查
  │   ├─ cmd = build_command(entry, work_id, role, card_path, default_workdir)
  │   │        # 模板占位符 {work_id}/{card_path}/{role}/{workdir} 替换 + shlex.split
  │   ├─ Popen(cmd, stdout={EXECUTOR_LOG_DIR}/{work_id}.log, cwd=workdir)
  │   ├─ proc.wait(timeout=EXECUTOR_TIMEOUT_SECONDS)
  │   └─ 退出码 0 → work.transition(已回写)
  │      非 0 / TimeoutExpired / OSError → work.transition(打回, problems=[...])
  ├─ MANUAL：work.transition(执行中) → 挂起等人（不收单，即便角色含 CLI 行也不拉起）
  └─ NONE：跳过（管理席/验收席/未知角色/未知执行体回退 NONE）
```

## 注册表 schema（契约 §7 + T32）

`executors.json` 每行字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| `角色` | 是 | 如「开发执行体」 |
| `分类` | 是 | 「可后台 CLI」/「手动 GUI」/「—」 |
| `当前绑定` | 是 | 工具名（如 OpenCode） |
| `命令` | 可后台 CLI 必填 | 启动命令（如 `opencode`） |
| `参数模板` | 可选 | 含 `{work_id}`/`{card_path}`/`{role}`/`{workdir}` 占位符 |
| `工作目录` | 可选 | 留空则用 config 的 `DATA_DIR` |
| `备注` | 是 | 说明 |

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `config/` | 经 `loader.load_config` 读运行参数；读 `EXECUTOR_REGISTRY_PATH` / `EXECUTOR_TIMEOUT_SECONDS` / `EXECUTOR_LOG_DIR` |
| `relay/` | 退役历史目录；现役模型经 M1 `3456 → LiteLLM → Code`（engine 不直连上游） |
| `board/` | 状态更新写入 `store.py` 看板接口（T3 换真实数据结构，不改接口） |
| `deploy/` | `run.example.sh` 以 `$PYTHON_BIN -m server.engine.main --config …` 启动本模块入口 |

## 运行

```
$PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳 + 催单）
$PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 真实派发 + 收单后退出
```

- `--once` 输出一行 JSON 统计（scanned / dispatched / in_flight / collected / timed_out + `audit_*` / `worktrees_cleaned`）。
- 缺 `--config` 或配置缺失 → 非零退出并报错。
- 持续模式：每轮 `run_once` 后输出心跳日志；若有超时任务，额外输出催单 warning。

## 并发槽与埋点（2026-08-07）

- **双池独立槽位**：执行池 `EXECUTOR_MAX_CONCURRENT`（默认 3）与机审池
  `EXECUTOR_MAX_AUDIT_CONCURRENT`（默认 2）互不占位；机审池每轮按「已回写且分支无机审
  证据」独立捞卡（跨重启从分支推导恢复）。
- **槽位热读**：持续模式每轮重读 `config.env` 中两个槽位键，改配置免重启生效。
- **埋点**：`{EXECUTOR_LOG_DIR}/engine-metrics.jsonl`（每轮心跳槽位/队列/吞吐快照）+
  `worker-events.jsonl`（每个执行/机审子进程退出事件：returncode/时长/峰值 RSS/CPU/退出类别）。
- **卫生清理**：合入批准后自动删已合入分支（`scripts/approve-merge.sh`）；Engine 每轮清理
  「已关闭 + 干净 + 已合入」的 worktree（`git worktree remove` + prune，脏 worktree 绝不强删）。

## 机审信封与运行时状态（2026-08-07 二改）

- **分支即信封**：机审通过结果由 Engine 写进 worktree 分支卡并 commit+push（`## 机审区`），
  合入 = 纯快进合并完整信封；生产卡只读，`ready_for_merge`/approve-merge 以
  `git show origin/<分支>:<卡>` 含「机审：通过」为准（跨机可验，不再依赖 2017 本地脏状态）。
- **合入前 Code Review（2026-08-07 三改）**：机审席加载 `code-review` 技能做完整审查
  （正确性/契约/健壮性/范围红线/验收/批注落实）；P0/P1 就地修复+复审闭环
  （连续 2 轮不过或范围性问题才打回），P2 记录不阻断；老板「合入批准」仍为人审兜底。
- **自验收（2026-08-07 四改）**：谁开发谁验收（OpenCode↔OpenCode / Claude↔Claude），
  日常单工具闭环；机审仍是独立步骤（开发禁止写机审区，验收席同工具也按独立审查执行），
  老板「合入批准」人审 diff 不可省。
- **机审判定与状态（2026-08-07 五改）**：业务结论优先（「机审：不通过」绝不被日志弱特征
  误判 infra）；infra 连续 3 次回待分派人工跟进；`EXECUTOR_AUDIT_TIMEOUT_SECONDS` 独立
  审计超时；看板机审列状态标签 = 审核中 / 冷却中 / 修复中 / 待审。
- **主树干净化**：`FileBoardStore` 有 `log_dir` 时 `save_work` 只写运行时 sidecar
  （`state/cards.jsonl`：state/retry_count/reason/redispatch），不写卡文件；看板以
  「git 卡真相 + 运行时状态 + 分支信封证据」合成。git_sync 对卡文件强制以 main 为准。
- **老板批注（最高指令）**：`## 人工批注` 随 main 卡走（worktree 天然读到）；回写区
  `## 批注落实` 为机械抓手（validate 门禁）；机审必须核对批注落实，未落实 → 不通过。
- **重新分派**：看板按钮/`redispatch-card.sh` 写运行时 redispatch 指令（不打回卡文件）。

## T3 施工入口

- `store.py` 接口不变，T3 用真实看板数据结构替换 `InMemoryBoardStore`（派发管道不变）。
