# CCC Nginx 统一入口部署与架构说明

本文档介绍 CCC（Connect-Claude Code）体系的 **Nginx 统一入口（Port 80）** 架构、部署脚本、以及日常运维和回滚指南。

---

## 一、架构设计

### 1.1 拓扑关系
在启用 Nginx 统一入口前，外部（Desktop 壳、网页、手机端）通过 `7788` 端口直连 CCC Web Server。
启用后，Nginx 监听内网 `80` 端口（或可选的 `443` HTTPS 端口），作为统一反向代理入口，将所有请求安全、高效地透传给本地的 `7788` 服务。

```
[任意客户端] ──(Port 80/443)──> [Nginx 统一入口] ──(127.0.0.1:7788)──> [CCC Web Server]
```

### 1.2 核心优化项
Nginx 作为成熟的反代服务器，为 CCC 带来了以下增强能力：
1. **长轮询与 SSE 透传**：针对 `/conversation` 路径，显式禁用 Proxy Buffering（`proxy_buffering off`），并将超时时间延长至 `300s`，保证流式 AI 对话（SSE）和长轮询即时到达。
2. **静态资源缓存**：通过正则匹配 `css|js|svg|ico|png|jpg|...` 等后缀，在 Nginx 层设置 7 天的客户端缓存头（`Cache-Control: public, max-age=604800`），极大提升网页加载速度并降低 Python 服务端负载。
3. **真实客户端信息传递**：携带 Host、X-Real-IP、X-Forwarded-For 和 X-Forwarded-Proto，保证后端能获取到真实的内网客户端 IP。
4. **统一日志审计**：所有的访问和异常均通过 `/var/log/nginx/ccc_access.log` 和 `ccc_error.log` 进行统一审计。

---

## 二、部署方式

所有的配置模板和部署脚本均存放在项目 `deploy/nginx/` 目录下：
- **配置模板**：`deploy/nginx/ccc.conf.example`
- **自动化部署脚本**：`deploy/nginx/install-nginx.sh`

### 2.1 脚本功能说明
`deploy/nginx/install-nginx.sh` 具有极高的高可用和幂等性：
1. **自动识别环境**：脚本自动适配 macOS Homebrew 环境（M1 芯片的 `/opt/homebrew/etc/nginx` 与 Intel 芯片的 `/usr/local/etc/nginx`）以及 Linux 标配环境（`/etc/nginx`）。
2. **幂等备份**：如果已存在 `ccc.conf`，脚本会在内容发生变化时，自动创建带时间戳的备份（如 `ccc.conf.bak.20260805120000`）。
3. **安全校验与自动回滚**：写入配置后，脚本会自动执行 `nginx -t` 进行语法校验。**如果校验失败，将立刻恢复先前的备份（或清除无效的新配置），绝不破坏现有的 Nginx 服务。**
4. **安全重载**：在校验通过后，执行优雅热重载（`nginx -s reload` 或 `systemctl reload nginx`），不影响现有连接。

### 2.2 部署步骤
由于红线硬规则要求，**本卡只产模板与脚本，不自动安装到生产环境**。安装需要 Codex 验收放行后，由管理员在目标机器上手动执行：

```bash
# 1. 切换到项目 deploy/nginx 目录
cd deploy/nginx/

# 2. 赋予可执行权限并运行（需要管理员权限以写入配置和重载服务）
sudo ./install-nginx.sh
```

---

## 三、验证方案

部署完成后，请依次检验以下指标：

1. **基本访问验证**：
   - 浏览器打开 `http://192.168.3.116/`（80 端口），确认页面正常加载，功能与访问 `:7788` 端口完全一致。
   - 确认看板、线路图、免登录状态或登录门渲染正常。

2. **流式与长轮询验证**：
   - 在对话框输入一条 prompt，观察流式（SSE）消息是否逐字返回。如果是一次性蹦出大段，说明 `proxy_buffering off` 未生效。
   - 打开浏览器开发者工具（F12）的网络面板（Network），检查 `GET /conversation` 长轮询请求，确认无断连重连噪音，请求最长挂起 `30s`（或依 `CCC_WEB_LONGPOLL_TIMEOUT` 配置）后正常返回。

3. **静态缓存验证**：
   - 在开发者工具中刷新页面，检查 `app.js` 或 css 文件的 Response Headers，确认 `Cache-Control` 包含 `max-age=604800`，且 Nginx 正确返回了缓存标识。

---

## 四、回滚与完全移除指南

如果反代遇到非预期瓶颈或需要紧急下线，Nginx 架构支持 **分钟级完全无损回滚**。直接移除配置并重载 Nginx，即可完美恢复 7788 直连：

1. **删除配置文件**：
   ```bash
   # macOS 示例
   sudo rm -f /usr/local/etc/nginx/servers/ccc.conf
   # 或 Linux 示例
   sudo rm -f /etc/nginx/sites-enabled/ccc.conf /etc/nginx/sites-available/ccc.conf
   ```

2. **语法校验**：
   ```bash
   sudo nginx -t
   ```

3. **重新载入 Nginx 以释放 80 端口**：
   ```bash
   sudo nginx -s reload
   ```

此时 Port 80 对应路径将不再转发，客户端直接请求 `http://192.168.3.116:7788/` 即可正常直连使用。
