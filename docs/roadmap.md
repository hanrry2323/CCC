# CCC 发展路线图

> **现行叙事**：[`VISION.md`](VISION.md) · **版本**：根目录 `VERSION`（v0.70.0）  
> **权威链**：[`INDEX.md`](INDEX.md) §0 · 文档怎么写：[`DOC-PROTOCOL.md`](DOC-PROTOCOL.md)  
> **历史正文**（v0.19–v0.26 等）：[`archive/roadmap-history-v0.19-v0.26.md`](archive/roadmap-history-v0.19-v0.26.md)（史；勿覆盖「当前方向」）。

---

## 当前方向（索引）

> 2026-08-02 架构重构定稿后方向：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳。

| 重构里程碑 | 完成度 | 说明 |
|------------|--------|------|
| **P0 旧栈退役** | ✅ 已完成 | `scripts/` 归档至 `docs/archive/legacy-retired-2026-08-02/scripts/`；旧端口（7777/7775/7778）退役 |
| **P1 新栈骨架** | ✅ 已完成 | `server/` 七模块（engine/board/web/relay/kb/config/deploy）+ 测试 |
| **P2 Engine + 看板 + HTTP** | ✅ 已完成 | 薄驱动 Engine + 看板服务端 + HTTP API（T1–T14） |
| **P3 线路图 + 运维定时** | ✅ 已完成 | 线路图聚合 + board-scheduler 只读巡检（T5–T7） |
| **P4 2017 部署** | ✅ 已完成 | 三 launchd 常驻（web-server/engine/board-scheduler，T22） |
| **P5 对话大脑 Agent** | ✅ 已完成 | `/conversation` 调 Claude Code via 6100（T29）+ HTTP 页面重构（T30） |

| 重构收口（T31–T35） | 状态 | 说明 |
|---------------------|------|------|
| **T31 文档基线** | ✅ 已完成 | 仓内权威文档切到新架构 |
| **T32 Engine 真派发** | ✅ 已完成 | 从「模拟拉起」到真实派发闭环 |
| **T33 硬编码清理** | ✅ 已完成 | 全仓硬编码扫描清零 |
| **T34 死码双壳清理** | ✅ 已完成 | src-tauri/ 等历史遗留归档 |
| **T35 回归挂账** | ✅ 已完成 | 重构挂账项回归（FileBoardStore + 挂账清零 + 双端复测） |

| 现状 | 说明 |
|------|------|
| **M1（开发机）** | 开发工具（Claude/OpenCode）改 CCC 仓；不保留业务第二树 |
| **M2（2017 生产）** | 单端 :7788 + Engine + board-scheduler 三服务常驻；大脑 Agent via 6100 |
| **M3（任意设备壳）** | Desktop / 网页 / 手机经 HTTP 直连 2017；账号密码 + token |
| **M4（中转站）** | 6100 Anthropic 出口 + 6102 Relay flash 出口 |

| 开源与介绍 | 说明 |
|------------|------|
| 文档口径 | 先读 [`INDEX.md`](INDEX.md) §0 + [`DOC-PROTOCOL.md`](DOC-PROTOCOL.md) |
| 项目注册 | [`projects/registry.yaml`](projects/registry.yaml)（唯一事实源） |
| 竖切蓝图 | [`vertical-qx.md`](vertical-qx.md)（业务向，非 CCC 骨架） |

**业务双轨（归档，非产品北星）**：[`archive/NEXT-DUAL-TRACK.md`](archive/NEXT-DUAL-TRACK.md)。

---

## 下一程挂账（产品）

> **北星**：一个主 IDE 谈意图 → `ccc-plan` 确认后自动拆卡入队 → Engine+硬门禁静默跑 → 只在 RED 或待合入时找人 → 人审 diff 后「合入批准」。  
> **2026-08-07**：下一程只挂北星竖切。冻结：不再挂「同义句/席位/Agent SOP」类项。竖切：[`product/north-star-slice.md`](product/north-star-slice.md)。

| 项 | 意图 | 备注 |
|----|------|------|
| **北星竖切 W0–W2** | plan-to-cards / ready_for_merge / 合入批准 | ✅ `1e78caa` + 2017 |
| **S1 权威入口反漂移** | STARTUP/CURSOR/rules/dev-channel 对齐合入批准 | ✅ |
| **S2a ops 旧端口去红** | opsRed 去掉 7775/7777；config.md 对齐 topology | ✅ |
| **S2b registry 单源接线** | PREFIXES/taskable ← registry.yaml | ✅ ccc005 已回写 |
| **S3 现网狗粮度量** | 调度≤2；禁新 SOP | ✅ 见下「度量」 |

### 度量（S3 · 2026-08-07 foundation anti-drift）

| 指标 | 结果 |
|------|------|
| 老板调度次数 | 2（①确认 foundation 计划 ②本程合入/部署） |
| 因流程不懂找人 | 0 |
| 新增 Agent SOP 文件 | 0（只改现行入口 + 脚本/API） |

### M2 ✅（北星产线加固 · 2026-08-07 · `bb64122`）

| 项 | 意图 | 备注 |
|----|------|------|
| **机审自动落盘 ccc006** | 机审通过但未写卡 → Engine 落盘 ## 机审区 | ✅ |
| **Console 文案对齐** | 「待验收」→「待合入批准」 | ✅ |
| **下一程方案落盘** | M3 方案进 notes | ✅ |

### M3 ✅（ready→合入批准闭环 · 2026-08-07 · `649afe6`）

| 项 | 意图 | 备注 |
|----|------|------|
| **假滞留清账** | audit 判定 + 索引 audit 旗标 + backfill 脚本 | ✅ |
| **Console ready** | 待合入接 `/board/ready_for_merge` | ✅ |
| **合入批准狗粮** | `approve-merge --close-only xy001` | ✅ |
| 里程碑 | [`notes/m3-milestone-2026-08-07.md`](notes/m3-milestone-2026-08-07.md) | ✅ |

### M4 ✅（首跑机审 + 关卡清账 · 2026-08-07 · `2588908`）

| 项 | 意图 | 备注 |
|----|------|------|
| **cd 前缀** | ccc004 意图经 registry | ✅ |
| **ccc005/006 首跑机审** | first-audit-evidence → ready | ✅ |
| **合入批准三卡** | ccc004/005/006 已关闭 | ✅ |
| 里程碑 / 下一程 | [`notes/m4-milestone-2026-08-07.md`](notes/m4-milestone-2026-08-07.md) · [`notes/m5-next-plan.md`](notes/m5-next-plan.md) | ✅ / 待批 |

| 项 | 意图 | 备注 |
|----|------|------|
| **任务卡退役 / 高效管理** | 已关闭卡不拖垮扫卡 | 看板已关闭 cap=10（已做）；其余挂账 |
| **product Hub 史减噪** | hub-* 标史或迁 archive | 分期；白名单见 DOC-PROTOCOL |

### 冻结清单（非阻塞绿路径不修）

- 禁止新增：验收同义句、席位表、AGENTS 长禁令、看板列解释文、了解类 SOP 扩写  
- 禁止平行：第二套拆卡 LLM 服务（拆卡 = 结构化 plan + 脚本）  
- Desktop/Hub 主对话面：暂缓维持  
- Agent 误读非阻塞 → 记债，不写心智补丁 |
