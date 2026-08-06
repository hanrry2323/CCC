/**
 * opsRed — 运维「只看红灯」聚合纯函数（无 DOM 依赖，可 node 单测）。
 *
 * 数据读取镜像 opsPage 现有 render 函数（缺失键 → 空，不抛），
 * 输出统一红灯/告警条目列表供聚合视图渲染。
 */

/** 现行拓扑关键端口（见 docs/deploy/topology.md）；7775/7777 Hub 已退役勿再红灯 */
const CRITICAL_PORTS = new Set([7788, 6100, 6102]);

function _sevOf(s) {
  return String(s || '').toLowerCase() === 'high' ? 'high' : 'warn';
}

/** 从 ops summary 聚合红灯/告警条目。 */
export function collectRedItems(agg) {
  const items = [];
  if (!agg || typeof agg !== 'object') return items;
  const push = (domain, severity, title, detail) => {
    items.push({ domain, severity, title, detail: String(detail || '') });
  };

  const risks = (agg.risks && agg.risks.risks) || [];
  const engineDownRisk = risks.some((r) => String(r.id || '') === 'engine-down');
  for (const r of risks) {
    const ws = (r.workspace || '').trim();
    push(
      'risks',
      _sevOf(r.severity),
      r.title || '未命名风险',
      [r.detail || '', ws && ws.toUpperCase() !== 'CCC' ? '· ' + ws : '']
        .filter(Boolean)
        .join(' ')
    );
  }

  const down = (agg.overview && agg.overview.down_ports) || [];
  for (const p of down) {
    push(
      'ports',
      CRITICAL_PORTS.has(Number(p.port)) ? 'high' : 'warn',
      `端口 ${p.port} 未响应 (${p.name || ''})`,
      p.label || p.host || ''
    );
  }

  const machines = (agg.overview && agg.overview.machines) || [];
  for (const m of machines) {
    if (!m.reachable) {
      push('machines', 'high', `机器 ${m.name} 不可达`, `${m.ip || ''} · ${m.role || ''}`);
    }
  }

  const targets = (agg.deploy && agg.deploy.targets) || [];
  for (const t of targets) {
    if (!t.reachable) {
      push('deploy', 'high', `部署目标 ${t.name} 不可达`, `${t.ip || ''} · ${t.role || ''}`);
    }
    for (const c of t.checks || []) {
      if (!c.alive) {
        push('deploy', 'warn', `${t.name || ''} ${c.label || c.port || ''} down`, '');
      }
    }
  }

  const wsRows = (agg.workspaces && agg.workspaces.workspaces) || [];
  for (const w of wsRows) {
    const abn = Number(w.abnormal || 0);
    if (abn > 0) {
      push('workspaces', 'high', `${w.id || w.workspace || ''} 异常 ${abn}`, w.path || '');
    }
  }

  // engine-down 已由 risks 覆盖时不重复报
  const control = agg.control || {};
  if (control.engine_running === false && !engineDownRisk) {
    push('engine', 'high', 'Engine 未运行', '控制面 engine_running=false');
  }

  const relay = agg.domains && agg.domains.relay;
  if (relay && relay.ok === false) {
    push('relay', 'warn', 'relay 不可达', relay.error || '客户端已切 fail-open');
  }

  return items;
}

/** 红灯/告警总数（toggle 角标）。 */
export function redCount(items) {
  return Array.isArray(items) ? items.length : 0;
}
