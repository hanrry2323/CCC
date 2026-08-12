# medio-0 (mx) 项目发展路线图

> 项目前缀：mx · 权威项目档案：[docs/projects/mx/README.md](README.md) · 版本：0.9.0  
> 冲突裁决：以 CCC 最高准则 `docs/CCC-PRIME-DIRECTIVE.md` 为唯一纲领，贯彻「线路图管未来，计划管当前，看板管正在进行时」思想。

---

## 一、 里程碑规划 (Milestones)

### Milestone 1：地基打磨与 RSS 深度修复 (RSS & Server Polish)
*   **状态**：✅ 已完成
*   **主要工作**：
    *   完成了 medio-0 的业务摸底与环境对齐，确立了 Server 基础健康巡检机制。
    *   建立了后端 `Cargo Fmt` 格式化 CI 门禁与前端 `oxlint/eslint` 静态扫描门禁。
    *   重构打磨了 RSS 双栏页面适配、OPML 导入属性顺序兼容、OPML 的 Bearer 认证导出。
    *   引入 SQLite 数据库事务以原子化保存 RSS 与自动生成的 Tags。
    *   完成核心模块耦合审计（`mx025`）并提供文档、开发指南支撑。
*   **关联方案**：`mx-plan-001`（RSS 打磨与服务端里程碑推进，关联卡 `mx001` - `mx029`）

### Milestone 2：生产收口与安全加固 (Security & Closure Hardening)
*   **状态**：⏳ 正在进行 (部分执行)
*   **主要工作**：
    *   修复 `issues.jsonl` 中积累的 4 个 P1 核心安全漏洞（XSS 移除 dangerouslySetInnerHTML、白名单 fail-closed 鉴权默认拒绝机制、Auth 端点暴力破解限制、远程下载 SSRF 异常保护）。
    *   敏感 Token 环境变量化改写，并对 Git 全仓提交记录进行安全风险复核。
    *   修正 4 处双机路径与文档脱节点，对齐根目录 `package.json` 与 `VERSION` 版本号为 `0.9.0`。
    *   清理 9 个长期未合并的积压分支，打好规范的 `v0.9.0` Git Tag。
    *   对大体积 `delete_videos.sh` 脚本进行敏感路径排查并重构脚本，迁出所有与核心业务无关的个人运维脚本。
*   **关联方案**：`mx-plan-002`（medio-0 收口与安全加固，关联卡 `mx030` - `mx035`）

### Milestone 3：底座解耦与中长期架构升级 (Decoupled Core Architecture)
*   **状态**：⏳ 待讨论 / 计划中
*   **主要工作**：
    *   针对耦合度审计发现的上帝状态进行全面解耦：统一使用依赖注入（DI）管理 Arc 共享服务，消灭冗余的 `MediaLibraryService` 初始化。
    *   拆解 `AppState` 上帝状态，将其拆分为更轻、特权更低的子状态结构。
    *   恢复由于路径编译错误被屏蔽的 `RssService` 与 `WebSub` 实时联动。
    *   剥离 `ImageCacheService` 反爬 UA/超时等硬编码参数，一律动态读取 `config.toml` 配置。
*   **关联方案**：`mx-plan-003` (底座解耦与架构升级，待起草方案)

### Milestone 4：公开化搬迁与多端 CI/CD (Public OpenSource Readiness)
*   **状态**：⏳ 远期挂账
*   **主要工作**：
    *   **独立脱敏**：重新换发鸿蒙签名证书（`.p7b.pem`），并执行 `git filter-repo` 全仓重写历史彻底抹除密钥泄漏痕迹。
    *   **静态清零**：对全仓私有 IP、敏感内网路径、硬编码 token 进行静态合规扫描。
    *   **开源准备**：补充开源 LICENSE、更新中英文 README 运行说明；将 Repo 设置为 Public 开放。
    *   **CI/CD 兑现**：启用 Actions 免费构建机，自动执行 Tauri 跨平台 DMG 打包与 HarmonyOS 应用远程发布流。
*   **关联方案**：`mx-plan-004` (开源公开化演进，待起草方案)

---

## 二、 草案池 (Draft Backlog — 待讨论的远期意图)

### 1. 【性能】大媒体库（万级文件）多级预缓存与磁盘 I/O 避让
*   **背景**：万级文件在首页加载和封面异步扫描时，可能会短暂引起磁盘 I/O 拥堵或 PTT 阻塞。
*   **意图**：实现 SQLite memory 缓存表，并在前端引入 `localforage` 缓存元数据，大图封面采用按需延迟加载和降低线程优先级等策略防止界面卡顿。

### 2. 【移动端】HarmonyOS 极简高保真 UI 与系统层常驻推送
*   **背景**：目前 Harmony 移动端功能完备度低，且后台定时巡检常因系统休眠/挂起而失效。
*   **意图**：深度打磨鸿蒙卡片式组件 UI，并在 HarmonyOS Native 注册后台 Service，由系统层代为订阅巡检并进行原生 Toast / 负一屏通知推送。

### 3. 【离线】Tauri / Native 双端离线阅读与增量数据离线保存
*   **背景**：在乘坐地铁、飞机等断网离线场景下，本地文章或视频元数据由于无法连接 mac2017 后端导致空白破损。
*   **意图**：提供客户端本地 SQLite / IndexDB 同步机制，在有网时增量拉取缓存，离线时完全依靠本地数据运行。
