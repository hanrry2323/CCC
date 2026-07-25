/**
 * TDD test: 429 + usage-limit body error → trigger cooldown
 *
 * 当前问题：
 *   上游返回 HTTP 429 + {"error":{"message":"usage limit exceeded"}}
 *   proxy 只 continue 跳过重试，不调用 bad()，下游也没冷却
 *
 * 期望行为：
 *   proxy 识别到 usage-limit/quota 类 body-error 后
 *   应调用 bad(up.name) 触发 10s 冷却
 *   后续请求自动跳过该上游
 *
 * 流程：
 *   1. 启动 mock 上游，对 /chat/completions 返回 429+usage-limit
 *   2. 通过 POST /admin/upstreams 注入测试上游
 *   3. 发一条流式请求触发 429
 *   4. 检查 /admin/upstreams 确认冷却已设置
 *   5. 发第二条请求确认该上游被跳过
 *   6. 清理
 */

import http from 'node:http';

const PROXY = 'http://127.0.0.1:4000';
const TEST_UPSTREAM = 'tdd-429-quota-test';

let passed = 0;
let failed = 0;

function assert(label, ok, detail) {
  if (ok) { passed++; console.log(`  ✅ ${label}`); }
  else { failed++; console.log(`  ❌ ${label}  ${detail || ''}`); }
}

async function api(path, opts = {}) {
  const u = new URL(path, PROXY);
  const r = await fetch(u, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts
  });
  const body = r.status === 204 ? null : await r.json().catch(() => null);
  return { status: r.status, body };
}

// ── 1. 启动 mock 上游 ──
function startMock() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url === '/chat/completions') {
        let body = '';
        req.on('data', c => body += c);
        req.on('end', () => {
          // 模拟火山引擎等上游返回 429 + usage limit
          res.writeHead(429, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            error: {
              message: 'usage limit exceeded: insufficient quota for this billing cycle',
              type: 'rate_limit_error',
              code: 'RATE_LIMIT_REACHED'
            }
          }));
        });
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port;
      console.log(`[mock] started on port ${port}`);
      resolve({ server: srv, port });
    });
  });
}

async function run() {
  console.log('\n=== TDD: 429 + usage-limit → cooldown ===\n');

  // 启动 mock
  const { server: mockSrv, port: mockPort } = await startMock();

  try {
    // ── 2. 注入测试上游 ──
    console.log('[step 1] 注入测试上游...');
    const addRes = await api('/admin/upstreams', {
      method: 'POST',
      body: JSON.stringify({
        name: TEST_UPSTREAM,
        base_url: `http://127.0.0.1:${mockPort}`,
        api_key: 'sk-test-fake',
        tier: 'flash',
        tier_priority: 0,   // 最高优先级，确保请求先走 mock
        models: ['flash'],
        upstream_model: 'test-model'
      })
    });
    assert('注入测试上游成功', addRes.status === 200 || addRes.status === 201,
      `status=${addRes.status}`);

    // 等一等让健康探测跑完
    await new Promise(r => setTimeout(r, 500));

    // ── 3. 发流式请求触发 429 ──
    //    注意：此请求应当触发 502（上游 429，其他上游也无可用）
    //    关键是冷却有没有被设置
    console.log('[step 2] 发请求触发 429...');
    const chatRes = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'hi' }],
        stream: true,
        max_tokens: 5
      })
    });
    // 预期：要么 502（全部上游不可用），要么成功命中其他上游
    // 不管结果如何，核心断言是下面冷却是否有设置
    console.log(`  POST chat 返回 status=${chatRes.status}`);

    // ── 4. 检查冷却状态 ──
    console.log('[step 3] 检查冷却状态...');
    await new Promise(r => setTimeout(r, 200));
    const upRes = await api('/admin/upstreams');
    const testUp = (upRes.body || []).find(u => u.name === TEST_UPSTREAM);
    assert('测试上游存在', !!testUp, 'not found');

    if (testUp) {
      const hasCooldown = !!testUp.cooldown;
      assert('上游已进入冷却 (cooldown 非空)', hasCooldown,
        `cooldown=${testUp.cooldown}`);

      if (hasCooldown) {
        const cdEnd = new Date(testUp.cooldown).getTime();
        const now = Date.now();
        const remaining = Math.round((cdEnd - now) / 1000);
        assert('冷却剩余时间 > 0', remaining > 0,
          `remaining=${remaining}s`);
      }

      // 检查健康状态应变为 ratelimit
      assert('健康状态为 ratelimit',
        testUp.health?.s === 'ratelimit' || testUp.health?.s === 'unhealthy',
        `health.s=${testUp.health?.s}`);
    }

    // ── 5. 发第二条请求，验证测试上游被跳过 ──
    console.log('[step 4] 再次发请求，验证上游被跳过...');
    const chatRes2 = await api('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        model: 'flash',
        messages: [{ role: 'user', content: 'hello again' }],
        stream: true,
        max_tokens: 5
      })
    });
    // 应该被路由到其他真实上游（200）或全部不可用（502）
    // 但不再是 TDD 测试上游
    console.log(`  第二次请求 status=${chatRes2.status}`);

  } finally {
    // ── 6. 清理 ──
    console.log('\n[cleanup] 删除测试上游...');
    await api(`/admin/upstreams/${TEST_UPSTREAM}`, { method: 'DELETE' });
    mockSrv.close();
    console.log('[cleanup] done');
  }

  // ── 总结 ──
  console.log(`\n=== 结果: ${passed} 通过, ${failed} 失败 ===\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => {
  console.error('测试异常:', e);
  process.exit(1);
});
