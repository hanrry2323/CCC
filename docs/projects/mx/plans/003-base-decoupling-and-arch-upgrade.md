# 方案 · medio-0 底座解耦与中长期架构升级

> 项目：mx · 编号：mx-plan-003 · 状态：已完成 · 作者：CCC 中枢 · 工具：ccc
> 创建：2026-08-14 · 更新：2026-08-15
> 关联卡：mx036, mx037, mx038, mx039, mx040, mx041
> 关联方案：mx-plan-002（已完结 · 本方案为其架构收口后的重构延续）
> 进度：6/6 (100%)
> 里程碑：底座解耦与中长期架构升级

## 目标

对 medio-0 后端 core 模块做依赖解耦与架构升级：恢复 WebSub 实时推送断链（P0）、消除 AppState 上帝状态、统一依赖注入（Arc 服务单例化）、配置外置化，为后续公开化与多端 CI 打稳底座。全部改造以行为等价为准（不改变业务语义，改动后现有测试全绿）。

## 背景

mx025 对 medio-core 做了技术债与高耦合度审计（`docs/architecture-coupling.md`），产出 6 项问题已挂账全局 roadmap「架构问题收集」：

| # | 问题 | 优先级 |
|---|------|--------|
| 1 | RssService WebSub 联动被注释禁用（路径重构致编译错误，`rss/service.rs:94`）——实时推送功能断链 | **P0** |
| 2 | ScanScheduler 内部现场 new MediaLibraryService（两次实例）——冗余初始化，无法 mock 测试 | P1 |
| 3 | AppState 上帝状态（捆绑 7+ 服务）——改动全局、违反最少特权 | P1 |
| 4 | API 路由层每次请求 new RssService——额外开销、屏蔽 DI | P1 |
| 5 | ImageCacheService 爬虫 UA/超时硬编码（不读 config）——反爬配置失效 | P2 |
| 6 | PlaybackService 强耦合内存 RateLimitMap——职责不清、锁竞争 | P2 |

重构方向（mx025 定）：依赖注入统一构造 Arc 服务；AppState 拆子状态；恢复 WebSub 断链。**部署=手动发布动作，不随卡自动执行**（既定前提）。

## 方案内容

### Phase 1 · P0 恢复 WebSub 断链

修复 `rss/service.rs:94` 的路径引用，恢复 RssService 与 WebSub 实时推送联动（订阅→hub 推送→回调更新）。

### Phase 2 · P1 依赖注入与状态拆分

1. **统一服务构造**：引入 DI 层，所有服务经一次构造为 `Arc<Service>`，注入 AppState；消灭函数内 `new Service()`（ScanScheduler/RssService 两处）。
2. **AppState 拆子状态**：把捆绑 7+ 服务的上帝状态拆成多个子状态域（rss / media / scan / cache / playback），各自持有依赖，AppState 聚合子域。
3. **API 路由层服务复用**：路由 handler 不再每次 new RssService，改从 state 取注入的单例。

### Phase 3 · P2 配置化与解耦

1. **ImageCacheService 配置外置**：爬虫 UA / 超时改读 config（不硬编码）。
2. **PlaybackService 解耦**：RateLimitMap 注入而非强耦合内存单例；锁竞争收敛。

### 约束

- 行为等价重构：不改业务语义，现有测试基线（`cargo test` + 前端 vitest + 冒烟）全绿为验收前提。
- 每阶段独立交付、独立验收，避免大爆炸式重构。

## 验收标准

- [x] WebSub 实时推送恢复（`rss/service.rs` 路径引用修复，联动逻辑可运行）
- [x] ScanScheduler / RssService 不再内部 new 服务，统一注入 Arc 单例
- [x] AppState 拆分完成（子状态域各自独立，AppState 仅聚合）
- [x] API 路由层 handler 复用注入服务（无每次 new）
- [x] ImageCacheService 读 config（UA/超时），PlaybackService 注入 RateLimitMap
- [x] `cargo test` + 前端 vitest + 冒烟测试全绿（行为等价）

## 功能卡

> 一个功能一张卡（ccc-plan-027）。节点② 老板确认清单后一次转卡（粒度 A）。

### 恢复 WebSub 实时推送断链（P0）

目标：修复 rss/service.rs 路径引用，恢复 RssService 与 WebSub 联动，实时推送功能可用。

实现：核对 `rss/service.rs:94` 断链处引用路径，恢复订阅/推送/回调更新逻辑，补测试。

验收：WebSub 推送链路可运行，相关测试通过。

### 统一服务依赖注入（P1）

目标：引入 DI 层，ScanScheduler / RssService 等服务一次构造为 Arc 单例注入，消灭函数内 new Service()。

实现：新增服务构造/注入层，改造 ScanScheduler（两次 new MediaLibraryService → 注入单例）、RssService 构造点。

验收：grep 无 `new MediaLibraryService`/`new RssService` 于非构造点，单测可 mock。

### AppState 拆子状态（P1）

目标：把捆绑 7+ 服务的上帝状态拆成子状态域（rss/media/scan/cache/playback），各自持有依赖，AppState 聚合。

实现：定义子状态域结构，迁移服务持有关系，AppState 组合子域，更新引用点。

验收：AppState 不再直接捆绑全部服务；各子域独立可测试。

### API 路由层服务复用（P1）

目标：路由 handler 不再每次 new RssService，改从 state 取注入单例。

实现：路由构造统一从 AppState 子域取服务，删除 handler 内 new。

验收：API 路由测试全绿，无每次请求 new 服务。

### 图片代理配置外置（P2）

目标：ImageCacheService 爬虫 UA / 超时改读 config，反爬配置生效。

实现：config 加 image_proxy 段，ImageCacheService 读配置替代硬编码。

验收：改 config 可生效（UA/超时），相关测试通过。

### 播放服务解耦（P2）

目标：PlaybackService 的 RateLimitMap 改为注入，职责清晰、锁竞争收敛。

实现：RateLimitMap 经构造注入，PlaybackService 不再强耦合内存单例。

验收：PlaybackService 单测通过，注入可替换。

## 转卡计划

新方案优先用上方「## 功能卡」段，节点② 确认后一次转卡（6 张功能卡）。

## 备注

- 全部改造行为等价：现有测试基线（后端 cargo test / 前端 vitest / 冒烟）全绿为验收前提。
- 依赖 Mac2017 源码（`/Users/fan/program/apps/medio-0`），开发由引擎在 Mac2017 执行。
- 公开化（mx-plan-004）涉及签名私钥清洗，独立另排，不在本方案范围。
