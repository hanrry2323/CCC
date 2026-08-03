# 任务卡 T28 · 桌面端重构后重新打包安装 + 可用性验证（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 壳零业务逻辑）· 依据：老板 2026-08-03 询问「新版本有没有编译，桌面端能用吗」；Codex 核实结论：**源码已重构编译通过，但 /Applications/CCCDesktop.app 仍是 8-3 02:01 旧包（T24 代码），未重新打包安装**· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 目标

用当前 main（含 T26/T26-R 重构后代码）**重新打包安装** `/Applications/CCCDesktop.app`，默认对接 `http://192.168.3.116:7788`（2017 新服务端），并实测 App 可用（启动 / 登录 / 对话 / 看板 / 运维）。

## 红线（先看）

1. **打包必须用当前 main 源码**（HEAD `0ccd011` 含 T26 重构 + T26-R 清理），禁止用旧 build 缓存；版本读仓内 `VERSION`。
2. **安装前备份旧包**：`mv /Applications/CCCDesktop.app ~/.ccc/backup-CCCDesktop-20260803-before-T28.app`（可回滚）。
3. 默认配置指向新服务端：`ccc.newServerURL=http://192.168.3.116:7788`、账号 `ccc`/密码 `ccc`；旧 Hub 相关 AppStorage（`ccc.server`/`ccc.agent` 等）不写入或置空。
4. 不动：`server/`、2017 各服务、M1 中转站 4100/4102、2017 中转站 6100/6102、engine/board-scheduler；不读写外脑。
5. 完成必须提交（如有仓内改动，如 VERSION/打包脚本）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 步骤

### A. 打包（M1）

1. 确认源码最新：`git log --oneline -1` = `0ccd011`（或更新）。
2. `cd desktop && swift build -c release`（先验证 release 构建零错误）。
3. 备份旧包：`mv /Applications/CCCDesktop.app ~/.ccc/backup-CCCDesktop-20260803-before-T28.app`（如不存在）。
4. 打包安装：`bash scripts/package-baseline.sh` → `cp -R desktop/.build/CCCDesktop.app /Applications/`。
5. 确认：`/Applications/CCCDesktop.app` 构建时间 = 今天、版本 = `VERSION`（v0.66.1 或更新）。

### B. 写默认配置（M1）

6. `defaults write com.ccc.desktop "ccc.newServerURL" -string "http://192.168.3.116:7788"`
7. `defaults write com.ccc.desktop "ccc.newServerUser" -string "ccc"`
8. `defaults write com.ccc.desktop "ccc.newServerPass" -string "ccc"`
9. 清理旧 Hub 配置（可选）：`defaults delete com.ccc.desktop "ccc.server"` / `"ccc.agent"`（若存在，避免误导）。

### C. 启动 + 可用性实测（M1）

10. `open /Applications/CCCDesktop.app` → 确认进程在、窗口正常、无崩溃（`ps` + 系统日志无 fatal）。
11. 连接：App 启动后项目列表出现（INT-120/CCC，来自 `/board/summaries` 派生）、连接状态正常、无「Hub 不可达」误判。
12. 对话：登录（ccc/ccc）→ 发送消息 → `/conversation` 真实回复（经 2017 6102 flash）。
13. 看板：`/board/snapshot` 渲染；运维：`/ops/summary` 显示。
14. 无旧协议请求：App 运行日志无 `/api/*` 404、无 17777 连接尝试（如可观察）。

### D. 验证 + 提交

15. 若打包脚本/VERSION 有改动 → 真实提交并 push。
16. 回写：卡头 `状态：待分派 → 已回写`，回写区填（打包时间/版本、安装路径、默认配置、启动/登录/对话/看板/运维实测输出、验收自检表）。

## 回滚

- `mv ~/.ccc/backup-CCCDesktop-20260803-before-T28.app /Applications/CCCDesktop.app`（恢复旧包）。
- 触发条件：release 构建失败 / App 启动崩溃 / 登录/对话/看板任一不可用 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `/Applications/CCCDesktop.app` 为新包（构建时间今天、版本 v0.66.1 或更新）；旧包有备份。
2. 默认配置指向 `http://192.168.3.116:7788`（ccc/ccc）。
3. App 启动正常：项目列表有值、连接正常、无「Hub 不可达」；对话/看板/运维实测可用。
4. 无旧协议请求（无 17777、无 `/api/*` 404）。
5. 真实提交（如有改动）；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–D 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
