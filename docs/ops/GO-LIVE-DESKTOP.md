# CCC Desktop LAN 上线卡

> **日期**：2026-07-19（架构对齐版） · **范围**：LAN 内测（未公证）  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)  
> 连接契约：[`../product/desktop-connection.md`](../product/desktop-connection.md)  
> 边界基线：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

## 主入口

| 面 | 怎么用 |
|----|--------|
| **CCC Desktop** | `/Applications/CCCDesktop.app`（v0.51.0） |
| Server | `http://192.168.3.116:7777`（Mac2017 Hub，API host） |
| 对话方案 Agent | **M1 本机 sidecar `:7788` + arm64 `vendor/loop-code/cli`**（M1 深度整合为对话意图工具） |
| Mac2017 编排面 | Engine = Claude Code 扇出；dev = OpenCode 写码；Router `:4000/:4002` |
| 网页 Hub | **运维/兼容**（看板/运维已迁入 Desktop，见 [../deprecate-web-board-ops.md](../deprecate-web-board-ops.md)） |

默认账号：`ccc` / `ccc`。

## 架构（2026-07-19 对齐后）

```text
M1 对话面（意图工具）             信息流（仅契约）              Mac2017 编排面（队列消费）
Desktop (SwiftUI)                POST /api/desktop/transfer    Hub :7777 (API host)
Sidecar :7788         ──────────────────────────────────────► Board :7775
loop-code cli (arm64)  ◄── SSE flow: epic/fanout/works ────  Engine (Claude Code 扇出)
本机 sessions 落盘                                          OpenCode (dev 写码) → Router :4000/4002
```

**关键变化**：M1 = 对话脑（Desktop+loop-code 深度整合）；Mac2017 = 纯编排消费队列。  
**不再**：2017 部署 loop-code 二进制作 Hub 方案 Agent；Hub `/api/chat` 路由已删。

## 每天这样用

```text
1. 打开 CCC Desktop（Server = http://192.168.3.116:7777）
   — 自动探测/拉起本机 sidecar；状态栏看「本机 Agent」或「本机 Agent 未就绪」（禁止 Hub 聊天回退）
2. 设置里为业务项目填「当前项目本机路径」（若本机有 checkout）
3. 选业务项目 → 本机对话定稿 → 转任务（需 Hub）→ 右栏看编排实时回传
4. 看板/运维：Desktop 侧栏直接进（不再开浏览器）
```

## ~80% 产品完整度清单

| # | 项 | 期望 |
|---|-----|------|
| 1 | Sidecar 自启 | 杀 :7788 后开 App → 徽章「本机 Agent」 |
| 2 | 工具轨持久 | 有 tool 的会话重开后仍见芯片 |
| 3 | 多路 | sidecar 下两会话可并行生成 |
| 4 | 工作区 | 项目本机路径生效（设置 / map） |
| 5 | 未就绪明示 | sidecar 起不来 →「本机 Agent 未就绪」+ toast；**不**回退 Hub `/api/chat` |

## 边界断言（基线）

契约：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

| # | 断言 | 验证 |
|---|------|------|
| B1 | Hub 断仍可本机聊；不能转任务有白话 | Desktop `canChat`/`canTransfer`；无 Hub chat fallback |
| B2 | 转任务 → 2017 backlog epic；右栏见拆分 | `flow/snapshot` + `flow/events` SSE |
| B3 | Engine cwd = 2017 业务仓 | `/Users/fan/program/apps/<id>`；product-session `--workspace` 同路径 |
| B4 | 闲聊全文不进 product/dev（仅 gate/plan） | Engine/board roles 无 `.ccc/chat` 读取；transfer 只带 gate 字段 |
| B5 | 常态无 Desktop→Hub `/api/chat` | Hub `/api/chat` 路由已删（404）；`APIClient.streamChat` 走 sidecar |
| — | PUT messages = 备份 | 响应 `role=backup`；Engine 不读 |
| — | sidecar Router → 2017 `:4000` | `health.router` 含 `192.168.3.116:4000` |
| — | 2017 Engine `enabled` | `ccc-autostart-guard.sh enable --start`；`mode=enabled` |

## 常用命令

```bash
cd ~/program/CCC

# 本机 sidecar（对话热路径）
bash scripts/install-agent-sidecar-plist.sh --start
bash scripts/ccc-agent-sidecar.sh status

# 端到端
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-e2e.sh
bash scripts/smoke-desktop-stable.sh
python3 scripts/tests/test_ccc_transfer_samples.py

# Desktop UI
CCC_SERVER=http://192.168.3.116:7777 bash desktop/scripts/smoke-ui-chat.sh

# 打包安装
bash desktop/scripts/package-baseline.sh
rm -rf /Applications/CCCDesktop.app
cp -R desktop/.build/CCCDesktop.app /Applications/
bash desktop/scripts/open-desktop.sh

# 2017 重装 Hub plist（不再写 CCC_EXECUTOR；Hub /api/chat 已删）
ssh fan@192.168.3.116 'bash /Users/fan/program/CCC/scripts/install-hub-plist.sh --start'
# 装完后务必再 enable Engine（install-hub --start 可能把 control 置回 ui）
ssh fan@192.168.3.116 'bash /Users/fan/program/CCC/scripts/ccc-autostart-guard.sh enable --start'
```

## 右栏与对话绑定（逻辑）

```text
左侧选中对话 (thread)
  → 仅加载该 thread 转出的 epic
  → 右栏显示「本对话编排」（实时 SSE）
  → 转任务时写入 thread_id，深度绑定
新对话 / 未转任务 → 右栏空态提示
```

## 已知限制

- 未 codesign / notarize（Gatekeeper 可能需右键打开一次）
- 账号体系预留
- 看板/运维已内嵌 Desktop（W2-W3 完成）；网页 `#/board` `#/ops` 重定向到提示
- Engine product 自动扇出偶发失败时，右栏可能短暂「待拆解」
- **M1 必须装 arm64 `vendor/loop-code/cli`**；Mac2017 不再需要 loop-code 二进制
