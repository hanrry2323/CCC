# 迁移：M1 自用 → Mac2017 服务端

> 操作清单。拓扑见 [`topology.md`](topology.md)；目录见 [`server-layout.md`](server-layout.md)。

---

## 目标

| 组件 | 迁前（M1） | 迁后（2017） |
|------|------------|--------------|
| ai-loop-router :4000/:4002 | 生产中转 | **唯一生产中转** |
| CCC Hub / Board / Engine | 常驻 M1 | **唯一生产服务** |
| 业务工作区（Engine） | 多仓舰队 | `apps/ccc-demo`（重置后） |
| M1 Claude / OpenCode | 本机 127.0.0.1 中转 | 指向 `192.168.3.116` |

---

## 纪律

1. 同一时刻只一台生产中转、只一台 Engine  
2. 先起 2017 → 再切客户端 → 最后停 M1（避免空窗）  
3. 密钥只留 Server  

---

## 步骤

### 0. 目录（P0b）

按 [`server-layout.md`](server-layout.md) 清理重组 `~/program`；fresh clone `CCC` + `infra/ai-loop-router`；建 `apps/ccc-demo`。

### 1. 中转（P1a）

1. 在 2017 `~/program/infra/ai-loop-router` 配置 `upstreams.json` / 密钥  
2. 启动并对 LAN 可达（至少对 M1）  
3. 验收（在 M1）：

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://192.168.3.116:4000/
curl -sS -o /dev/null -w "%{http_code}\n" http://192.168.3.116:4002/
```

（具体健康路径以 router 文档为准；非 000/连接失败即基础设施通。）

### 2. 切断双中转（P1b）

1. M1：设置 Claude → `ANTHROPIC_BASE_URL=http://192.168.3.116:4000`  
2. M1：OpenCode → `http://192.168.3.116:4002`  
3. **停止 M1 生产中转**（launchd/进程）  
4. 验收：M1 上 Claude / OpenCode 各一条最小请求  

### 3. CCC 服务（P1c）

1. 2017：启动 Hub（7777）+ Board + Engine；本机 relay 用 `127.0.0.1`  
2. **停止 M1 上 Engine / Hub**  
3. 验收：M1 浏览器打开 `http://192.168.3.116:7777`，demo 任务能进闭环  

### 4. 产品重置（P2）

见 [`../product/reset-demo-fleet.md`](../product/reset-demo-fleet.md)。

---

## 回滚（简）

- 临时在 M1 重新拉起中转/Hub **仅应急**；恢复后立刻回到「仅 2017」  
- 回滚须在运维笔记记一笔，避免双脑残留  

---

## 验收记录（迁移日填写）

| 项 | 结果 | 时间 |
|----|------|------|
| 2017 program 布局合规 | PASS（顶层仅 CCC/infra/apps/archive/README；残骸在 archive/2026-07-18-preserver） | 2026-07-18 |
| :4000/:4002 自 M1 可达 | PASS（health=healthy；Claude `-p` → OK） | 2026-07-18 |
| M1 中转已停 | PASS（plist 移至 LaunchAgents/disabled-relay-20260718） | 2026-07-18 |
| Hub :7777 自 M1 可达 | PASS（projects 含 ccc-demo，default=ccc-demo） | 2026-07-18 |
| M1 Engine/Hub 已停 | PASS（plist 移至 LaunchAgents/disabled-ccc-server-20260718） | 2026-07-18 |
| demo 注册 | PASS（2017 registry：orch CCC + app ccc-demo） | 2026-07-18 |
| vendor/loop-code | PASS（M1 已拷贝 cli；**2017 已删，不再需要**） | 2026-07-19 对齐 |
| Executor 解析冒烟 | PASS（`smoke-executor-stack.sh` on 2017） | 2026-07-18 |
| ccc-demo 闭环 | PASS：`demo-readme-line` planned→…→released；README 含 `Status: CCC server demo OK`；耗时约 3min（修 OpenCode `baseURL`→`127.0.0.1:4002` 后） | 2026-07-18 |

### 闭环笔记（2026-07-18）

- 首次挂起：2017 `~/.opencode/opencode.json` 仍指向 M1 `192.168.3.140:4002`（中转已迁走）→ 已改为 `http://127.0.0.1:4002/v1`
- Server 上 OpenCode / Claude 必须指本机中转，不得再指 Client IP
