# 方案 · 管线全链预演·ccc-tst 仓 add 纯函数与 pytest 单测

> 项目：tst · 编号：tst-plan-003 · 状态：待排期 · 作者：engine-drill · 工具：ccc
> 创建：2026-08-30 · 更新：2026-08-30
> 关联卡：无
> 关联方案：无
> 里程碑：无
> 子项目：无
> 环境准备：ccc-tst 仓可写（/Users/fan/program/apps/ccc-tst，本地裸仓 ccc-tst.git），pytest 可用

## 目标

真实 DSH 驱动走通全链（方案→出卡→派发→开发→已回写→CC 审核→合入→部署→关闭），
在 ccc-tst 仓新增一个最小纯函数与 pytest 单测并跑通，作为 15:00 正考的预演（试考）卡。

## 背景

15:00 正考前需要一次全链真实预演，暴露流程毛刺。tst 项目专用于管线自检/冒烟/E2E，
卡内容最小化可标识，禁止承载真实业务逻辑/数据。

## 方案内容

1. 在 ccc-tst 仓（/Users/fan/program/apps/ccc-tst）新增纯函数 add（两数相加）与 pytest 单测。
2. 本地跑 pytest，断言通过。
3. 走既有 fail-safe：失败重试 3 次 + ledger 告警 + 卡不丢。

## 验收标准

- [ ] ccc-tst 仓存在 add 纯函数（源码可见）
- [ ] ccc-tst 仓 pytest 单测通过（可复跑，EXIT=0）

## 功能卡

### 管线全链预演·add 纯函数与 pytest 单测

目标：在 ccc-tst 仓新增 add 纯函数 + pytest 单测并跑通，驱动真实全链预演。

实现：在 /Users/fan/program/apps/ccc-tst 新增纯函数实现与单测文件；本地 pytest 验证。

验收：见方案验收标准两条（函数可见 + pytest EXIT=0）。

颗粒度：单仓两个小文件 + 一次 pytest，最小可标识。

依赖：无

架构位置：tst 管线自检链（DSH 开发 → CC 审核 → 看板闭合）

## 转卡计划

管线全链预演·add 纯函数与 pytest 单测

## 备注

预演卡：真实驱动（PHASE2_AUDIT_DRIVER=real），禁 mock；预期暴露的毛刺如实记录入回执。

## 机器段（ccc-plan）

```ccc-plan
{
  "title": "管线全链预演·ccc-tst 仓 add 纯函数与 pytest 单测",
  "project": "tst",
  "slices": [
    {
      "title": "管线全链预演·add 纯函数与 pytest 单测",
      "slug": "pipeline-drill-add",
      "executor": "DSH",
      "acceptance": [
        "ccc-tst 仓存在 add 纯函数（源码可见）",
        "ccc-tst 仓 pytest 单测通过（可复跑，EXIT=0）"
      ],
      "whitelist": [
        "/Users/fan/program/apps/ccc-tst（新增纯函数与单测文件）"
      ]
    }
  ]
}
```
