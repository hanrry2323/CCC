# CCC Desktop LAN 上线卡

> **日期**：2026-07-19 · **范围**：LAN 内测（未公证）  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)  
> 连接契约：[`../product/desktop-connection.md`](../product/desktop-connection.md)

## 主入口

| 面 | 怎么用 |
|----|--------|
| **CCC Desktop** | `/Applications/CCCDesktop.app`（v0.51.0） |
| Server | `http://192.168.3.116:7777`（Mac2017 Hub） |
| 方案 Agent | **loop-code**（`CCC_EXECUTOR=loop-code` → `vendor/loop-code/cli`，x86_64） |
| 网页 Hub | **运维/兼容**；看板/运维深链仍可从 Desktop 打开浏览器 |

默认账号：`ccc` / `ccc`。

## 每天这样用

```text
1. 打开 CCC Desktop（Server = http://192.168.3.116:7777）
   — 自动探测/拉起本机 sidecar；状态栏看「本机 Agent」或「本机 Agent 未就绪」（禁止 Hub 聊天回退）
2. 设置里为 ccc-demo 填「当前项目本机路径」（若本机有 checkout）
3. 选业务项目 → 本机对话定稿 → 转任务（需 Hub）→ 右栏看编排
4. 看板/运维需要时点侧栏（浏览器）
```

## ~80% 产品完整度清单

| # | 项 | 期望 |
|---|-----|------|
| 1 | Sidecar 自启 | 杀 :7788 后开 App → 徽章「本机 Agent」 |
| 2 | 工具轨持久 | 有 tool 的会话重开后仍见芯片 |
| 3 | 多路 | sidecar 下两会话可并行生成 |
| 4 | 工作区 | 项目本机路径生效（设置 / map） |
| 5 | 未就绪明示 | sidecar 起不来 →「本机 Agent 未就绪」+ toast；**不**回退 Hub `/api/chat` |

## GO-LIVE 95+ 清单（本阶段）

| # | 维度 | 期望 | 出门标准 |
|---|------|------|----------|
| A | 对话稳态 | sidecar 优先、SSE 自愈 1 次、flow 不因聊天停 | `smoke-desktop-stable.sh` |
| B | 任务规划 | `ccc-transfer` → 一键确认条；样例门禁 ≥90% | `test_ccc_transfer_samples.py` 10/10 |
| C | 拆分动画 | 转任务后 ≤15s 见 epic→works 生长；失败白话 | 人工/录屏 + fanout JSONL |
| D | 事件推送 | fanout/work_status 写 JSONL；看板轮询 ≥8s | Hub `flow/events` + `_product_fanout` |

自评目标：**≥95/100**（规划 / 对话 / 动画 各 ≥9.5）。

## 2026-07-19 验收记录（门禁重签）

| # | 项 | 结果 | 证据 |
|---|-----|------|------|
| 1 | Hub `:7777` `/api/desktop/config` | **PASS** | `agent_runtime=loop-code`，`agent_cli=.../vendor/loop-code/cli` |
| 2 | 方案 Agent = loop-code（plist） | **PASS** | `CCC_EXECUTOR=loop-code`；cli 为 **x86_64**（非 arm64） |
| 3 | `smoke-desktop-agent.sh` | **PASS** | 完整 SSE，`done.partial=false`，正文「代理OK」 |
| 4 | `smoke-executor-stack.sh`（缺 vendor 则 FAIL） | **PASS** | loop-code resolve 硬断言 |
| 5 | `smoke-desktop-e2e.sh` | **PASS** | config+gate+transfer+snapshot；含 loop-code 断言 |
| 6 | `desktop/scripts/smoke-ui-chat.sh` | **PASS** | assistant=`自检OK` |
| 7 | pytest desktop API / transfer-gate | **PASS** | 14 passed |
| 8 | `.app` 安装 | **PASS** | `/Applications/CCCDesktop.app` version **0.51.0**（边界收口后重装同版） |
| 9 | Hub 稳定性补丁 | **PASS** | projects TTL/`to_thread`；chat `is_disconnected`+`partial` |

## 2026-07-19 95+ 证据重签

| # | 项 | 结果 | 证据 |
|---|-----|------|------|
| 10 | `test_ccc_transfer_samples.py` | **PASS** | 10/10 门禁过（本地定稿协议） |
| 11 | hub_voice 含 `ccc-transfer` 约定 | **PASS** | `hub_voice.py` 定稿块例外 |
| 12 | flow SSE 推送优先 | **PASS** | `desktop.py` JSONL `after_ts` + 8s 看板兜底 |
| 13 | fanout 写 `project_id` | **PASS** | `_product_fanout.append_event` |
| 14 | Desktop 拆分动画 + 确认条 | **PASS** | `FlowCanvasView` / `TransferDraftParser` / 确认条 |
| 15 | `smoke-desktop-stable.sh` | **PASS** | sidecar health/route + 定稿样例 10/10；Hub 项在 Server 可达时跑（本机取证时 Hub LAN 曾 SKIP） |

## Cursor 感性能（2026-07-19）

| # | 项 | 结果 | 证据 |
|---|-----|------|------|
| 16 | 本机会话 SSOT | **PASS** | `LocalSessionStore` → Application Support；Hub PUT 重试 |
| 17 | 连接态解耦 | **PASS** | `canChat`≠`hubReachable`；「Hub 暂不可达（可聊）」 |
| 18 | sidecar `/warm` | **PASS** | `POST /warm` + Desktop 240s / 发送前 120s |
| 19 | `prompt_mode=light` | **PASS** | `hub_voice` + sidecar；定稿强制 full |
| 20 | TTFB 备注 | 现场 | `bash scripts/spike-loopcode-ttfb.sh`（热路径目标 ≤1s） |
| 21 | sidecar launchd KeepAlive | **PASS** | `com.ccc.agent-sidecar`；kill -9 后自动复活 |

## 对话面 / 编排面边界（2026-07-19 全面收口）

契约：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

| # | 断言 | 结果 | 证据 |
|---|------|------|------|
| B1 | Hub 断仍可本机聊；不能转任务有白话 | **PASS** | Desktop `canChat`/`canTransfer`；无 Hub chat fallback |
| B2 | 转任务 → 2017 backlog epic；右栏见拆分 | **PASS** | `boundary-e2e-120005-cc76d1c5` → 3 works；flow snapshot |
| B3 | Engine cwd = 2017 业务仓 | **PASS** | `/Users/fan/program/apps/ccc-demo`；product-session `--workspace` 同路径 |
| B4 | 闲聊全文不进 product/dev（仅 gate/plan） | **PASS** | Engine/board roles 无 `.ccc/chat` 读取；transfer 只带 gate 字段 |
| B5 | 常态无 Desktop→Hub `/api/chat` | **PASS** | `APIClient.streamChat` 无 sidecar 直接抛错；`smoke-desktop-stable` 源码门禁 |
| — | PUT messages = 备份 | **PASS** | 响应 `role=backup`；Engine 不读 |
| — | sidecar Router → 2017 `:4000` | **PASS** | `health.router` 含 `192.168.3.116:4000` |
| — | 2017 Engine `enabled` | **PASS** | `ccc-autostart-guard.sh enable --start`；`mode=enabled` |

```bash
bash scripts/install-agent-sidecar-plist.sh --start
bash scripts/ccc-agent-sidecar.sh status
```

基线取证目录：`.ccc/dockets/ssot-mature-20260719-031420/`。

## 常用命令

```bash
cd ~/program/CCC

# 方案 Agent + 完整 chat
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh

# 转任务 / flow
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-e2e.sh

# 95+ 稳态 + 定稿样例
bash scripts/smoke-desktop-stable.sh
python3 scripts/tests/test_ccc_transfer_samples.py

# Desktop UI
CCC_SERVER=http://192.168.3.116:7777 bash desktop/scripts/smoke-ui-chat.sh

# 打包安装
bash desktop/scripts/package-baseline.sh
rm -rf /Applications/CCCDesktop.app
cp -R desktop/.build/CCCDesktop.app /Applications/
bash desktop/scripts/open-desktop.sh

# 2017 重装 Hub plist（含 CCC_EXECUTOR=loop-code）
# 注意：install-hub --start 可能把 control 置回 ui；装完后务必再 enable Engine
ssh fan@192.168.3.116 'bash /Users/fan/program/CCC/scripts/install-hub-plist.sh --start'
ssh fan@192.168.3.116 'bash /Users/fan/program/CCC/scripts/ccc-autostart-guard.sh enable --start'
# Intel 机必须装 arch 匹配的 cli：
# bash scripts/install-executor-loop-code.sh /path/to/x86_64-claude-compatible-cli
```

## 右栏与对话绑定（逻辑）

```text
左侧选中对话 (thread)
  → 仅加载该 thread 转出的 epic
  → 右栏显示「本对话编排」
  → 转任务时写入 thread_id，深度绑定
新对话 / 未转任务 → 右栏空态提示
```

## 已知限制

- 未 codesign / notarize（Gatekeeper 可能需右键打开一次）
- 账号体系预留
- **看板 / 运维下一版内嵌 Desktop**（本轮仍开浏览器）
- Engine product 自动扇出偶发失败时，右栏可能短暂「待拆解」
- Mac2017（x86_64）上 `vendor/loop-code/cli` 必须为 **同架构** Claude 兼容二进制；arm64 会 Errno 86
