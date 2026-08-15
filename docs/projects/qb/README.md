# qb

## 是什么

CCC 自动化开发测试用业务仓（挂 Engine 出卡）。

## 路径

| 机 | 路径 |
|----|------|
| M1 | **无**本机代码（勿用 `/Users/apple/program/projects/qb/`） |
| Mac2017 | `/Users/fan/program/apps/qb`（SMB: `/Volumes/fan/program/apps/qb`） |

## 在 CCC 怎么动

- **前缀**：`qb` → `docs/dispatch/qb/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project qb --title "..."`；执行 cwd 写在卡内（2017 apps/qb）

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 qb） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 qb） |
| 项目档案（本页） | docs/projects/qb/README.md |
| 方案文件 | docs/projects/qb/plans/ |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |


## 线路 / 近况

- 档案以外业务深文写在 qb 仓，不在 CCC 复制
- 近况见看板 `项目=qb` 未关闭卡

## 禁区

- 禁止在 CCC 建 `docs/qb/` 深文档树
- 禁止把 M1 错误路径当工作区
