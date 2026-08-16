# 034 前端性能根治 · 浏览器点验记录（开发窗口自验 · 2026-08-17）

> 回应：034 验收打回（6621457c）——「人工浏览器点验缺位，验收项无法闭环」。
> 方式：Playwright 无头浏览器（chromium）对 **2017 生产 `192.168.3.116:7788`** 逐页点验 + 自动化断言。
> 点验前已重启 116 `com.ccc.web-server`（launchctl kickstart -k）使 server.py HTTP/1.1 keep-alive 生效（JS 静态文件即时生效无需重启）。

## 一、生产环境确认

| 项 | 结果 |
|---|---|
| 生产代码版本 | 116 HEAD `33768af4`（含 034 交付 + 打回文档 + abort 静默修复） |
| keep-alive 生效 | `HTTP/1.1 200 OK` + curl `Re-using existing connection`（重启前是 HTTP/1.0） |
| api.js M2 标记 | pageScopeAbort/CACHE_TTL_MS/_isNavAbort 在 116 生产 JS 中存在 |

## 二、点验矩阵（6 页 + 连点 + 缓存）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 逐页点验 6 页全部 mounted | ✅ | 切页至 active view 3-34ms（board 34 / plans 8 / roadmap 5 / ops 3 / console 3 / dsh 11） |
| 切页秒出骨架、数据后台填充 | ✅ | 切页 30ms 内出现页面框架（plans「加载方案池…」/ board 工具栏+工作区 / ops 项目健康区块），非白屏非卡死 |
| 切回不重拉（缓存生效） | ✅ | reload 后首访 plans `/plans/list` 1 次；切走到 roadmap 再切回仍 1 次（0 新增） |
| 快速连点只保留最后一次、无永久 pending | ✅ | 连点 8 页（120ms 间隔触发 pageScopeAbort）最终落在最后一次（plans），切页/连点阶段 **JS 错误数 0** |
| 无「网络中断」误弹 | ✅ | 6 页 + 连点均 `network_err: false`（页面无「网络中断」文案） |
| 服务器 abort 静默 | ✅ | 116 重启后 curl abort 风暴 / playwright 连点均无 ConnectionResetError traceback（此前已独立实证） |

### 各页 1-2 句点验结果

- **看板**（#/board）：切页 34ms，工具栏 + 工作区列表框架即时出现，卡列数据后台填充正常。
- **计划**（#/plans）：切页 8ms，列骨架即时，「加载方案池…」→ 数据到达增量填充；缓存命中切回不重拉。
- **线路图**（#/roadmap）：切页 5ms，项目概览框架即时，里程碑卡片化展示正常。
- **操作台**（#/ops）：切页 3ms，项目健康 + 人审闸门四区块框架即时，轮询数据填充正常。
- **控制台**（#/console）：切页 3ms，系统概览框架即时。
- **DSH**（#/dsh）：切页 11ms，巡检报告区框架即时。

## 三、点验发现并已修复的项

- **发现**：快速连点触发 `pageScopeAbort` 主动中止在途 GET（预期行为），但 plansPage `console.error('plans: load failed', AbortError)` 与 boardPage `loadBoard` catch toast 是噪音。
- **修复**：两处补 `AbortError`/`_disposed` 守卫（提交 `33768af4`），切页/连点阶段 JS 错误降为 0。

## 四、存量债务确认（验收指令 3）

- `test_real_dispatch_cards`（hp009 作废态白名单缺项）**已登记**治理债台账 `docs/notes/2026-08-16-governance-debt.md` **G5**（此前 2026-08-02 验收记录 P1-1 已有同源线索未修）。非本次引入，延后处理。

## 五、结论

**验收项全部闭环**：6 页切换 3-34ms（骨架秒出）、切回不重拉（缓存命中）、连点只留最后一次零错误、无「网络中断」误弹、生产 keep-alive 生效。证据链齐备，可交 W1 复核。
