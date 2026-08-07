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
| **xy009** | 接入 Pexels/Pixabay API 检索下载短视频素材 | 待分派 |
| **xy010** | 全链路视频高码率高质量 CRF 编码升级 | 待分派 |
| **xy011** | 引入双色卡拉 OK 高亮与高表现力 ASS 滤镜渲染 | 待分派 |
| **xy012** | 爆款 TTS 情绪人声分流与配音轨道声学增强 | 待分派 |
| **xy013** | 激活并打通 Hyperframes 网页组件渲染引擎 | 待分派 |

> **下一程意向**：推进 xianyu 仓视频、配音与渲染全链路高表现力加固与自动化发布

---

## 业务线路（hp）

### 知识库基础设施与监控盲区修复（2026-08-07 挂账）

| 卡号 | 意图 | 进度 |
|------|------|------|
| **hp001** | 首次摸底：recon baseline 与业务线路图梳理 | 待合入批准 |
| **hp002** | 监控盲区：daily-sync 与服务探活接入 qx-map | 已回写 |
| **hp003** | 备份对齐：异地/冷热数据备份流程机制规范化 | 待分派 |

> **下一程意向**：推进 hp 仓监控盲区修复、探活探针接入与数据备份对齐，确保基础设施高可用与零断链

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

