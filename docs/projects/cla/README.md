# cla

## 是什么

ClawMed-CCC（药械采销情报系统）：从政府药械招采网与 B2B 电商采集药品价格，经清洗/机会挖掘/合规审核后向客户推送降价预警与营销话术。全程零 CCC 运行时依赖（纯 Python + sqlite3 自研调度）。

## 路径

| 机 | 路径 |
|----|------|
| M1 | **无**本机代码（勿在 M1 假装有本体） |
| Mac2017 | `/Users/fan/program/apps/clawmed-ccc`（SMB: `/Volumes/fan/program/apps/clawmed-ccc`） |

## 在 CCC 怎么动

- **前缀**：`cla` → `docs/dispatch/cla/`
- **taskable**：是（engine 自动派发，max_concurrent=1）
- **出卡**：`scripts/new-card.sh --project cla --title "..." --depends "卡ID列表"`；执行 cwd 写在卡内（2017 apps/clawmed-ccc）

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 cla） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 cla） |
| 项目档案（本页） | docs/projects/cla/README.md |
| 方案文件 | docs/projects/cla/plans/ |
| 里程碑 | docs/projects/cla/roadmap.md |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |
| 开发蓝图 | 业务仓 docs/development-blueprint-2026-08-18.md |

## 当前状态

- M1 SQLite 底座已落地（队列/账本/闪退恢复）
- M2 gov 爬虫（四川药械）执行中；M3-M5 按依赖链推进
- 红线：开发禁 mock 假数据；凭证真值只进 .env；前端静态 SPA 由 FastAPI 一体化挂载
