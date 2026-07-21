# Brief F0 · 四面协作建制

| 字段 | 值 |
|------|-----|
| brief_id | `F0-20260721-four-role-charter` |
| 波次 | F0 |
| 状态 | `done` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |

## 1. 目标

落地四面协作基建：角色按面切、brief 模板、流畅基线指标建档；另三窗可按 brief 开工。

## 2. 非目标

- 不改产品代码（壳 / 过桥 / 编排实现）
- 不 bump `VERSION`
- 不新开项目根杂目录；brief 仅用 `docs/briefs/`

## 3. 契约变更

无（协作约定，非 Hub API 字段变更）。

## 4. 分工白名单

| 面 | 参与 | 路径 |
|----|------|------|
| 架构 | 是 | `docs/product/four-role-fluency-charter.md` · `docs/briefs/` · `docs/INDEX.md` |
| 壳 / 过桥 / 编排 | 否 | — |

## 5. 验收清单

- [x] 流畅基线建档：`docs/product/four-role-fluency-charter.md`
- [x] brief 模板：`docs/briefs/_TEMPLATE.md`
- [x] INDEX 可发现（协作约定入口）
- [x] 文件夹卫生：仅 `docs/product/` + `docs/briefs/`，无根下散落目录
- [x] 本 brief 自身归档

## 6. 执行回贴

| 面 | 摘要 | 自检 | 完成 |
|----|------|------|------|
| 架构 | 建档 + 模板 + INDEX 链 | 路径在 `docs/` 下；无无关代码改动入本 commit | 是 |

## 7. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | **通过** |
| 缺口 | 无；F1 待用户指定最卡手感问题后开下一 brief |
| 验收日 | 2026-07-21 |

## 产出索引

| 文件 | 用途 |
|------|------|
| [`../product/four-role-fluency-charter.md`](../product/four-role-fluency-charter.md) | 流畅基线 + 四角色 SSOT |
| [`_TEMPLATE.md`](_TEMPLATE.md) | 复制用 brief 模板 |
| 本文件 | F0 闭环记录 |
