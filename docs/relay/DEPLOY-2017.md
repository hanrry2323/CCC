# CCC Relay · 2017 部署 Runbook（已废弃）

> **该文档已废弃**（2026-08-01）。  
> **原因**：CCC 仓内 `relay/` 已拆出，Mac2017 不再运行 relay 实例。  
> 所有 relay 请求走 M1 的 ai-loop-router（`~/program/ai-loop-router`，端口 4100/4102）。  
> 
> 如需部署 M1 的 ai-loop-router，请参考：
> - `~/program/ai-loop-router/docs/SETUP.md`
> - `~/program/ai-loop-router/scripts/com.ai-loop-router.plist.example`
> - `~/program/ai-loop-router/README.md`
>
> **注意**：本文档中所有旧 `:4000`/`:4002` 端口引用已更新为 `:4100`/`:4102`，指向 M1 的 ai-loop-router。

---

## 历史参考（仅考古）

以下内容为 2026-08-01 前的部署步骤，仅作考古，不再执行。

### 原目标

Mac2017 部署 / 热更 CCC Relay；Engine / OpenCode 走 **flash** 同池。

### 原前置

```bash
node --version   # >= 18
lsof -nP -iTCP:4000 -sTCP:LISTEN || true
```

### 原部署步骤

1. `cd /Users/fan/program/CCC && git pull && cd relay && npm ci && npm run build`
2. 配置 `~/.ccc/relay/upstreams.json`
3. `bash scripts/install-relay-plist.sh --start --host 2017`
4. 验证：`curl http://127.0.0.1:4000/admin/status`

### 原回滚

```bash
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
```

---

## 当前替代方案

| 原操作 | 现操作 |
|--------|--------|
| 2017 编译 relay | 无需编译，M1 的 ai-loop-router 已构建 |
| 2017 安装 relay plist | 无需安装 |
| 2017 验证 :4000 | 2017 验证 M1 :4100：`curl http://192.168.3.140:4100/admin/status` |
| 2017 配 upstreams | 密钥在 M1 的 `~/.ccc/relay/upstreams.json` |