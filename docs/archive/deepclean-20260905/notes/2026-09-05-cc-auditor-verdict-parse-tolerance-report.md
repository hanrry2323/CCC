# cc-auditor verdict 解析容忍修复记录

日期：2026-09-05

## 结论

`scripts/cc-auditor.sh` 的 verdict 解析现在容忍裁决行前的空格、Tab 等行首空白，同时仍要求裁决文本位于整行起始语义位置，不会把普通说明行当作结论。

- `机审：通过`（含行首空白）→ exit 0；
- `机审：不通过（原因）`（含行首空白）→ exit 2；
- 非空工件无裁决行 → exit 1；
- stdout 兜底提取同样容忍行首空白；
- verdict 语义未改变，未放宽为任意包含匹配。

## 证据

- 改动：`scripts/cc-auditor.sh`
- 隔离测试：`scripts/tests/test-cc-auditor-verdict.sh`
- 新增场景：空格缩进通过、Tab 缩进不通过、无结论工件仍 exit 1；不访问真实 xy060。
- 语法：`bash -n scripts/cc-auditor.sh`、`bash -n scripts/tests/test-cc-auditor-verdict.sh` 通过。
- 测试：`bash scripts/tests/test-cc-auditor-verdict.sh` 通过。

## 边界保持

维护区四问、`test-evidence.sh` 真实性门禁、结果工件缺失前置失败均未改动；不改业务代码、不改卡正文、不做状态绕过。phase2 每轮读取脚本路径，无需重启引擎。
