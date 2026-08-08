# medio-0（前缀 mx）

## 是什么

Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。

## 路径

| 机 | 路径 |
|----|------|
| M1 | 无 |
| Mac2017 | `/Users/fan/program/apps/medio-0` |

## 在 CCC 怎么动

- **前缀**：`mx`（UI id：`medio-0`）→ `docs/dispatch/mx/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project mx --title "..."`

## 线路 / 近况

- 版本 v0.9.0；本地 main 领先 origin 1 个 commit（安全修复 `2e093b5`），工作区干净。
- 三条功能分支（`library-management`/`ui-upgrade`/`rss-bugs`）已 100% 合入 main（领先其 184~232 个 commit），集成风险为 0。
- 近期重点：打磨盘点（mx005）与 HTTP 页面/RSS 双端巡检（mx008）已完成，巡检清单已归档并回写 roadmap，后续推进 mx 业务线路高可用加固。
- 公开化准备已挂账（roadmap「业务线路（mx）」）：目标转 GitHub Public，前提=清签名私钥历史 + 敏感信息清零；不急执行，开发中逐步准备。

## 禁区

- 前缀是 `mx` 不是 `medio`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

---

## 附 A：技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 语言 | Rust | edition 2021 |
| 工作区版本 | Cargo workspace | 0.9.0 |
| 后端框架 | axum | 0.8 |
| 数据库 | SQLite（sqlx） | 0.8 |
| 异步运行时 | tokio | 1 |
| 前端 | React + TypeScript | 19 / 5.6 |
| 构建工具 | Vite | 6 |
| UI 框架 | Tailwind CSS 4 + Radix UI | 4 / 1 |
| 状态管理 | Zustand + TanStack React Query | 5 / 5 |
| 路由 | React Router | 7 |
| 桌面壳 | Tauri | Cargo workspace 内 |
| 移动端 | HarmonyOS（hvigor） | — |
| 前端测试 | Vitest + Testing Library | 4.1 / 16 |
| 后端/端到端测试 | Python pytest + aiohttp | 3.9+ |
| 代码质量 | ESLint 9 + Prettier + Husky + lint-staged | — |
| CI/CD | GitHub Actions | — |

### Rust workspace crate 清单

| Crate | 路径 | 职责 |
|-------|------|------|
| `medio-core` | `src/backend/core/` | 核心逻辑 |
| `medio-server` | `src/backend/server/` | HTTP API 服务 |
| medio-tauri | `src/backend/tauri/` | Tauri 桌面壳 |

## 附 B：目录树（深度 3）

```
medio-0/
├── Cargo.toml                  # Rust workspace (v0.9.0)
├── package.json                # Vite 6 / React 19 / husky
├── VERSION                       # 0.9.0
├── config.toml                   # 运行时配置
├── config-test.toml             # 测试配置
├── .github/workflows/
│   ├── ci.yml
│   ├── harmony-build.yml
│   └── release.yml
├── adr/                          # 架构决策记录（ADR-001 ~ ADR-013）
├── data/
│   └── nlp_keywords.json
├── deploy-package/               # 部署制品
│   ├── config.toml.example
│   ├── medio-server.service
│   ├── start.sh / stop.sh
│   └── frontend/
├── docs/
│   ├── deployment.md
│   ├── user-guide.md
│   ├── lessons.md
│   ├── scripts-inventory.md
│   ├── archive/                  # 旧修复/升级文档
│   └── security/
├── medio-harmony-app/            # HarmonyOS 移动端
│   ├── build-profile.json5
│   ├── entry/                    # 应用入口
│   ├── scripts/                  # 构建/签名脚本
│   └── hvigor/
├── release/archive/              # 历史发布包
├── scripts/
│   ├── build.sh / build-dmg.sh / build_hp_release.sh
│   ├── deploy.sh / deploy-hp.sh / deploy-rollback.sh
│   ├── test_api_smoke.py / test_e2e.py / test_mvp_features.py / test_rss.py
│   ├── video_audit.py / generate_covers.sh
│   ├── hash_check.sh / full_hash_check.sh / full_hash2.sh
│   ├── bump-version.sh
│   └── merge_bilibili*.sh / clean-*.sh / delete_videos.sh
├── src/
│   ├── backend/
│   │   ├── core/                 # medio-core crate
│   │   ├── server/               # medio-server crate (axum HTTP API)
│   │   └── tauri/                # Tauri 桌面壳 crate
│   └── frontend/
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── eslint.config.js
│       ├── index.html
│       └── src/                  # React 应用源码
└── tests/
    ├── conftest.py
    ├── test_probe.py
    ├── requirements.txt
    └── perf/                     # 性能测试
```

## 附 C：业务线路梳理

| 业务线路 | 核心功能/在飞分支 | 现状与最近提交 | 完成度 | 下一步意向 |
| :--- | :--- | :--- | :--- | :--- |
| **媒体库管理** | `feature/library-management` | 已合入 main (`5991b25`)；支持首页媒体库视图 MVP、按 library_id 筛选视频与媒体库管理 API/UI。 | 100% (已合入) | 推进多存储源挂载优化与扫描性能提升 |
| **UI 体验升级** | `feature/ui-upgrade-to-emby-level` | 已合入 main (`dc94998`)；支持封面右下角删除快捷键、播放列表自动加载下一批（refill 机制）、Player/Settings CSS 提取与无障碍审计。 | 100% (已合入) | 优化大媒体库下的流畅度与封面加载速度 |
| **RSS 订阅修复** | `fix/rss-bugs` | 已合入 main (`6c73e01`)；修复 RSS 双栏功能、修复 HTML tags 过滤 script 问题、增量扫描网络挂载抖动误删保护等。 | 100% (已合入) | 接入多 RSS 源容灾备份与爬虫防封策略 |
| **基础能力与安全** | main 已发布能力 / `codex/mx002` | 支持 Rust/Axum + SQLite 服务端；最新分支 `codex/mx002` 新增 v1 health endpoint 及 Python 端到端冒烟测试。 | 100% (已合入) / mx002 待合入 | 对接 qx-map 实现健康探针自动巡检与监控 |

### 附 D：关键架构决策与教训沉淀

#### 1. 关键架构决策（ADR-001 ~ ADR-013）
- **技术选型**：后端 Rust/Axum + SQLite (sqlx)（ADR-001/002）；前端 React SPA + Tailwind CSS 4（ADR-003）。
- **部署架构**：支持 Web + Tauri Mac 桌面双模式部署（ADR-005/007）；HarmonyOS 移动端采用 ArkTS 构建（ADR-008）。
- **特色功能**：具备 RSS 爬虫架构（ADR-006）、随机发现（ADR-011）及一键删除+回收站机制（ADR-012/013）。

#### 2. 核心教训沉淀（lessons.md）
- **网络存储误删保护**：增量扫描中使用 `Path::exists()` 会因网络挂载暂时断开导致误删。修复为增量扫描不进行删除，且全量扫描设置 10% 最小阈值守卫。
- **iOS Safari 播放权限限制**：切换视频时重建 `<video>` 元素会导致 iOS Safari 丢失播放授权。修复为在切换时复用同一 `<video>` 元素，并保证播放触发在手势上下文内。
- **播放列表 refill 状态丢失**：refill 自动加载下一批随机视频时，如果未保存 `randomContext` 会导致串文件夹。修复为在设置播放列表时同步写入 random context。