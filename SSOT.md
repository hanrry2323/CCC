# SSOT — 真相源地图

> 文件夹卫生后短表。细节与人机共识：[`docs/product/loop-engineer-authority.md`](docs/product/loop-engineer-authority.md)。

## 产品 / 共识

| 文件 | 角色 |
|------|------|
| `docs/product/loop-engineer-authority.md` | **事实权威 + 人机共识（最新）** |
| `docs/VISION.md` | 对外/对内叙事 |
| `docs/product/dialogue-orchestration-boundary.md` | 对话/编排过桥 |
| `docs/INDEX.md` | 文档索引（先读 §0） |
| `VERSION` / `CHANGELOG.md` | 版本 |
| `STARTUP-BRIEF.md` | Agent 启动（省 token） |
| `README.md` | 对外首页（须与 VISION 一致） |

## 运行时

| 目录 | 状态 |
|------|------|
| `scripts/` | **SSOT** — Engine / Board / Hub / sidecar |
| `scripts/chat_server/` | Hub API + SPA |
| `skills/` | 阶段默认能力包 |
| `desktop/` | Desktop 源码（构建产物 `.build/` 勿提交） |
| `app/` `lib/` `db/` | 浅层附属，非主架构 |

新增编排逻辑改 `scripts/`，不要平行第二条流水线。

已完成 phase 记录 → `docs/archive/hub-shell-phases/`（`docs/product/` 仅留跳转 stub）。
