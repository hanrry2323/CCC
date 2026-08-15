# 交付报告 · clwarp 0.3.0 缺陷收口与会话加固

> 项目：clw · 编号：clw-delivery-003 · 方案：clw-plan-003 + clw-plan-005 · 作者：OpenCode（执行）· Claude（中枢整理）
> 交付日期：2026-08-12 · 软件版本：v0.3.0 · 对应 Git Tag：无（远端仅 v0.1.0 tag；以 release commit `cc4b6af` + 会话加固 `01fec3a` 为版本锚点）

---

## 1. 交付目标与背景

系统化收口 v0.2.0 遗留的 P0/P1 缺陷（设置面板空壳/死代码、CSS 模板残留、PTY 泄漏、视图切换杀终端、事件时序竞态、CSP 锁死单 IP、CI 不可绿），并追加会话打开可靠性加固（codex 不可执行 → 会话打不开的 P0）。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本交付报告已完成并归档至 `docs/projects/clw/deliveries/`。
- [x] **CHANGELOG**：业务仓 `CHANGELOG.md` 已由 release commit `cc4b6af` 追加 v0.3.0 变更日志。
- [x] **RELEASE**：业务仓发布文档已由 release commit `cc4b6af` 更新（「版本号 + 发布文档」）。
- [ ] **Git Tag**：v0.3.0 **未打 tag**（远端仅 v0.1.0），以 release commit `cc4b6af` 为版本锚点；后续版本统一补 tag。
- [x] **可复跑安装验证**：DMG v0.3.0 打包、安装 `/Applications` 冒烟通过。

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：`docs/projects/clw/plans/003-clwarp-v030-hardening.md` 与 `005-clwarp-v030-session-hardening.md` 均已「已完成」。
- [x] **方案验收标准全勾**：clw-plan-003 / clw-plan-005 验收标准全部置 `- [x]`。
- [x] **关联任务卡全关闭**：clw013-018、clw021、clw023-025 已全部关闭并合入批准。
- [x] **项目档案近况同步**：`docs/projects/clw/README.md` 线路/近况已同步 v0.3.0 及追加加固。
- [x] **全局线路图挂账同步**：`docs/roadmap.md` 业务线路（clw）已推进到 v0.3.0 + 会话加固。

## 4. 版本与发布信息

- **软件版本**：`v0.3.0`
- **代码提交**：
  - release commit `cc4b6afd084dda1bdcd0d3afc515defcacc58063`（2026-08-11 12:09 +0800）
  - 会话加固收尾 `01fec3a`（clw023-025，2026-08-12）
- **发布渠道/部署机**：Mac2017 本地开发机及 `/Applications/clwarp.app` 安装分发

## 5. 可复跑安装与部署验证

### 5.1 环境要求
- macOS Sonoma (v14) 或 Sequoia (v15)
- Rust 1.97.0+ / Node.js 22.16.0+ / Xcode Command Line Tools

### 5.2 安装步骤
```bash
git clone git@github.com:hanrry2323/clwarp.git
cd clwarp
git checkout 01fec3a   # 会话加固收尾（含 v0.3.0 全部）
npm install
npm run build
```

### 5.3 运行验证
```bash
cargo tauri build
hdiutil attach src-tauri/target/release/bundle/dmg/clwarp_0.3.0_*.dmg
cp -R /Volumes/clwarp/clwarp.app /Applications/
hdiutil detach /Volumes/clwarp
/Applications/clwarp.app/Contents/MacOS/app & PID=$!
sleep 3 && ps -p $PID && kill $PID
# 会话功能冒烟：新建 claude 会话可交互；codex 会话恢复给出友好错误（不白屏）
```

## 6. 备注与遗留问题

- **本次交付覆盖**：设置接线（clw013）/ CSS 主题重建（clw014）/ 终端生命周期（clw015）/ CSP 加固（clw016）/ 工程化修绿（clw017）/ 文档一致（clw018）/ 并行流程验证（clw021）/ 会话打开可靠性（clw023-025）。
- **遗留挂账下一期（M4 → M5）**：codex 会话体验仍是最短板，仅打通打开可靠性；M5 Codex 体验加固待 M4 债务清理后立项。
- **版本锚点说明**：v0.3.0 走 release commit 而非 git tag；如需统一追溯，建议后续补打 tag。
