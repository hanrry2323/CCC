# 任务卡 hp042 · health 报告自动化（M3） — 实施「health 报告自动化」（OpenCode 执行）
> 批准：老板确认转卡 · 2026-08-17

> 关联：hp-plan-019 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：hp · 日期：2026-08-17




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/hp/README.md`
- 方案池：`docs/projects/hp/plans/`（关联方案见卡头「关联」）

## 目标

完成子项目 3.5 health 报告自动化，交付可验收产物。

## 实现

1. 功能背景：生产节点上的多项健康指标目前散落在不同探针程序中，缺乏自动化的每日（Daily）健康监测汇总报告与最新状态。同时，若服务连接发生僵尸（Zombie）假死或进程意外崩溃，系统需要具有自动发现并利用 systemd 进行自动拉起（Auto-Restart / Auto-Repair）的能力，避免进入静默失效期。
2. 开发实现：
   - 新增 `scripts/qa/hp-health-report.py` 报告脚本，它并发调用三态探针 `hp-probes.py` 评估五个服务（PostgreSQL, Ollama, memory-store, mcp-server, graph-server）的进程、端口与真实请求状态。
   - 脚本增加自动修复（Auto-Repair）逻辑：对于异常的服务，利用 passwordless sudo 自动运行 `systemctl restart <unit>` 命令进行重启，并在等待 5 秒温升期后重新探测状态，记录修复结果。
   - 脚本对齐 PostgreSQL 数据库底层，查询 Chunks 计数、Documents 计数以及跨域 SHA 重复率等核心数据。
   - 报告将汇总整理成精美的 Markdown 文本，并保存至 `/data/knowledge/health/history/health-report-YYYYMMDD.md`（并硬拷贝或符号链接至 `/data/knowledge/health/latest-report.md`）。
   - 在远程生产节点 `/data/knowledge/health/pg-health.sh` 创建定时任务入口，使得 crontab 调度的每 5 分钟级别巡检能够无缝执行此项自愈及报告生成逻辑。

## 红线（先看）

1. 严禁改动无关的业务代码，改动应精确限制在 `scripts/qa/hp-health-report.py` 与 `docs/lessons.md`。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 业务仓改动：
  - 新增 `scripts/qa/hp-health-report.py` (健康自愈报告器)
  - 维护 `docs/lessons.md` (记录 hp042 自动化自愈教训)

## 步骤

1. 在业务仓 `scripts/qa/` 目录下设计并编写 `hp-health-report.py`，实现三态诊断、systemd 自动修复，并读取 PG 统计合成 Daily 报告。
2. 运行 `ruff` 完成对新脚本的 lint 检查。
3. 在 `hp@hp` 远程生产节点创建桥接 cron 入口 `health/pg-health.sh`，赋予可执行权限，并测试运行，保证其成功在 `health/history/` 下生成最新的 Markdown 每日报告，测试验证出口码及功能健壮性。
4. 在业务仓 `docs/lessons.md` 追加 hp042 的相关设计教训。
5. 提交并 push 业务仓代码到 `codex/hp042-health-m3-health` 同名分支。

## 验收标准

1. 健康报告脚本 `scripts/qa/hp-health-report.py` 与远程 `health/pg-health.sh` 配合无间，可直接通过 `ssh hp "/data/knowledge/health/pg-health.sh"` 手动触发。
2. 运行后成功于远程 `hp` 节点生成 `/data/knowledge/health/history/health-report-YYYYMMDD.md` 和 `/data/knowledge/health/latest-report.md` 报告。
3. 报告中清晰准确展现各服务的三态（Process / Port / Request）探活结果及数据库 Chunks 级最新元数据统计。

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：
编译：
lint：
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-17

### 1. 实现说明
- 成功设计并编码 `scripts/qa/hp-health-report.py` 报告脚本，复用三态探针底层诊断各服务，对异常服务执行 `sudo -n systemctl restart` 自动拉起，合并输出 PostgreSQL 统计，最终固化为结构清晰的每日/最新 MD 健康报告。
- 桥接并更新了生产节点 `/data/knowledge/health/pg-health.sh` 入口，支持每 5 分钟级别周期自动化检测、自愈、报告输出。

### 2. 测试结果
- 本地 `ruff check` 完美全绿通过。
- 远程 `pg-health.sh` 测试运行：
  ```text
  === HP Health Report & Auto-Repair Execution ===
  Running initial service probes...
  All services are healthy. No repair action needed.
  Fetching PostgreSQL statistics...
  Report saved to: /data/knowledge/health/history/health-report-20260817.md
  Latest report symlinked/copied to: /data/knowledge/health/latest-report.md
  SUCCESS: All services healthy.
  ```

### 3. PUSH 证据
- 业务仓改动分支：`codex/hp042-health-m3-health`
- 业务仓 Commit Hash：`2c241de2bd405391e0a297e01e63a8a3a96cbaf6`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `hp-plan-019` 的状态同步为「已完成」，交付了全套自动报告与故障自修复服务。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：已在业务仓 `docs/lessons.md` 新增 2026-08-17 「HP 健康报告与自愈自动化 M3.5（hp042）」教训条目，总结了健康汇总快照、服务异常自愈设计及定时任务桥接版本化的一系列经验。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变既有项目结构、底层数据库、端口、技术栈与调用路径。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：没有超出既定里程碑规划。

## 批注落实

（无批注）

## 执行提示

- 项目：hp（HP 个人 AI agent 中央知识库基础设施 + 教训沉淀平台。）

- 项目仓（只读参考）：/Users/fan/program/apps/hp（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：daily 健康报告 + 异常标记，异常自动拉起/标记，避免静默失效。验收标准：health 报告自动化完成，验收点可复核（命令/可观察结果）。

- 项目线路/近况：
  - **M1 底座固化（已完成）**：hp-plan-001/002——5267 docs 在线，语义检索/记忆/向量化/备份就绪
  - **2026-08-15 架构定论**：六条主里程碑确立——**M2 稳控与可恢复 / M3 可观测与告警 / M4 数据保鲜与质量 / M5 生态消费 / M6 演进（待定）**；M2-M5 方案已落库（hp-plan-004~007，状态已确认，待排期）
  - **主线方向**：开发（mac2017 SSOT）与部署（hp 节点）彻底隔离；HP 升级为全文知识底座（ccc-kb 降为离线降级副本）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 历史教训（避免踩坑）：
  - [domains::projects::3__采集器数据源漂移_2026-08___hp004_] 3. 采集器数据源漂移（2026-08 · hp004） - **根因**：多项目 watcher 配置未与 registry 对齐 - **修复**：统一从 registry 派生采集配置 - **适用场景**：采集器配置变更
  - [domains::projects::2__备份缺失导致回滚困难_2026-08___hp009_] 2. 备份缺失导致回滚困难（2026-08 · hp009） - **根因**：清理操作前未新建独立快照 - **修复**：后续任务统一走 命名备份 - **适用场景**：数据库写操作
  - [domains::projects::1__短_chunk_检索漂移_2026-08___hp006_hp007_] 1. 短 chunk 检索漂移（2026-08 · hp006/hp007） - **根因**：knowledge/incoming 导入产生 437 个 <50 字符 short chunk，导致检索结果碎片化 - **修复**：短 chunk 合并策略 + 尾端对齐，target < 15% - **适用...

- 禁区：- 绝对禁止在 M1 本地修改、添加、删除任何业务仓 `/Users/fan/program/apps/hp` 的代码文件，必须通过 Desktop transfer → Engine 派发执行。
- 绝对禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文），业务/知识深文应留在 hp 仓或知识库产品侧。
- 端口与路径权威一律以 qx-map `cluster/path-authority.md` 为准，禁止在 CCC 仓复制或维护端口表副本，防双源漂移。

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：hp（HP 个人 AI agent 中央知识库基础设施 + 教训沉淀平台。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 历史教训（审查时重点关注）：
  - [domains::projects::3__采集器数据源漂移_2026-08___hp004_] 3. 采集器数据源漂移（2026-08 · hp004） - **根因**：多项目 watcher 配置未与 registry 对齐 - **修复**：统一从 registry 派生采集配置 - **适用场景**：采集器配置变更
  - [domains::projects::2__备份缺失导致回滚困难_2026-08___hp009_] 2. 备份缺失导致回滚困难（2026-08 · hp009） - **根因**：清理操作前未新建独立快照 - **修复**：后续任务统一走 命名备份 - **适用场景**：数据库写操作
  - [domains::projects::1__短_chunk_检索漂移_2026-08___hp006_hp007_] 1. 短 chunk 检索漂移（2026-08 · hp006/hp007） - **根因**：knowledge/incoming 导入产生 437 个 <50 字符 short chunk，导致检索结果碎片化 - **修复**：短 chunk 合并策略 + 尾端对齐，target < 15% - **适用...

- 架构约束/红线：- 绝对禁止在 M1 本地修改、添加、删除任何业务仓 `/Users/fan/program/apps/hp` 的代码文件，必须通过 Desktop transfer → Engine 派发执行。
- 绝对禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文），业务/知识深文应留在 hp 仓或知识库产品侧。
- 端口与路径权威一律以 qx-map `cluster/path-authority.md` 为准，禁止在 CCC 仓复制或维护端口表副本，防双源漂移。

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。
