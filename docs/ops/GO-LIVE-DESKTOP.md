# CCC Desktop 上线卡

> **日期**：2026-07-22（对齐 v0.60 / 隧道默认） · **范围**：内测（未公证）  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)  
> 连接契约：[`../product/desktop-connection.md`](../product/desktop-connection.md) · 隧道：[`../product/hub-ssh-tunnel.md`](../product/hub-ssh-tunnel.md)  
> 边界基线：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

## 主入口

| 面 | 怎么用 |
|----|--------|
| **CCC Desktop** | `/Applications/CCCDesktop.app` |
| Hub（M1 **默认**） | `http://127.0.0.1:17777`（`com.ccc.hub-tunnel`） |
| Hub（2017 / 排障 LAN） | `http://192.168.3.116:7777`（**非** Desktop/sidecar 默认） |
| 对话方案 Agent | **M1 本机 sidecar `:7788` + arm64 `vendor/loop-code/cli`** |
| 远程浏览器聊 | **M1 `:7788`**（与 Desktop 同口；勿开 2017 `#/chat` 当产品路径） |
| Mac2017 编排面 | Engine = Claude→MiniMax 扇出；dev = OpenCode→讯飞写码（中转已退役） |
| 网页 Hub | **编排口 / 兼容**（`#/board` `#/ops`） |
| 意图完成口径 | `released` ≠ 完成；见 [`../product/lpsn-ship-gate.md`](../product/lpsn-ship-gate.md) |

默认账号：`ccc` / `ccc`。

## 双口远程验收（浏览器）

| URL | 用途 |
|-----|------|
| `http://192.168.3.140:7788/` | **对话口**（设置里填 M1 `~/.ccc/agent-token`） |
| `http://192.168.3.116:7777/#/board` | **编排口**（Hub Basic `ccc`/`ccc`） |

```bash
# 双口烟测（勿以 2017 为 chat origin）
CCC_AGENT=http://192.168.3.140:7788 \
CCC_SERVER=http://192.168.3.116:7777 \
  bash scripts/smoke-dual-port-remote.sh
```

断言：聊直打 M1 `/api/chat`（不经 Hub `/api/agent`）；transfer 在 2017 出 epic。  
Hub `:7777/#/chat` 会跳转对话口。详见 [`../product/hub-remote-management.md`](../product/hub-remote-management.md)。

## 架构（2026-07-19 对齐后）

```text
M1 对话面（意图工具）             信息流（仅契约）              Mac2017 编排面（队列消费）
Desktop (SwiftUI)                POST /api/desktop/transfer    Hub :7777 (API host)
Sidecar :7788 → MiniMax ─────────────────────────────────────► Board :7775
loop-code cli (arm64)  ◄── SSE flow: epic/fanout/works ────  Engine
本机 sessions 落盘                                          Claude→MiniMax · OpenCode→讯飞
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
| — | sidecar → MiniMax 直连 | plist `ANTHROPIC_BASE_URL` 含 `minimaxi.com` |
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

# 双口远程
CCC_AGENT=http://192.168.3.140:7788 CCC_SERVER=http://192.168.3.116:7777 \
  bash scripts/smoke-dual-port-remote.sh

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
