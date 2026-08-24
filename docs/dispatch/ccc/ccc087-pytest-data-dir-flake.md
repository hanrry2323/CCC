# 任务卡 ccc087 · pytest 单实例锁夹具去共享——消 test_once_smoke 偶发失败（DSH 执行）

> 关联：环节②交接(2026-08-25)问题3 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

server/tests/test_engine_main.py _write_env 默认 DATA_DIR=/tmp/ccc2/data 为同文件多测试共享，engine.lock 偶发 BlockingIOError/SystemExit(2) 造成 test_once_smoke 间歇失败。改夹具为每测试唯一 DATA_DIR。

## 红线

- 白名单：server/tests/test_engine_main.py（必要时 conftest.py）。
- 不改单实例锁生产逻辑。

## 步骤

1. _write_env 默认值改为基于 tmp_path 的唯一目录（保留 overrides 覆盖能力，供锁竞争专项测试显式传同路径）。
2. 自测：连续全量 server/tests ×3，0 次 test_once_smoke 及相关锁类 flake。

## 验收标准

- [ ] 连续三轮全量 pytest 零该 flake（附三轮尾部输出）
- [ ] 显式传同 DATA_DIR 的锁竞争测试（如有）仍有效

## 回写要求

- 回写区附三轮输出与 diff；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
