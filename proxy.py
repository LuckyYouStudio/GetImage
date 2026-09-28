#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地启动器：静态服务 index.html + 转发 /v1/* 到图片接口。

为什么需要它：img.the5288.com 的预检请求（OPTIONS）返回 403 且不下发
Access-Control-Allow-* 响应头，浏览器直连（file:// 打开页面）必被 CORS 拦截。
让页面和 API 走同一个源（本机 127.0.0.1）就绕开了这个限制。

用法：
    python proxy.py                                    # 启动并自动打开浏览器
    python proxy.py --port 9000                        # 换端口
    python proxy.py --target https://other-relay.com   # 换中转站
    python proxy.py --no-browser                       # 不自动开浏览器

仅监听本机回环地址；不读取也不存储 API Key（随请求头原样透传给目标服务）。
需要 Python 3.7+，无第三方依赖。
"""

import argparse
import os
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = "https://img.the5288.com"
PANEL = ""     # Sub2API 面板主机（--panel）。配了才转发 /api/v1/keys，供嵌入模式自动取 Key
TIMEOUT = 300  # 图片生成可能很慢，给足超时

ROOT = os.path.dirname(os.path.abspath(__file__))
API_PREFIXES = ("/v1/", "/v1beta/")

# 只透传必要的请求头：带上 Host / Origin / Referer 反而可能被目标站拒绝。
# user-agent 必须透传，原因见下面的 FALLBACK_UA。
FORWARD_REQ_HEADERS = ("authorization", "content-type", "accept", "user-agent",
                       "x-api-key", "openai-organization", "openai-project")

# 实测：img.the5288.com 会拦截 User-Agent 为 "Python-urllib/x.y" 的请求，
# 返回 502 {"message":"Upstream access forbidden, please contact administrator"}。
# 而 urllib 在请求头里没有 UA 时会自动补上这个值 —— 所以这里必须显式给一个。
# 浏览器发来的 UA 会原样透传，只有非浏览器客户端才会落到这个兜底值（已验证可用）。
FALLBACK_UA = "curl/8.4.0"
# 这几个响应头由 http.server 自己负责，原样回传会导致响应体错乱
SKIP_RESP_HEADERS = ("transfer-encoding", "connection", "content-encoding", "content-length")

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Windows 上 SO_REUSEADDR 允许直接抢占已被占用的端口，两个实例会同时绑到一个口上，
    # 端口占用检测因此失效。关掉它，让 bind 真正报错，下面的端口顺延才有意义。
    # 类 Unix 上保持 True，否则重启时会撞上 TIME_WAIT。
    allow_reuse_address = (os.name != "nt")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "getimage-local"

    # ---------- 响应小工具 ----------

    def _cors(self):
        # 同源访问其实用不到，留着是为了让人能从别处的页面指过来
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept, X-Api-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _fail(self, code, message):
        body = ('{"error":{"message":%s,"type":"local_proxy_error"}}'
                % _json_str(message)).encode("utf-8")
        self._send(code, body)

    # ---------- 路由 ----------

    def _route(self):
        """返回该请求应转发到的上游 origin；None 表示走静态文件。"""
        path = self.path.split("?", 1)[0]
        if path.startswith(API_PREFIXES):
            return TARGET
        # 面板嵌入模式下页面用登录 token 取用户自己的 API Key，只放行这一个面板接口
        if PANEL and path == "/api/v1/keys":
            return PANEL
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        upstream = self._route()
        if upstream:
            self._forward("GET", upstream)
        else:
            self._static()

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        upstream = self._route()
        if upstream:
            self._forward("POST", upstream)
        else:
            self._fail(404, "未知路径：%s" % self.path)

    # ---------- 静态文件 ----------

    def _static(self):
        rel = self.path.split("?", 1)[0].split("#", 1)[0]
        if rel in ("", "/"):
            rel = "/index.html"
        path = os.path.normpath(os.path.join(ROOT, rel.lstrip("/\\")))
        if not path.startswith(ROOT) or not os.path.isfile(path):
            self._fail(404, "找不到文件：%s" % rel)
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            self._fail(500, "读取失败：%s" % e)
            return
        ctype = MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        self._send(200, data, ctype, extra=[("Cache-Control", "no-store")])

    # ---------- API 转发 ----------

    def _forward(self, method, upstream):
        url = upstream.rstrip("/") + self.path
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""

        headers = {k: v for k, v in self.headers.items()
                   if k.lower() in FORWARD_REQ_HEADERS}
        if not any(k.lower() == "user-agent" for k in headers):
            headers["User-Agent"] = FALLBACK_UA
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        print("  -> %s %s" % (method, url), flush=True)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data, status, rhead = resp.read(), resp.status, resp.headers
        except urllib.error.HTTPError as e:
            # 目标站的错误响应体对排查非常有用，原样回传
            data, status, rhead = e.read(), e.code, e.headers
        except Exception as e:
            print("  !! %s" % e, flush=True)
            self._fail(502, "转发失败：%s" % e)
            return

        print("  <- %d (%d bytes)" % (status, len(data)), flush=True)
        self.send_response(status)
        self._cors()
        for k, v in rhead.items():
            kl = k.lower()
            if kl not in SKIP_RESP_HEADERS and not kl.startswith("access-control-"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # 用上面自己的日志，屏蔽默认那行


def _json_str(s):
    esc = {"\r": "\\r", "\n": "\\n", "\t": "\\t", '"': '\\"', "\\": "\\\\"}
    out = ['"']
    for ch in str(s):
        if ch in esc:
            out.append(esc[ch])
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def main():
    global TARGET, PANEL
    ap = argparse.ArgumentParser(description="图片生成器的本地启动器（静态服务 + API 转发）")
    ap.add_argument("--port", type=int, default=8788, help="监听端口（默认 8788）")
    ap.add_argument("--target", default=TARGET, help="转发目标（默认 %s）" % TARGET)
    ap.add_argument("--panel", default="", help="Sub2API 面板地址，如 https://panel.example.com；配了才转发 /api/v1/keys")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()
    TARGET = args.target
    PANEL = args.panel.strip().rstrip("/")

    # 端口被占用时自动往后找一个能用的，省得用户自己去查冲突
    srv, port = None, None
    for candidate in range(args.port, args.port + 12):
        try:
            srv = Server(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if srv is None:
        print("%d ~ %d 端口全被占用了。" % (args.port, args.port + 11))
        print("手动指定一个空闲端口：python proxy.py --port 9500")
        sys.exit(1)
    if port != args.port:
        print("%d 端口被占用，已自动改用 %d" % (args.port, port))
    home = "http://127.0.0.1:%d/" % port

    print("已启动")
    print("  打开：%s" % home)
    print("  转发：%s" % TARGET)
    print("  用完直接关掉这个黑窗口即可\n")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(home)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        srv.server_close()


if __name__ == "__main__":
    main()
