# 任务卡 T14-R-E2E · 重新导出测试（新栈 E2E 临时卡）

> 关联：INT-120（CCC 重构收尾）· 执行体：开发执行体 · 状态：已回写 · 日期：2026-08-02

## 目标

在 `server/web/README.md` 末尾追加一行 `# E2E test marker — new stack`，验证新栈全链路。

## 范围

- 只改：`server/web/README.md`
- 只读使用：`server/engine/main.py --once`、`server/board/export.py`

## 步骤

1. `server/engine/main --once` 派发
2. Mock 执行体追加标记行 + 更新卡头状态为执行中
3. Mock 回写：更新卡头状态为已回写 + 填写回写区日期
4. `server.board.export` 重导出
5. 验证 `board.js` 三视图/线路图包含本任务

## 验收

- `server/engine/main --once` 输出 JSON 统计含 scanned ≥ 1
- `server/web/README.md` 末尾含 `# E2E test marker — new stack`
- `board.js` 三视图/线路图含本任务，状态为已回写

## 回写区

**日期**：2026-08-02

（T14-R 临时测试卡，保留不删除，已回写）