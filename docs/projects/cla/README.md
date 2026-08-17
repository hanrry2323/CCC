# ClawMed-CCC

## 是什么

ClawMed-CCC 是一个医药分布式决策调度平台，采用智能规划调度、SQLite持久化账本以及本地/在线LLM双轨决策链路，专门服务于挂网价格监控、电商竞价、合规初审以及营销机会话术推送。

## 路径

| 机 | 路径 |
|---|---|
| Mac2017 | `/Users/fan/program/apps/clawmed-ccc` |

## 在 CCC 怎么动

- **前缀**：`cla` → `docs/dispatch/cla/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project cla --title "..."`
- **技术栈**：Python 3.12+ (SQLite3 / httpx / pytest)

## 里程碑与近况

- **M1 · 独立底座与路径清零**：SQLite 乐观锁任务队列持久化已重构合入。
- **M3 · LLM 双轨适配器**：本地 Ollama ↔ 在线 API 配置层与用量控制已闭环交付 (cla018)，支持 100% 配置热切换、自动降级与每日限额。
