# 任务卡 mx004 · service health probe integration（OpenCode 执行）

> 关联：ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

medio-0 现网健康巡检落地：承接 mx002 的 `/api/v1/health` 接口，在 medio-0 仓新增/增强健康巡检脚本（curl 探活 + 退出码 + 告警），支持手动运行与定时接线，补上 medio-0 服务监控盲区（对齐 hp002 模式）；qx-map 侧接入留后续人工项，不在本卡。

## 红线（先看）

1. **只动白名单**：`scripts/` 下健康巡检脚本（若已有类似脚本则增强，不新建重复）、medio-0 仓监控/部署相关文档 ≤1 篇、`deploy-package/` 部署脚本（仅当需接线定时巡检）。
2. **禁止**修改任何业务 API 逻辑、数据库表结构、`config.toml`/`config-test.toml` 运行配置；禁止 `cargo build`/`npm install`/装包。
3. 人为停服自测**必须还原**服务并记录证据（回写区写清自测过程 + 还原结果）。
4. qx-map（M1 `/Users/apple/qx-map`）非 CCC 出卡面：探活结论只落 medio-0 仓，qx-map 侧同步留人工项。
5. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/` 下健康巡检脚本（新增或增强；参考既有 `scripts/test_api_smoke.py` 的调用方式与端口约定）
- medio-0 仓监控/部署相关文档 ≤1 篇（写清探针清单、运行方式、告警行为）
- `deploy-package/`（如需接线定时巡检，如 `medio-server.service` 或 start.sh 只读确认端口与启动方式）
- 本卡在 CCC 仓回写区

## 步骤

1. 侦察现状：`cd /Users/fan/program/apps/medio-0`，只读确认服务启动方式与端口（`deploy-package/start.sh`、`deploy-package/medio-server.service`、`config.toml` 端口字段）；确认 `scripts/` 下是否已有健康巡检/监控类脚本（有则增强，无则新建）。
2. 实现健康巡检脚本（如 `scripts/health_probe.sh`）：`curl -fsS http://127.0.0.1:<port>/api/v1/health` 校验 `{"status":"ok"}` 且 version 非空；正常退出码 0 并输出 health 状态，异常退出码 1 并输出原因（沿用 hp002 的 osascript 告警模式，若 medio-0 无先例可省）。
3. 手动运行验证（真实服务进程）：
   - 服务正常：脚本输出 `health ok`（含 version）且退出码 0。
   - 人为停服自测：kill medio-server 后脚本能检出异常（退出码非 0）；**自测后立即还原服务**（重启并确认 `/api/v1/health` 恢复 200），回写区记录全过程与还原证据。
4. 文档 ≤1 篇：写清探针清单、运行方式（手动命令 / 可选 cron 或 launchd 接线）、告警行为、退出码约定。
5. 探针自检：`git -C /Users/fan/program/apps/medio-0 status -sb` 只含白名单改动、无残留进程；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 健康巡检脚本实测通过：medio-server 正常时退出码 0 且输出含 /api/v1/health 状态；人为停服自测能检出异常（自测后必须还原），回写区记录过程
2. 运行方式（手动/定时）与告警行为写进 medio-0 仓文档 ≤1 篇
3. 只动白名单文件；业务 API / 数据库表结构零改动；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
