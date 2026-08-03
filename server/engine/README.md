# engine/ — 薄驱动核心

> 施工卡：T2（骨架）+ T32（真实派发闭环）· 依赖：`config/`（已就绪）· 被依赖：`web/`、`deploy/`、`tests/`

## 职责

- 读取 `config/executors.json`（契约 §7 注册表），决定任务派发给谁。
- 发单：把待办任务变为可执行 work；派发：按执行体「分类」选择自动拉起（可后台 CLI）或挂起等人（手动 GUI）。
- **真实派发**（T32）：`subprocess.Popen` 拉起可后台 CLI 执行体，stdout/stderr 重定向到 `{EXECUTOR_LOG_DIR}/{work_id}.log`，按 `EXECUTOR_TIMEOUT_SECONDS` 超时收单。
- 收单：按退出码判定 → 0 = 已回写；非 0 / 超时 / 启动失败 = 打回（附问题清单）。
- 状态更新写入看板接口（`store.py`），T3 前用内存实现。

## 关键约定

- **Engine 负责真实派发/收单**：`engine/` 不含任何具体工具逻辑；工具名只存在于注册表配置；按注册表配置真实拉起可后台 CLI 执行体、采集结果、按契约状态机收单并驱动看板。
- 派发规则（契约 §7 → §2）：`可后台 CLI` → Engine 自动拉起（Popen + wait + 退出码判定）；`手动 GUI` → 挂起等人；管理席/验收席（分类「—」）与未知角色 → 不派发。
- 状态机 = **契约 §2 五态**：`待分派 → 执行中 → 已回写 → 已关闭`；失败路径 `执行中/已回写 → 打回（附问题清单）`，人工处理后 `打回 → 待分派` 重新派发；终态 `已关闭`。**非法状态转移一律抛 `IllegalTransitionError`。**
- 零硬编码：执行体命令/参数模板/工作目录全部走注册表；超时/日志目录走 `config.env`。代码不出现工具名字面量。
- 模型出口一律经 `relay/`，engine 不直连上游。

## 实现

| 文件 | 职责 |
|------|------|
| `task.py` | `Work` 数据结构（含 `card_path`）+ 契约 §2 状态机（合法/非法转移） |
| `dispatch.py` | 注册表读取（§7 字段/分类/命令校验）+ `decide()` 派发决策 + `build_command()` 命令构造 |
| `store.py` | 看板对接接口 `BoardStore` + 内存实现 `InMemoryBoardStore`（T3 前占位） |
| `main.py` | 入口：`--config` → `load_config`；`--once` 单次扫描+真实派发+收单；持续模式循环+心跳+催单 |
| `scheduler.py` | 通用定时任务框架：只读巡检 + 变更类走卡（不绕过 Engine） |
| `cluster.py` | 集群节点状态采集（只读巡检） |

## 派发管道（T32 真实派发闭环）

```text
run_once(registry, store, cfg)
  ├─ 扫描「待分派」work
  ├─ decide(role) → AUTO / MANUAL / NONE
  ├─ AUTO：
  │   ├─ work.transition(执行中) → store.save
  │   ├─ entry = registry.cli_entry_for_role(role)
  │   ├─ cmd = build_command(entry, work_id, role, card_path, default_workdir)
  │   │        # 模板占位符 {work_id}/{card_path}/{role}/{workdir} 替换 + shlex.split
  │   ├─ Popen(cmd, stdout={EXECUTOR_LOG_DIR}/{work_id}.log, cwd=workdir)
  │   ├─ proc.wait(timeout=EXECUTOR_TIMEOUT_SECONDS)
  │   └─ 退出码 0 → work.transition(已回写)
  │      非 0 / TimeoutExpired / OSError → work.transition(打回, problems=[...])
  ├─ MANUAL：work.transition(执行中) → 挂起等人（不收单）
  └─ NONE：跳过（管理席/验收席/未知角色）
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
| `relay/` | 出模型时调 relay 路由（engine 不直连上游） |
| `board/` | 状态更新写入 `store.py` 看板接口（T3 换真实数据结构，不改接口） |
| `deploy/` | `run.example.sh` 以 `$PYTHON_BIN -m server.engine.main --config …` 启动本模块入口 |

## 运行

```
$PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳 + 催单）
$PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 真实派发 + 收单后退出
```

- `--once` 输出一行 JSON 统计（scanned / dispatched / in_flight / collected / timed_out）。
- 缺 `--config` 或配置缺失 → 非零退出并报错。
- 持续模式：每轮 `run_once` 后输出心跳日志；若有超时任务，额外输出催单 warning。

## T3 施工入口

- `store.py` 接口不变，T3 用真实看板数据结构替换 `InMemoryBoardStore`（派发管道不变）。
