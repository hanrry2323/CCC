# CCC

## 是什么

自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。

## 路径

| 机 | 路径 | 职责 |
|----|------|------|
| M1（中枢） | `/Users/apple/program/CCC` | 中枢出卡/验收/合入/看板 + 轻量开发 |
| Mac2017（生产与执行） | `/Users/fan/program/CCC` | 执行写码节点（engine worktree） + 生产 :7788 |

## 在 CCC 怎么动

- **前缀**：`ccc` → 卡在 `docs/dispatch/ccc/`
- **taskable**：是（平台自身开发）
- **出卡**：`scripts/new-card.sh --project ccc --title "..."`
- **共享库**：`scripts/lib/`（resolve_card 等命令共享函数，勿在脚本内重复 `find | head -1` 猜卡）
- **出卡前了解**：按 [`../../product/hub-context-sop.md`](../../product/hub-context-sop.md) **本仓本地**读码/图谱/看板即可，**无需 ssh**

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 ccc） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 ccc） |
| 项目档案（本页） | docs/projects/ccc/README.md |
| 方案文件 | docs/projects/ccc/plans/ |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |


## 线路 / 近况

- 北星：[`docs/roadmap.md`](../../roadmap.md)「当前方向」
- 挂账：文档与项目注册统一治理；任务卡退役/高效管理
- 规范：[`docs/DOC-PROTOCOL.md`](../../DOC-PROTOCOL.md)

## 禁区

- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed
