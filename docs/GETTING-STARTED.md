# Getting Started — CCC Hub + Loop Engineer

> 目标：陌生人 **10 分钟内**打开 Hub，走通「对齐 → 定稿 → 转任务」。  
> 叙事见 [`VISION.md`](VISION.md)。端口权威：[`ccc-hub-ports.md`](ccc-hub-ports.md)。

---

## 0. 你将得到什么

- 浏览器里的 **CCC Hub**（对话 + 看板 + 控制台）  
- 可选的 **Engine**（队列消费者：自动编排开发 / 验收）  
- 默认 **不**自动常驻、**不**自造任务（控制面 `disabled`）

---

## 1. 环境

- macOS（当前一等公民；launchd 安装脚本按 macOS 编写）  
- Python 3.10+（`python3`）  
- 建议：本机已能跑 Claude / OpenCode（执行面）；仅体验 Hub UI 可不装执行器  

```bash
git clone https://github.com/hanrry2323/CCC.git
cd CCC
python3 --version
```

---

## 2. 启动 Hub（入口）

```bash
# Board API（本机 7775）
bash scripts/install-board-plist.sh --start

# Hub UI（0.0.0.0:7777）
bash scripts/install-hub-plist.sh --start
```

浏览器打开：**http://127.0.0.1:7777**  
登录：**用户名 `ccc` / 密码 `ccc`**（可用环境变量覆盖，见 `ccc-hub-ports.md`）

前台开发（不碰 launchd）：

```bash
bash scripts/ccc-hub-dev.sh
```

---

## 3. 第一条闭环（只用人，不强制 Engine）

在 Hub「对话」页：

1. 选好项目（侧栏）  
2. 点 **对齐基线** → 再点 **下一步**（可选）  
3. 点 **定稿方案**，确认助手输出 `CCC_DISPATCH` 块  
4. 点 **转任务** → 核对标题 → 可选 Skill 软偏好 → **下达并开工**  
5. 打开 **看板**，应看到新任务；若已挂 plan/phases，可跳过 product 拆解  

此时若控制面仍是 `disabled` / `ui`，任务会落在板上，**不会**自动被 Engine 吃掉——这是刻意的安全默认。

---

## 4. 打开自动编排（显式）

只消费已有队列（推荐日常）：

```bash
bash scripts/ccc-autostart-guard.sh enable --start
bash scripts/ccc-autostart-guard.sh status
```

允许系统自造 / 进化类任务（须你明确需要）：

```bash
bash scripts/ccc-autostart-guard.sh invent --start
```

关闭：

```bash
bash scripts/ccc-autostart-guard.sh disable
```

详见 [`CONTROL.md`](CONTROL.md)。

---

## 5. 接入新项目（已有仓 / 空仓）

权威：[`workspace-binding.md`](workspace-binding.md)

```bash
mkdir -p ~/program/myapp   # 若全新
python3 scripts/ccc-init.py ~/program/myapp --register
# 编辑 ~/program/myapp/CLAUDE.md 后，在 Hub 选该项目即可对话 / 转任务
```

路径须在 `~/program/` 下；`ccc-init` 会建七列看板 + 种子 CLAUDE.md。

---

## 6. 验证安装

```bash
# Hub 是否在听
curl -s -o /dev/null -w '%{http_code}\n' -u ccc:ccc http://127.0.0.1:7777/

# 控制面
python3 -c "import sys;sys.path.insert(0,'scripts');from _ccc_control import get_mode;print(get_mode())"

# 失败账本（若跑过任务）
python3 scripts/ccc-failure-report.py --last 5
```

---

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| 手机整页要滑才能见输入框 | 硬刷新 Hub；≥ v0.42.1 已用 fixed+dvh 锁视口 |
| 下达后任务不动 | 控制面是否 `enable`？Board/Engine 是否在跑？看控制台与 `docs/observability.md` |
| Hub 选不到新项目 | 是否有 `.ccc/board`？是否在 `~/program/`？见 [`workspace-binding.md`](workspace-binding.md) |
| 对话串到别的仓 | 确认侧栏选中的项目；Agent cwd = 该项目根 |
| 登录失败 | 确认 `CCC_CHAT_USER` / `CCC_CHAT_PASS`；默认 `ccc`/`ccc` |
| 端口冲突 | 见 `ccc-hub-ports.md`；勿再开废弃 8084 |

更多：[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

---

## 8. 下一步读什么

| 你是… | 读 |
|-------|-----|
| 想理解「为什么不是角色超市」 | [`VISION.md`](VISION.md) |
| 多项目绑定 / 新项目接入 | [`workspace-binding.md`](workspace-binding.md) |
| 日常怎么用 | [`USAGE.md`](USAGE.md) |
| Agent 改本仓库 | [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) |
| 贡献代码 | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
