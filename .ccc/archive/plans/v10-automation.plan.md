# v1.0 Automation Implementation Plan

> CCC v0.5 → v1.0 自动化实现路线图
> 基于：Trae 三方审计报告 (2026-07-06)

## 范围

- **目标**：从"手动跨设备协同"升级到"CCC 自动选设备"。
  把 Trae 报告识别的 7 项 gap 全部补上：cluster-bus.py / ccc-dispatch.py / cluster-protocol.md / capability-required test / node yaml examples / cluster-doctor.sh / abc report CONDITIONAL_PASS。
- **只改文件**：
  - `scripts/cluster-bus.py` (新建, ~150 行)
  - `scripts/ccc-dispatch.py` (新建, ~200 行)
  - `references/cluster-protocol.md` (新建, ~100 行)
  - `tests/cluster/test-capability-required.py` (新建, ~50 行)
  - `examples/cluster/m1.yaml` + `feiniu.yaml` (新建)
  - `tools/cluster-doctor.sh` (新建, ~60 行)
  - `~/program/abc/.ccc/reports/v1.0-acceptance.report.md` (修订)
- **不改文件**：所有其他文件
- **执行方式**：auto
- **Phase 数**：8 (P0-1 + P0-2 + P1-1 + P1-2 + P2-1 + P2-2 + P3-1 + P3-2)

## 改动 1: cluster-bus.py (P0-1)

### 做什么
跨设备协调中枢。监听 node 注册/心跳，提供 node 列表查询。

### 怎么做
- FastAPI 单文件应用
- POST `/api/node/register` → 内存 dict 持久化（重启丢失 OK，M1 重启 -> 重新 heartbeat 即可）
- POST `/api/node/heartbeat` → 更新 last_heartbeat + increment ping count
- GET `/api/node/list` → 列出所有 active nodes (last_heartbeat < 90s ago)
- 端口 9100 (避开 abc 8000 / claude proxy 4000 / ai-loop-router 4000)
- 用 stdlib sqlite3 持久化 (5 min checkpoint) — 抗重启
- capability declaration on register: `capabilities: [shell, git, claude-p, ollama]` L1/L2/L3 free-form

### 验收
- `python3 scripts/cluster-bus.py &` 起服务
- `curl -X POST localhost:9100/api/node/register -d '{"node_id":"m1","host":"127.0.0.1","port":9101,"capabilities":["shell","claude-p"]}'` 返回 200
- `curl -X POST localhost:9100/api/node/heartbeat -d '{"node_id":"m1"}'` 返回 200
- `curl localhost:9100/api/node/list` 返回 m1 active
- 测试超时不发心跳 → 90s 后 list 看不到

## 改动 2: ccc-dispatch.py (P0-2)

### 做什么
任务派单器。读 .ccc/plans/ + .ccc/phases/，输出三元组让人 review。

### 怎么做
- 解析 plan.md + phases.json
- 提取 "能力需求" (用什么 capability match: analyzer.py grep "skill: claude-p" 从 plan 推断)
- 调 cluster-bus.py `/api/node/list` 拿 active nodes
- 按 capability match + load score 排序
- 输出三元组:
  ```
  [dispatcher] plan=add-abc-cost-report
  [dispatcher] needed_capability=claude-p
  [dispatcher] candidates:
    - m1 @ 127.0.0.1:9101, capabilities=[shell, claude-p], load=2
    - mac2017 @ 192.168.3.116, capabilities=[shell], load=0
  [dispatcher] recommendation: m1 (capabilities match + load OK)
  [dispatcher] model_tier: sonnet (CCC Executor default)
  [dispatcher] est_cost_seconds: 600
  [dispatcher] VERDICT: ready-for-human-review (NOT auto-dispatch)
  ```
- 不开自动派单！输出后等 stdin "yes" 才发

### 验收
- 跑 dispatch dry-run 显示 5 个 candidate
- 三元组格式合法可解析
- "ready-for-human-review" 信息明示无自动派单

## 改动 3: cluster-protocol.md (P1-1)

### 做什么
协议规范文档。必含 mTLS auth (red line 19, agentmesh 教训)。

### 怎么做
- 章节：discovery / register / heartbeat / list / error_code / TLS
- mTLS 说明：自签 CA + 双向证书 (clawmed-ai 6 项目都没做，CCC 必须做)
- 错误码表：400 / 401 / 404 / 409 / 410 / 500
- API call examples (curl + python)
- 借鉴 clawmed-ai heartbeat 协议 (30s/90s)

### 验收
- 文档存在 ≥ 80 行
- 章节齐
- 错误码表 6 个

## 改动 4: test-capability-required.py (P1-2)

### 做什么
红线 18 enforcement test。cluamed-ai v3.1 失败教训——能力匹配代码被注释掉没用。

### 怎么做
- 启动 dispatcher with test mode
- 模拟"试图禁用能力匹配" → 必须 panic
- 模拟正常 task → 必须看到三元组
- pytest fixture spin up cluster-bus fixture

### 验收
- pytest 6 case pass
- 注释掉 dispatch.py 里 capability-required line 必须 raise

## 改动 5: examples/cluster yaml (P2-1)

### 做什么
node config templates。M1 + feiniu 各一份。

### 怎么做
- m1.yaml: host=127.0.0.1, port=9101, capabilities=[shell, claude-p, git]
- feiniu.yaml: host=192.168.3.131, port=9101, capabilities=[shell, ollama-bge-m3]
- 注释必填字段
- 注意 feiniu 是 ollama embedding, 不能跑 CCC executor (Lesson 5 真实数据)

### 验收
- yamllint pass
- 配置文件加载到 cluster-bus 时不报错

## 改动 6: cluster-doctor.sh (P2-2)

### 做什么
诊断工具。一条命令看集群健康。

### 怎么做
- 5 段输出：
  1. bus 服务可达性 (curl localhost:9100)
  2. 注册的 node 列表
  3. 心跳新鲜度 (last_heartbeat 距 now 多少秒)
  4. capability 矩阵 (L1/L2/L3 columns)
  5. 失败节点警告 (heartbeat > 90s 标红)

### 验收
- 运行 exit 0 表示 healthy, exit 1 表示有问题
- 输出可读彩色 (optional)

## 改动 7: abc report CONDITIONAL_PASS (P3-1)

### 做什么
Trae 三方审计 + 这次实现 = 状态变化。

### 怎么做
- 在原 `v1.0-acceptance.report.md` 顶部加 verdict 段
- 标记 7 项 CONDITIONAL items (已被这次开发 plan 覆盖)
- 留下 CONDITIONAL_PASS 而非 PASS

### 验收
- 文件 ≥ 200 行
- 三方审计 cite 可见

## 改动 8: dispatcher PoC end-to-end (P3-2)

### 做什么
真实跑 dispatcher。验证三元组。

### 怎么做
- 启动 cluster-bus 在 M1 background
- 注册 m1 + mac2017 两个 node
- 跑 ccc-dispatch dry-run
- 输出三元组 review (人工目视)
- 跑 cluster-doctor 看 health

### 验收
- 三元组打印正确
- mac2017 显示 unreachable (因为我们没真在 mac2017 跑 bus)
- doctor exit 0

## 全局验收清单

- [ ] cluster-bus.py: 6 endpoint curl PASS (3 分钟 smoke)
- [ ] ccc-dispatch.py: 三元组格式正确
- [ ] cluster-protocol.md: 80+ 行, 章节齐
- [ ] test-capability-required.py: 6 pytest pass
- [ ] m1.yaml + feiniu.yaml: yamllint pass
- [ ] cluster-doctor.sh: exit code 区分
- [ ] abc report: CONDITIONAL_PASS 标记
- [ ] PoC: dispatcher 真输出三元组

## Commit 计划

| Phase | 改动 | Commit message |
|-------|------|----------------|
| 1 | cluster-bus.py | `feat(ccc): cluster-bus.py (P0-1) — node registry + heartbeat` |
| 2 | ccc-dispatch.py | `feat(ccc): ccc-dispatch.py (P0-2) — task dispatcher + triple` |
| 3 | cluster-protocol.md | `docs(ccc): cluster-protocol.md (P1-1) — auth/TLS 规范` |
| 4 | test-capability-required.py | `test(ccc): capability-required enforcement (P1-2)` |
| 5 | yaml examples | `docs(ccc): cluster yaml examples (P2-1)` |
| 6 | cluster-doctor.sh | `feat(ccc): cluster-doctor.sh (P2-2) — 1-key diagnose` |
| 7 | abc report update | `docs(abc): v1.0 acceptance report CONDITIONAL_PASS` |
| 8 | dispatcher PoC | `docs(ccc): dispatcher PoC report (P3-2)` |

## 风险声明

- Mac2017 真在 dispatcher PoC 中不可达 — 用单 M1 双 socket 模拟两个 node
- 模型路由不稳 — 三元组**只输出不自动派单**，必须人工 review
- Plan 阶段总会改设计 — 实际行数可能与估计 ±50%

## 借鉴来源（clawmed-ai 教训）

- 6 个 agentmesh 项目共识：TCP service registration + capability-based routing
- 反借鉴清单：6 项目均无 auth → CCC 必须 mTLS
- Heartbeat 协议：30s ping / 90s timeout（参考 clawmed T1.2_worker_analysis.md）
- chunk_id 幂等性（红线 15）：commit message 含 `ccc-task-id=<id>`
