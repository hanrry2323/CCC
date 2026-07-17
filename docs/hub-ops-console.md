# Hub 运维 vs 控制台 · Cockpit 迁移

> 对应计划：Hub 运维页 + 控制台大升级。运维是 Hub 1.0 能力提前落地，不绑架 HP 仓库。

## 页面职责

| 入口 | 路由 | 一句话 |
|------|------|--------|
| **控制台** | `#/console` | 今天队列里发生了什么、卡在哪、怎么重开（任务 KPI） |
| **运维** | `#/ops` | 机器与服务是否活着、代码是否干净、日审说了什么 |

控制台顶部「运维告警 N」读 `/api/ops/risks` 的 high/count，链到 `#/ops`。

## API（Hub `:7777`）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/ops/overview` | 三机卡片 + 告警数 |
| GET | `/api/ops/ports` | infrastructure.md + TCP/HTTP 探测（缓存 ≤30s） |
| GET | `/api/ops/resources` | 本机 load/mem/disk |
| GET | `/api/ops/workspaces` | 注册仓 branch/dirty/ahead |
| GET | `/api/ops/daily-review` | 最新日审报告索引 |
| POST | `/api/ops/daily-review/run` | dry-run / apply（鉴权 + 防抖） |
| GET | `/api/ops/risks` | 聚合风险 |
| GET | `/api/ops/kb-health` | HP 端口探活 |
| GET | `/api/ops/deploy` | Mac2017 / feiniu 只读部署态 |
| GET | `/api/ops/docs-debt` | 文档债提示 |
| GET | `/api/ops/quality` | 质量日摘要 |
| GET | `/api/ops/ops-auto` | backlog 中 `ops-auto` 卡 |
| POST | `/api/ops/adopt` | 建议一键入队（tags 含 `ops-auto`） |

端口 SSOT 仍是 [`.ccc/infrastructure.md`](../.ccc/infrastructure.md)；运维页只展示路径，不散落硬编码。

## 自动化（非 invent）

- 日 diff：`scripts/ccc-daily-diff-review.py`（`--apply` 仅 C/E/F/I 可行动决策建卡；D/G 只告警）
- 建卡标签：`ops-auto` + `daily-review`
- 文档审：`scripts/ccc-daily-docs-review.py`
- 定时安装（**显式**）：`bash scripts/install-ops-plist.sh install`（默认写入 `disabled-ccc`；加 `--enable` 才 load）
- 定时默认 **dry-run**；需要 apply 请改 plist `ProgramArguments`

红线：定时写 backlog = 用户安装时启用的 ops 策略，不是 agent 会话里偷偷 invent。

## Cockpit `:7778` 迁移路径

1. **现在**：Hub `#/ops` 为运维主入口；Cockpit 深链可保留一期（infrastructure 仍登记 7778）。
2. **达标后**：在 infrastructure 将 Cockpit 标为可选/废弃；不再平行维护两套 UI。
3. **不要**复活 cluster-bus；探测逻辑在 `scripts/_ops_probe.py`。

## 与控制台 KPI

Board `GET /api/dashboard` 的 `kpi` 现含：

- `in_progress` / `testing` / `abnormal` / `released_today`
- 兼容：`today.released`、`ready_to_release`
