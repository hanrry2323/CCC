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

- 当前版本 v0.9.0；分支 `main` 领先 origin 1 个 commit（安全修复），工作区干净。
- 活跃功能分支：`feature/library-management`、`feature/ui-upgrade-to-emby-level`、`fix/rss-bugs`。
- 近况见看板未关闭 `mx*` 卡。

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

## 附 C：最近 15 条 commit

```
2e093b5 fix(security): untrack HarmonyOS signing keys & sync project to v0.9.0
8328aed fix(release): sync Cargo.toml workspace version to 0.9.0
b100d53 fix(ci): rewrite harmony-build workflow as minimal valid placeholder
9bb2a11 fix(ci): ignore 3 known-risk-accepted RUSTSEC IDs in cargo audit
55befd7 fix(ci): cargo audit ignore unmaintained/unsound + grant checks:write
f61e2ca fix(ux): replace native confirm/alert with ConfirmDialog/toast
4f545a7 fix(theme): dark default + root-level theme init
8498684 fix(ci): harmony-build workflow
e2d8686 fix(ci): install ffmpeg for test fixtures (file_move test)
826cdd7 fix(build): track Cargo.lock for reproducible builds + audit
9f46c3c fix(ci): install Tauri system deps for backend+coverage jobs
96a24c1 fix(deploy): sync VERSION to HP
473932b docs(security): cert asset assessment + ledger entry
ed18015 fix(ci): grant contents:read + fix harmony-build trigger
aa1aa2f release: bump to v0.9.0
```