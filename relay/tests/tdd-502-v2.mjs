/**
 * TDD: 502 fix validation — streamlined version
 * Focus: verify bad() + affinity.delete() are called on stream body quota error
 */

import http from 'node:http';

const PROXY = 'http://127.0.0.1:4000';
const BAD_NAME = 'tdd-502-bad';

let passed = 0, failed = 0;
function assert(l, ok, d) { ok ? passed++ : failed++; console.log(`  ${ok ? '✅' : '❌'} ${l}${d ? ' — ' + d : ''}`); }

async function api(path, opts = {}) {
  const u = new URL(path, PROXY);
  const r = await fetch(u, { headers: { 'Content-Type': 'application/json', ...opts.headers }, ...opts });
  const body = r.status === 204 ? null : await r.json().catch(() => null);
  return { status: r.status, body };
}

async function getUpstream(name) {
  const r = await api('/admin/upstreams');
  return (r.body || []).find(u => u.name === name) || null;
}

async function run() {
  console.log('\n╔═══════════════════════════════════════╗');
  console.log('║  TDD: stream body error → cooldown   ║');
  console.log('╚═══════════════════════════════════════╝\n');

  // ── mock: returns 200 + stream body with quota error ──
  const { server, port } = await new Promise(resolve => {
    const srv = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url === '/chat/completions') {
        // Read body to consume it (needed for health check)
        let b = ''; req.on('data', c => b += c);
        req.on('end', () => {
          res.writeHead(200, { 'Content-Type': 'text/event-stream' });
          res.write('data: ' + JSON.stringify({
            error: { message: 'usage limit exceeded: quota exhausted', type: 'quota_error' }
          }) + '\n\n');
          res.end();
        });
      } else { res.writeHead(404); res.end(); }
    });
    srv.listen(0, '127.0.0.1', () => resolve({ server: srv, port: srv.address().port }));
  });
  console.log(`[mock] port ${port}`);

  try {
    // ── Inject mock at highest priority (0) ──
    const add = await api('/admin/upstreams', {
      method: 'POST',
      body: JSON.stringify({
        name: BAD_NAME, base_url: `http://127.0.0.1:${port}`,
        api_key: 'sk-bad', tier: 'flash', tier_priority: 0,
        models: ['flash'], upstream_model: 'quota-sim'
      })
    });
    assert('注入 mock', add.status === 200 || add.status === 201, `status=${add.status}`);

    // ── Wait for health check ──
    await new Promise(r => setTimeout(r, 1000));

    // ── Diagnostic: check upstreams state ──
    const preUp = await getUpstream(BAD_NAME);
    console.log(`  [diag] health=${JSON.stringify(preUp?.health)}, cooldown=${preUp?.cooldown}`);

    // ── Send streaming request ──
    console.log('\n── TC-1: 流式请求触发 quota error ──');
    const tc1 = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'tdd-verify-cooldown-' + Date.now() }],
        stream: true, max_tokens: 100
      })
    });
    console.log(`  HTTP ${tc1.status} ${tc1.body?.error?.message || ''}`);
    assert('TC-1: 请求返回非 502', tc1.status !== 502, 'fallback 成功');

    // ── Check cooldown ──
    await new Promise(r => setTimeout(r, 500));
    const postUp = await getUpstream(BAD_NAME);
    console.log(`\n── TC-2: 验证冷却 ──`);
    if (postUp) {
      const now = Date.now();
      console.log(`  cooldown: ${postUp.cooldown ? new Date(postUp.cooldown).toISOString() : 'null'}`);
      console.log(`  remaining: ${postUp.cooldown ? Math.round((postUp.cooldown - now)/1000) + 's' : 'N/A'}`);
      assert('TC-2: cooldown 已设置', !!postUp.cooldown,
        '==> BUG: bad() 未被调用');
    }

    console.log('  [diag] ' + (postUp?.cooldown ? '✅ 修复生效！bad() 已调用' : '❌ cooldown 仍为空'));

  } finally {
    console.log('\n── 清理 ──');
    await api(`/admin/upstreams/${BAD_NAME}`, { method: 'DELETE' });
    server.close();
  }

  console.log(`\n╔═══════════════════════════════════════╗`);
  console.log(`║  结果: ${passed} 通过, ${failed} 失败           ║`);
  console.log(`╚═══════════════════════════════════════╝\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => { console.error('异常:', e); process.exit(1); });
