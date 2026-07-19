# Mac2017 服务端目录规范

> SSOT：Server 机 `~/program` 布局。禁止随意新建顶层业务目录。  
> 机器：`fan@192.168.3.116`（SSH host `mac2017`）

---

## 根路径

**`/Users/fan/program`**

不换根名（与习惯/文档一致）；**内容按本规范重组**，不软链 M1。

```text
/Users/fan/program/
  README.md                 # 本机三句话说明 → 指向本文
  CCC/                      # 主产品 + orch（唯一编排仓）
  infra/
    ai-loop-router/         # 唯一生产中转
  apps/
    ccc-demo/               # 默认唯一 engine 业务仓
  archive/
    YYYY-MM-DD-*/           # 冷数据 / 半同步残骸
```

---

## 规则

| 路径 | 用途 | 规则 |
|------|------|------|
| `CCC/` | 产品代码、Hub/Engine、文档、`vendor/` | 唯一主仓；不在仓外散落产品代码 |
| `infra/ai-loop-router/` | 模型中转 | 中转只此一处 |
| `apps/<name>/` | 经 doctor register 的业务仓 | **新项目必须落这里** |
| `archive/` | 冷存 | 不参与 Engine 登记 |
| 其他顶层目录 | — | **禁止**；先改本文再创建 |

---

## 新项目流程

1. `mkdir -p ~/program/apps/<name> && cd ... && git init`（或 clone）
2. 在 Server 上：`python3 ~/program/CCC/scripts/ccc-init.py ~/program/apps/<name> --register`（以实际脚本参数为准）
3. `python3 ~/program/CCC/scripts/ccc-workspace-doctor.py`
4. 更新登记说明；不把路径写死进 CCC 产品代码

---

## 与 M1 客户端

- M1 可保留自己的 `~/program` 作移动开发
- **生产执行、中转、Hub/Engine** 以 2017 为准
- **M1 对话**：Desktop + sidecar `:7788` + arm64 `vendor/loop-code/cli`（M1 本机；gitignore）
- **Mac2017 不再部署 loop-code 二进制**（架构对齐 2026-07-19；Hub `/api/chat` 已删，2017 不做对话）

---

## 清理原则

半同步/残缺副本 → 移入 `archive/YYYY-MM-DD-preserver/`，再按需删除。  
不在生产路径上「接着用旧半吊子 clone」。
