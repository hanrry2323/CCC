# CCC Desktop LAN 上线卡

> **日期**：2026-07-19 · **范围**：LAN 内测（未公证）  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)

## 主入口

| 面 | 怎么用 |
|----|--------|
| **CCC Desktop** | 本机 `/Applications/CCCDesktop.app`（或 `desktop/.build/CCCDesktop.app`） |
| Server | `http://192.168.3.116:7777`（Mac2017 Hub） |
| 网页 Hub | **运维/兼容**；看板/运维深链仍可从 Desktop 打开浏览器 |

默认账号：`ccc` / `ccc`。

## 每天这样用

```text
1. 打开 CCC Desktop（设置里 Server = http://192.168.3.116:7777）
2. 选业务项目（如 ccc-demo；不要选编排仓）
3. 对话定稿 → 转任务 → 右栏看编排
4. 看板/运维需要时点侧栏（浏览器）
```

## 2026-07-19 验收记录

| # | 项 | 结果 |
|---|-----|------|
| 1 | M1 → `:7777` `/api/desktop/config` | OK |
| 2 | 2017 代码 | `fff2aed`（bundle 同步 + Hub/Engine kickstart） |
| 3 | `CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-e2e.sh` | **PASS** |
| 4 | 转任务验收 epic | `desktop-golive-395202` |
| 5 | `engine_wake.ok` | true（mode=enabled, launchd） |
| 6 | flow snapshot 扇出 | `desktop-golive-395202-w1`（planned / 脚本） |
| 7 | Desktop 进程 | `swift run CCCDesktop` 已起 |
| 8 | `.app` | 版本对齐 `VERSION` → `/Applications/CCCDesktop.app` |

## 常用命令

```bash
# 冒烟（在 CCC 仓根）
cd ~/program/CCC
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-e2e.sh

# 打包并安装到 Applications
bash desktop/scripts/package-baseline.sh
rm -rf /Applications/CCCDesktop.app
cp -R desktop/.build/CCCDesktop.app /Applications/

# 2017 重启 Hub（SSH fan@192.168.3.116）
launchctl kickstart -k gui/$(id -u)/com.ccc.chat-server
launchctl kickstart -k gui/$(id -u)/com.ccc.engine
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
