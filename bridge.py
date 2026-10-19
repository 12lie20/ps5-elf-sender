#!/usr/bin/env python3
"""
PS5 ELF bridge
==============

يسرّع ملف ELF إلى جهاز PS5 عبر منفذ 9021 (الخدمة ``elfldr`` من
ps5-payload-dev/elfldr) بدون أي مكتبات خارجية - بايثون القياسية فقط.

لماذا الجسر؟
-------------
المتصفحات لا تستطيع فتح منفذ TCP خام، لذلك الصفحة (github.io / HTTPS) لا
تصل مباشرة إلى ``PS5:9021``. هذا الجسر يعمل على جهازك، يستقبل الملف من
الصفحة عبر HTTP، ثم يفتح اتصال TCP عادي إلى ``PS5:9021`` ويرسل الـ ELF
خاماً بالترتيب الذي يتوقعه ``elfldr``:

    recv(52)  -> Elf64_Ehdr
    recv(...) -> من e_shoff حتى نهاية جدول الأقسام
    recv(...) -> بقية الأقسام إن كانت أوسع

أي ببساطة: أرسل الملف كاملاً بالترتيب.

الاستخدام
---------
    python bridge.py                       # تشغيل الخادم على 127.0.0.1:8765
    python bridge.py --host 0.0.0.0         # إتاحته لأجهزة الشبكة
    python bridge.py --send crlr69.elf     # إرسال ملف مباشرة من الطرفية
    python bridge.py --send crlr69.elf --host 192.168.1.50 --port 9021
"""

import argparse
import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))

DEFAULT_BRIDGE_PORT = 8765
DEFAULT_PS5_PORT = 9021
DEFAULT_READ_TIMEOUT = 3.0
MAX_UPLOAD = 64 * 1024 * 1024

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".elf": "application/octet-stream",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}


def lan_ips():
    """عناوين IP المحلية للجهاز (بدون loopback)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


def send_payload(host, port, data, read_timeout=DEFAULT_READ_TIMEOUT, connect_timeout=5.0):
    """يرسل bytes إلى PS5:port عبر TCP ويعيد (الرد، الزمن، خطأ القراءة)."""
    started = time.time()
    sock = socket.create_connection((host, port), timeout=connect_timeout)
    try:
        sock.settimeout(connect_timeout)
        sock.sendall(data)
        sock.settimeout(read_timeout)
        chunks = []
        reset = None
        try:
            while True:
                part = sock.recv(4096)
                if not part:
                    break
                chunks.append(part)
        except socket.timeout:
            pass
        except OSError as e:
            # الجهاز أغلق الاتصال بشكل مفاجئ (RST) - غالباً رفض الحمولة
            reset = e
        return b"".join(chunks), time.time() - started, reset
    finally:
        try:
            sock.close()
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "PS5ElfBridge/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------- plumbing ----------------
    def log_message(self, fmt, *args):
        sys.stderr.write("  [bridge] %s\n" % (fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Private-Network")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, code=200):
        body = text.encode("utf-8", "replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------------- routes ----------------
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if route == "/info":
            self._json({
                "ok": True,
                "bridge": "http://127.0.0.1:%d" % self.server.server_address[1],
                "lanIPs": lan_ips(),
                "port": self.server.server_address[1],
                "root": ROOT,
            })
            return

        if route == "/ping":
            host = query.get("host", "").strip()
            port = int(query.get("port", DEFAULT_PS5_PORT) or DEFAULT_PS5_PORT)
            if not host:
                self._json({"ok": False, "message": "missing host"}, 400)
                return
            try:
                s = socket.create_connection((host, port), timeout=4.0)
                s.close()
            except OSError as e:
                self._json({"ok": False, "message": "%s: %s" % (host, e)}, 200)
                return
            self._json({"ok": True, "message": "%s:%d reachable" % (host, port)})
            return

        self._static(route)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if route != "/send":
            self._json({"ok": False, "message": "unknown route %s" % route}, 404)
            return

        host = query.get("host", "").strip()
        port = int(query.get("port", DEFAULT_PS5_PORT) or DEFAULT_PS5_PORT)
        if not host:
            self._json({"ok": False, "message": "missing host"}, 400)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_UPLOAD:
            self._json({"ok": False, "message": "empty or oversized payload"}, 400)
            return

        data = self.rfile.read(length)
        if len(data) != length:
            self._json({"ok": False, "message": "short read"}, 400)
            return

        try:
            reply, elapsed, reset = send_payload(host, port, data)
        except OSError as e:
            self._json({
                "ok": False,
                "message": "TCP %s:%d failed: %s" % (host, port, e),
                "sent": 0,
            })
            return

        text = reply.decode("utf-8", "replace").replace("\x00", "")
        message = "sent %d bytes to %s:%d in %.3fs" % (len(data), host, port, elapsed)
        if reset is not None:
            message += " - الجهاز أغلق الاتصال بدون رد (%s)" % reset
            if not text:
                text = "[elfldr] no reply - the console closed the connection (payload rejected?)"
        self._json({
            "ok": True,
            "message": message,
            "sent": len(data),
            "reply": text.strip(),
        })

    # ---------------- static ----------------
    def _static(self, route):
        rel = route.lstrip("/") or "index.html"
        target = os.path.normpath(os.path.join(ROOT, rel))
        if not target.startswith(ROOT) or not os.path.isfile(target):
            self._text("not found: %s\n" % route, 404)
            return
        with open(target, "rb") as fh:
            body = fh.read()
        ctype = CONTENT_TYPES.get(os.path.splitext(target)[1].lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)


def run_server(bind, port):
    httpd = ThreadingHTTPServer((bind, port), Handler)
    httpd.daemon_threads = True
    ips = lan_ips()
    print("PS5 ELF bridge جاهز")
    print("  محلي : http://127.0.0.1:%d/" % port)
    for ip in ips:
        print("  شبكة : http://%s:%d/" % (ip, port))
    print("  إرسال: POST /send?host=<PS5_IP>&port=9021   (body = ملف ELF)")
    print("  اختبار: GET  /ping?host=<PS5_IP>&port=9021")
    print("  معلومات: GET /info")
    print("  لإيقاف الجسر: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nتم إيقاف الجسر.")
    finally:
        httpd.server_close()


def run_once(host, port, path, timeout):
    with open(path, "rb") as fh:
        data = fh.read()
    print("أرسل %s (%d bytes) إلى %s:%d ..." % (path, len(data), host, port))
    try:
        reply, elapsed, reset = send_payload(host, port, data, read_timeout=timeout)
    except OSError as e:
        print("فشل الاتصال: %s" % e)
        return 1
    print("تم الإرسال في %.3fs" % elapsed)
    if reset is not None:
        print("الجهاز أغلق الاتصال بدون رد: %s" % reset)
    if reply:
        print("رد الجهاز:\n%s" % reply.decode("utf-8", "replace").replace("\x00", ""))
    else:
        print("لا يوجد رد من الجهاز (هذا طبيعي إذا كان الـ payload يعمل بدون طباعة).")
    return 0


def main():
    # الطرفية على ويندوز قد تستخدم cp1252 - نثبت UTF-8 حتى لا تتعطل عند طباعة العربية
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="PS5 ELF bridge - إرسال ملفات ELF إلى PS5 عبر منفذ 9021")
    ap.add_argument("--host", default="127.0.0.1", help="عنوان الاستماع للـ HTTP (0.0.0.0 لإتاحته للشبكة)")
    ap.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT, help="منفذ الجسر")
    ap.add_argument("--send", metavar="FILE", help="أرسل ملف ELF مباشرة إلى PS5 وخرج")
    ap.add_argument("--ps5-host", default="", help="عنوان PS5 (يُستخدم مع --send)")
    ap.add_argument("--ps5-port", type=int, default=DEFAULT_PS5_PORT, help="منفذ PS5 (افتراضي 9021)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_READ_TIMEOUT, help="مدة انتظار رد الجهاز")
    args = ap.parse_args()

    if args.send:
        target = args.ps5_host or os.environ.get("PS5_HOST", "")
        if not target:
            print("حدد عنوان الـ PS5: --ps5-host 192.168.1.50", file=sys.stderr)
            return 2
        return run_once(target, args.ps5_port, args.send, args.timeout)

    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
