# 方案 · 运行方式重建（M2-2.3）

> 项目：xy · 编号：xy-plan-004 · 状态：部分执行 · 作者：Claude（中枢） · 工具：Claude Code
> 批准：老板确认转卡 · 2026-08-17
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：xy049, xy050, xy051
> 关联方案：无
> 进度：1/3 (33%)
> 里程碑：M2 · 生产就绪
> 子项目：2.3 运行方式重建
> 环境准备：mac2017 xianyu 业务仓可写；可创建 launchd plist（`~/Library/LaunchAgents/`）

## 目标

重建 xy 的常驻运行方式——admin 台（8765+8080）与 worker 池可拉起、可守护、可观测，并让 `ARCHITECTURE.md` 的部署描述与实际一致。

## 背景

债务清理删除了 30 个失效 launchd plist（路径漂移 + 生产停摆），但**没有重建运行方式**——当前 xy 没有任何守护，只能手动 `admin/start.sh` 或 `python -m xianyu` 临时跑。`ARCHITECTURE.md` 仍写 deploy/launchd/，与实际不符。没有常驻运行，生产就绪无从谈起。

## 方案内容

按「可运行、可守护、文档一致」三块：

1. **admin 台拉起**：`bash admin/start.sh` 一键起 8765（admin API）+ 8080（静态页）可用；确认 Basic Auth 与 CORS 正常。
2. **worker 池守护**：`python -m xianyu`（worker pool 常驻）以 launchd 方式拉起（新 plist，含正确路径/环境变量/日志），或按现状选择 manual 方式并文档化。注意：调度由 openclaw cron 接管（K5 不造轮子），worker 池是执行侧。
3. **部署文档对齐**：`ARCHITECTURE.md` deploy 段重写，与「清理后 + 重建后」的真实运行方式一致（哪些 launchd、哪些 manual、路径/日志位置）。

## 验收标准

- [ ] `bash admin/start.sh` 后 admin 8765 可访问（Basic Auth 登录成功）、8080 静态页可打开
- [ ] worker 池可常驻运行（launchd 拉起或文档化的 manual 方式），日志可观测
- [ ] `ARCHITECTURE.md` 部署段与实际运行方式一致（无残留「deploy/launchd/ 已删」的描述）
- [ ] 不引入新轮子（K5 红线：不写调度器，用 openclaw cron）

## 功能卡

### admin台拉起

目标：admin 台（8765+8080）一键可起，作为 xy 的运营可视入口。

实现：验证并完善 `admin/start.sh`（8765 admin API + 8080 静态页）；确认 Basic Auth（`admin/api/server.py`）与 CORS；补启动后自检（curl /health 200）。

验收：`bash admin/start.sh` 后 8765 与 8080 均可访问。

颗粒度：脚本验证 + 可能的启动自检补全，单模块。

依赖：无

架构位置：admin 台（xy 运营可视层）

### worker池守护

目标：worker 池（`python -m xianyu`）可常驻运行并守护。

实现：按现状选择守护方式（launchd 新 plist 或 manual + 文档化）；plist 含正确 `WorkingDirectory`（`/Users/fan/program/apps/xianyu`）、`.venv` python 路径、日志路径；启动后确认进程存活。

验收：worker 池常驻，进程稳定（30 分钟无退出），日志有产出。

颗粒度：守护配置 + 验证，单模块。

依赖：无

架构位置：worker 执行层（内容生产 Worker 池）

### 部署文档对齐

目标：`ARCHITECTURE.md` 部署段与真实运行方式一致。

实现：按重建后的 admin/worker 运行方式重写 `ARCHITECTURE.md` 的 deploy/launchd 描述；删除「deploy/launchd/」残留引用；标注哪些是 launchd、哪些 manual。

验收：文档与实际运行方式逐项一致，无过时引用。

颗粒度：文档修正，单文件。

依赖：admin台拉起, worker池守护

架构位置：文档层（架构描述）

## 转卡计划

admin 台拉起 / worker 池守护 / 部署文档对齐

## 备注

- K5 红线：不写调度器（openclaw cron 管调度）、不写自建守护框架（用系统 launchd）——本方案只重建运行方式，不引入新轮子。
- 若 launchd 重建与「生产停摆」判断冲突（老板此前定生产下线），本方案默认「可运行、可守护」，是否正式调度由后续另行立项。
