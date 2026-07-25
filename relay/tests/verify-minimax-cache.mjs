/**
 * 验证 MiniMax M3 streaming 响应是否包含 cached_tokens
 * 结论: 如果 streaming 模式不发送 cached_tokens，则解释 0.7% 缓存命中率
 */
import fs from 'node:fs';

async function test() {
  // 从 upstreams.json 读取 API key
  const ups = JSON.parse(fs.readFileSync('/Users/apple/program/ai-loop-router/upstreams.json', 'utf8'));
  const mm = ups.find(u => u.name === 'my-minimax');
  if (!mm) { console.log('MiniMax not in config'); return; }

  const apiKey = mm.api_key;
  const baseUrl = mm.base_url;

  console.log('=== 测试 1: Non-streaming (基准) ===');
  const r1 = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'MiniMax-M3',
      messages: [
        { role: 'system', content: 'You are a helpful assistant. This is a long system prompt designed to test the prompt caching feature of MiniMax M3. It needs to be long enough to trigger the 512 token minimum for auto-caching. '.repeat(30) },
        { role: 'user', content: 'Say "hello"' }
      ],
      max_tokens: 20
    })
  });
  const d1 = await r1.json();
  console.log('Status:', r1.status);
  console.log('usage:', JSON.stringify(d1.usage, null, 2));
  const nc = d1.usage?.prompt_tokens_details?.cached_tokens || 0;
  console.log(`cached_tokens: ${nc}`);

  console.log('\n=== 测试 2: 同一 system prompt，Non-streaming 第二次 (应命中缓存) ===');
  const r2 = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'MiniMax-M3',
      messages: [
        { role: 'system', content: 'You are a helpful assistant. This is a long system prompt designed to test the prompt caching feature of MiniMax M3. It needs to be long enough to trigger the 512 token minimum for auto-caching. '.repeat(30) },
        { role: 'user', content: 'Say "world"' }
      ],
      max_tokens: 20
    })
  });
  const d2 = await r2.json();
  console.log('Status:', r2.status);
  console.log('usage:', JSON.stringify(d2.usage, null, 2));
  const nc2 = d2.usage?.prompt_tokens_details?.cached_tokens || 0;
  console.log(`cached_tokens: ${nc2}`);

  console.log('\n=== 测试 3: Streaming 模式 (检查 usage chunk) ===');
  const r3 = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'MiniMax-M3',
      messages: [
        { role: 'system', content: 'You are a helpful assistant. This is a long system prompt designed to test the prompt caching feature of MiniMax M3. It needs to be long enough to trigger the 512 token minimum for auto-caching. '.repeat(30) },
        { role: 'user', content: 'Say "hello"' }
      ],
      stream: true,
      max_tokens: 50
    })
  });

  const reader = r3.body.getReader();
  const dec = new TextDecoder();
  let lastChunk = null;
  let allChunks = [];

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = dec.decode(value, { stream: true });
      const lines = text.split('\n');
      for (const ln of lines) {
        const tr = ln.trim();
        if (tr.startsWith('data: ')) {
          try {
            const p = JSON.parse(tr.slice(6));
            allChunks.push(p);
            // Check if this is the usage chunk
            if (p.usage) {
              lastChunk = p;
              console.log('FOUND usage chunk in streaming:', JSON.stringify(p.usage, null, 2));
            }
          } catch {}
        }
      }
    }
  } catch(e) {
    console.log('Stream read error:', e.message);
  }

  if (lastChunk) {
    const sc = lastChunk.usage?.prompt_tokens_details?.cached_tokens || 0;
    console.log(`Streaming cached_tokens: ${sc}`);
  } else {
    console.log('NO usage chunk found in streaming response');
    console.log('Chunks received:', allChunks.length);
    if (allChunks.length > 0) {
      console.log('Last chunk:', JSON.stringify(allChunks[allChunks.length - 1]).slice(0, 300));
    }
  }

  console.log('\n=== 结论 ===');
  if (nc2 > 0 && !lastChunk?.usage?.prompt_tokens_details?.cached_tokens) {
    console.log('✅ Non-streaming correctly reports cached_tokens');
    console.log('❌ Streaming does NOT report cached_tokens in usage chunk');
    console.log('👉 这就是 0.7% 缓存命中率的根因：Claude Code 全走 streaming，MiniMax 不在 streaming chunk 中发送 cached_tokens');
  } else if (nc2 > 0 && lastChunk?.usage?.prompt_tokens_details?.cached_tokens > 0) {
    console.log('✅ Both streaming and non-streaming report cached_tokens');
    console.log('👉 缓存命中率低另有原因');
  } else {
    console.log('⚠️  Neither showed cache hit — MiniMax auto-cache may not be triggering');
  }
}

test().catch(e => console.error('Error:', e.message));
