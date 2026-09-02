# 方案 · 收卡部署闭环 + Loop Observer 调度启用

> 项目：ccc · 编号：ccc-plan-015 · 状态：已完成 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
>  关联卡：已归档（原引用 ccc044, ccc045, ccc046 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：无（2026-08-10 复盘新增）
> 进度：0/3 (0%)

## 目标

1. **部署并入收卡流程**（C1）：合入后自动检查 2017 生产 vs 主干，落后则部署一次。
2. **卡积压提醒**（C2）：待合入 ≥N 张提醒收卡。
3. **Loop Observer 真正挂上调度**：ccc027-032 建的巡查框架未实际运行（快照停 8/9 23:08），需启用并治理报告路径。

## 背景

2026-08-10 复盘确认：
- **C1**：approve-merge 合入后没人跑 deploy-ccc.sh，今天 20 卡部署是手动补的；deploy-ccc.sh 的 kickstart 还不含 board-scheduler。
- **C2**：无待合入积压阈值/提醒；积压太多再收有集成风险（observer 五路重写即例）。
- **Observer 未调度**：com.ccc.scheduler 服务没挂，observer 快照停在 8/9 23:08；且巡查报告落 docs/notes/（git 跟踪文件被反复重写 → 永久 dirty churn）。

## 方案内容

1. **卡1（C1）部署并入收卡**：approve-merge 收卡流程增加「部署检查」步——2017 生产 HEAD vs origin/main 落后则调 deploy-ccc.sh；deploy-ccc.sh 的 kickstart 补 board-scheduler 重启；收卡 SOP 文档更新。
2. **卡2（C2）待合入积压提醒**：看板/收卡工具增加「待合入 ≥N（默认 5）提醒收卡」。
3. **卡3（Observer 启用 + 报告治理）**：2017 挂 com.ccc.scheduler 服务使 observer 每日/合入触发真正运行；巡查报告从 docs/notes 改落 DATA_DIR/observer/（内容变化才写，消 churn）。

## 验收标准

- [x] C1：approve-merge 收完卡后自动触发部署检查；deploy-ccc.sh 重启包含三个服务。
- [x] C2：待合入 ≥5 张有明确提醒（board-live/看板提示）。（关联卡 `ccc045`，机审通过待合入）
- [x] Observer：2017 com.ccc.scheduler 运行、DATA_DIR/observer/ 有新快照、git 无 patrol 报告 churn。

## 转卡计划

```ccc-plan
title: 收卡部署闭环 + Loop Observer 调度启用
project: ccc
slices:
  - title: 部署并入收卡流程（approve-merge 部署检查 + deploy 补 board-scheduler）
    slug: deploy-on-collect
    acceptance:
      - approve-merge 收卡后自动检查 2017 生产 HEAD vs origin/main，落后则调 deploy-ccc.sh
      - deploy-ccc.sh / kickstart-ccc.sh 重启覆盖 engine + web-server + board-scheduler 三服务
      - 收卡 SOP（onboarding.md 或 approve-merge 注释）写明「合入后须部署检查」
      - 真实跑通一次：合入→部署检查→重启→服务健康
    whitelist:
      - scripts/approve-merge.sh
      - scripts/deploy-ccc.sh
      - scripts/kickstart-ccc.sh
      - docs/projects/onboarding.md
    executor: OpenCode
  - title: 待合入积压提醒（≥N 张）
    slug: backlog-alert
    acceptance:
      - 待合入（已回写+机审通过）≥N（默认 5）时看板/收卡工具给出明确提醒
      - 提醒机制（board API 或 approve-merge 前置检查）可配置阈值
      - 测试覆盖阈值判定
    whitelist:
      - server/board/**
      - server/web/**
      - scripts/approve-merge.sh
      - server/tests/**
    executor: OpenCode
  - title: Loop Observer 调度启用 + 报告路径治理
    slug: observer-scheduler-enable
    acceptance:
      - 2017 部署 server/deploy/com.ccc.scheduler.plist 并 launchctl 挂载，observer 每日/合入触发真实运行
      - DATA_DIR/observer/ 产生新快照（验证 run_observer 输出）
      - 巡查报告改落 DATA_DIR/observer/（或内容变化才写 docs/notes），git 不再有 patrol 报告 churn
      - 2017 与 M1 侧 docs/notes 的巡逻报告文件移出跟踪或改为非 git 输出
    whitelist:
      - server/engine/observer.py
      - server/engine/scheduler.py
      - server/deploy/com.ccc.scheduler.plist
      - docs/notes/
    executor: OpenCode
```

## 备注

- Observer 现状：统一模块（027-032）已合入可导入，但无进程在跑（快照停 8/9 23:08）。
- 复盘相关登记见 hp-kb `/codex/topics/ccc/backlog-3-items-pending-2026-08-10`。
