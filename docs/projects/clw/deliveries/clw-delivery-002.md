# 交付报告 · clwarp 0.2.0 全量重构（真实可用）

> 项目：clw · 编号：clw-delivery-002 · 方案：clw-plan-002 · 作者：OpenCode（执行）· Claude（中枢整理）
> 交付日期：2026-08-11 · 软件版本：v0.2.0 · 对应 Git Tag：无（远端仅 v0.1.0 tag；以 release commit `d61312d` 为版本锚点）

---

## 1. 交付目标与背景

v0.1.0 实测暴露核心链路不可用（GUI PATH 导致会话拉不起、终端无 resize/退出检测、dev 端口不匹配）且声明大于实际（GPU/Metal、看板内嵌、设置面板均未真实落地）。0.2.0 全量重构，从「声明大于实际」到真实可用的桌面驾驶舱。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本交付报告已完成并归档至 `docs/projects/clw/deliveries/`。
- [x] **CHANGELOG**：业务仓 `CHANGELOG.md` 已由 release commit `d61312d` 追加 v0.2.0 变更日志。
- [x] **RELEASE**：业务仓发布文档已由 release commit `d61312d` 更新（「版本号提升 + 发布文档」）。
- [ ] **Git Tag**：v0.2.0 **未打 tag**（远端仅 v0.1.0），以 release commit `d61312d` 为版本锚点；后续版本统一补 tag。
- [x] **可复跑安装验证**：DMG v0.2.0 打包、安装 `/Applications` 冒烟通过。

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：`docs/projects/clw/plans/002-clwarp-v020-rebuild.md` 状态已为「已完成」。
- [x] **方案验收标准全勾**：clw-plan-002 验收标准全部置 `- [x]`。
- [x] **关联任务卡全关闭**：clw008-clw012 五张卡已全部关闭并合入批准。
- [x] **项目档案近况同步**：`docs/projects/clw/README.md` 线路/近况已同步 v0.2.0。
- [x] **全局线路图挂账同步**：`docs/roadmap.md` 业务线路（clw）已推进到 v0.2.0。

## 4. 版本与发布信息

- **软件版本**：`v0.2.0`
- **代码提交**：`d61312d8add24103907a7e75663b55a8df320c99`（release commit · 2026-08-11 02:34 +0800）
- **发布渠道/部署机**：Mac2017 本地开发机及 `/Applications/clwarp.app` 安装分发

## 5. 可复跑安装与部署验证

### 5.1 环境要求
- macOS Sonoma (v14) 或 Sequoia (v15)
- Rust 1.97.0+ / Node.js 22.16.0+ / Xcode Command Line Tools

### 5.2 安装步骤
```bash
git clone git@github.com:hanrry2323/clwarp.git
cd clwarp
git checkout d61312d   # v0.2.0 release commit
npm install
npm run build
```

### 5.3 运行验证
```bash
cargo tauri build
hdiutil attach src-tauri/target/release/bundle/dmg/clwarp_0.2.0_*.dmg
cp -R /Volumes/clwarp/clwarp.app /Applications/
hdiutil detach /Volumes/clwarp
/Applications/clwarp.app/Contents/MacOS/app & PID=$!
sleep 3 && ps -p $PID && kill $PID
```

## 6. 备注与遗留问题

- **遗留缺陷转入下一期**：v0.2.0 仍存在 P0/P1 缺陷（设置面板空壳/死代码、CSS 层为 Vite 模板残留、StrictMode PTY 泄漏、视图切换杀终端、事件时序竞态、CSP 锁死单 IP、CI 不可绿）→ 由 clw-plan-003（0.3.0 缺陷收口）承接。
- **下一期挂账**：0.3.0 缺陷收口（clw013-018）→ 0.3.0 追加会话加固（clw023-025）。
- **版本锚点说明**：v0.2.0 走 release commit 而非 git tag；如需统一追溯，建议后续补打 v0.2.0/v0.3.0 tag。
