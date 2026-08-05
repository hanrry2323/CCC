# 任务卡 T63 · Nginx 统一入口（Claude Code 执行）

> 关联：阶段 3（Nginx 统一入口）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t63 -b codex/t63-nginx-entry origin/main`，在其中工作；分支 `codex/t63-nginx-entry`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

2017 Nginx 统一入口：内网 80 反代 7788（web-server），路径收敛 + 访问日志 + 静态缓存；可配置 TLS/域名（先内网 80）。

## 具体项

1. **Nginx 配置模板**：`deploy/nginx/ccc.conf.example`——server 80 → proxy_pass 127.0.0.1:7788；路径全部透传（/conversation /board/* /projects /cards /config 等）；长轮询/SSE 连接不超时（proxy_read_timeout 300s、buffering off）；访问日志 + 静态缓存（css/js 缓存头）。
2. **部署脚本**：`deploy/nginx/install-nginx.sh`——备份现有配置、写入 ccc.conf、nginx -t 校验、reload；幂等。
3. **验证**：安装后 `http://192.168.3.116/`（80）与 `:7788` 行为一致（免登录/对话/看板/线路图/后台进程）；SSE 流式经 80 正常。
4. 可选：TLS 自签 + `ccc.lan` 域名说明（注释内给出，不默认启用）。

## 红线

1. 只加 deploy/nginx/ + docs/；**不自动安装到生产**（本卡只产模板与脚本；2017 安装由 Codex 验收后放行）。
2. 不改变 web-server 本身；80 反代失败必须能快速回退（nginx 配置可整体移除恢复 7788 直连）。
3. 回写前 push 成功并附证据。

## 验收标准

1. 配置模板与脚本完整（nginx -t 通过、幂等、含回滚说明）。
2. 在 M1 本地或 2017 验证（Codex 放行后）：80 → 7788 全链路可用（含 SSE 流式）。
3. 无破坏性：移除 nginx 后 7788 直连正常。
4. push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：模板/脚本、验证记录（80 与 7788 对照、SSE 经 80）、回滚说明、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
