const expr = process.argv[2];
if (!expr) { console.error('usage: bun eval.mjs "<js expression>"'); process.exit(1); }

const targets = await (await fetch('http://127.0.0.1:9222/json')).json();
const page = targets.find(t => t.type === 'page' && t.url.includes('discord.com'));
if (!page) { console.error('no discord page target (is the app running with CDP?)'); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

const id = Math.floor(Math.random() * 1e9);
const result = await new Promise((res) => {
  const handler = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id === id) { ws.removeEventListener('message', handler); res(msg); }
  };
  ws.addEventListener('message', handler);
  ws.send(JSON.stringify({
    id,
    method: 'Runtime.evaluate',
    params: { expression: expr, returnByValue: true, awaitPromise: true },
  }));
});
ws.close();

if (result.result?.exceptionDetails) {
  console.error(JSON.stringify(result.result.exceptionDetails, null, 2));
  process.exit(2);
}
console.log(JSON.stringify(result.result?.result?.value ?? null));