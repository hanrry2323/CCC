# 任务卡 ccc088 · 陈旧双索引 docs/dispatch/cards.index.jsonl 清理（DSH 执行）

> 关联：环节②交接(2026-08-25)问题4 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

查明 docs/dispatch/cards.index.jsonl（陈旧，mtime 持续更新）的写入方与读取方；确无合法依赖后移除，消除与 data/cards/cards.index.jsonl 的双写。

## 红线

- 只读排查先行；删除动作仅在确认零读依赖后执行。
- 不改 loader.get_index_path 判定逻辑本身（CCC_DATA_DIR 语义保持）。

## 步骤

1. 写入方定位：全仓 grep 写该路径的代码路径（含 loader pytest 分支、close/approve 工具链在无 CCC_DATA_DIR shell 下的回落）；对 mtime 变化做一次性前后取证。
2. 读取方定位：grep 全仓消费点。
3. 若唯一写手是「工具链裸跑回落」：修复其调用环境说明或在该工具内补 CCC_DATA_DIR 注入；随后删除陈旧文件并复查 24h 不复生。

## 验收标准

- [ ] 写/读依赖结论明确（grep 输出引用）
- [ ] 文件移除后看板显示与权威索引一致
- [ ] 24h 内不复生（回写时可先给即时复核+承诺后续复核）

## 回写要求

- 回写区附依赖矩阵与删除前后对比；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
