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

> 记录意向，未出卡；出卡前再拆验收标准。

| 项 | 意图 | 备注 |
|----|------|------|
| **任务卡退役 / 高效管理** | 历史开发卡（尤其已关闭）不能无限堆在 `docs/dispatch/` 与 IDE agent 上下文里，否则扫卡/读仓会拖慢执行体效率 | 候选：关闭卡归档、看板已关闭 cap=10（已做）、scheduler 汇总退役、agent 只读活跃工作集 |
| **文档与项目注册统一治理** | 少入口、单注册表、每项目一页；PREFIXES / KB seed / taskable 收成同一事实源 | 阶段 A（规范+骨架）已落盘：`DOC-PROTOCOL` + `projects/registry.yaml`；阶段 B 见卡 `ccc005`（代码单源 + 校验） |
| **product Hub 史减噪** | `product/hub-*` 等文首统一「史」或迁 archive，避免 agent 当现行 | 分期；白名单见 DOC-PROTOCOL |
