# 任务卡 hp018 · HP 数据节点就绪：PG backtest 库初始化+首轮回填+增量 cron+备份（OpenCode 执行）

> 关联：INT-075 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-09

## 目标

HP PostgreSQL backtest 数据库完整初始化，首轮历史 K 线回填，增量 cron 自动同步，备份机制落地。

## 红线（先看）

1. 不碰 HP 生产知识库数据（/data/knowledge/）
2. 不修改现有 mcp-server 或 memory-store 配置
3. 备份先手动验证再接入 cron

## 范围

- HP PG：创建 backtest 数据库 + 表 schema
- 首轮回填：CCXT → HP PG（Gate.io 主流交易对，1h K 线）
- 增量 cron：每日自动拉取最新 K 线
- 备份：pg_dump 定时 + 保留策略

## 步骤

1. 验证 HP 环境就绪：venv、psycopg、CCXT、PG 服务
2. 初始化 backtest 数据库和表结构
3. 首轮回填（验证数据量和质量）
4. 增量 cron 脚本 + 调度
5. 备份脚本 + 调度
6. 验收：schema 正确、数据量合理、cron 运行、备份可恢复

## 验收标准

- backtest 库存在，表 schema 与 QuantHive 兼容
- 首轮回填 ≥ 3 个交易对 × 500+ 条 K 线
- 增量 cron 每日自动运行
- pg_dump 备份可恢复验证通过

## 回写要求

完成后更新本卡验收区，Engine 自动回写 INT-075。