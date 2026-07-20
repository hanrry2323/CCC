# Hub-Shell Phase10 — xianyu 仓卫生

> 日期：2026-07-21 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) Wave4 · 解锁 Phase11

## 选择

| 项 | 值 |
|----|-----|
| 仓 | **xianyu**（2017 `~/program/apps/xianyu`） |
| 问题 | porcelain ~338（332 删除 + 少量 M）；空列与 `index.json` 计数不一致 |
| 处理 | 提交磁盘已删的陈旧 `.ccc` 产物；重建空板 `index.json` |
| xianyu commit | `625e317` `chore(xianyu): phase10 workspace hygiene for hub-shell` |
| 残留 | 仅 `?? .ccc/_pre_migration_artifacts/`（不入库） |

## 验收

| 断言 | 结果 |
|------|------|
| doctor xianyu OK | 绿 |
| porcelain 可控 | 绿（1 untracked 归档目录） |
| board index 与空列一致 | 绿（全 0） |
| 可写 `.ccc/flow-smoke.md` 烟测 | 就绪（Phase11） |

## 部署注记

2017 同步 CCC 时须含 **`templates/`**（见 [`../deploy/desktop.md`](../deploy/desktop.md)），否则 product 扇出会因缺 plan 模板卡住。
