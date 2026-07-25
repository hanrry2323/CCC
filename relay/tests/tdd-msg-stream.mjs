/**
 * TDD: stream body error → cooldown via /v1/messages (Anthropic path)
 * This is the path that real Claude Code uses, and we've seen it work on my-minimax
 */
import http from 'node:http';

const PROXY = 'http://127.0.0.1:4000';
const BAD_NAME = 'tdd-msg-test';
let passed = 0, failed = 0;
function assert(l, ok, d) { ok ? passed++ : failed++; console.log(`  ${ok ? '✅' : '❌'} ${l}${d ? ' — ' + d : ''}`); }

async function api(path, opts = {}) {
  const u = new URL(path, PROXY);
  const r = await fetch(u, { headers: { 'Content-Type': 'application/json', ...opts.headers }, ...opts });
  const body = r.status === 204 ? null : await r.json().catch(() => null);
  return { status: r.status, body };
}

async function run() {
  console.log('\n╔═══════════════════════════════════════╗');
  console.log('║  TDD: /v1/messages stream err → bad() ║');
  console.log('╚═══════════════════════════════════════╝\n');

  const { server, port } = await new Promise(resolve => {
    const srv = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url === '/chat/completions') {
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
  console.log(`[mock] :${port}`);

  try {
    // Inject
    const add = await api('/admin/upstreams', {
      method: 'POST',
      body: JSON.stringify({
        name: BAD_NAME, base_url: `http://127.0.0.1:${port}`,
        api_key: 'sk-msg', tier: 'flash', tier_priority: 0,
        models: ['flash'], upstream_model: 'tdd-msg-model'
      })
    });
    assert('注入', add.status === 200 || add.status === 201, `s=${add.status}`);
    await new Promise(r => setTimeout(r, 1200));

    // Check health before
    const pre = await api('/admin/upstreams');
    const preU = (pre.body || []).find(u => u.name === BAD_NAME);
    console.log(`  [diag] health=${preU?.health?.s}, cooldown=${preU?.cooldown}`);

    // Send Anthropic-format request via /v1/messages
    console.log('\n── 发送 /v1/messages 流式请求 ──');
    const tc = await api('/v1/messages', {
      method: 'POST',
      headers: { 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'hi test ' + Date.now() }],
        stream: true, max_tokens: 100
      })
    });
    console.log(`  HTTP ${tc.status}`);

    // Check cooldown AFTER
    await new Promise(r => setTimeout(r, 500));
    const post = await api('/admin/upstreams');
    const postU = (post.body || []).find(u => u.name === BAD_NAME);
    console.log(`\n── 验证冷却 ──`);
    if (postU) {
      const cd = postU.cooldown;
      console.log(`  cooldown: ${cd ? new Date(cd).toISOString() + ' (' + Math.round((cd - Date.now())/1000) + 's)' : 'null'}`);
      assert('cooldown 已设置', !!cd, cd ? 'OK' : '❌ BUG: bad() 未调用');
    }

  } finally {
    await api(`/admin/upstreams/${BAD_NAME}`, { method: 'DELETE' });
    server.close();
  }

  console.log(`\n╔═══════════════════════════════════════╗`);
  console.log(`║  结果: ${passed} 通过, ${failed} 失败           ║`);
  console.log(`╚═══════════════════════════════════════╝\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => { console.error('Exception:', e); process.exit(1); });
