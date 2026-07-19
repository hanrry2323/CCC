# CCC 运行控制面（v0.51.0）

> **SSOT**：`~/.ccc/control.json`（[`scripts/_ccc_control.py`](../scripts/_ccc_control.py)）  
> CLI：`bash scripts/ccc-autostart-guard.sh {status|disable|ui|enable|invent}`  
> 前端开发：`bash scripts/ccc-hub-dev.sh`（不碰 control / launchd）  
> 失败查询：见 [`observability.md`](observability.md)

**v0.41+ 产品规则**：Hub/Board **下达任务成功** → 强制 `enabled`（若非 invent）+ 写 `~/.ccc/engine.wake` + 尝试 launchd 拉起 Engine。**无确认弹窗。** 不打开 invent。

**v0.42 收官**：
- product 硬门：无验收 / 空 scope / 裸 `['all']` **不准进 planned**（记 failure ledger）
- failures → `POST /api/tasks/reopen`（Console + 对话旁）→ planned + wake
- Hub `GET /api/runtime-status`：control · wake · 队列计数
- Hub / Claude 侧栏会话 **保持分开**（不做合并）

**v0.42.1 下达闭环补强**（UI 面 ≠ 消费面）：
- Hub **与** Board 均调用 `ensure_engine_for_task`（Hub 双保险，防 Board 旧进程）
- 下达时把目标项目 path **幂等写入** `~/.ccc/workspaces.json`（Engine 默认只扫 CCC；显式下达才扩权）
- `install-hub --start` → `ui` 仍正确；**下达**才切 `enabled` 并恢复 `com.ccc.engine` plist

**v0.42.3 invent 硬禁用**：
- `_ccc_control.py` 设 `INVENT_HARD_DISABLED=True`，`may_invent()` 永远返回 False
- 即使 `control.json` 写 `invent`，Engine 也不会自造任务（视为 disabled）
- 保留档位仅为兼容历史 control.json；新部署应使用 `enabled`

**v0.51.0 鉴权与持久化加固**：
- `ccc-board-server.py` 移除 `CCC_BOARD_ALLOW_LOCAL_NO_TOKEN` 跳过分支（F-SEC-05）
- `engine/active_tasks.py` 移除 finally unlink（F-CON-02），保留崩溃恢复文件
- `chat_server/auth.py` 默认不信任 `X-Forwarded-For`（P1-1），需反向代理时显式 `CCC_TRUST_PROXY=1`

---

## 业务状态机

```
disabled ──默认──► 无常驻
ui       ──显式──► 仅 Hub+Board；无 Engine
enabled  ──显式──► Engine 只消费已有队列（禁止 invent）
invent   ──显式──► [v0.42.3 起硬禁用] 仅保留档位，Engine 视为 disabled
```

| 模式 | Hub/Board | Engine | 自造任务 |
|------|-----------|--------|----------|
| `disabled` | 否 | 否 | 否 |
| `ui` | 可 | 否 | 否 |
| `enabled` | 可 | 可 | **否**（队列消费者） |
| `invent` | 可 | **否（硬禁用）** | **否**（`may_invent()` 永远 False） |

**根因纠正**：`enable ≠ 永远在线自造任务`。空队列时 Engine **深睡 60s**，不跑 audit/abnormal。

Workspace 发现默认 **仅 CCC 自身**；全扫需 `CCC_DISCOVER_ALL=1` 或 `~/.ccc/workspaces.json` / `CCC_WORKSPACES`。

---

## 命令

```bash
bash scripts/ccc-autostart-guard.sh status
bash scripts/ccc-autostart-guard.sh disable
bash scripts/ccc-autostart-guard.sh ui [--start]
bash scripts/ccc-autostart-guard.sh enable [--start]   # 推荐日常自动化
bash scripts/ccc-autostart-guard.sh invent [--start]   # v0.42.3 起硬禁用（仅兼容历史档位）
bash scripts/ccc-hub-dev.sh                           # 前端前台
python3 scripts/ccc-failure-report.py --last 20
```

---

## 禁止

1. crontab 里 `python3 ccc-engine.py &`
2. patrol `Popen(ccc-engine.py)`
3. 为看前端去 `launchctl load` KeepAlive
4. 把 `invent` 当成默认 enable

---

## 流水线环境变量（v0.40.1+）

| 变量 | 默认 | 作用 |
|------|------|------|
| `CCC_CLAUDE_BIN` | 自动解析 | claude 绝对路径（launchd PATH 不全时必设） |
| `CCC_UPSTREAM_STRICT` | off | `1` 时 upstream 探针仅 HTTP 200 算健康 |
| `CCC_REVIEWER_FALLBACK` | `static` | `static`=LLM 挂时 PASS+WARN 过门；`quarantine`=进 abnormal |
| `CCC_DAILY_REVIEW_LLM` | off | `1` 时日审走 Claude JSON（失败回退启发式） |
| `CCC_TRUST_PROXY` | off | `1` 时 chat_server/auth.py 信任 `X-Forwarded-For`（反向代理后开启） |
| `CCC_EXEC_COMMIT_ALLOWED_PATHS` | 空 | 设置后 ccc-exec-commit.sh 仅允许 WORKSPACE 在指定目录树下 |

## 闭环步骤（角色名 = 给人看；自动化 = prompt+skill+harness）

```
对齐基线 → 下一步 → 下达 backlog → wake Engine
  → product(Claude+skill) → plan/phases 硬 lint → planned
  → dev(OpenCode+scope) → testing（测试/验收）
  → pytest 硬门 → reviewer(Claude+skill) → verified
  → kb 程序发布 → released
  → daily-diff-review（A–J）→ 必要时再 backlog+wake
失败 → ledger → Hub 重开 → planned+wake
```

日审：`python3 scripts/ccc-daily-diff-review.py --workspace <ws> [--apply]`  
重开：`POST /api/tasks/reopen` `{"id":"…","workspace":"CCC","to":"planned"}`  
状态条：`GET /api/runtime-status?workspace=CCC`

---

## 版本关系

- v0.37：空看板 invent 默认 OFF
- v0.39：启停控制面
- **v0.40**：`enabled`=队列消费者；`invent` 独立；失败账本
- **v0.40.1**：claude PATH / upstream 4xx / reviewer static fallback / hang 降噪
- **v0.41**：下任务强制开工；基线对齐；日审骨架；Hub SSE 去重
- **v0.42.3**：invent 硬禁用（`INVENT_HARD_DISABLED=True`，`may_invent()` 永远 False）
- **v0.51.0**：鉴权加固（移除 allow_local 跳过、XFF 默认不信任）+ 持久化修复（finally unlink 移除）+ 版本同步 CI 强制
