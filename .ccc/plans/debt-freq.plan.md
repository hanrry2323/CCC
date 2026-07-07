# debt-freq

> 标题: 修复角色频率：文档 vs plist 不一致
> 创建: 2026-07-07T12:45:01Z

## 目标

## 问题
CLAUDE.md 写的频率和实际 plist 不同。
| 角色 | CLAUDE.md | 实际 plist | 正确？|
|------|-----------|-----------|------|
| dev | 1h(3600s) | 30min(1800s) | 30min 老板指定 |
| reviewer | 1h(3600s) | 2h(7200s) | ❌ 不对 |
| ops | 1h(3600s) | 30min(1800s) | 30min 老板指定 |
| tester | 2h(7200s) | 4h(14400s) | ❌ 不对 |

## 执行方案
1. 确认老板最终频率表
2. 跑 bash install-ccc-roles.sh 更新 com.ccc.* plist
3. 同步更新 CLAUDE.md 角色矩阵的频率列
4. 验证 launchctl list 确保新间隔生效

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
