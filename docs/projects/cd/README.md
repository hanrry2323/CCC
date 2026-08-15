# ccc-demo（前缀 cd）

## 是什么

CCC 演示/验证项目：跑通「注册 → 方案 → 出卡 → 派发 → 验收 → 合入」全流程的演示仓（2016-08-09 起正式注册为 taskable）。

> **⚠️ 已废除（2026-08-15）**：演示使命已完成，封版归档，不再出卡（registry `status: archived` / `taskable: false`）。

## 路径

| 机 | 路径 |
|----|------|
| M1 | 无 |
| Mac2017 | `/Users/fan/program/apps/ccc-demo` |

## 在 CCC 怎么动

- **前缀**：`cd` → `docs/dispatch/cd/`
- **taskable**：是（演示用途，不承载生产业务）
- **出卡**：`scripts/new-card.sh --project cd --title "..."`

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 cd） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 cd） |
| 项目档案（本页） | docs/projects/cd/README.md |
| 方案文件 | docs/projects/cd/plans/ |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |

## 线路 / 近况

- 2026-08-09 由 catalog 升级为正式档案；无卡无方案（占位）

## 禁区

- 演示项目不建生产依赖、不挂生产数据
