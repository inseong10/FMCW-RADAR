#!/usr/bin/env python3
"""Local-only radar dashboard. Start from any working directory."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser

from data import board_baseline, import_spectra, recording, simulate

STATIC = Path(__file__).with_name('static')
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/style.css': ('style.css', 'text/css')}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type='application/json'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            if self.path == '/api/recording':
                return self.respond(200, recording())
            if self.path == '/api/baseline':
                return self.respond(200, board_baseline())
            if self.path in ASSETS:
                filename, content_type = ASSETS[self.path]
                return self.respond(200, (STATIC / filename).read_bytes(), content_type)
            self.respond(404, dict(error='요청한 경로가 없습니다.'))
        except (OSError, ValueError, KeyError) as exc:
            self.respond(400, dict(error=str(exc)))

    def do_POST(self):
        # The local app accepts same-origin JSON only, with bounded input.
        if self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host")}'):
            return self.respond(403, dict(error='다른 출처의 요청은 허용하지 않습니다.'))
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.respond(415, dict(error='JSON 요청이 필요합니다.'))
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8 * 1024 * 1024:
                raise ValueError('요청 크기는 8 MiB 이하여야 합니다.')
            values = json.loads(self.rfile.read(size))
            if not isinstance(values, dict):
                raise ValueError('JSON 객체가 필요합니다.')
            if self.path == '/api/simulate':
                return self.respond(200, simulate(values))
            if self.path == '/api/import':
                return self.respond(200, import_spectra(values))
            self.respond(404, dict(error='요청한 경로가 없습니다.'))
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RuntimeError, ImportError) as exc:
            self.respond(400, dict(error=str(exc)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='Open the dashboard in the default browser')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'FMCW RADAR LAB · {url}\nStop: Ctrl+C', flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
