#!/usr/bin/env node
/**
 * PS5 ELF bridge — نسخة Node.js (بدون أي مكتبات خارجية).
 *
 * الاستخدام:
 *   node bridge.js                       # خادم على 127.0.0.1:8765
 *   node bridge.js --host 0.0.0.0
 *   node bridge.js --send crlr69.elf --ps5-host 192.168.1.50
 *
 * نفس واجهة HTTP التي تستخدمها الصفحة:
 *   GET  /info                          -> معلومات الجسر
 *   GET  /ping?host=IP&port=9021        -> اختبار الاتصال بالـ PS5
 *   POST /send?host=IP&port=9021        -> body = ملف ELF، يُرسل خاماً عبر TCP
 *   GET  /<file>                        -> ملفات ثابتة (الصفحة والحمولة)
 */

'use strict';

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = __dirname;
const DEFAULT_BRIDGE_PORT = 8765;
const DEFAULT_PS5_PORT = 9021;
const READ_TIMEOUT_MS = 3000;
const MAX_UPLOAD = 64 * 1024 * 1024;

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.elf': 'application/octet-stream',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/plain; charset=utf-8',
};

function lanIPs() {
  const out = [];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const ni of list || []) {
      if (ni.family === 'IPv4' && !ni.internal) out.push(ni.address);
    }
  }
  return out;
}

function sendPayload(host, port, data) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const chunks = [];
    let wrote = false;
    let done = false;
    const sock = net.createConnection({ host, port });
    sock.setTimeout(5000);
    sock.on('connect', () => { wrote = true; sock.write(data); });
    sock.on('data', (c) => chunks.push(c));
    sock.on('end', () => finish());
    sock.on('close', () => finish());
    sock.on('timeout', () => sock.destroy());
    sock.on('error', (e) => {
      if (wrote) { finish(e); } else { reject(e); }
    });
    function finish(err) {
      if (done) return;
      done = true;
      resolve({ reply: Buffer.concat(chunks), elapsed: (Date.now() - started) / 1000, reset: err || null });
    }
    setTimeout(() => { if (!done) { done = true; sock.destroy(); resolve({ reply: Buffer.concat(chunks), elapsed: (Date.now() - started) / 1000, reset: null }); } }, READ_TIMEOUT_MS);
  });
}

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Private-Network');
  res.setHeader('Access-Control-Allow-Private-Network', 'true');
  res.setHeader('Access-Control-Max-Age', '600');
}

function json(res, obj, code = 200) {
  const body = Buffer.from(JSON.stringify(obj), 'utf8');
  cors(res);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Length', body.length);
  res.writeHead(code);
  res.end(body);
}

function serveStatic(res, route) {
  const rel = route.replace(/^\/+/, '') || 'index.html';
  const target = path.resolve(ROOT, rel);
  if (!target.startsWith(path.resolve(ROOT)) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
    cors(res);
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('not found\n');
    return;
  }
  const body = fs.readFileSync(target);
  const ctype = CONTENT_TYPES[path.extname(target).toLowerCase()] || 'application/octet-stream';
  cors(res);
  res.setHeader('Content-Type', ctype);
  res.setHeader('Content-Length', body.length);
  res.setHeader('Cache-Control', 'no-store');
  res.writeHead(200);
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const route = url.pathname.replace(/\/+$/, '') || '/';
  const q = url.searchParams;

  if (req.method === 'OPTIONS') {
    cors(res);
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === 'GET' && route === '/info') {
    json(res, { ok: true, bridge: `http://127.0.0.1:${server.address().port}`, lanIPs: lanIPs(), port: server.address().port, root: ROOT });
    return;
  }

  if (req.method === 'GET' && route === '/ping') {
    const host = (q.get('host') || '').trim();
    const port = parseInt(q.get('port') || String(DEFAULT_PS5_PORT), 10);
    if (!host) { json(res, { ok: false, message: 'missing host' }, 400); return; }
    const s = net.createConnection({ host, port });
    s.setTimeout(4000);
    s.on('connect', () => { s.destroy(); json(res, { ok: true, message: `${host}:${port} reachable` }); });
    s.on('timeout', () => { s.destroy(); json(res, { ok: false, message: `timeout ${host}:${port}` }); });
    s.on('error', (e) => json(res, { ok: false, message: `${host}: ${e.message}` }));
    return;
  }

  if (req.method === 'POST' && route === '/send') {
    const host = (q.get('host') || '').trim();
    const port = parseInt(q.get('port') || String(DEFAULT_PS5_PORT), 10);
    if (!host) { json(res, { ok: false, message: 'missing host' }, 400); return; }
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_UPLOAD) { req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => {
      const data = Buffer.concat(chunks);
      if (!data.length) { json(res, { ok: false, message: 'empty payload' }, 400); return; }
      sendPayload(host, port, data)
        .then(({ reply, elapsed, reset }) => {
          const text = reply.toString('utf8').replace(/\0/g, '').trim();
          json(res, {
            ok: true,
            message: `sent ${data.length} bytes to ${host}:${port} in ${elapsed.toFixed(3)}s`
              + (reset ? ` — console closed the connection without a reply (${reset.message})` : ''),
            sent: data.length,
            reply: text || (reset ? '[elfldr] no reply — the console closed the connection (payload rejected?)' : ''),
          });
        })
        .catch((e) => json(res, { ok: false, message: `TCP ${host}:${port} failed: ${e.message}`, sent: 0 }));
    });
    return;
  }

  if (req.method === 'GET') { serveStatic(res, route); return; }

  json(res, { ok: false, message: 'unknown route' }, 404);
});

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

async function main() {
  const sendFile = arg('--send', '');
  if (sendFile) {
    const host = arg('--ps5-host', process.env.PS5_HOST || '');
    const port = parseInt(arg('--ps5-port', String(DEFAULT_PS5_PORT)), 10);
    if (!host) { console.error('حدد عنوان الـ PS5: --ps5-host 192.168.1.50'); process.exit(2); }
    const data = fs.readFileSync(sendFile);
    console.log(`أرسل ${sendFile} (${data.length} bytes) إلى ${host}:${port} ...`);
    try {
      const { reply, elapsed } = await sendPayload(host, port, data);
      console.log(`تم الإرسال في ${elapsed.toFixed(3)}s`);
      if (reply.length) console.log('رد الجهاز:\n' + reply.toString('utf8').replace(/\0/g, ''));
      else console.log('لا يوجد رد من الجهاز (طبيعي إذا كان الـ payload يعمل بدون طباعة).');
    } catch (e) {
      console.error('فشل الاتصال: ' + e.message);
      process.exit(1);
    }
    return;
  }

  const bind = arg('--host', '127.0.0.1');
  const port = parseInt(arg('--port', String(DEFAULT_BRIDGE_PORT)), 10);
  server.listen(port, bind, () => {
    console.log('PS5 ELF bridge جاهز');
    console.log(`  محلي : http://127.0.0.1:${port}/`);
    for (const ip of lanIPs()) console.log(`  شبكة : http://${ip}:${port}/`);
    console.log('  إرسال: POST /send?host=<PS5_IP>&port=9021   (body = ملف ELF)');
    console.log('  اختبار: GET  /ping?host=<PS5_IP>&port=9021');
  });
}

main();
