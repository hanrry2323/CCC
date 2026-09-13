# 任务卡 xy075 · 6.3 预览页补实时刷新+导航入口

> 关联：xy-plan-009（6.3 视频/图文预览页面）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy075 · 状态版本：1
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
1. 方案同步：[是] xy-plan-009 6.3 补缺口，本卡号 xy075（登记见回执）。
2. 教训沉淀：[否]（如机审要求补具体路径）。
3. 档案/README：[否]。
4. 线路图：[否]。