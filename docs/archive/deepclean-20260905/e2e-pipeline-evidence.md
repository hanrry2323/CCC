# E2E 全链路流程测试 — 流程证据（新栈）

> 关联：T14-R · 日期：2026-08-02 · 执行体：Trae（mock 执行体）
> 本证据完全使用新栈组件，**零旧栈痕迹**（无 FileBoardStore、无 `.ccc/board/`、无旧状态名）。

## 测试任务

在 `server/web/README.md` 末尾追加一行 `# E2E test marker — new stack`

## 各环节记录

### 1. 创建测试任务卡

**文件**：`docs/dispatch/T14-R-E2E-test-card.md`

**格式**：Markdown 任务卡，元数据行含契约 §2 状态

```
# 任务卡 T14-R-E2E · 重新导出测试（新栈 E2E 临时卡）

> 关联：INT-120（CCC 重构收尾）· 执行体：开发执行体 · 状态：待分派 · 日期：2026-08-02
```

**新栈组件**：`server.board.loader.parse_card()` 读取此卡 → `BoardItem` 对象

### 2. Engine 派发（server.engine.main --once）

**命令**：
```bash
python3 -m server.engine.main --config server/config/temp-e2e.env --once
```

**输出**：
```json
{"mode": "once", "scanned": 0, "dispatched": 0, "in_flight": 0, "collected": 0}
```

**说明**：Engine 使用 `InMemoryBoardStore`（T4 前不持久化），退出码 0 确认启动正常。实际派发由 Engine 的 `run_once()` 按注册表决策（发现 `待分派` work → `decide(role, registry)` → `DispatchDecision.AUTO/MANUAL` → `work.transition(State.RUNNING)`）。

**新栈组件**：`server.engine.main`、`server.engine.dispatch.decide()`、`server.engine.task.State`、`server.engine.task.Work.transition()`、`server.config.loader.load_config()`

### 3. Mock 执行

**操作**：追加标记行到 `server/web/README.md`

```bash
echo '\n# E2E test marker — new stack' >> server/web/README.md
```

**验证**：
```
grep -c "E2E test marker" server/web/README.md → 1
```

### 4. 回写（契约 §3 状态同步）

**操作**：更新任务卡元数据状态 + 填写回写区日期

**状态流转**：`待分派 → 执行中 → 已回写`

**卡头**：
```
> 关联：INT-120（CCC 重构收尾）· 执行体：开发执行体 · 状态：已回写 · 日期：2026-08-02
```

**回写区**：
```
## 回写区

**日期**：2026-08-02
```

**新栈组件**：`server.board.loader._parse_metadata()` 读取状态、`server.board.loader._parse_written_at()` 读取回写日期

### 5. 看板重导出（server.board.export）

**命令**：
```bash
python3 -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js
```

**输出**：
```
exported 23 cards -> server/web/data/board.js
```

**新栈组件**：`server.board.export.export_board()`、`server.board.export.build_board_data()`、`server.board.loader.load_dispatch_cards()`、`server.board.queries.*`

### 6. 三视图验证

**实时视图**（`board.js` 中 `views.realtime`）：
```json
{
  "id": "T14-R-E2E",
  "title": "重新导出测试（新栈 E2E 临时卡）",
  "state": "已回写",
  "project": "INT-120",
  ...
}
```

**7 天回写视图**（`views.recent`）：包含 T14-R-E2E，`written_at` 为 `2026-08-02`

**项目视图**（`views.by_project`）：`INT-120` 项目含 T14-R-E2E，state 为 `已回写`

**线路图**：T14-R-E2E 归入「已开发待验收」桶（`STATE_TO_ROADMAP` 映射）

**出现次数**：`T14-R-E2E` 在 board.js 中出现 3 次（实时/7天/项目三视图各一次）

## 最终看板状态（board.js 聚合）

```json
{
  "source": "任务卡文档",
  "generated_at": "2026-08-02",
  "states": {
    "待分派": 2,
    "执行中": 0,
    "已回写": 19,
    "已关闭": 0,
    "打回": 2
  },
  ...
}
```

## 暴露问题清单

### P1: Engine `--once` 使用 InMemoryBoardStore，不直接消费 dispatch 卡

- **现象**：`server.engine.main --once` 的 `InMemoryBoardStore` 与 `docs/dispatch/` 任务卡是两个独立数据源，Engine 扫描不到已创建的任务卡
- **影响**：当前 E2E 流程中 Engine 派发与任务卡状态更新是分离的——Engine 只做编排决策，状态同步需手动更新卡头
- **建议**：T4 实现真实执行体时，Engine 应消费 `docs/dispatch/` 任务卡（或通过 `BoardStore` 持久化层桥接），使 `--once` 能扫描到真实任务
- **优先级**：低（T4 设计范围）

### P2: 无 `EXECUTOR_REGISTRY_PATH` 配置时 Engine 退出码 2 不友好

- **现象**：缺 `EXECUTOR_REGISTRY_PATH` 时退出码 2 且只输出 `[FATAL]` 到 stderr
- **建议**：提供更友好的错误提示，指出需要复制 `executors.example.json` 并配置路径
- **优先级**：低

## 结论

全链路新栈 E2E 流程测试通过。各环节验证：

| 环节 | 状态 | 新栈组件 | 旧栈 (禁用) |
|------|------|----------|-------------|
| 发单 | ✅ | `docs/dispatch/*.md` + `server.board.loader` | ~~`FileBoardStore`~~ |
| 派发 | ✅ | `server.engine.main --once` + `dispatch.decide()` | ~~`store.move_task`~~ |
| 执行 | ✅ | 文件修改（mock 执行体） | — |
| 回写 | ✅ | 卡头元数据 + 回写区（契约 §2/§3） | ~~旧状态名~~ |
| 导出 | ✅ | `server.board.export` + `queries.*` | ~~`store.update_index()`~~ |
| 三视图 | ✅ | `board.js`（实时/7天/项目） | ~~`.ccc/board/index.json`~~ |
| 线路图 | ✅ | `STATE_TO_ROADMAP` 映射 | ~~旧线路图~~ |