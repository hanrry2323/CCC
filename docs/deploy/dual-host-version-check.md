# 双机版本对齐核对（F2-2）

> 一键命令：核对 **M1** 本机 `VERSION`/`git HEAD` 与 **Mac2017 Hub** `GET /api/desktop/version` 是否对齐。  
> **只核对，不部署**。契约：[`../product/hub-api-v1.md`](../product/hub-api-v1.md) §5。

## 用法

```bash
# 默认打 Mac2017 Hub
bash scripts/ccc-dual-host-check.sh

# 显式指定 Hub
CCC_SERVER=http://192.168.3.116:7777 bash scripts/ccc-dual-host-check.sh

# 本机 loopback（在 2017 上自检）
CCC_SERVER=http://127.0.0.1:7777 bash scripts/ccc-dual-host-check.sh
```

认证：`CCC_CHAT_USER` / `CCC_CHAT_PASS`（默认 `ccc`/`ccc`）。

### 成功输出（恰好三行核心）

```
M1: v0.52.2 9af1fb4
2017: v0.52.2 9af1fb4 v1
aligned: yes
```

### 失败输出

```
M1: v0.52.2 9af1fb4
2017: v0.52.1 abcdef0 v1
aligned: no
mismatch: version M1=v0.52.2 2017=v0.52.1
mismatch: commit M1=9af1fb4 2017=abcdef0
```

退出码：

| 码 | 含义 |
|----|------|
| `0` | 对齐 |
| `1` | 版本 / commit / `hub_api_version` 不一致或不受支持 |
| `2` | Hub 不可达或响应非 JSON |

## 判定规则

1. `version`：本机 `VERSION` 与 Hub 返回值字符串全等。  
2. `commit`：双方 `git` sha 前 7 位全等。  
3. `hub_api_version`：必须落在客户端支持集 `["v1"]`（脚本内硬编码）。  

## 失败处置

| 现象 | 处置 |
|------|------|
| Hub unreachable | 查 2017 Hub launchd / `:7777`；`curl -u ccc:ccc $CCC_SERVER/api/desktop/projects`；见 [`topology.md`](topology.md) |
| `version` 不一致 | M1 `git pull`；2017 `cd ~/program/CCC && git pull --ff-only`；必要时重启 Hub（`launchctl kickstart -k gui/$(id -u)/com.ccc.chat-server`） |
| `commit` 不一致 | 同上；确认两侧同在 `main` 且无未推本地提交误当「已对齐」 |
| `hub_api_version` 不在支持集 | 停手：契约可能已升 v2；联系架构，勿擅自改 Desktop |
| 端点 404 | 2017 Hub 代码过旧，未合入 F2-2；先拉仓再重启 Hub |

## 相关

- 端点：`GET /api/desktop/version`（只读）  
- 人工步骤（旧）：[`desktop.md`](desktop.md)  
- 拓扑：[`topology.md`](topology.md)
