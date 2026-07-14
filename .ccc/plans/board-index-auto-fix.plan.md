# Plan: board-index-auto-fix — Patrol 同步 index.json 后检查一致性

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（1016 行单文件，`main()` 按 7 步顺序执行：0-Engine 存活 → 1-扫描 → 2-异常排查 → 3-卡死检测 → 4-持久化 → 5-commit → 6-报告）
- **当前结构要点**：
  1. `_move_task()`（L376-398）通过 `FileBoardStore.move_task()` 移动 task 文件后，紧跟 `store.update_index()` 重新生成 index.json——此函数内部扫描目录重建计数，文件系统状态正确时 index 一定正确
  2. `read_board_index()`（L121-130）故意**绕过** index.json，直接遍历目录统计——patrol 自身的决策不受 index.json 影响，但外部消费者（dashboard、board-server）读取 index.json 可能读到脏数据
  3. `_sync_board_index()`（L106-118）在 `commit_patrol_fix()` 之前再次调用——但无 readback 验证；`ccc-engine.py` 中 `_ensure_task_in_testing()` 调 `move_task()` 而不调 `update_index()`，存在不一致路径
  4. 目前无 read-verify-repair 机制：`update_index()` 跑完不做任何检查就返回
- **待改动点**：
  - `scripts/ccc-patrol-v4.py`：新增 `verify_board_index(ws: Path) -> list[str]` 函数，在 Step 4（状态持久化）完成后、Step 5（commit）前调用，对所有工作区验证 index.json 与目录一致性并自动修复

---

## 范围

- **目标**：Patrol 每次巡检完成后，对所有 workspace 验证 `index.json` 与 board 目录实际内容一致，不一致时自动修复并记录到报告中
- **只改文件**：`["scripts/ccc-patrol-v4.py"]`
- **不改文件**：`["scripts/_board_store.py", "scripts/ccc-engine.py", "scripts/opencode-pool.py", "scripts/ccc-board.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：新增 index.json 一致性校验函数 + main() 中调用

### 做什么

在所有 task 移动操作完成后，对每个 workspace 校验 board 目录下的 `index.json` 是否与实际的 board 子目录文件数一致。不一致时自动调用 `update_index()` 修复，并记录操作到 `all_fix_ops` 和 `warnings`，避免外部消费者读到脏数据。

具体行为：
1. 对每个 workspace，读取 `index.json` 内容
2. 遍历所有 7 列（BOARD_COLS）目录，统计实际 `.jsonl`/`.json` 文件数量（复用现有 `read_board_index()` 逻辑）
3. 对比 index.json 中的计数与实际计数：差值按列输出
4. 不一致 → 追加 `warnings` 项（如 `"CCC:index 不一致 backlog(实际=3 idx=2)"`）
5. 自动调用 `_sync_board_index(ws)` 修复，修复后记录到 `all_fix_ops`
6. index.json 不存在或无法解析时视为"全新不一致"（空 dict vs 实际），同样修复
7. 一致或 ws 无 board 目录时静默跳过（不产生报告噪声）

### 怎么做

**1a. `scripts/ccc-patrol-v4.py`** — 在 `read_board_index()` 函数附近（L130 后、`scan_all_ws()` 前）新增函数：

```python
def verify_board_index(ws: Path) -> list[str]:
    """验证 workspace 的 index.json 与 board 目录一致性，自动修复。

    Args:
        ws: workspace 根路径

    Returns:
        操作描述列表：不一致时返回修复摘要，一致时返回 []
    """
```

实现细节：
- board 路径 = `ws / ".ccc" / "board"`
- 若无 `index.json`，直接返回空列表（首次部署无 index.json 不算异常，后续 patrol 操作会创建）
- 若无 board 目录，返回空列表
- `idx_data = json_load(board / "index.json")`，非 dict 或空则视为空 dict
- 对每列 `c = BOARD_COLS`：
  - 实际数 = `read_board_index(ws).get(c, 0)`
  - index 数 = `idx_data.get(c, 0)`
  - 差 = 实际数 - index 数
  - 差 != 0 → 收集到 `diffs` 列表
- 有 diffs → 构造 warning 格式 `"{ws_name}:index 不一致 {列(实际=N idx=M)}"`，追加到 `repairs`
- 调用 `_sync_board_index(ws)` 修复
- 修复后追加 `"{ws_name}:index 已修复 ({len(diffs)}列不一致)"` 到 `repairs`
- 修复过程 try/except 保护，不抛异常中断 main()

**1b. `scripts/ccc-patrol-v4.py`** — 在 `main()` 中 Step 4（状态持久化）之后、Step 5（commit 前）插入调用。具体位置在 `save_patrol_state()` 调用后（L991）、commit 循环前（L994），新增一个 Step 4.5：

```python
    # ── Step 4.5: index.json 一致性校验 ──
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        repairs = verify_board_index(path)
        if repairs:
            all_fix_ops.extend(repairs)
            # 将描述性的 warning 加入 warnings（如果有 diffs 描述）
            for r in repairs:
                if "不一致" in r:
                    warnings.append(f"{name}:{r}")

```

注意：因为 `_sync_board_index()` 内部直接调 `FileBoardStore(ws).update_index()`，这会走文件系统扫描 + 原子写，无需重复实现 update_index。函数只做"读 index + 对比 + 调用修复"三层，不做文件移动。

### 验收清单

- [ ] 新函数 `verify_board_index(ws: Path) -> list[str]` 存在，位于 `read_board_index()` 附近
- [ ] 函数签名 `def verify_board_index(ws: Path) -> list[str]:`
- [ ] 读取 `index.json` 用现有的 `json_load()` 工具函数，不重新实现文件读取
- [ ] 对比实际文件数用现有的 `read_board_index()`，不重复实现目录遍历
- [ ] 不一致时调用 `_sync_board_index(ws)` 修复
- [ ] 每列比较：实际数从目录遍历 get，index 数从 index.json get，差值非零则收集
- [ ] 无 board 目录或 index.json 不存在时静默返回 `[]`
- [ ] 修复操作 try/except 保护，不抛异常中断 main
- [ ] `main()` 中 Step 4 与 Step 5 之间有循环调用点
- [ ] 调用点将 `repairs` 追加到 `all_fix_ops`
- [ ] 调用点将有 "不一致" 标记的 repair 也追加到 `warnings`
- [ ] `python3 -m compileall -q scripts/ccc-patrol-v4.py` 零错误
- [ ] 所有现有测试通过

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-patrol-v4.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/ccc-patrol-v4.py').read())"` → 无异常
- [函数存在] `grep -n "def verify_board_index" scripts/ccc-patrol-v4.py` → 匹配
- [调用存在] `grep -n "verify_board_index" scripts/ccc-patrol-v4.py` → 至少 2 处（定义 + 调用）
- [复用 read_board_index] `grep -n "read_board_index" scripts/ccc-patrol-v4.py` → 新函数内使用（>=3 处总出现，含已有调用）
- [复用 json_load] `grep "json_load" scripts/ccc-patrol-v4.py` → 新函数内使用
- [修复调 sync] `grep "_sync_board_index" scripts/ccc-patrol-v4.py` → 新函数内调用 + 已有调用（>=2 处）
- [import 无新增] 不引入新 import——json_load/read_board_index/_sync_board_index 都是已有函数
- [报告集成] `grep "index" scripts/ccc-patrol-v4.py` → warnings 包含不一致描述
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过
- [E2E 回归] `python3 -m pytest tests/e2e/ -q --timeout=120`（如可用）→ 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新增 `verify_board_index()` 函数校验 index.json 与目录一致性 + `main()` 中 Step 4.5 调用点 + 报告集成 | `feat(patrol): index.json 一致性校验 + 自动修复 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] 所有验收意图全部达成
- [ ] 新函数复用现有的 `read_board_index()`、`json_load()`、`_sync_board_index()`，只做"读→对比→修复"三层
- [ ] 修复流程有 try/except 保护，不因单 workspace 异常而中断全流程
- [ ] 报告集成：不一致 warning 加入 `warnings`，修复操作加入 `all_fix_ops`，在 patrol 单行报告中可见

---

## 后续步骤

完成此改动后，建议：
- Board Server 和 Cockpit Dashboard 可增加 index.json 一致性指示器
- `ccc-engine.py` 中 `_ensure_task_in_testing()` 路径缺少 `update_index()` 调用，可后续修复
- 长期可在 FileBoardStore 层面增加自动一致性检查（每次 move_task 后自动 verify）