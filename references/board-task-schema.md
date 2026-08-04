# CCC Board Protocol v2 — 任务卡文档流 + 派生看板（现行）

> 状态：现行（2026-08-04 重写，对齐代码现状）。旧 v1.2「6+1 列 jsonl + epic/work 扇出」流程已于 2026-08-02 重构取消，全文见 git 历史（本文件上一版本）。
> 关联：契约 §1–§4（任务卡格式/状态机/回写/看板数据模型）· 实现：`server/board/loader.py`、`server/board/queries.py`、`server/board/export.py`、`server/engine/`。

## 一、任务卡 = 唯一事实源

任务卡是 `docs/dispatch/T<序号>-<slug>.md` 的 Markdown 文档。**没有独立待办库**；看板是派生视图，不存数据、不做决策。

### 卡结构

```markdown
# 任务卡 T46 · 标题（执行体名执行）

> 关联：项目/意图 · 执行体：X · 验收：Codex · 状态：待分派 · 日期：YYYY-MM-DD

## 目标
一句话，可验收。

## 红线（先看）
1. ...

## 范围
...

## 步骤
...

## 验收标准
...

## 回写要求
卡头状态更新为「已回写」；回写区填 ...

## 回写区
**执行体**：X · 日期：
```

卡头 `>` 元数据行为 `key：value` 以 `·` 分隔（关联/执行体/验收/状态/日期）；`server/board/loader.py` 正则解析。

## 二、状态机（契约 §2，五态）

```text
待分派 → 执行中 → 已回写 → 已关闭
   │        │
   └── 打回（附问题清单）──→ 待分派/执行中（重派）
```

- 非法状态转移抛 `IllegalTransitionError`（`server/engine/task.py`）。
- 状态唯一事实 = 卡头 `状态：X` 行；看板/卡流以它为源。

## 三、执行体注册表（契约 §7）

`server/config/executors.json`：五角色（开发/维护/管理/验收/…），分类只允许「可后台 CLI / 手动 GUI / —」。

- 可后台 CLI（OpenCode/Claude Code）→ Engine 自动拉起（命令+参数模板来自注册表，零硬编码）；
- 手动 GUI（Trae）→ 挂起等人；
- 管理/验收席（Codex）→ 不派发。
- 派发决策按**卡头执行体绑定优先**（`decide_work`，T39）。

## 四、Engine 驱动（server/engine/）

1. `FileBoardStore` 扫 `docs/dispatch/*.md` → 解析卡头 → `Work`；
2. `decide_work` 决策：AUTO 真实 `subprocess.Popen`（超时/退出码判定）；MANUAL 挂起；
3. 收单：退出码 0 → 已回写；非 0/超时/启动失败 → 打回附原因；
4. `save_work` 原子回写卡头 `状态` 行（tmp + os.replace）。

## 五、看板 = 派生视图（server/board/）

- `loader.py`：正则扫卡 → `BoardItem`；
- `queries.py`：实时 / 7 天 / 按项目 + 线路图聚合；
- `export.py`：导出 `server/web/data/board.js`；HTTP API `/board/*` 同源。
- 看板只读，禁止手工改看板覆盖任务卡。

## 六、回写协议（契约 §3）

- 执行体完成后：卡头 `状态` 改「已回写」+ 回写区填结果/证据/commit/push 证据；
- 验收席验收后改「已关闭」；打回改「打回」并附问题清单。

## 七、历史（重构前，仅供追溯）

旧 v1.2：`backlog/planned/in_progress/released/abnormal` 6+1 列 jsonl + epic/work 扇出 + 复杂度分流 + 角色分层（Planner/Verifier）。已于 2026-08-02 重构取消；旧数据归档于 `docs/archive/ccc-legacy-2026-08-02/ccc-roleflow-legacy/`。
