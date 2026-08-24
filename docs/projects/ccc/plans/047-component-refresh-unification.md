# 方案 · 前端统一二期：全站实时事件流与组件结构复刻

> 项目：ccc · 编号：ccc-plan-047 · 状态：已确定 · 作者：DSH（ox-alpha）· 工具：DSH
> 创建：2026-08-24 · 更新：2026-08-24（v2 按老板指令重写：传输层全站实时化，轮询清零）
> 关联方案：046（一期皮层已完成）；取代本文件 v1 的「调度器+轮询兜底」折中案
> 前置教训：046-M4 复盘（CSS 禁批量自动删除）

## 目标

**全站单一实时事件流，前端零轮询。**
任何页面看到的任何数据，都是服务端变更后主动推送到浏览器的最新快照；
六页各自的 setInterval 全部退役；组件结构收编为信息墙设计语言的共享体系。

## 一、架构定稿

### 1.1 服务端：单一聚合事件流 `/hub/stream`

把信息墙已实证的「采样 → diff → SSE 推送」引擎泛化为多通道广播器
（新增 `server/web/hub_stream.py`，复用 wall.py 的 Condition/diff 骨架）：

| 通道 | 数据源（全部复用现有加载函数） | 服务端采样策略 |
|---|---|---|
| `board` | `_enriched_cards()`（已有 20s mtime 键控缓存） | mtime 变化才重算 |
| `plans` | 方案目录 rglob mtime 快检 → 变化才重建 list | 文件级，成本极低 |
| `roadmap` | roadmap 聚合加载函数 | 同上 |
| `ops` | ops summary/failures 加载函数 | 15s 低频采样 |
| `console` | services/ports/concurrency/running | 10s 低频采样 |
| `dsh` | dsh-findings 加载函数 | 15s 低频采样 |

推送语义（与墙一致）：每通道独立字符串 diff，变化才发
`event: <通道名>` + 全量快照；无变化不发包；全局心跳保活。
**写后即时性**：所有 apiPost/apiPut 类 handler 成功后调用
`hub.bump(channel)` 强制下轮立即重算该通道——写操作 → 全端即时可见。

### 1.2 前端：单一连接 + 频道订阅总线 `js/lib/hubClient.js`（新增，~100 行）

```js
hub.subscribe('board', snapshot => renderBoard(snapshot));
```

- 应用生命周期内**仅一条** EventSource（`/hub/stream`），与页面路由解耦：
  页面 mount/unmount 只增删订阅者，连接常驻（含断线指数退避重连、回前台补拉）
- 订阅即得当前缓存快照（首帧渲染零等待）；此后每次推送触发页面增量渲染
- 断线降级：连接失败期间自动切换一次性 GET 拉取（复用现有端点），
  恢复后回到推送态——弱网可用性不倒退

### 1.3 轮询清零

六页全部 setInterval 删除；wall 自有 `/wall/api/stream` 二期并入同一客户端
（本期保留，避免同时动两头）。写操作后的定向刷新由 hub.bump 承担，
前端不再有任何「成功后手动 loadXxx」补丁。

## 二、组件结构复刻（与 1. 并行的结构线）

| 共享件 | 取代 |
|---|---|
| `.k-section/.k-section-title` | 三种分区头实现收敛 |
| `.k-card` 四件套 + 修饰类 | 五套卡片实现收编（pcard/rm-card/console-card/ops-proj-card/dsh-sum-card）|
| `.k-empty/.k-loading/.k-chip/.k-badge/.k-dot` | 各页私有状态原语 |
| setHtmlStable 提为 `js/lib/render.js` 统一导出 | 手写 __lastHtml 模式 |

迁移顺序（高危殿后）：dsh → console → ops → roadmap → plans → board。

## 三、分期计划（每期独立 commit 可单独回滚）

### P1 实时内核 + 两通道试点（解决老板点名问题）
hub_stream.py（board/plans 双通道）+ hubClient.js + board/plans 接入 +
六页 setInterval 不动（下一期拆）。验收：卡状态/方案文件变更 ≤3s 全端可见；
双开浏览器一致性；断线恢复自动续推。

### P2 全通道 + 轮询清零
ops/console/dsh/roadmap 四通道接入；六页 setInterval 全部删除；
写操作 bump 链路接通。验收：全站 `grep setInterval js/pages` 归零；
后台标签流量审计（Network 面板）仅一条 SSE 心跳。

### P3 结构复刻（顺序 dsh→console→ops→roadmap→plans→board）
每页一个 commit：卡片/分区/空态换 k 族原语；行为回归清单逐页点验。
board 单独分支预演虚拟滚动+拖拽后才合入。

### P4 清理重做（人工白名单制）+ 墙并入 hubClient + 终验矩阵刷新入库

## 四、总体验收

- [ ] `grep -r "setInterval" js/pages/` 归零；全站运行期网络连接 = 1 条 SSE
- [ ] 任一通道数据变更 → 所有打开该视图的端点 ≤3s 可见（双浏览器实测）
- [ ] 写操作（转卡/审核/改状态）→ 本端即时反馈 + 他端 ≤3s 跟进
- [ ] 五套卡片收编完成，七视图截图矩阵（42 张）刷新入库
- [ ] pytest 全量绿；每页功能回归清单通过

## 五、风险与缓解

| 风险 | 缓解 |
|---|---|
| ops/console 采样打爆系统命令 | 低频(10–15s)+复用现有缓存；实测 CPU 基线对比 |
| SSE 连接数随标签页增长 | 每标签 1 条是仪表盘常态；服务端 ThreadingHTTP 已验证承载 |
| board 虚拟滚动/拖拽回归 | P3 压轴 + 分支预演；不达标不合入 |
| 大快照重复推送带宽 | diff 后仍大的通道（board 200 卡）改增量 patch（P2 视实测决定）|

## 附：实施前评估报告（2026-08-24 实测数据 · 老板要求先行探查）

### A. 服务端各通道采样成本实测（3 次取最优）

| 通道函数 | 成本 | 快照载荷 | 结论 |
|---|---|---|---|
| board `_enriched_cards`（20s mtime 缓存）| **9.4 ms** | 110.7 KB | 可行；推送仅在变更时发生 |
| plans `list_plans`（文件扫描） | ms 级 | 小 | 可行 |
| ops `_build_ops_summary` | 1.9 ms | 1.1 KB | 可行 |
| console ports（lsof 全量） | **243.6 ms** ⚠️ | 1.9 KB | **采样 ≥30s 或仅手动触发** |
| console running | 8.7 ms | ≈0 | 可行 |
| ops nodes / dsh findings | ≈0 | ≈0 | 可行 |

### B. 墙引擎基线（已在产运行）
无变化轮 0.19–0.47ms × 每 0.6s = **≈0.03% 单核**，可忽略。

### C. 生产进程基线
空闲态 CPU 0–0.7%，RSS 稳定 ~175MB。（ps 首查的 41% 为启动期累计均值，非实时。）

### D. SSE 连接开销实测（关键发现）
3 条挂起连接：RSS +67MB（**≈22MB/条**）、瞬时 CPU 4.3%；断开后部分回落。
根因：现行墙引擎**每连接各自序列化全量快照**（会话 blocks 大，
单份 JSON 即 MB 级），N 连接 = N 份序列化 + N 份缓冲。
**→ 设计硬要求：hub_stream 必须每次变更只序列化一次、扇出缓存字节；
墙引擎自身在 P2 同步改造回收该内存。**

### E. 页面加载基线
首屏资产（壳 + 全部 CSS + 入口 JS）gzip 实测 **51KB**；七页懒加载模块
合计再 62KB——加载速度无问题，结构复刻为中性变更。

### F. 结论与设计修订
1. 架构判定：**可行（GO）**，负载量级为毫秒级采样 + 变更才推送；
2. 修订一：console 的 ports 子通道采样 ≥30s（244ms 成本所致）；
3. 修订二：hub_stream 单次序列化扇出列为 P1 硬性验收项；
4. 修订三：墙引擎接入同一序列化扇出，列 P2 内存回收项；
5. board 快照 110KB：先全量推送（变更才发），P2 视实测改增量 patch。
