# medio-0 线路图

> 项目：mx · 更新：2026-08-14

## 草案池

- 【性能】大媒体库（万级文件）多级预缓存与磁盘 I/O 避让（SQLite memory 缓存表 + localforage 元数据缓存 + 大图按需延迟加载）
- 【移动端】HarmonyOS 极简高保真 UI 与系统层常驻推送（后台 Service 原生订阅巡检 + Toast/负一屏通知）
- 【离线】Tauri / Native 双端离线阅读与增量数据离线保存（本地 SQLite/IndexDB 同步机制，断网离线可用）

## 里程碑

### 地基打磨与 RSS 深度修复
- 状态：已完成
- 关联方案：mx-plan-001
- 描述：RSS 打磨与服务端里程碑推进（关联卡 mx001-mx029）。完成业务摸底与环境对齐、Server 基础健康巡检、Cargo Fmt/oxlint CI 门禁、RSS 双栏页/OPML 兼容/Bearer 导出、SQLite 事务原子化、核心模块耦合审计（mx025）。

### 生产收口与安全加固
- 状态：已完成
- 关联方案：mx-plan-002
- 描述：medio-0 收口与安全加固（关联卡 mx030-mx035）。修复 4 个 P1 安全漏洞（XSS/鉴权 fail-closed/暴力破解限制/SSRF）、Token 环境变量化、双机路径对齐、9 个积压分支清理、v0.9.0 Tag、敏感路径脚本重构。

### 底座解耦与中长期架构升级
- 状态：草案
- 关联方案：mx-plan-003
- 描述：底座解耦与架构升级（待起草方案）。统一 DI 管理 Arc 共享服务、拆解 AppState 上帝状态、恢复 RssService 与 WebSub 联动、剥离 ImageCacheService 硬编码参数。

### 公开化搬迁与多端 CI/CD
- 状态：草案
- 关联方案：mx-plan-004
- 描述：开源公开化演进（待起草方案）。换发签名证书 + git filter-repo 历史重写、静态合规清零、开源 LICENSE/README、Actions 跨平台打包与鸿蒙发布流。
