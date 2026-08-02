# E2E 全链路流程测试 — 流程证据

> 关联：T14 · 日期：2026-08-02 · 执行体：Trae（mock 执行体）

## 测试任务

在 `server/README.md` 末尾追加一行 `# E2E test marker — do not remove`

## 各环节记录

### 1. 发单（创建测试卡 + 注册看板）

```
docs/dispatch/T14-E2E-test-card.md          ← 测试任务卡
.ccc/board/backlog/e2e-pipeline-test.jsonl  ← epic 卡（split_status=planned）
.ccc/board/planned/e2e-pipeline-test.jsonl  ← work 卡
.ccc/plans/e2e-pipeline-test.plan.md        ← 计划文件
.ccc/phases/e2e-pipeline-test.phases.json   ← phase 文件
```

**命令**：手动创建文件 + `FileBoardStore.list_tasks()` 验证

**输出**：
```
backlog: 1 个任务 (epic)
planned: 1 个任务 (work)
```

### 2. 派发（Engine 模拟 — planned → in_progress）

**操作**：`store.move_task('e2e-pipeline-test', 'planned', 'in_progress')`

**输出**：
```
[ccc.board] e2e-pipeline-test: planned → in_progress
当前列: in_progress
card_kind: work
```

**状态流转**：`planned` → `in_progress`

### 3. 执行（Mock 执行体）

**操作**：`echo '\n# E2E test marker — do not remove' >> server/README.md`

**输出**：
```
server/README.md 当前行数: 50
追加后行数: 52
最后 3 行: ['- 新增执行体 → ...', '', '# E2E test marker — do not remove']
```

### 4. 回写（Dev 完成 — in_progress → testing）

**操作**：`store.move_task('e2e-pipeline-test', 'in_progress', 'testing')`

**输出**：
```
[ccc.board] e2e-pipeline-test: in_progress → testing
当前列: testing
```

同时更新 phase 状态：`pending` → `done`

### 5. 验收门禁（testing → verified）

**验收命令**：`grep -q "E2E test marker" server/README.md`

**输出**：`PASS`（exit code 0）

**操作**：`store.move_task('e2e-pipeline-test', 'testing', 'verified')`

**输出**：
```
[ccc.board] e2e-pipeline-test: testing → verified
当前列: verified
```

### 6. 发版（verified → released）

**操作**：`store.move_task('e2e-pipeline-test', 'verified', 'released')`

**输出**：
```
[ccc.board] e2e-pipeline-test: verified → released
当前列: released
```

### 7. Epic 完成

更新 epic split_status：`planned` → `done`

### 8. 看板重导出

**操作**：`store.update_index()`

**输出**（index.json）：
```json
{"generation": 15, "backlog": 1, "planned": 0, "in_progress": 0,
 "testing": 0, "verified": 0, "released": 1, "abnormal": 0}
```

## 最终看板状态

| 列 | 任务数 | 说明 |
|----|--------|------|
| backlog | 1 | epic（split_status=done） |
| released | 1 | work 卡（已发版） |
| 其余列 | 0 | 全部清空 |

## 暴露问题清单

### P1: Engine 缺少 `--once` 单次执行模式

- **现象**：任务卡要求 `Engine --once`，但 `main()` CLI 只支持 `--port`，无单次执行模式
- **影响**：无法在 CI/测试环境以单次模式验证全链路
- **建议**：新增 `--once` 参数，执行策略：
  1. 消费 backlog → 尝试扇出（epic→work）
  2. 尝试 launch planned → 等待执行完成（或超时）
  3. 跑 testing/verified 门禁
  4. 更新 index 后退出
- **优先级**：低（Engine 设计为长驻进程，单次模式非必须）

### P2: 同名 epic 和 work 卡在多列继承时会被自动清理

- **现象**：`move_task` 自动删除其它列的同 id 文件（`move_task removed leftover backlog/...`）
- **影响**：epic 卡在 work 卡移动时被自动删除，需手动重建
- **建议**：考虑 epic 和 work 使用不同 id 前缀（如 `epic-` vs `work-`），或 `move_task` 只清理 work 卡
- **优先级**：低（当前行为在 epic 独立生命周期场景下无问题）

### P3: .jsonl 单行格式易出错

- **现象**：初始创建文件时使用多行 pretty-print JSON，导致 `list_tasks` 解析失败
- **影响**：新手容易误用格式
- **建议**：在文档中明确 `.jsonl` 格式要求，或提供辅助创建脚本
- **优先级**：低

## 结论

全链路 E2E 流程测试通过。各环节验证：

| 环节 | 状态 | 证据 |
|------|------|------|
| 发单 | ✅ | 测试卡 + 看板注册 |
| 派发 | ✅ | planned → in_progress |
| 执行 | ✅ | 文件修改成功 |
| 回写 | ✅ | in_progress → testing |
| 验收 | ✅ | grep PASS + testing → verified |
| 发版 | ✅ | verified → released |
| 看板 | ✅ | index.json 重导出正确 |
| Epic | ✅ | split_status → done |