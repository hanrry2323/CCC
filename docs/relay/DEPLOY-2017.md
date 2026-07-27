# CCC Relay · 2017 部署 Runbook

> **目标**:在 Mac2017(编排消费面)部署 CCC Relay 子系统,Engine 切流量。  
> **何时做**:M1 推送 `feat/ccc-relay-integration` 之后。  
> **约束**:2017 `git pull --ff-only` 拉(不直接 push);单实例独占 :4000/:4002 端口;**fail-open 必须验证**(防重蹈退役覆辙)。  
> **SSOT**:`docs/product/loop-engineer-authority.md`「CCC Relay」+「三层架构与 loop-code 槽位化」。

---

## 0. 前置检查

```bash
# 0.1 确认 M1 已 push(在 M1 上)
cd ~/program/CCC
git log origin/feat/ccc-relay-integration..HEAD --oneline
# 应为空(全在远端)

# 0.2 确认 relay 残骸(防双实例抢 :4000)
ls ~/Library/LaunchAgents/disabled-relay-20260718/ 2>/dev/null
# 应有 com.ai-loop-router.anthropic.plist / com.ai-loop-router.environment.plist(2026-07-20 退役残留)

# 0.3 node 版本
node --version
# 需要 >= 18(实测用 22;npm 11)
```

---

## 1. 拉分支 + 编译 relay

```bash
cd /Users/fan/program/CCC
git fetch origin
git checkout feat/ccc-relay-integration
# 或保持 main:git pull --ff-only origin feat/ccc-relay-integration
# 验证:ls relay/dist/proxy.js 应不存在(尚未 build)

cd relay
npm ci
npm run build
# 验证:ls -la dist/proxy.js (~134KB)
```

## 2. relay 配置与密钥

```bash
mkdir -p ~/.ccc/relay
chmod 700 ~/.ccc/relay

# 拷脱敏模板
cp ~/program/CCC/templates/relay-upstreams.example.json ~/.ccc/relay/upstreams.json
chmod 600 ~/.ccc/relay/upstreams.json

# 编辑填真 key(三档必填)
# flash → OpenCode Zen deepseek-v4-flash-free（多 key + 可选 HK :18080）
# Pro   → 空档时回落 flash（可后续填付费档）
# code  → Zen 免费池 big-pickle 主力 + flash-free 备份（讯飞 xfyun 退役）
# 模板注释勿写进 JSON 的 $comment（OpenCode 拒收 unrecognized key）
$EDITOR ~/.ccc/relay/upstreams.json
```

**三档契约检查**(填完后跑一次,缺档即报错):
```bash
python3 -c "
import json
cfg = json.load(open('$HOME/.ccc/relay/upstreams.json'))
ups = cfg if isinstance(cfg, list) else cfg.get('upstreams') or []
have = set()
for u in ups:
  if u.get('enabled', True) is False: continue
  t = (u.get('tier') or '').lower()
  if t: have.add(t)
missing = [t for t in ('flash','code') if t not in have]
print('OK' if not missing else f'缺启用档: {missing}; have={sorted(have)}')
"
```

## 3. 清残骸

```bash
# 防双 relay 抢端口(2026-07-20 退役的 ai-loop-router plist)
mkdir -p ~/.ccc/archive
mv ~/Library/LaunchAgents/disabled-relay-20260718/com.ai-loop-router.* ~/.ccc/archive/ 2>/dev/null
# 验证:lsof -i:4000 应无输出
lsof -i:4000 || echo "✓ 4000 端口空"
```

## 4. 装 relay plist + 启动

```bash
cd /Users/fan/program/CCC
bash scripts/install-relay-plist.sh --start --host 2017
# 验证:launchctl list | grep ccc.relay → com.ccc.relay.2017 在列
#       curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4000/admin/status
#       应 200
```

**若 lsof 报 :4000 已占**:检查 `~/Library/LaunchAgents/` 是否有遗留的 `com.ai-loop-router.*.plist` 漏清,或 `com.ccc.relay.2017.plist` 已被 `disabled-ccc/` 移到。再 `cccdisable` 即可。

## 5. 启动 Engine(自动接 relay)

```bash
bash scripts/ccc-autostart-guard.sh enable --start
# relay 先起、Engine 后起(autostart-guard 顺序)
# 验证:launchctl list | grep ccc.engine → 在列
```

## 6. 密钥硬化(可选,但推荐)

`relay` 已上,opencode 走 `:4002` 即可。旧 `~/.config/opencode/opencode.json` 的明文 xfyun/zhipu key 可清理:

```bash
# 6.1 备份
cp ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.bak-$(date +%Y%m%d)

# 6.2 装直连兜底
cp ~/program/CCC/templates/opencode.direct.example.json \
   ~/.config/opencode/opencode.direct.json
chmod 600 ~/.config/opencode/opencode.direct.json
# 编辑填 xfyun/zhipu 真实 key

# 6.3 主配置改 loop → :4002（模板）
cp ~/program/CCC/templates/opencode.relay.example.json \
   ~/.config/opencode/opencode.json
chmod 600 ~/.config/opencode/opencode.json
# 可选同步 ~/.opencode/opencode.json
# opencode-exec 探 :4002 失败时自动切 xfyun/code + OPENCODE_CONFIG 指向 opencode.direct.json
# Engine 默认 OPENCODE_MODEL=loop/code（scripts/ccc-engine.sh）
# 验收:opencode run --model loop/code "ping" 走 relay；日志 [fail-open] 不出现即正常
```

---

## 7. E2E 探针(部署后跑,逐条确认)

```bash
# 7.1 端口 + Dashboard
curl -s -o /dev/null -w 'dashboard: %{http_code}\n' http://127.0.0.1:4000/dashboard
# 应 200

# 7.2 三档契约
curl -s http://127.0.0.1:4000/admin/upstreams | python3 -m json.tool | head -40
# 期望:每条记录带 tier 字段;flash/Pro/code 三档 upstreams 各至少 1 条

# 7.3 用量(初始应全 0)
curl -s 'http://127.0.0.1:4000/admin/usage?period=1d' | python3 -m json.tool

# 7.4 路由命中(跑 product 后再查)
curl -s 'http://127.0.0.1:4000/admin/trail?limit=5' | python3 -m json.tool

# 7.5 Hub 运维面
curl -s -u ccc:ccc http://127.0.0.1:7777/api/ops/summary | python3 -m json.tool | grep -A 10 '"relay"'
# 期望:domains.relay.ok=true 含 tiers:{flash,Pro,code}
```

## 8. **门禁③ fail-open 验证**(关键 · 防退役覆辙)

```bash
# 8.1 跑一个 product 任务(确认 relay 路由命中)
ls /Users/fan/program/CCC/   # 挑一个 register 过的 apps/* 仓
python3 -c "import json, time; print(json.dumps({'task':'quick-probe','ts':time.time()}))" \
  > /tmp/probe.json
# 走实际 hub transfer 触发 product:
# curl -u ccc:ccc -X POST -H 'Content-Type: application/json' \
#   -d @/tmp/probe.json http://127.0.0.1:7777/api/transfer/<project_id>

# 8.2 杀 relay
launchctl kill TERM "gui/$(id -u)/com.ccc.relay.2017"
sleep 2
lsof -i:4000 || echo "✓ relay down(4000 空)"

# 8.3 再跑一个 product 任务 → **必须完成**(走直连,不算失败)
# 8.4 查 Engine 日志:应含 [breaker] upstream(relay) 不可用 → 开熔断并切 fail-open 直连
tail -100 ~/.ccc/logs/ccc-engine.out.log | grep -E "fail-open|直连"

# 8.5 查 upstream-probe.jsonl 应记 unhealthy
tail -5 ~/.ccc/stats/upstream-probe.jsonl

# 8.6 启回 relay
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
sleep 35  # 等 30s 探活缓存刷新

# 8.7 再跑一个 product 任务 → 走回 relay
```

**通过标准**:8.3 任务完成(虽然 relay 死了),日志显示走直连,无任务被 block/skip/quarantine。

## 9. 回滚

```bash
# 9.1 Engine 切回直连(秒级,改 env)
echo 'AGENT_PLANNER_BASE_URL=""' >> ~/.ccc/engine.env
# 9.2 重启 Engine 让 env 生效
launchctl kickstart -k "gui/$(id -u)/com.ccc.engine"
# 9.3 验证
curl -u ccc:ccc http://127.0.0.1:7777/api/ops/summary | jq '.domains.relay.ok'
# 应 false(直连不走 relay)或 null(无 relay_usage 拉取)

# 9.4 完全撤掉 relay
launchctl bootout "gui/$(id -u)/com.ccc.relay.2017"
mv ~/Library/LaunchAgents/com.ccc.relay.2017.plist \
   ~/Library/LaunchAgents/disabled-ccc/
```

## 10. 排障

| 现象 | 排查 |
|---|---|
| 4000 启动失败 | `cat ~/.ccc/logs/ccc-relay-2017.err.log \| tail -50`;`node --version`(要 ≥ 18);upstreams.json 三档契约校验 |
| 端口占用 | `lsof -i:4000 -i:4002`;若是被旧 ai-loop-router 残留占,见 §3 清理 |
| Engine 报 upstream 不可用 | 探 `:4000/admin/status`;`cat ~/.ccc/stats/upstream-probe.jsonl \| tail -3` |
| fail-open 未触发 | 确认 `_claude_env(relay_url=None)` 路径走通;Engine 日志 `[breaker] → 切 fail-open 直连` 关键字 |
| opencode 直连降级 | `cat ~/.config/opencode/opencode.direct.json` key 填了;`lsof -i:4002` 看 relay 状态 |
| 三档用量一直 0 | 跑 product 任务后查 `/admin/trail`;无 trail 记录说明请求未进 relay,检查 `AGENT_PLANNER_BASE_URL` env |
| Desktop 显示 `fail-open 直连` | 正常!relay 暂时不可达;恢复后下次 ops summary 轮询(30s)自动回切 |

## 11. 完成后

- [ ] relay 服务在 launchd 内(`launchctl list | grep ccc.relay`)
- [ ] 三档契约配置生效(`/admin/upstreams` 含 flash/Pro/code)
- [ ] Engine 命中 relay(`/admin/trail` 有 anthropic 记录)
- [ ] **门禁③ fail-open 验证通过**(杀 relay 后任务仍完成)
- [ ] Hub `#/ops` 看到 Relay 面板
- [ ] Desktop 运维面看到 Relay chip
- [ ] upstream-probe.jsonl 记 unhealthy → healthy 状态切换

## 12. 后续

- 完成 → 在 PR #2(feat/ccc-relay-integration) 评论 "[2017 部署通过]"
- 观察 24h,确认无回归 → 合并到 main(`git checkout main && git merge --no-ff feat/ccc-relay-integration`)
- 合并后:删除本地 `feat/ccc-relay-integration` 分支(已落 main);保留 worktree 由用户决定

---

**SSOT**:`docs/product/loop-engineer-authority.md`「CCC Relay(硬 · 2026-07-25)」。  
**门禁**:`references/red-lines.md` 红线 9(卡死立即止损)+ 共识 fail-open 不可协商。
