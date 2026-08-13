# 方案 · CCC 架构扩展性基线 + 知识库路径规划（前期定规则防走弯路）

> 项目：ccc · 编号：ccc-plan-019 · 状态：已完成 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：ccc059
> 关联方案：ccc-plan-004（系统化升级·已完成，本方案为其扩展性收口）
> 进度：0/1 (0%)

## 目标

把「未来扩容×10（卡量/项目/并发/多机）」视角下 CCC 架构的明显局限与 HP 知识库路径遗留问题，在项目初期一次性收敛为 **三份可执行资产**：① 现在纠正项清单（本周内做）② 定死的前期规则（写入规范防漂移）③ 明确不拆的架构墙（记档防走弯路）。做到后期升级顺滑、不拆现状。

## 背景

2026-08-10 双机重启后产线恢复，老板要求站在扩容视角前瞻调查。派出 6 个子 agent 并行取证（引擎/调度、存储/数据、流程/治理、部署/拓扑、HP 资产盘点、调用路径规划），发现：

1. **引擎侧**：main.py 2590 行单文件 + 每轮心跳 8 次全量读盘（O(N²)）；多机派发零通道；状态机 6+ 处影子系统
2. **存储侧**：全文件+全量读模型，无 DB 无轮转；cards.jsonl 无界（228 卡已 1234 行）；exec 日志 731 文件单目录平铺
3. **流程侧**：卡头契约无单一 schema（改字段=13 处人肉对齐）；方案↔卡同步是纸面承诺；出卡编号并发无锁；registry 单真值被 seed/executors.json/双解析器稀释
4. **部署侧**：2017 全栈单端无备机；执行体 3+3 封顶；模型出口每档仅 1 个 enabled 上游；新机器重建无剧本；零告警推送；零硬编码红线只管入口文档（4100 死引用仍在）
5. **HP 侧（🔴 高危）**：mcp-server/memory-store **源码已丢失**（目录只剩 .bak），服务靠「永不重启」维系；资产散落 6+ 顶层路径；备份一天 7 份重复；reference 17 仓带 .git 体积翻倍
6. **调用侧**：HP 接入无单一权威入口——MCP 配置散 3 处（qx-map/.mcp.json、opencode.json、2017 settings），hpkb-query 技能 3 份拷贝内容分叉，opencode.json 缺 ccc-kb 通道（文档宣称与实际不符），`~/.ccc/workspaces.json` 死引用

## 方案内容

### A. 全局分层（红=现在纠正 / 黄=定规则 / 蓝=墙·记档不拆）

#### 🟥 A 层：现在纠正（本周内，低成本防漂移）

| # | 纠正项 | 动作 | 性质 |
|---|--------|------|------|
| A1 | 卡头契约单一 schema | 冻结新增卡头字段；收敛 CardHeader 单一模型（loader/validate/docgate/prompt_inject 统一 import） | 代码 |
| A2 | 出卡编号并发锁 | new-card.sh 加 flock（`<dispatch-dir>/.card-lock`） | 脚本 |
| A3 | 模型出口每档 ≥2 上游 | 恢复 free-1..5 enabled 并按 tier_priority 排序；立规则「上游变更必须留热备」 | 配置 |
| A4 | 零告警 | board-live.sh 探活失败推送通知；watchdog-ccc.sh 挂 2017 launchd（60s 探心跳） | 脚本/部署 |
| A5 | registry 单真值收敛 | seed 兜底改只读归档；executors.json 项目行并入 registry 派生；解析器统一（registry.py 替换 validate-plans.sh 的 grep） | 代码 |
| A6 | 方案↔卡同步闭环 | 卡关闭时 approve-merge.sh 自动调 plans 写关联卡+推进状态；Q1 校验 OR→AND | 代码 |
| A7 | **HP 服务源码恢复（P0）** | 从 _staging 6/21 备份恢复 mcp_server.py 进 git 工作区；验证重启可起；立「服务源码必须进 git」规则 | 运维/代码 |
| A8 | 调用路径单一权威入口 | 见 C 节 | 配置/文档 |

#### 🟨 B 层：定规则（写入规范，暂不动代码）

| # | 规则 | 写入位置 |
|---|------|---------|
| B1 | 多机=按仓/按项目物理隔离独立引擎实例（每实例独立 DISPATCH_DIR+log_dir），不写分布式代码 | 本方案 + CCC 架构文档 |
| B2 | 并发上限钉死 3+3，禁止改数字硬撑（8 核 16GB 物理边界） | config.env 注释 |
| B3 | 卡量预警线 ~1000：到线前做 main.py 模块化重构 + 数据层 SQLite/内存索引 | roadmap 挂账 |
| B4 | 文件轮转：metrics 30 天、cards.jsonl 定期 compact、exec 日志按卡分子目录、engine-claude 产物按卡清理 | daily-sync 加 hygiene |
| B5 | 执行体配对表/门禁清单/infra 关键词表外置配置，代码只读配置 | 开发规范 |
| B6 | 零硬编码红线扩到 scripts/ 与工具脚本；IP 收敛单一 location-truth；清 4100 死引用 | check-entry-docs.py 扩展 |
| B7 | 存储三主线（HP 侧）：代码=git 工作区、数据=/data/knowledge、备份=/data/backups 单一归档 | HP README/运维文档 |
| B8 | 新状态/新门禁三处清单（task.py 转移表 + store 映射 + models.STATES）必须同步 | 开发规范 |

#### 🟦 C 层：墙（记档不拆，边界清楚）

| # | 墙 | 拆的条件 |
|---|-----|---------|
| C1 | 真·多机派发 = 重写派发层（worker 协议 + 心跳注册 + 远端占槽） | 物理隔离顶不住时（B1 先行） |
| C2 | 执行体跨机 = worktree 本地语义改 clone 分支制 | 需要按机器分片执行时 |
| C3 | 全栈单端 = 最低成本退路 M1 冷备路由（6102 双实例 + 客户端双地址） | 2017 可用性不达标时 |

### B. HP 知识库资产地图（2026-08-10 盘点）

| 资产 | 路径 | 大小 | 说明 |
|------|------|------|------|
| 主知识库（git 仓） | `/data/knowledge/` | 9.4G / ~58k 文件 | reference(1.5G 镜像) + local + incoming(3253 未入库) + docs + catalog |
| 运行中 PG | `/data/pg-knowledge` | 14G | knowledge + backtest 两库（旧 pgdata 在 /data/knowledge/pgdata 已废弃） |
| WAL+备份 | `/data/backups` | 80G | wal 66G + dump 14G（另有 knowledge/backups 重复 2.7G） |
| 服务 | mcp-server :8083 / memory-store :8082 / ollama :11434 / llama :39603 | — | 🔴 源码丢失，靠永不重启维系 |
| 冷备份 | Mac2017 `sync/kb-cold-backup` | 7 快照 | 每日 08:00 自动 |

**路径规则（B7）**：代码（含服务源码）一律进 git 工作区；数据（PG/向量）在 /data/knowledge 数据目录；备份（dump/wal）统一 /data/backups 单一归档，禁止 knowledge/backups 与 _staging 再堆放。

### C. 调用路径单一权威入口（A8 细化）

**规则：HP 知识库接入只有一个权威定义源——qx-map `AGENTS.md`「知识库操作 SOP」；所有工具配置从此派生。**

1. **MCP 三通道收敛**：hp-kb（远端 8083）= 唯一知识查询入口（OpenCode + Claude Code + Codex 全部走它）；ccc-kb（本地 stdio）= CCC 仓知识专用，**补进 opencode.json**（当前缺失，文档宣称与实际不符）
2. **hp-kb 配置同构**：qx-map/.mcp.json 与 opencode.json 的 hp-kb 均带 `Accept` header，行为一致
3. **技能单一主版**：hpkb-query 系列收敛为一版（qx-map/.claude/skills/qx-hpkb-query 为主，删除 .reasonix 分叉）；修正 SKILL.md 内部矛盾（第 9 行「CLI 唯一路径」与实际「MCP 首选」相反）
4. **死引用清理**：mcp-manifest 中 `~/.ccc/workspaces.json` 条目删除或改指向真实文件
5. **CCC 运行时零引用 HP 红线维持**（设计使然，server 不读远端），仅文档层单向登记
6. **domain 速查单一来源**：AGENTS.md 定义，各 skill 引用不复制

## 验收标准

- [x] A1-A8 全部落地（A7 HP 源码恢复经「重启 mcp-server 验证可起」）
- [x] B1-B8 规则写入对应文档/规范并有 git 记录
- [x] C 层墙清单记入架构文档（docs/architecture.md 或 roadmap 挂账）
- [x] 调用侧：opencode.json 含 ccc-kb + hp-kb（带 header）、技能单一主版、死引用清零
- [x] 模型出口每档 ≥2 enabled 上游，scnet 断流场景实测有兜底

## 转卡计划

| 卡 | 内容 | 执行体 |
|----|------|--------|
| ccc059 | A1 卡头单一 schema + A2 出卡 flock（合并，同属卡流程层） | OpenCode |
| ccc0XX | A3 模型出口上游恢复 + 规则（含配置备份与验证） | OpenCode |
| ccc0XX | A4 告警推送 + watchdog 挂载 | OpenCode |
| ccc0XX | A5 registry 收敛 + A6 方案卡同步闭环（代码改动较大，单列） | OpenCode |
| ccc0XX | A7 HP 源码恢复 + 重启验证（P0，涉及 2017/HP 运维） | OpenCode |
| ccc0XX | A8 调用路径收敛（MCP 配置/skill 主版/死引用） | OpenCode |

## 备注

- 依赖：A3 需动 2017 生产配置，执行前备份 upstreams.json；A7 需谨慎（当前服务在跑，恢复源码=复制回工作区并做 dry-run 启动验证，重启窗口选在低峰）
- 风险：A1 收敛解析器期间可能触发机审/合入对账差异，落地后跑全量 validate + 出卡冒烟
- 排期：本周 A2/A3/A4/A8 先行（配置/脚本级），A1/A5/A6/A7 随后（代码级）
