# Plan: qb-index-json-init — qb 看板 index.json 初始化/校验

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`/Users/apple/program/projects/qb/.ccc/board/index.json`
- **当前结构要点**：
  1. qb `.ccc/board/` 当前已有 index.json（124 字节），内容：`backlog: 20, planned: 1, in_progress: 0, testing: 0, verified: 0, released: 42, abnormal: 0`
  2. qb 看板 7 列实际文件数与 index.json 计数完全一致（已验证）
  3. qb 看板还包含非标准目录 `events/`、`plans/`、`on-hold/` —— 这些不在 `_BOARD_COLUMNS`（ccc-engine.py:252-260）定义中，index.json 不需要也不能包含，否则 Engine 解析会出问题
  4. CCC Engine 启动时首次加载 qb workspace 会读 board/index.json 来了解各列积压状态（ccc-engine.py:279）；`install-ccc-roles.sh:44-46` 在 index.json 缺失时写入默认 0 值
  5. `ccc-patrol-v4.py:98-99` 在 patrol scan 时读 index.json；若缺失则 `json_load` 返回 None，后续 `scan_all_ws` 容忍无 index.json 情况但日志警告
- **待改动点**：
  - 若 index.json 不存在 → 创建；若存在但计数不准 → 修正；若已正确 → 无需改动

---

## 范围

- **目标**：确保 qb `.ccc/board/index.json` 存在且包含准确的 7 列 task 计数，使 Engine 可以正常读取 qb 看板
- **只改文件**：`/Users/apple/program/projects/qb/.ccc/board/index.json`
- **不改文件**：CCC 本体任何脚本、qb 业务代码、看板 task JSONL 文件
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：校验/创建 qb index.json

### 做什么

确保 qb 看板的 index.json 存在且 7 列计数与磁盘实际 task 文件数一致。

当前 index.json 已存在且计数正确（所有列偏差为 0），因此本 task 的 dev 执行以 **验证通过** 即完成。若将来 index.json 缺失或偏差，此 plan 覆盖的自动化逻辑依然可以回收。

### 怎么做

**步骤 1：检查 index.json 是否存在**

目标路径：`/Users/apple/program/projects/qb/.ccc/board/index.json`

- 存在 → 读取并解析 JSON
- 不存在 → 创建初始文件，所有列设为 0

**步骤 2：逐列比对计数**

CCC 标准 7 列（与 `_BOARD_COLUMNS` 一致）：
```
backlog planned in_progress testing verified released abnormal
```

比对方式 — 对每列：
1. `ls -1 <column_dir>/ | grep -c '\.jsonl$'`（只算 `.jsonl` 文件，跳过 `.gitkeep`、`.` 文件）
2. 与 index.json 对应值比较
3. 偏差 > 0 时修正

非标准目录（`events/`、`plans/`、`on-hold/`）不入 index.json。

**步骤 3：写入修正**

使用 `python3` 写入（确保 JSON 格式正确），不依赖 shell `echo`。不覆盖已有文件内容中可能存在的未知字段（如果有的话），只修正 7 列计数。

**步骤 4：验证结果**

- `python3 -c "import json; json.load(open('...'))"` — 合法 JSON
- 7 列值均为非负整数
- `cat index.json | jq .` — 可读格式

### 验收清单

- [ ] 验收条件 1：index.json 是合法 JSON（7 个键值对的扁平 dict）
- [ ] 验收条件 2：7 列值与 `ls <列>/*.jsonl | wc -l` 完全一致
- [ ] 验收条件 3：非标准目录（events/、plans/、on-hold/）不在 index.json 中
- [ ] 边界场景：空目录（testing/、verified/、in_progress/）→ 计数为 0
- [ ] 错误处理：某列目录不存在 → 计数为 0，不抛异常
- [ ] 安全相关：无。只读/写 JSON 文件，不执行任务

### 验收

- [JSON 合法性] `python3 -c "import json; d=json.load(open('/Users/apple/program/projects/qb/.ccc/board/index.json')); assert set(d.keys()) == {'backlog','planned','in_progress','testing','verified','released','abnormal'}"` 无异常
- [计数一致性] `python3 -c "
import json,pathlib
d=json.load(open('/Users/apple/program/projects/qb/.ccc/board/index.json'))
for col in ['backlog','planned','in_progress','testing','verified','released','abnormal']:
    cnt=len(list(pathlib.Path(f'/Users/apple/program/projects/qb/.ccc/board/{col}').glob('*.jsonl')))
    assert d[col]==cnt, f'{col}: expected {cnt}, got {d[col]}'
print('ALL MATCH')
"` 输出 `ALL MATCH`
- [非标准目录不包含] `python3 -c "import json; d=json.load(open('/Users/apple/program/projects/qb/.ccc/board/index.json')); assert 'events' not in d; assert 'plans' not in d; assert 'on-hold' not in d"` 无异常

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 校验/创建 qb 看板 index.json（7 列计数与磁盘一致） | `chore(qb): 初始化/校验 .ccc/board/index.json (phase 1/1)` |

---

## 全局验收清单

- [ ] index.json 是合法 JSON（`python3 -c "import json; json.load(...)"` 无异常）
- [ ] 7 列计数与磁盘文件数完全一致
- [ ] diff 范围仅限 qb 的 index.json
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

当前 index.json 已正确，dev 阶段以验证通过即完成。若将来 qb 看板有 task 增删变动，`ccc-board.py:197` 的 `update_index()` 或 `board-reconcile.py` 会自动同步，此 `index.json` 无需手工维护。