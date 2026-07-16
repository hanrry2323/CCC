# CCC 运行控制面（v0.39）

> **SSOT**：`~/.ccc/control.json`（模块：`scripts/_ccc_control.py`）  
> CLI：`bash scripts/ccc-autostart-guard.sh {status|enable|disable}`  
> 或：`python3 scripts/_ccc_control.py {status|enable|disable}`

---

## 业务状态机（根源）

旧模型错误地把「永远在线 + 多通道自愈」当成业务：

```
crontab / patrol Popen / launchd KeepAlive / opencode KeepAlive
        ↓ 互不知情
   用户杀掉 → 5 分钟内复活 → 内存爆
```

新模型（红线 12 对齐）：

```
control=disabled  ──默认──► 任何路径禁止拉起；观察脚本空操作
control=enabled   ──显式──► 仅 launchd:com.ccc.engine 可拉起
                            patrol 禁止 Popen 旁路
                            loop-monitor 永不自启
空看板            ────────► Engine 真空闲（不 evolve / 不 replenish）
```

| 模式 | 含义 |
|------|------|
| `disabled` | 安全默认。Engine 若被 KeepAlive 拉起也只 idle sleep。 |
| `enabled` | 用户显式启用。有任务才跑 7 角色闭环。 |

---

## 合法启动路径（唯一）

1. `bash scripts/ccc-autostart-guard.sh enable --start`  
   或 `install-ccc-roles.sh` 后 `launchctl bootstrap … com.ccc.engine`
2. **禁止**：crontab 里 `python3 ccc-engine.py &`
3. **禁止**：patrol `subprocess.Popen(ccc-engine.py)`

---

## 常用命令

```bash
# 查看
bash scripts/ccc-autostart-guard.sh status

# 停机（写 control=disabled + 卸 agent + 杀进程 + 清 crontab 自启）
bash scripts/ccc-autostart-guard.sh disable

# 启用控制面（不自动起进程）
bash scripts/ccc-autostart-guard.sh enable

# 启用并经 launchd 启动 Engine
bash scripts/ccc-autostart-guard.sh enable --start
```

---

## 与 v0.37/v0.38 关系

- v0.37：空看板不自造任务（`CCC_AUTO_REPLENISH=0`）
- v0.38：7 角色闭环 + DISABLED 哨兵止血
- **v0.39**：把「启停」提升为正式控制面状态机，删掉 Popen 旁路自愈
