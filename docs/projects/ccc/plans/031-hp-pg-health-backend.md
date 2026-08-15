# 方案 · HP PostgreSQL 健康接入控制台（后端底座 + 前端待办）

> 项目：ccc · 编号：ccc-plan-031 · 状态：部分执行 · 作者：Claude Code · 工具：Claude Code
> 创建：2026-08-15 · 更新：2026-08-15
> 关联卡：无
> 关联方案：026（控制台重构 · /ops/hp-health 同款接入先例）

## 背景

2026-08-15 运维事故：HP 知识库 PostgreSQL 僵死约 20 小时无人发现（`/dev/shm` 共享内存段被清，postmaster 僵尸：端口通但新连接全挂）。复盘发现三个检测盲区，其中一个在 CCC 侧：

- 控制台 `/ops/hp-health` 对 HP 只做 **TCP 握手探活**（8083 端口），PG 无任何查询级探活 → 僵尸态（进程活着、端口在听、连接全挂）在控制台上显示「正常」。
- 同款盲区也存在于 `/ops/kb-health` 的 hp_kb 部分（TCP + HTTP MCP，均不触及 PG 真实可用性）。

**老板定调（2026-08-15）**：后端底座由 Claude Code 本方案实施（探针已部署 + 数据源接口）；**前端渲染对接由同步项目开发团队另行实施，列入本方案待办**，不与后端冲突。

## 现状盘点（已落地）

| 层 | 现状 |
|----|------|
| **HP 探针（已完成，2026-08-15）** | `pg-health.sh`：真连接检测（`SELECT 1`），三态 `ok / zombie / down`；cron 每 5 分钟；输出 `/data/knowledge/health/pg-health.status`（KV，机器可读）+ 30 天日志 + 连续失败告警标记。权威副本：qx-map `cluster/scripts/hp-pg-health.sh` |
| **CCC 现有** | `/ops/hp-health`（TCP 8083）· `/ops/kb-health`（hp_kb = TCP + HTTP MCP）· 均不覆盖 PG |
| **缺口** | 控制台无 PG 健康展示；CCC 后端无 PG 数据源接口 |

## 方案（后端 · 本次实施）

**数据源 = HP 探针状态文件（单一数据源）**，CCC 后端只做读取汇总，不做二次探测。理由：探针在 HP 本机真连接检测（最可靠）、带三态语义（僵尸态精确识别）、5 分钟一次（对 PG 零探测压力）；CCC 每 15s 轮询读状态文件即可。

1. `server/config/loader.py` `OPTIONAL_KEYS` 加 `CLUSTER_PG_TARGET`（默认 `""`，零配置兼容，模式同 `CLUSTER_HP_TARGET`）。
2. `server/web/server.py` 新增 `_build_pg_health()`：
   - `CLUSTER_PG_TARGET` 未配置 → `configured: False`（容错不 500）。
   - TCP 兜底探活 `check_tcp_reachable`（同 `/ops/hp-health` 口径，返回网络层可达性 + 延迟）。
   - SSH 读 HP 探针状态文件（`ssh -o BatchMode=yes -o ConnectTimeout=5 hp@<host> cat /data/knowledge/health/pg-health.status`，超时兜底 → `status: "missing"`）。
   - 返回：`{configured, host, port, tcp_reachable, latency_ms, status, probe_ts, probe_detail, probe_elapsed_ms, consecutive_fail}`。
3. 新增 handler `_handle_ops_pg_health()` + 路由 `GET /ops/pg-health`（仿 `/ops/hp-health` 注册）。
4. 测试：`server/tests/test_http_api.py` 新增 `TestOpsPgHealth`（仿 `TestOpsSummary` 的 `api_server` + monkeypatch 模式；SSH 探针读取用 monkeypatch 打桩，保证测试确定性、不依赖真实 SSH）。

## 前端对接（待办 · 同步项目开发团队实施，本次不做）

| 项 | 说明 |
|----|------|
| 文件 | `server/web/legacy-chat/js/pages/consolePage.js` |
| 改动 | `pollSystem()` 的 `Promise.all` 加 `apiGet('/ops/pg-health')`；新增 `renderPg()` 在「知识库健康」卡内展示 PG 三态 pill（绿 ok / 橙 zombie / 红 down）+ 最近探测时间；`renderNodes()` 节点计数可把 PG 并入 |
| 数据流 | `consolePage.js → GET /ops/pg-health → _build_pg_health() → SSH cat 探针状态文件 → JSON` |
| 样式 | 沿用 `pill()` / `console-node` 现有样式，一般无需动 css |

## 数据流（汇总）

```
consolePage.js pollSystem() 每 15s
  → GET /ops/pg-health
  → server.py _build_pg_health()
      ├─ TCP 兜底：check_tcp_reachable(host, 5432)
      └─ SSH cat HP 探针状态文件（pg-health.status，5 分钟粒度）
  → JSON {status, probe_ts, probe_detail, tcp_reachable, latency_ms, ...}
  → renderPg() 渲染三态 pill
```

## 待办清单

- [ ] **前端 consolePage.js 渲染 /ops/pg-health**（同步项目开发团队，数据源接口本方案已就绪）
- [ ] HP 悬空 cron 清理：`0 3 * * * /data/knowledge/health/daily-check.sh` 指向已不存在的脚本（08-03 已 `.bak`），每天跑必失败
- [ ] 探针告警的推送通道接入（本地 alert 标记 → 群通知/控制台告警），后续另立方案
- [ ] 异席机审：本方案后端改动待 Codex 独立终验

## 红线（遵守）

- ccc 平台自研禁出卡（`registry.yaml` `ccc: taskable:false`）。本方案**不转卡**，由 M1 主窗口直接开发 + 直接测试（pytest）+ 异席机审。
- 禁 `git add -A`；显式文件提交；不碰运行面/密钥。
