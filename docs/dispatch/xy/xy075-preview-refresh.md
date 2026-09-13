# 任务卡 xy075 · 6.3 预览页补实时刷新+导航入口

> 关联：xy-plan-009（6.3 视频/图文预览页面）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy075 · 状态版本：2
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标
xy009 6.3「预览页面」补两处缺口（plan 卡要求=页面实时展示当日产出）：
1. `admin/pages/preview.html` 加定时轮询（默认 15s 刷新 /api/v1/library，页面停留自动更新，无需手动 reload；失败静默降级不打断）。
2. `admin/index.html` 首页导航加「预览」入口（指向 preview.html），让老板从 admin 首页可直达当日视频/图文。

## 实现要求
1. preview.html：加 `setInterval` 轮询数据渲染函数；首次加载+每 15s 重拉 `/api/v1/library` 更新列表；fetch 失败静默（console 记一笔，不白屏不改 UI）。
2. index.html：导航区补 entry（按钮/链接指向 `preview.html`），与其他页样式一致。
3. 补前端存在性测试（照 `tests/admin/test_workflow_page.py` 先例：导航含 entry + 页面含轮询标记），自测全绿。
4. **方案关联卡登记（Q1 前置，模板纪律第5条）**：同 commit 把 xy075 追加进 `docs/projects/xy/plans/009-frontend-showcase.md` 头部「关联卡」清单（行尾顿号分隔、先 grep 核实实际行再 replace）。

## 红线
1. 只动 xianyu 业务仓：`admin/pages/preview.html`、`admin/index.html`、测试文件；009 的在 CCC 仓单独提交。
2. 不动 `/api/v1/library` 后端、不碰 M7/Cookie/发布、不改其他页。
3. diff 全检查：≤3 文件、每文件小改。

## 范围
- /Users/fan/program/apps/xianyu/admin/pages/preview.html
- /Users/fan/program/apps/xianyu/admin/index.html
- /Users/fan/program/apps/xianyu/tests/admin

## 步骤
1. 读 preview.html 结构+index.html 导航区。
2. preview.html 加轮询；index.html 加入口。
3. 补测试；跑 `pytest tests/admin/ -q` 全绿（基线 106 passed 不降）。
4. 009 关联卡补 xy075（grep 实际行后 replace）。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. preview.html 含轮询标记（grep setInterval 命中）+ 15s 间隔代码。
2. index.html 含 `preview.html` 导航 entry。
3. `pytest tests/admin/ -q` 无新失败（比基线持平或更高）。
4. 009「关联卡」行含 xy075。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围路径在仓内存在）——卡满足；exposed 后端零改动。

## 回写要求
- 回写区四问逐项填；教训沉淀引用业务仓 docs/lessons.md 具体文件。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

> 任务卡 xy075 · 6.3 预览页补实时刷新+导航入口

## 1. 探针输出

### 1.1 卡白名单范围核对（改动前）
```
$ git status
On branch codex/xy075-preview-refresh
Untracked files: .venv   ← .gitignore 第36行 .venv/ 已覆盖，不入库
$ ls docs/projects/xy/plans/   # 业务仓内无 plans 目录
no plans dir in biz repo
```
→ 009 plan 文件不在业务仓内，属 CCC 仓；卡红线 1「009 的在 CCC 仓单独提交」确认本 commit 不动 CCC 仓。

### 1.2 结构探针（改动前）
```
$ grep -n "pages/.*\.html" admin/index.html   # 改动前无 <nav> 导航区
Line 13: health-link href="pages/logs.html"（仅健康条内一个排查链接）
Line 40: <a href="pages/workflows.html">查看完整看板 →</a>（区块内链接）
Line 49: <a href="pages/tasks.html">查看全部 →</a>（区块内链接）
```
→ index.html 无集中导航区，需新建 <nav>；预览入口缺失。
```
$ grep -n "setInterval\|location.reload" admin/pages/preview.html   # 改动前
Line 18: <button class="btn btn-ghost" onclick="location.reload()">↻ 刷新</button>（仅手动刷新）
```
→ preview.html 无定时轮询，仅手动刷新。

### 1.3 009 关联卡登记探针（步骤 4 / 验收标准 4）
```
$ grep -n "关联卡" /Users/fan/program/CCC/docs/projects/xy/plans/009-frontend-showcase.md
6:> 关联卡：xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064、xy073、xy074、xy075

$ cd /Users/fan/program/CCC && git log -1 --format="%h %ci %s" -S "xy075" -- docs/projects/xy/plans/009-frontend-showcase.md
e8a34351f 2026-09-13 23:08:15 +0800 CCC Dev feat(xy075): 6.3 预览页实时刷新+导航入口（Q1 关联卡登记同commit）

$ git status --short docs/projects/xy/plans/009-frontend-showcase.md
（无输出=CCC 仓工作区干净，登记已提交）
```
→ **步骤 4 已由 CCC 仓独立 commit e8a34351f 完成**（同卡号 xy075，延续 xy073/xy074「009 在 CCC 仓单独提交」先例），本执行体在 biz worktree 授权范围内无需再动 CCC 仓。

### 1.4 测试基线探针
```
$ .venv/bin/python -c "import pytest; print(pytest.__version__)"
pytest 9.0.3
$ .venv/bin/python -m pytest tests/admin/ -q   # 改动前基线
106 passed
```

## 2. 自测输出

### 2.1 新增测试单跑（5 项存在性测试，照 test_workflow_page.py 先例）
```
$ .venv/bin/python -m pytest tests/admin/test_preview_refresh.py -v
collected 5 items

tests/admin/test_preview_refresh.py::test_preview_has_polling_setinterval PASSED [ 20%]
tests/admin/test_preview_refresh.py::test_preview_polling_interval_is_15s PASSED [ 40%]
tests/admin/test_preview_refresh.py::test_preview_polling_refetches_library PASSED [ 60%]
tests/admin/test_preview_refresh.py::test_preview_polling_failure_silent PASSED [ 80%]
tests/admin/test_preview_refresh.py::test_index_has_preview_nav_entry PASSED [100%]

============================== 5 passed in 1.03s ===============================
```
退出码 0。

### 2.2 tests/admin/ 全量回归（基线不降）
```
$ .venv/bin/python -m pytest tests/admin/ -q
======================= 111 passed, 30 warnings in 9.41s =======================
```
退出码 0。基线 106 → 111 passed（+5，无新失败，无回退）。

### 2.3 验收标准逐项 grep 核验
```
$ grep -n "setInterval" admin/pages/preview.html
233:    setInterval(function() { loadData(false); }, 15000);        ← 验收1 命中

$ grep -n "15000\|API.get('/api/v1/library')\|loadData(true)" admin/pages/preview.html
214:        var d = await API.get('/api/v1/library');
232:    loadData(true);
233:    setInterval(function() { loadData(false); }, 15000);         ← 15s 间隔代码

$ grep -n "console.warn\|轮询刷新失败" admin/pages/preview.html
227:          console.warn('[preview] 轮询刷新失败:', e.message);    ← 失败静默降级

$ grep -n "pages/preview.html" admin/index.html
16:    <a href="pages/preview.html" ...>👁 预览</a>                   ← 验收2 命中
```
验收标准 1/2/3 通过；验收标准 4（009「关联卡」行含 xy075）见 §1.3，由 CCC 仓 commit e8a34351f 满足。

### 2.4 门禁核对
- diff 文件数 ≤3：`admin/pages/preview.html`、`admin/index.html`、`tests/admin/test_preview_refresh.py`（+ `.venv` 未跟踪且已 gitignore，不入库）→ 3 文件 ✓
- exposed 后端零改动：`/api/v1/library` 服务端代码未动 ✓
- 不动 M7/Cookie/发布、不改其他页：仅 3 个白名单文件 ✓
- 未 git add -A、未直推 main、未 force push ✓
- `.ccc-result.md` 未 git add/commit/push ✓

## 维护区

1. **方案同步**：[是] ** xy-plan-009 6.3「视频/图文预览页面」补两处缺口（轮询刷新 + 首页导航入口），本卡号 xy075 已登记进 009「关联卡」行（CCC 仓 commit e8a34351f，见 §1.3；延续 xy073/xy074「009 在 CCC 仓单独提交」双仓两段先例）。
2. **教训沉淀**：[无] ** 本轮无新教训——轮询失败静默降级沿用 xy073 工作流状态区「独立 try/catch 只降级本区块」既有模式（业务仓 `docs/lessons.md` 无新增条目）；无新踩坑。
3. **档案/README**：[否] ** 预览页为既有页面（xy009 6.3 已交付），本轮仅补交互能力，README/档案无新增描述需求。
4. **线路图**：[否] ** 无新增页面/路由/管线节点，admin 导航结构变化属页面内增量，不改动项目线路图。
