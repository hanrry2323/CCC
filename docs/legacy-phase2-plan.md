# 第二阶段退役执行清单（T15 产出，待放行后执行）

> 依据：`docs/legacy-retirement-list.md`（T12-R 版）· 产出卡：T15 · 日期：2026-08-02
> ⚠️ **本阶段不可执行**，须以下条件全部满足后方可放行：
> 1. 新栈 `server/` 已全部就绪并接管 qb 产线
> 2. 2017 旧引擎停止方案已与 qb 产线确认不影响交易
> 3. 老板/管理席明确放行

---

## 第二阶段处置项

| 项 | 动作 | 放行条件 |
|----|------|----------|
| `scripts/` | 归档 → `docs/archive/legacy-retired-<date>/` | 新栈全部就绪 + 2017 旧引擎停止 |
| `templates/` | 归档 → `docs/archive/legacy-retired-<date>/` | 新栈模板就绪，旧引擎不再引用 |

---

## scripts/ 归档步骤

### 前置确认（执行前必跑）

```bash
# 1. 确认 2017 旧引擎已停止（SSH 到 Mac2017）
ssh mac2017 "ps aux | grep -E 'ccc-engine|ccc-board|ccc-chat' | grep -v grep"
# 期望输出：空（无进程）

# 2. 确认 2017 launchd 已卸载
ssh mac2017 "launchctl list | grep ccc"
# 期望输出：空（无 ccc 服务）

# 3. 确认 2017 ~/.ccc/control.json 已降为 disabled
ssh mac2017 "cat ~/.ccc/control.json | grep mode"
# 期望输出："mode": "disabled"

# 4. 确认新栈已运行
python3 -m server.engine.main --config server/config/config.env --once
# 期望输出：退出码 0，JSON 统计正常
python3 -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js
# 期望输出：exported N cards -> server/web/data/board.js

# 5. 确认 qb 产线引用路径已切换（检查 qb 仓 .ccc/plans/ 中无 scripts/ 引用）
ssh mac2017 "grep -r 'scripts/ccc' ~/program/apps/qb/.ccc/plans/ | head -5"
# 期望输出：空（已全部切换到 server/ 新栈命令）
```

### 执行步骤

```bash
# 切换到项目根
cd /Users/apple/program/CCC

# 创建归档目录
ARCHIVE_DATE=$(date +%Y-%m-%d)
mkdir -p "docs/archive/legacy-retired-${ARCHIVE_DATE}"

# git mv scripts/ → 归档
git mv scripts/ "docs/archive/legacy-retired-${ARCHIVE_DATE}/scripts/"

# git mv templates/ → 归档
git mv templates/ "docs/archive/legacy-retired-${ARCHIVE_DATE}/templates/"

# 更新退役清单标记第二阶段完成
# 编辑 docs/legacy-retirement-list.md，将第二阶段项标记为 ✅ 已完成

# 提交
git add -A
git commit -m "chore(retire): phase 2 — archive scripts/ and templates/"

# 验证
git status  # 期望 clean
python3 -m pytest server/tests/ -q --tb=short  # 期望无回归
```

---

## 2017 旧引擎停止/切换步骤

### 停止旧引擎（SSH 到 Mac2017）

```bash
# SSH 到 Mac2017
ssh mac2017

# 1. 卸载 launchd plist
launchctl bootout gui/$(id -u)/com.ccc.engine
launchctl bootout gui/$(id -u)/com.ccc.board
launchctl bootout gui/$(id -u)/com.ccc.chat-server

# 2. 确认进程已停止
ps aux | grep -E 'ccc-engine|ccc-board|ccc-chat' | grep -v grep
# 期望输出：空

# 3. 备份并降级 control.json
cp ~/.ccc/control.json ~/.ccc/control.json.bak-$(date +%Y%m%d)
# 编辑 control.json 将 mode 改为 "disabled"

# 4. 停止 6100 planner（如确认不再需要）
kill 69311  # 验证 PID 后执行
```

### 切换 qb 产线引用（SSH 到 Mac2017）

```bash
# qb 仓的 .ccc/plans/ 中所有 scripts/ 路径需切换到 server/ 新栈命令
# 影响范围：
#   - scripts/ccc-hub-lens.py → server/board/hub_lens.py（或 server/ 等价命令）
#   - scripts/ccc-mind-update.py → server/ 等价命令
#   - scripts/ccc-board.py index → server.board.export 等价命令

# 具体命令待新栈完全就绪后确定
# 本清单仅记录替换范围，不执行替换
```

---

## 回滚方案

### 回滚条件

以下任一情况触发回滚：
1. 归档后 `server/` 测试失败（pytest 非全绿）
2. 2017 旧引擎停止后 qb 产线异常
3. `board.js` 导出后看板数据异常
4. 老板/管理席要求回滚

### 回滚步骤

```bash
# 1. 恢复 scripts/ 和 templates/（如已归档）
cd /Users/apple/program/CCC
ARCHIVE_DIR="docs/archive/legacy-retired-$(date +%Y-%m-%d)"
git mv "${ARCHIVE_DIR}/scripts/" scripts/
git mv "${ARCHIVE_DIR}/templates/" templates/
git commit -m "chore(retire): rollback phase 2 — restore scripts/ and templates/"

# 2. 恢复 2017 旧引擎
ssh mac2017 "
  cp ~/.ccc/control.json.bak-* ~/.ccc/control.json
  launchctl bootstrap gui/$(id -u)/com.ccc.engine
  launchctl bootstrap gui/$(id -u)/com.ccc.board
  launchctl bootstrap gui/$(id -u)/com.ccc.chat-server
"

# 3. 恢复 qb 产线引用
# 从 git 历史恢复 .ccc/plans/ 中的旧引用路径
# git checkout HEAD~1 -- .ccc/plans/*.plan.md  # 仅恢复引用路径

# 4. 验证恢复
python3 -m pytest server/tests/ -q --tb=short
ssh mac2017 "ps aux | grep ccc-engine"  # 期望有进程
```

### 回滚确认命令

```bash
# 确认 scripts/ 已恢复
ls scripts/ccc-engine.py  # 期望存在

# 确认 2017 引擎已恢复
ssh mac2017 "ps aux | grep ccc-engine | grep -v grep | wc -l"
# 期望输出 ≥ 1

# 确认看板正常
python3 -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js
# 期望输出：exported N cards -> server/web/data/board.js
```

---

## 放行条件汇总

1. ✅ **新栈 `server/` 全部就绪**（T1–T14 已验收）
2. ❌ **2017 旧引擎停止**（需确认 qb 产线可切换）
3. ❌ **qb 产线引用路径切换**（从 `scripts/` 到 `server/`）
4. ❌ **老板/管理席放行**
5. ❌ **`relay/dist/` 清理**（第一阶段待执行项）

只有全部条件满足后，方可执行本清单的 `scripts/` 归档步骤。