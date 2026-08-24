# mx-plan-003 六卡深度代码质量评估（真跑通核心指标）

> 日期：2026-08-16 · 评估对象：OpenCode（执行体）在 medio-0 codex 分支写的 6 张卡代码
> 方法：读实际 diff（`git diff origin/main...origin/codex/<卡分支>`），逐维度评分（可读性/优雅/复杂度/规模/风格/健壮性/可维护性/测试质量）

## 一、总评分

| 卡 | 功能 | commits | diff | 评分 | 一句话 |
|----|------|---------|------|------|--------|
| mx036 | WebSub 恢复 | 2 | +287/-15 | **9/10** | 功能完整+配置化+有测试+教训沉淀 |
| mx037 | 依赖注入 | 1 | +98/-48 | **8.5/10** | DI 干净+防御fallback+RwLock |
| mx038 | AppState 拆分 | 1 | +143/-60 | **8.5/10** | 子状态域清晰+有doc+聚合模式 |
| mx039 | 路由复用 | 1 | +78/-16 | **7.5/10** | 正确但14处重复样板（DRY缺口） |
| mx040 | 图片代理配置 | 2 | +108/-12 | **9/10** | 外置干净+partial容错+测试 |
| mx041 | 播放解耦 | 1 | +33/-19 | **8.5/10** | trait解耦优雅+改动最小 |
| **总体** | — | 8 | ~+747/-170 | **8.5/10** | 整体高质量，聚焦/有边界/有测试 |

## 二、各卡详细观察（读代码后）

### mx036 恢复 WebSub（9/10）— 亮点卡
- **功能完整**：不止恢复断链，还补全了「检测→自动订阅→回调解析→落库+自动打标」完整闭环。
- **优雅**：`::rss::Channel` 显式绝对路径解决局部模块遮蔽（Rust 模块与外部 crate 同名陷阱，干净处理）。
- **配置化**：`with_websub_callback` 注入回调地址，避免硬编码。
- **健壮**：自动订阅失败仅 log 不阻断；订阅不存在返回 NotFound；解析失败静默。
- **测试**：新增 `test_handle_notification_with_xml_content` 真实验证解析+入库+打标。
- **沉淀**：`lessons.md` 记录模块遮蔽教训（可复用知识）。
- 小瑕疵：rss.rs 两处构造重复（create/import），与 mx039 是前后接力。

### mx037 依赖注入（8.5/10）
- **干净**：`state.rss_service()` 访问器 + `unwrap_or_else` 防御性 fallback（未注入时临时构造，保证行为一致）。
- **并发**：`set_progress_callback` 用 RwLock 替代 Option（单例可修改）。
- **聚焦**：scan_scheduler 的重复 new 消灭，DI 注入单例。
- 小瑕疵：DI 重构无专门新增测试（行为等价，靠 cargo test）。

### mx038 AppState 拆分（8.5/10）
- **清晰**：5 个子状态域（Rss/Media/Scan/Cache/Playback）各有 doc 注释，AppState 只聚合。
- **合理**：公共字段（db/config/rate_limiter）留 AppState，服务类依赖进子域。
- **涉及面广但干净**：跨 9 文件迁移引用，路径改动一致（state.media_service → state.media.media_service）。
- 小瑕疵：main.rs 直接字段构造 vs builder 的 with_* 混用（轻微不一致）。

### mx039 路由复用（7.5/10）— 有 DRY 缺口
- **正确**：全部 rss handler 改从 state 取注入单例。
- **健壮**：`ok_or_else` 明确错误（服务未初始化）。
- **缺口**：14 处重复 `state.rss_service.as_ref().ok_or_else(|| AppError::Internal(...))?` 样板——应提取辅助方法（如 `state.rss() -> Result<&RssService, AppError>`）。影响优雅度。

### mx040 图片代理配置（9/10）— 边界考虑亮点
- **外置干净**：ImageCacheService 读 config，UA/超时从硬编码改为配置。
- **边界容错**：`#[serde(default = "default_...")]` 让「只改 UA、缺超时」的 partial config 也能解析（避免 0 超时立即失败）——专门考虑并测试。
- **测试**：`image_proxy_partial_section_uses_defaults` 验证 partial 容错。

### mx041 播放解耦（8.5/10）— 最优雅
- **抽象好**：`PlaybackRateLimiter` trait + `impl for Mutex<RateLimitMap>`，把加锁+过期清理收敛进 trait 实现，调用方一行。
- **最小改动**：+33/-19，trait 解耦干净。
- 小瑕疵：`as Arc<dyn ...>` 类型转换在 7+ 处重复（测试和 main）。

## 三、溯源

- **代码**：全部由 OpenCode（执行体）在各自 `codex/mxNNN-*` 分支提交，commit 语义规范（feat/refactor/fix）。
- **审查**：Claude Code（机审席）的审查质量待机审触发后评估（卡「## 机审区」记录）。

## 四、改进建议（供后续项目参考）

1. **DRY**：路由层取服务用辅助方法（`state.rss()`）替代 14 处重复样板。
2. **测试配套**：DI/拆分类重构可补「注入后 mock 可测」的专项断言（现有靠行为等价全绿）。
3. **跨卡接力协调**：mx036/mx037/mx039 都在 rss.rs/state.rs 改同一字段（rss_service）——分卡开发时有重叠，合并需留意（本次因分卡分分支未冲突，但 m 合入要协调）。

## 五、结论

OpenCode 写的 6 张卡代码**整体高质量（8.5/10）**：改动聚焦白名单内、有边界考虑（partial config 容错）、有测试配套（mx036/040）、有知识沉淀（lessons.md）、commit 收敛（1-2/卡）。**真跑通 + 代码质量双指标达标。**
