# `cluster-doctor.sh` — v1.0 Cluster Health Diagnostic

> 一条命令看集群健康（bus / nodes / heartbeat / capabilities / 总结）。

## 用途

P2-2 调试工具。诊断 cluster 是否健康，输出 5 段信息。

## 用法

```bash
bash tools/cluster-doctor.sh                          # 默认 http://127.0.0.1:9100
bash tools/cluster-doctor.sh --bus-url http://mac2017:9100
bash tools/cluster-doctor.sh http://10.0.0.5:9100     # positional arg 也支持
```

## 5 段输出

1. **bus liveness**: 健康/不健康
2. **node list**: 已注册的 nodes
3. **heartbeat freshness** (< 90s = OK): 标记 STALE
4. **capability matrix**: node × cap 矩阵
5. **verdict**: 总结 + exit code

## Exit codes

- **0** = healthy (cluster 有 active nodes, all fresh)
- **1** = bus unreachable (curl failed)
- **2** = 0 active nodes
- **3** = some nodes stale

## v3 Portability (Lesson 29)

- `$BUS_URL` 在外层 shell 双引号展开
- set -euo pipefail on
- 不用 `bash -c '...$VAR...'` 单引号嵌套

## Example

```bash
$ bash tools/cluster-doctor.sh
CCC cluster-doctor — http://127.0.0.1:9100
================================

[1/5] bus liveness
  OK: {"status":"ok","service":"ccc-cluster-bus",...}

[2/5] node list
m1
mac2017-fake
feiniu

[3/5] heartbeat freshness (< 90s = healthy)
  [OK] m1 @ 127.0.0.1:9101  last_hb=0.1s
  [OK] mac2017-fake @ 192.168.3.116:22  last_hb=0.1s
  [OK] feiniu @ 192.168.3.131:9100  last_hb=0.1s

[4/5] capability matrix
  capability               nodes
  ------------------------ ------
  claude-p                 m1,mac2017-fake
  git                      m1,mac2017-fake
  ollama-bge-m3            feiniu
  python                   m1,feiniu
  shell                    m1,mac2017-fake,feiniu
  ssh-remote               m1

[5/5] verdict
  OK: cluster healthy (3 active nodes, all fresh)
$ echo $?
0
```

## 关联

- `references/red-lines.md` § 红线 19 (跨设备独立 verifier)
- `scripts/cluster-bus.py` (被诊断的 service)
- `scripts/ccc-dispatch.py` (dispatcher PoC 模式读这条诊断)
