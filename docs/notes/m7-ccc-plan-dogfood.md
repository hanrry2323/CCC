# M7 ccc-plan 狗粮

```ccc-plan
title: M7 ready-probe dogfood
project: ccc
slices:
  - title: ready-probe 脚本
    slug: ready-probe-script
    acceptance:
      - "test -x scripts/ready-probe.sh"
      - "scripts/ready-probe.sh | grep -E '^ready_count=[0-9]+$'"
    whitelist:
      - "scripts/ready-probe.sh"
    executor: OpenCode
```
