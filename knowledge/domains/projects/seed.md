# 项目元数据域

> 来源：T9 种子包 `02-project-metadata.json`（qx-map `cluster/path-authority.md` + `cluster/cluster.json`）
> 导入日期：2026-08-02 · 更新：知识库独立维护后在此标注变更

## 优先级

**主体**：CCC（底座 · 主仓）

**CCC 子项目**：
- **qb** — CCC 自动化开发测试项目（Mac2017 `/Users/fan/program/apps/qb/`，SMB 可挂载）

## 项目清单

| 项目 | 路径 | 机器 | 性质 | 访问方式 |
|------|------|------|------|---------|
| **CCC（底座）** | `/Users/apple/program/CCC/` | M1 | git 仓，主副本 | 本地直接开发 |
| **qx-map** | `/Users/apple/qx-map/` | M1 | 知识地图/权威解析（无 remote） | 本地直接访问 |
| **QuantHive** | `/Users/apple/ZCodeProject/QuantHive/` | M1 | 独立轨道，git 仓 | 本地直接开发 |
| **ai-loop-router** | `/Users/apple/program/ai-loop-router/` | M1 | loop-router 源码，git 仓 | 本地直接开发 |
| **ccc-relay-runtime** | `/Users/apple/.ccc/relay-runtime/` | M1 | ccc-relay 副本 | 本地直接访问 |
| **qb** | `/Users/fan/program/apps/qb/` | Mac2017 | CCC 自动化开发测试项目，git 仓 | SMB 或 ssh |
| **medio-0** | `/Users/fan/program/apps/medio-0/` | Mac2017 | git 仓 | SMB 或 ssh |
| **xianyu** | `/Users/fan/program/apps/xianyu/` | Mac2017 | git 仓（origin=hanrry2323/xianyu） | SMB 或 ssh |
| **qx-observer** | `/Users/fan/program/apps/qx-observer/` | Mac2017 | git 仓（origin=hanrry2323/qx-observer，M1 无本体） | ssh |
| **hp 服务仓** | `/Users/fan/program/apps/hp/` | Mac2017 | git 仓（origin=hanrry2323/hp） | ssh |
| **ccc-demo** | `/Users/fan/program/apps/ccc-demo/` | Mac2017 | git 仓（origin=hanrry2323/ccc-demo） | ssh |
| **clawmed-ccc** | `/Users/fan/program/apps/clawmed-ccc/` | Mac2017 | git 仓（origin=hanrry2323/clawmed-ccc） | ssh |
| **qx（旧项目）** | `/Users/apple/program/projects/qx/` | M1 | git 仓（origin=hanrry2323/qx），未纳入双轨 | 本地直接访问 |
| **clawmed-ai** | `/Users/apple/program/projects/clawmed-ai/` | M1 | git 仓（无 remote），待定去向 | 本地直接访问 |
| **social-auto-upload** | `/Users/apple/program/social-auto-upload/` | M1 | 含 cookies/conf，**禁入 git** | 本地直接访问 |
| **nexus-core** | `/Users/apple/program/nexus-core/` | M1 | git 仓（无 remote），待定去向 | 本地直接访问 |
| **learning** | `/Users/apple/program/learning/` | M1 | git 仓（origin=hanrry2323/learning） | 本地直接访问 |

## 已清理路径（历史误导源）

| 曾用的错误路径 | 真相 |
|----------------|------|
| `/Users/apple/program/projects/qb/` | 不是目录，是 171B 文本文件；qb 真实在 Mac2017 |
| `/Users/apple/program/qb/` | 曾是空状态目录，2026-08-01 已删 |
| `/Users/apple/program/qx-observer/` | 是 4K MOVED 指引文件（指向 Mac2017），不是项目目录 |