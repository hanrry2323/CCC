# CCC 重构 · 改造说明索引

> 日期：2026-08-02
> 关联方案：`__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md`（qx-map）
> 执行体：Trae（CCC 仓内执行）
> 验收人：Codex

---

## 目录结构

| 路径 | 说明 |
|------|------|
| `docs/archive/ccc-legacy-2026-08-02/RETENTION-LIST.md` | 保留清单+归档明细+不确定项 |
| `docs/archive/ccc-legacy-2026-08-02/` | 旧协议归档目录 |
| `docs/archive/ccc-legacy-2026-08-02/briefs/` | 旧任务 briefs（53 文件） |
| `docs/archive/ccc-legacy-2026-08-02/intent-proposals/` | 已完成烟测方案（7 文件） |
| `docs/archive/ccc-legacy-2026-08-02/dev-packets/` | 已完成指令包（16 文件） |
| `docs/archive/ccc-legacy-2026-08-02/dispatch/` | 单次分派任务卡（17 文件） |
| `docs/archive/ccc-legacy-2026-08-02/stability/` | 旧稳定性修复记录（3 文件） |
| `docs/archive/ccc-legacy-2026-08-02/product/` | 旧阶段协议与旧重构方案（25 文件） |
| `docs/archive/ccc-legacy-2026-08-02/relay/` | 已废弃 relay 部署文档（1 文件） |
| `docs/archive/ccc-legacy-2026-08-02/` | 根目录旧方案（3 文件） |

## 保留清单

详见 [RETENTION-LIST.md](docs/archive/ccc-legacy-2026-08-02/RETENTION-LIST.md)。

关键原则：红线、控制面纪律、仍然有效的权威基线（INDEX §0 引用）→ 保留。旧任务协议/旧窗口任务书/已完成且被本方案取代的方案 → 归档。

## 统计

- 归档文件总数：156（含 T34 追加 31：orphan-shell-web 4 + tauri-desktop-legacy 27）
- 保留文件总数：约 180+（含 references/ skills/ templates/ 等）
- 不确定项：无
- 删除文件：0（仅 git mv，无删除）

## 验收标准

- [x] 保留清单齐全且红线/权威基线全覆盖（无遗漏）— RETENTION-LIST 17 类全覆盖
- [x] 旧协议全部归档、无任何删除（git status 无未解释的 deleted）— 125 文件 git mv 归档
- [x] 不确定项有清单可裁决 — RETENTION-LIST §三「不确定项：无」
- [x] git 工作树干净，commit 只含文档移动与新增 — T34 追加 src-tauri 归档
- [x] 全程未触碰控制面/运行服务/外脑 — 三服务常驻 2017，M1 仅开发