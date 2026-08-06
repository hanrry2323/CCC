# 项目元数据域

> 来源：种子包 `02-project-metadata.json`（qx-map `cluster/path-authority.md` + `docs/architecture.md` v0.70.0 + `ccc-refactor-方案-定稿-2026-08-02.md`）
> 初始化：2026-08-02 · M4 刷新：2026-08-03 · 之后知识库独立维护在此标注变更

## 优先级

**主体**：CCC（底座 · 主体 · 主仓）

**CCC 子项目**：
- **qb** — CCC 自动化开发测试项目（Mac2017 `/Users/fan/program/apps/qb/`，SMB 可挂载）

## CCC（主仓）

| 项 | 值 |
|---|---|
| 路径 | M1 `/Users/apple/program/CCC/` |
| 性质 | CCC 底座 · 主仓（git 仓，主副本） |
| 角色 | 自动化平台底座（薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端） |
| 访问 | 本地直接开发（开发期）+ HTTP 直连 2017:7788（运行期） |
| 版本 | v0.70.0（2026-08-02 重构定稿） |
| 最近活动 | ongoing |

## qb（CCC 自动化开发测试项目）

| 项 | 值 |
|---|---|
| 路径 | Mac2017 `/Users/fan/program/apps/qb/`（SMB: `/Volumes/fan/program/apps/qb/`） |
| 性质 | CCC 自动化开发测试项目（git 仓） |
| 访问 | SMB 挂载或 `ssh fan@192.168.3.116` |
| M1 注意 | M1 无本机 qb 代码（曾用错误路径 `/Users/apple/program/projects/qb/` 是 171B 文本文件，非目录） |
| 最近活动 | 2026-07-29 |

## 其他项目清单

| 项目 | 路径 | 机器 | 性质 | 访问方式 |
|------|------|------|------|---------|
| **qx-map** | `/Users/apple/qx-map/` | M1 | 知识地图/权威解析（git 仓，无 remote） | 本地直接访问（M4 移交后 CCC 独立运行，不再读写） |
| **QuantHive** | `/Users/apple/ZCodeProject/QuantHive/` | M1 | 独立轨道；**禁止 CCC Engine** | 本地直接开发（不经 CCC） |
| **ai-loop-router** | `/Users/apple/program/ai-loop-router/` | M1 | loop-router 源码，git 仓 | 本地直接开发 |
| **ccc-relay-runtime** | `/Users/apple/.ccc/relay-runtime/` | M1 | ccc-relay 副本 | 本地直接访问（已离线，与双轨决议无关） |
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

## 关键独立性纪律

- **QuantHive 独立轨道**：禁止与 CCC/qb 合并表述；**禁止经 CCC Engine 出卡/派发**（2026-08-06）。
- **CCC 与 QXMAP 绝对独立**（D2）：运行时零依赖。
- **CCC 自建知识库独立运行**（D3）：M4 移植后不再读写 qx-map / hp-kb。

## 已清理路径（历史误导源）

| 曾用的错误路径 | 真相 |
|----------------|------|
| `/Users/apple/program/projects/qb/` | 不是目录，是 171B 文本文件；qb 真实在 Mac2017 |
| `/Users/apple/program/qb/` | 曾是空状态目录，2026-08-01 已删 |
| `/Users/apple/program/qx-observer/` | 是 4K MOVED 指引文件（指向 Mac2017），不是项目目录 |

**纪律**：新文档禁止引用这些错误路径；非 git 散装目录（M1）见 `path-authority.md` 原文，本种子包仅含 git 仓项目。
