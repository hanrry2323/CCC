# CCC 发展路线图

> **现行叙事**：[`VISION.md`](VISION.md) · **版本**：根目录 `VERSION`（v0.70.0）  
> **权威链**：[`INDEX.md`](INDEX.md) §0 · 文档怎么写：[`DOC-PROTOCOL.md`](DOC-PROTOCOL.md)  
> **历史正文**（v0.19–v0.26 等）：[`archive/roadmap-history-v0.19-v0.26.md`](archive/roadmap-history-v0.19-v0.26.md)（史；勿覆盖「当前方向」）。

---

## 当前方向（索引）

> 2026-08-02 架构重构定稿后方向：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳。

| 重构里程碑 | 完成度 | 说明 |
|------------|--------|------|
| **P0 旧栈退役** | ✅ 已完成 | `scripts/` 归档至 `docs/archive/legacy-retired-2026-08-02/scripts/`；旧端口（7777/7775/7778）退役 |
| **P1 新栈骨架** | ✅ 已完成 | `server/` 七模块（engine/board/web/relay/kb/config/deploy）+ 测试 |
| **P2 Engine + 看板 + HTTP** | ✅ 已完成 | 薄驱动 Engine + 看板服务端 + HTTP API（T1–T14） |
| **P3 线路图 + 运维定时** | ✅ 已完成 | 线路图聚合 + board-scheduler 只读巡检（T5–T7） |
| **P4 2017 部署** | ✅ 已完成 | 三 launchd 常驻（web-server/engine/board-scheduler，T22） |
| **P5 对话大脑 Agent** | ✅ 已完成 | `/conversation` 调 Claude Code via 6100（T29）+ HTTP 页面重构（T30） |

| 重构收口（T31–T35） | 状态 | 说明 |
|---------------------|------|------|
| **T31 文档基线** | ✅ 已完成 | 仓内权威文档切到新架构 |
| **T32 Engine 真派发** | ✅ 已完成 | 从「模拟拉起」到真实派发闭环 |
| **T33 硬编码清理** | ✅ 已完成 | 全仓硬编码扫描清零 |
| **T34 死码双壳清理** | ✅ 已完成 | src-tauri/ 等历史遗留归档 |
| **T35 回归挂账** | ✅ 已完成 | 重构挂账项回归（FileBoardStore + 挂账清零 + 双端复测） |

| 现状 | 说明 |
|------|------|
| **M1（开发机）** | 开发工具（Claude/OpenCode）改 CCC 仓；不保留业务第二树 |
| **M2（2017 生产）** | 单端 :7788 + Engine + board-scheduler 三服务常驻；大脑 Agent via 6100 |
| **M3（任意设备壳）** | Desktop / 网页 / 手机经 HTTP 直连 2017；账号密码 + token |
| **M4（中转站）** | 6100 Anthropic 出口 + 6102 Relay flash 出口 |

| 开源与介绍 | 说明 |
|------------|------|
| 文档口径 | 先读 [`INDEX.md`](INDEX.md) §0 + [`DOC-PROTOCOL.md`](DOC-PROTOCOL.md) |
| 项目注册 | [`projects/registry.yaml`](projects/registry.yaml)（唯一事实源） |
| 竖切蓝图 | [`archive/vertical-qx.md`](archive/vertical-qx.md)（业务向，非 CCC 骨架） |

**业务双轨（归档，非产品北星）**：[`archive/NEXT-DUAL-TRACK.md`](archive/NEXT-DUAL-TRACK.md)。

---

## 下一程挂账（产品）

> **北星**：一个主 IDE 谈意图 → `ccc-plan` 确认后自动拆卡入队 → Engine+硬门禁静默跑 → 只在 RED 或待合入时找人 → 人审 diff 后「合入批准」。  
> **2026-08-07**：下一程只挂北星竖切。冻结：不再挂「同义句/席位/Agent SOP」类项。竖切：[`product/north-star-slice.md`](product/north-star-slice.md)。

| 项 | 意图 | 备注 |
|----|------|------|
| **北星竖切 W0–W2** | plan-to-cards / ready_for_merge / 合入批准 | ✅ `1e78caa` + 2017 |
| **S1 权威入口反漂移** | STARTUP/CURSOR/rules/dev-channel 对齐合入批准 | ✅ |
| **S2a ops 旧端口去红** | opsRed 去掉 7775/7777；config.md 对齐 topology | ✅ |
| **S2b registry 单源接线** | PREFIXES/taskable ← registry.yaml | ✅ ccc005 已回写 |
| **S3 现网狗粮度量** | 调度≤2；禁新 SOP | ✅ 见下「度量」 |
| **web CPU / 轮询优化（挂账）** | boardPanel 5s 轮询 + Edge 看板页（/cards 已缓存缓解，轮询源未收敛） | ⏳ 2026-08-08 |
| **仓库归位搬迁（运维项）** | M1/2017 散落项目文件夹统一归位（registry location 已标注；搬迁需停机窗口一仓一验） | ⏳ 排期，非 SOP |
| **M8 Loop 基线 300 卡** | 跑卡度量 → 数据定四大升级项顺序（目标驱动闭环/自动任务发现/技能封装/循环健康指标） | ⏳ 2026-08-08 定稿 |

### 度量（S3 · 2026-08-07 foundation anti-drift）

| 指标 | 结果 |
|------|------|
| 老板调度次数 | 2（①确认 foundation 计划 ②本程合入/部署） |
| 因流程不懂找人 | 0 |
| 新增 Agent SOP 文件 | 0（只改现行入口 + 脚本/API） |

### M2 ✅（北星产线加固 · 2026-08-07 · `bb64122`）

| 项 | 意图 | 备注 |
|----|------|------|
| **机审自动落盘 ccc006** | 机审通过但未写卡 → Engine 落盘 ## 机审区 | ✅ |
| **Console 文案对齐** | 「待验收」→「待合入批准」 | ✅ |
| **下一程方案落盘** | M3 方案进 notes | ✅ |

### M3 ✅（ready→合入批准闭环 · 2026-08-07 · `649afe6`）

| 项 | 意图 | 备注 |
|----|------|------|
| **假滞留清账** | audit 判定 + 索引 audit 旗标 + backfill 脚本 | ✅ |
| **Console ready** | 待合入接 `/board/ready_for_merge` | ✅ |
| **合入批准狗粮** | `approve-merge --close-only xy001` | ✅ |
| 里程碑 | [`notes/m3-milestone-2026-08-07.md`](notes/m3-milestone-2026-08-07.md) | ✅ |

### M4 ✅（首跑机审 + 关卡清账 · 2026-08-07 · `2588908`）

| 项 | 意图 | 备注 |
|----|------|------|
| **cd 前缀** | ccc004 意图经 registry | ✅ |
| **ccc005/006 首跑机审** | first-audit-evidence → ready | ✅ |
| **合入批准三卡** | ccc004/005/006 已关闭 | ✅ |
| 里程碑 / 下一程 | [`notes/m4-milestone-2026-08-07.md`](notes/m4-milestone-2026-08-07.md) · [`notes/m5-next-plan.md`](notes/m5-next-plan.md) | ✅ / ✅已批 |

### M5 ✅（Engine 真机审狗粮 · 2026-08-07 · `bdc7044` + 分支 `4c93d9f`）

| 项 | 意图 | 备注 |
|----|------|------|
| **真机审 ccc007** | Engine `--audit` → audit.log + 机审区 | ✅ ready |
| **rebase 提醒** | new-card 模板一行（减 close-only） | ✅ |
| **xy002** | 执行中消化 | 挂账 → M6 |
| 里程碑 / 下一程 | [`notes/m5-milestone-2026-08-07.md`](notes/m5-milestone-2026-08-07.md) · [`notes/m6-next-plan.md`](notes/m6-next-plan.md) | ✅ / ✅已批 |

### M6 ✅（自动机审默认路径 · 2026-08-07 · `33f3eb0`）

| 项 | 意图 | 备注 |
|----|------|------|
| **ccc007 合入** | 合入批准 ff | ✅ `7383e96` |
| **xy002 自动机审** | 收单→Engine 自动 audit | ✅ ready |
| **xy002 合入** | 人审合入批准 | 挂账 → M7 |
| 里程碑 / 下一程 | [`notes/m6-milestone-2026-08-07.md`](notes/m6-milestone-2026-08-07.md) · [`notes/m7-next-plan.md`](notes/m7-next-plan.md) | ✅ / 待批 |

### M8 ⏳（Loop 基线 300 卡 · 2026-08-08 定稿）

> 评估主档：qx-map `__archive__/decisions/ccc-loop-engineering-评估与300卡基线计划-2026-08-08.md`。
> 判断：CCC 已是 Loop Engineering 治理型实现；跑满 300 卡（≈7–10 产线日）后用数据排四大升级项顺序。

| 项 | 意图 | 备注 |
|----|------|------|
| **300 卡基线** | 累计 300 张开发卡（xy/hp/mx + ccc），流程稳定 + 指标完整 | 实测 ~45 卡/产线日；300 卡统计充分，500 只多 ~40% 时间、边际增量小 |
| **埋点看板化** | 每卡时长/调用/打回率/机审延迟出可视图 | `server/web/exec_metrics.py` 数据已就绪（08-07~08 已有 47 卡） |
| **检查点** | 每 50 卡快照；100 卡初排升级项；150–200 卡中期校正；300 卡出优化决策 | 只修流程硬伤，不蔓延 |
| **参考库补录** | loop-engineering 社区 6 月后资料入 HP 参考库 | 挂账，非心智补丁 |
| 里程碑 / 下一程 | [`notes/m8-loop-baseline-plan.md`](notes/m8-loop-baseline-plan.md) | 已定稿 |

| 项 | 意图 | 备注 |
|----|------|------|
| **任务卡退役 / 高效管理** | 已关闭卡不拖垮扫卡 | 看板已关闭 cap=10（已做）；其余挂账 |
| **product Hub 史减噪** | hub-* 标史或迁 archive | 分期；白名单见 DOC-PROTOCOL |

### 冻结清单（非阻塞绿路径不修）

- 禁止新增：验收同义句、席位表、AGENTS 长禁令、看板列解释文、了解类 SOP 扩写  
- 禁止平行：第二套拆卡 LLM 服务（拆卡 = 结构化 plan + 脚本）  
- Desktop/Hub 主对话面：暂缓维持  
- Agent 误读非阻塞 → 记债，不写心智补丁 |

---

## 业务线路（xy）

### 视频质量加固（2026-08-07 挂账）

| 卡号 | 意图 | 进度 |
|------|------|------|
| **xy009** | 接入 Pexels/Pixabay API 检索下载短视频素材 | 已关闭 |
| **xy010** | 全链路视频高码率高质量 CRF 编码升级 | 已关闭 |
| **xy011** | 引入双色卡拉 OK 高亮与高表现力 ASS 滤镜渲染 | 已关闭 |
| **xy012** | 爆款 TTS 情绪人声分流与配音轨道声学增强 | 已关闭 |
| **xy013** | 激活并打通 Hyperframes 网页组件渲染引擎 | 已关闭 |

### 根基立稳：审计遗留问题治理（2026-08-07 挂账 · 老板批准）

| 卡号 | 意图 | 进度 |
|------|------|------|
| **xy016** | 视频出片链路全摸底与架构图 HTML 产出 | 已回写 |
| **xy017** | 存储路径统一规划与硬编码消除 | 待分派 |
| **xy018** | 配置漂移修复与文档对齐 | 待分派 |
| **xy019** | 生产补漏：Pexels Key 部署与 BGM 校验与调度核实 | 待分派 |

> **下一程意向**：当前首要任务 = **搭建工程框架、解决技术债/文档债、熟悉项目**；xy017-019 完成后做**第二轮历史遗留排查**（根基立稳），输出完整遗留清单与治理方案。launchd 部署/调度重建**挂账延后**——实际视频还没产出，调度无意义；待主链路真实出片稳定后再议。

---

## 业务线路（hp）

### 知识库基础设施与监控盲区修复（2026-08-07 挂账）

| 卡号 | 意图 | 进度 |
|------|------|------|
| **hp001** | 首次摸底：recon baseline 与业务线路图梳理 | 已合入 |
| **hp002** | 监控盲区：daily-sync 与服务探活接入 qx-map | 已合入 (外仓 main 已含) |
| **hp003** | 备份对齐：异地/冷热数据备份流程机制规范化 | 已合入 (外仓 main 已含) |
| **hp004** | 采集器重建与数据源扩展：launchd 守护与 ingest 补强 | 已回写 (外仓 main 未含，在 codex/hp004-collector-source-expansion 分支) |
| **hp005** | 前端治理与 API 合约对齐：伪数据治理与 Quality 升级 | 已回写 (外仓 main 未含，在 codex/hp005-frontend-fake-data-contract 分支) |
| **hp006** | 向量检索与数据质量治理：合并短 chunk 恢复检索相关度 | 已回写 (外仓 main 未含，在 codex/hp006-search-quality-short-chunks 分支) |

> **下一程意向**：推进 hp 仓监控盲区修复、探活探针接入与数据备份对齐，已通过 hp002-hp006 高质量闭环。下一阶段（hp007）攻坚 CLI 检索复活与短 chunk 拦截。

---

## 业务线路（mx）

### 媒体库管理、UI与订阅加固（2026-08-07 挂账）

- **现状**：版本 v0.9.0；本地 main 领先 origin 1 个 commit（安全修复 `2e093b5`），工作区干净；三条在飞分支已 100% 合入 main，集成风险为 0。
- **近况**：mx002（服务端健康 API 与冒烟测试）已就绪；后续将启动 mx 监控盲区巡检与 RSS 订阅高可用加固。

| 卡号 | 意图 | 进度 |
|------|------|------|
| **mx003** | 首次摸底：在飞分支对齐、技术栈与业务线路梳理 | 已回写 |
| **mx005** | 打磨盘点：摸底并盘点现有代码质量、功能细节与 UI 优化点 | 已回写 |

> **下一程意向**：推进 mx 媒体库管理、UI 体验升级与 RSS 订阅等核心业务线路平稳合入与现网加固

### 打磨点清单（mx005 盘点产出）

#### 一、代码质量（Code Quality）

1. **后端格式化 CI 与 Hook 缺失**
   - **现状**：CI 配置准备了 `clippy, rustfmt`，但 backend steps 未执行 `cargo fmt --check`。且本地 Husky pre-commit hook 只对前端运行 prettier/eslint，无法拦截后端 Rust 格式化不规范的问题。
   - **建议动作**：CI 中 backend 增加 `cargo fmt --all -- --check` 步骤；在 `package.json` 的 `lint-staged` 或 husky hook 中引入 Rust 代码格式化校验。
   - **预估成本**：S

2. **后端测试覆盖率关键服务被排除**
   - **现状**：tarpaulin 针对 `medio-core` 设置了较多排除文件（如 `websub_service`、`scan_scheduler`、`rss_service` 等核心逻辑被排除在覆盖率统计外）。
   - **建议动作**：收窄并移除不必要的 `exclude-files` 排除项，并补齐 `sqlite` 内存数据库下核心服务的单测，实现真实的整体覆盖率 ≥80%。
   - **预估成本**：M

3. **前端测试覆盖率未纳入 CI**
   - **现状**：前端存在 `"test:coverage": "vitest run --coverage"` 脚本，但 CI `Frontend` 任务只跑了 `npm run test`，未进行覆盖率门禁校验。
   - **建议动作**：在 CI 中引入前端覆盖率（vitest coverage）检查并与 `fail-under`（如 70%）绑定，防止质量退化。
   - **预估成本**：S

4. **历史依赖漏洞安全债务**
   - **现状**：`cargo audit` 忽略了 quick-xml (0.36 DoS) 与 rsa (Marvin Attack) 漏洞，属于历史遗留的安全债，且 quick-xml 0.41 包含 API breaking changes 导致升级成本高。
   - **建议动作**：后续迭代规划升级 quick-xml 至 0.41+ 并适配重构代码，对 rsa 依赖链路进行排查替代。
   - **预估成本**：M

#### 二、功能细节（Functional Details）

5. **证书私钥历史泄露隐患**
   - **现状**：鸿蒙签名私钥/证书 `medio.p7b.pem` 曾在 commit `e8bf66a` 误入库。虽已被 gitignore，但历史提交中依然存在，可被反向提取。
   - **建议动作**：v1.0 前执行 `git filter-repo` 彻底清除历史痕迹，并重新签发并部署新版鸿蒙签名。
   - **预估成本**：S

6. **设置页路径输入缺失前端校验**
   - **现状**：`SettingsPage.tsx` 路径输入框前端零校验，完全依赖后端 `validate_path` 进行安全兜底，可能造成安全和 UX 体验差的风险。
   - **建议动作**：前端在输入框加入前置白名单与格式校验（防 `..` 或非法字符），提供实时反馈。
   - **预估成本**：S

7. **敏感端点缺乏速率限制与爆破防护**
   - **现状**：`/auth` 登录及鉴权端点没有任何 IP 级的速率限制，白名单模型偏脆弱。
   - **建议动作**：加入中间件限制登录和敏感端点的请求频率，提高暴破防御；重构 Auth 中间件机制，使其采用默认阻断的白名单设计。
   - **预估成本**：S

#### 三、UI 优化（UI Optimization）

8. **CSS Tailwind 4 unsafe-inline CSP 限制**
   - **现状**：由于对 Tailwind 4 / shadcn 的行内样式重度依赖，后端需开启 `style-src 'unsafe-inline'` 的 CSP 配置，这极大削弱了 CSP 防御 XSS 注入的效果。
   - **建议动作**：重构并采用静态抽取 Tailwind 样式，或者对内联样式在编译期注入 `nonce` 进行校验。
   - **预估成本**：M

9. **移动端高危操作与 Toast/ConfirmDialog 适配**
   - **现状**：在移动端，一键物理删除（F-04）按钮为防误触调大至 44px 且常驻显示，虽有 Trash 恢复机制，但在触屏上缺少防呆设计与撤销按钮。
   - **建议动作**：强化 ConfirmDialog 安全防呆（特别是移动端），增加二次确认手势（如滑动删除或延迟动作），并在 Toast 提示中增加 "撤销" (Undo) 功能。
   - **预估成本**：S

### HTTP 页面巡检清单（mx008 巡检产出）

#### 一、代码问题 (Code Quality)

1. **标准 RSS/Atom 爬虫中的 Atom 解析器极其脆弱 (P0)**
   - **现状**：`builtin.rs` 中的 `extract_atom_entries` 未使用标准 XML/Atom 库，而是通过裸字符串 `split` 以及 `find` 匹配特定的 `<title>` 和 `<link href="` 来提取条目。这种手工解析非常脆弱，在遇到 CDATA 字段、带有命名空间的复杂 XML 结构、注释，或格式稍微不标准（如换行或多属性顺序变化）的 Atom 订阅源时，会发生解析遗漏、截断或错误。
   - **建议动作**：在 `medio-core` 中引入成熟的 XML/Atom 解析库（如 `quick-xml` 或 `atom-syndication`），对 Atom 源进行结构化、健壮的流式/树形解析，彻底消除手写字符串截取逻辑。
   - **预估成本**：M

2. **RSS 统计页 (RssStatsPage) 存在 1000 条硬编码数据截断与客户端全量计算瓶颈 (P1)**
   - **现状**：`RssStatsPage.tsx` 中为了计算未读/已读/收藏数以及日/周发布数量，采用 `rssApi.items({ perPage: 1000 })` 直接拉取最多 1000 条数据到前端并在客户端进行 `filter` 和 `reduce` 计算。
     1. 数据不准确：一旦用户总条目数超过 1000，统计结果将完全失真。
     2. 内存与性能瓶颈：一次性拉取 1000 条大型 JSON 文章数据到内存，并进行大量的 JS 数组过滤操作，极易导致前端界面严重卡顿或网络慢。
   - **建议动作**：后端提供专门的轻量级统计聚合接口（如 `GET /api/v1/rss/stats`），由 SQLite 直接执行 `COUNT(*)` 聚合，前端直接获取数值显示。
   - **预估成本**：S

3. **小时级自动巡检 `crawl_all` 无法向数据库写回异常状态与重试计数 (P1)**
   - **现状**：`scheduler.rs` 中的手动刷新单个源 `crawl_one` 接口在发生抓取错误时，能正确捕获并写入 DB 中的 `last_error` 和 `retry_count` 字段。而作为每小时定时执行的主进程 `crawl_all` 虽有并发信号量限制，但其 `Err` 分支只打印了 `tracing::warn!` 警告日志，未向 SQLite 更新任何订阅失败状态。这导致自动调度失败状态在前端和订阅源列表中不可见。
   - **建议动作**：对齐 `crawl_all` 和 `crawl_one` 的错误写回逻辑，使自动巡检失败时也能写回 `last_error`、`last_error_at` 和递增 `retry_count`，保障异常追踪链路统一。
   - **预估成本**：S

4. **定时自动巡检 `crawl_all` 绕过了 RSS 图片本地化预缓存逻辑 (P1)**
   - **现状**：手动刷新 `crawl_one` 会在保存后调用 `replace_image_urls`，利用 `ImageCacheService` 将 RSS 正文内的图片抓取并缓存到本地。然而每小时跑一次的后台自动扫描进程 `crawl_all` 却完全忽略了此调用，导致通过自动轮询拉回的所有 RSS 文章图片均保留原始热链。这在离线阅读时图片无法显示，且由于很多图片源防盗链或速度极慢，导致前端显示体验非常差。
   - **建议动作**：在 `crawl_all` 成功写入条目后，统一调用正文图片本地化预缓存服务，支持静默后台缓存。
   - **预估成本**：S

5. **保存 RSS 条目和自动生成标签时缺乏数据库事务保护 (P2)**
   - **现状**：`save_rss_item_with_auto_tags` 在保存单条 RSS Item 时，会依次执行 `INSERT into rss_items`、`SELECT tags`，然后循环执行 `INSERT OR IGNORE into rss_item_tags`，这些 SQL 在单次异步中串行运行，未被包裹在 `sqlx` Transaction 事务内。遇到包含几十个新文章的大型 feed 导入时，会引发几十次磁盘 I/O 写入，不仅速度慢，还极易触发 SQLite Busy 锁数据库错误。
   - **建议动作**：将单个或批量 RssItem/Tags 写入步骤使用 `sqlx::Transaction` 包装，大幅减少 commit 的 I/O 开销并确保写入原子性。
   - **预估成本**：S

6. **OPML 导入解析器的 XML 属性读取顺序依赖漏洞 (P2)**
   - **现状**：在 `api/routes/rss.rs` 的 `parse_opml` 中，遍历 XML 属性是无序的。若 `<outline>` 标签中的 `xmlUrl` 属性出现在 `text` 属性之前（非常普遍），此时 `current_text` 仍为空，解析器会在 `xmlUrl` 触发时将 `name` 直接设为 `url` 写入列表；等后续读到 `text` 属性时虽能更新 `current_text` 变量，但由于已完成 push，导致该条订阅的显示名称在数据库中永久丢失并显示为原始 URL。
   - **建议动作**：重构 `parse_opml`，不应在属性循环内部直接 push 结果。应在完整解析完 outline 的所有属性并填充临时结构体后，在循环外部按优先级设定 `name` 并执行 push。
   - **预估成本**：S

#### 二、显示问题 (UI/Display Quality)

7. **RSS 阅读器渲染组件 `RssReader` 缺少统一的 CSS 样式类绑定 (P2)**
   - **现状**：`index.css` 在 `.rss-reader` 类上声明了许多页面级响应式布局样式。但 `RssReader.tsx` 的外层容器仅绑定了 `rss-pane` 和 `active`，并没有 `.rss-reader` 类，导致其大部分专属样式在浏览器中失效，退而依赖一些不一致的内联样式属性。
   - **建议动作**：为 `RssReader.tsx` 外层容器容器增加 `rss-reader` CSS 类，消除内联样式和 CSS 冲突。
   - **预估成本**：S

8. **RSS 文章图片缺少防盗链/防 CORS 代理防护 (P2)**
   - **现状**：对于未完成本地缓存的图片（如自动巡检拉下的文章或缓存中途断网），前端会直接发起原生 `<img>` 请求。这些请求因为携带了 Medio 的 Origin，会被如微博、微信、B站等防盗链图片 host 拒绝（403/CORS 报错），导致图片破损。
   - **建议动作**：后端提供一个统一的图片代理解析端点（例如 `/api/v1/media/proxy?url=...`），在前端图片加载失败时（onError 分支）或检测到特定敏感 host 时，通过代理获取图片，以绕过浏览器防盗链和跨域限制。
   - **预估成本**：S

#### 三、PC端适配 (PC Adaptation)

9. **RSS 订阅 OPML 导出链接不支持 Bearer Token 鉴权 (P0)**
   - **现状**：`RssSidebar.tsx` 里的 "导出" (OPML) 按钮采用原生 `<a>` 标签，直接链接至 `${API_BASE}/rss/opml`。在系统开启了 Bearer Token 强鉴权模式下，由于原生超链接点击无法附加 `Authorization` 请求头，导致 PC 浏览器点击导出时会报 401 Unauthorized，甚至直接弹出 Token 重输页面，导出功能对加锁用户彻底废弃。
   - **建议动作**：按钮改用 `fetch` API 请求导出内容，将结果转换为 `Blob` URL，通过创建虚拟 `<a>` 并模拟 `click()` 的方式，实现携带 Bearer 头且安全的导出文件下载。
   - **预估成本**：S

10. **缺乏键盘快捷键操作支持，阻碍 PC 端流畅盲打阅读 (P1)**
    - **现状**：PC 端 RSS 双栏非常适合键盘流，但目前全站只在 `RssPage` 中绑定了 `ArrowLeft` 和 `ArrowRight` 用来上一篇/下一篇切歌，完全没有快捷键去操作文章星标、标记已读/未读或呼出搜索/标签面板，使得在 PC 桌面阅读时仍要频繁使用鼠标点击小图标，破坏交互连贯性。
    - **建议动作**：引入全局快捷键监听，在 PC 端支持按 `S` 收藏/取消收藏当前文章，`M` 标记已读/未读，`R` 强制刷新当前源。
    - **预估成本**：S

#### 四、移动端适配 (Mobile Adaptation)

11. **768px 边界分辨率下响应式布局发生严重挤压与垂直堆叠崩溃 (P0)**
    - **现状**：JS 断点识别 `useIsMobile()` 和 `useIsTablet()` 在非触屏的 768px 分辨率下认为其是 Desktop 级（因为 768px >= 768px），于是前端 RssPage 将三个面板（Sidebar, List, Reader）全部激活设为 `active={true}`。然而 CSS 的 `@media (max-width: 768px)` 指令触发，将大框架 `.page` 的 `flex-direction` 设为了 `column`（垂直排布），并将 `rss-sidebar` 和 `rss-list` 宽度拉伸为 `100% !important`。这导致 768px 视口下三个大面板同时处于 display: flex 并在垂直方向堆叠在一起，挤扁了整个阅读区，布局完全崩塌、无法看清任何文字。
    - **建议动作**：对齐前端 JavaScript `useMediaQuery` 媒体查询规则与 CSS 的 `@media` 查询断点（确保两端的分界数值完全闭合、不重叠）；或者在 768px 的平板视图下，采用左侧 Sidebar 抽屉式收起，仅显示 List + Reader 的双栏布局。
    - **预估成本**：S

12. **移动端浏览器下通知轮询机制频繁中断和卡死 (P2)**
    - **现状**：`RssPage` 中使用前端 `setInterval(..., 60000)` 来向后端查询未读文章数量并调起通知。但移动端浏览器（Safari / 微信内置浏览器 / 鸿蒙系统 WebView）为了省电，在应用切换至后台或熄屏后，会极其激进地暂停或节流所有 JS Timer 线程。一旦被挂起，轮询将不再触发，通知到达的实时性变为 0，且应用唤醒后由于大量 timer 积压还可能出现高频重发请求的现象。
    - **建议动作**：移动端放弃单纯的前端定时器轮询策略。对桌面/移动壳，在 Tauri / HarmonyOS 原生层注册后台常驻 Worker/Service，由操作系统级别进行订阅巡检与原生 Push 推送，实现真正高可用的通知。
    - **预估成本**：M
