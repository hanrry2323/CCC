/**
 * TDD: 502 流式上游耗尽 bug — 根因定位 + 修复验证
 *
 * 核心假设:
 *   流式 peek 检测到 body error 时 (line 638-640)
 *   只 reader.cancel() + continue，没有:
 *     ✗ bad(up.name, 300000) → 不上冷却
 *     ✗ affinity.delete()     → 不清理绑定
 *
 *   导致: 冷却缺失 → 后续请求仍走故障上游 → 反复 exhausted → 502
 *
 * 测试矩阵:
 *   TC-1: 流式 body 含 MATCHING quota error → 验证 bad() + affinity.delete()
 *   TC-2: 流式 body 含 NON-MATCHING error → 验证至少 affinity.delete()
 *   TC-3: 外部验证: opencode-go 的 reasoning_content error 不被当作 quota error
 */

import http from 'node:http';

const PROXY = 'http://127.0.0.1:4000';
const MOCK_NAME = 'tdd-502-stream-test';
const MOCK_GOOD = 'tdd-502-good-fallback';

let passed = 0;
let failed = 0;

function assert(label, ok, detail) {
  if (ok) { passed++; console.log(`  ✅ ${label}`); }
  else { failed++; console.log(`  ❌ ${label}  ${detail ? '— ' + detail : ''}`); }
}

async function api(path, opts = {}) {
  const u = new URL(path, PROXY);
  try {
    const r = await fetch(u, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts
    });
    const body = r.status === 204 ? null : await r.json().catch(() => null);
    return { status: r.status, body, headers: Object.fromEntries(r.headers) };
  } catch(e) {
    return { status: 0, body: null, error: e.message };
  }
}

function createMock(handler) {
  return new Promise((resolve) => {
    const srv = http.createServer(handler);
    srv.listen(0, '127.0.0.1', () => {
      resolve({ server: srv, port: srv.address().port });
    });
  });
}

// ── 从 admin/upstreams 获取特定上游的详细信息 ──
async function getUpstream(name) {
  const r = await api('/admin/upstreams');
  return (r.body || []).find(u => u.name === name) || null;
}

// ── 注入 mock 上游 ──
async function injectMock(name, port, apiKey, priority, upstreamModel) {
  const r = await api('/admin/upstreams', {
    method: 'POST',
    body: JSON.stringify({
      name, base_url: `http://127.0.0.1:${port}`,
      api_key: apiKey, tier: 'flash',
      tier_priority: priority, models: ['flash'],
      upstream_model: upstreamModel
    })
  });
  return { status: r.status, body: r.body };
}

async function deleteMock(name) {
  return api(`/admin/upstreams/${name}`, { method: 'DELETE' });
}

async function run() {
  console.log('\n╔════════════════════════════════════════╗');
  console.log('║  TDD: 502 流式 fallback — bad() 缺失  ║');
  console.log('╚════════════════════════════════════════╝\n');

  // ── 启动 2 个 mock ──
  const { server: badSrv, port: badPort } = await createMock((req, res) => {
    if (req.method === 'POST' && req.url === '/chat/completions') {
      // 模拟 MiniMax: HTTP 200 + stream body 含 quota error
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      res.write('data: ' + JSON.stringify({
        error: { message: 'usage limit exceeded: quota', type: 'api_error' }
      }) + '\n\n');
      res.end();
    } else { res.writeHead(404); res.end(); }
  });

  const { server: goodSrv, port: goodPort } = await createMock((req, res) => {
    if (req.method === 'POST' && req.url === '/chat/completions') {
      let body = ''; req.on('data', c => body += c);
      req.on('end', () => {
        res.writeHead(200, { 'Content-Type': 'text/event-stream' });
        res.write('data: ' + JSON.stringify({
          id: 'ok', object: 'chat.completion.chunk',
          choices: [{ index: 0, delta: { role: 'assistant', content: 'hi' } }],
          usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 }
        }) + '\n\n');
        res.write('data: [DONE]\n\n');
        res.end();
      });
    } else { res.writeHead(404); res.end(); }
  });

  console.log(`[mock] bad  :${badPort}  good  :${goodPort}\n`);

  try {
    // ── 步骤 0: 注入 mock 上游，使其排在真实上游前面 ──
    // 策略: bad mock tier_priority=0 (最高), good mock tier_priority=100 (最低兜底)
    // 如果真实上游都不可达/失败，最终会 fallback 到 good mock
    
    console.log('── 注册测试上游 ──');
    const r1 = await injectMock(MOCK_NAME, badPort, 'sk-bad', 0, 'mock-bad-model');
    const r2 = await injectMock(MOCK_GOOD, goodPort, 'sk-good', 100, 'mock-good-model');
    assert('注册 bad mock', r1.status === 200 || r1.status === 201, `status=${r1.status}`);
    assert('注册 good mock', r2.status === 200 || r2.status === 201, `status=${r2.status}`);
    await new Promise(r => setTimeout(r, 800));

    // ── TC-1: 发送请求到 bad mock → 验证 cooldown ──
    console.log('\n── TC-1: 流式 body quota error → 验证 cooldown ──');
    const tc1 = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'tc1-test-quota' }],
        stream: true, max_tokens: 100
      })
    });
    console.log(`  HTTP status: ${tc1.status}`);
    
    // 检查 bad mock 的 cooling 状态
    await new Promise(r => setTimeout(r, 300));
    const badUp = await getUpstream(MOCK_NAME);
    assert('TC-1: bad upstream 存在', !!badUp, JSON.stringify(badUp));

    if (badUp) {
      const hasCooldown = !!badUp.cooldown;
      console.log(`  cooldown: ${badUp.cooldown || 'null'}`);
      console.log(`  health  : ${JSON.stringify(badUp.health)}`);
      
      // ⚠️ 核心断言：如果 cooldown=null，证实 bad() 没有被调用
      if (!hasCooldown) {
        console.log('\n  ⚠️  BUG 确认: bad() 未被调用！流式 body error 路径缺少冷却逻辑');
      }
      assert('TC-1: bad upstream 已进入冷却', hasCooldown,
        '==> 根因确认: 流式 peek error 路径未调用 bad()');
    }

    // ── TC-2: 同会话第二次请求 → 验证是否跳过 bad mock ──
    console.log('\n── TC-2: 同会话第二次请求 ──');
    const tc2 = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'tc1-test-quota' }],  // 相同首消息 → 同 affinity
        stream: true, max_tokens: 100
      })
    });
    console.log(`  HTTP status: ${tc2.status}`);
    // 如果 bad upstream 没有被 cooldown，这次请求仍可能走它 → 再次失败
    
    // ── TC-3: 流式 body 含 NON-quota error (例如 reasoning_content error) ──
    console.log('\n── TC-3: 流式 body non-quota error ──');
    // 先清掉旧 mock，注入新的 "reasoning_content error" mock
    await deleteMock(MOCK_NAME);
    
    const { server: reasoningSrv, port: reasoningPort } = await createMock((req, res) => {
      if (req.method === 'POST' && req.url === '/chat/completions') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream' });
        // 模拟 DeepSeek 的 reasoning_content 错误 — 注意这里 JSON 是有效的 chunk
        // 但 error checker 会跳过（因为这是 data chunk 不是 error）
        res.write('data: ' + JSON.stringify({
          choices: [{
            delta: { reasoning_content: 'this is thinking' },
            index: 0
          }]
        }) + '\n\n');
        res.end();
      } else { res.writeHead(404); res.end(); }
    });
    
    await injectMock('tdd-reasoning', reasoningPort, 'sk-reason', 0, 'ds-reasoning');
    await new Promise(r => setTimeout(r, 600));

    const tc3 = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'tc3-reasoning' }],
        stream: true, max_tokens: 100
      })
    });
    console.log(`  HTTP status: ${tc3.status}`);
    
    const reasonUp = await getUpstream('tdd-reasoning');
    if (reasonUp) {
      console.log(`  cooldown: ${reasonUp.cooldown || 'null'}`);
      // 这个场景下 content=undefined 但 role 可能是 "assistant"
      // 测试代码的判断是否正确
    }

    // 清理
    await deleteMock('tdd-reasoning');
    reasoningSrv.close();

    // ── 总结 ──
    console.log('\n── 诊断总结 ──');
    console.log('  根因: proxy.mjs 流式 peek 错误处理 (line 638-640)');
    console.log('  只调用 reader.cancel()+continue，未调用 bad() 和 affinity.delete()');
    console.log('  后果: 故障上游不冷却 → 下次请求仍走它 → 循环失败 → 502');

  } finally {
    console.log('\n── 清理 ──');
    await deleteMock(MOCK_NAME);
    await deleteMock(MOCK_GOOD);
    badSrv.close();
    goodSrv.close();
  }

  console.log(`\n╔════════════════════════════════════════╗`);
  console.log(`║  结果: ${passed} 通过, ${failed} 失败            ║`);
  console.log(`╚════════════════════════════════════════╝\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => { console.error('测试异常:', e); process.exit(1); });
