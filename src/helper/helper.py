#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer


HOST = "0.0.0.0"
PORT = 8091


HTML = b"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TorrServer Helper</title>
</head>
<body>
    <h1>TorrServer Helper</h1>
    <p>Status: Running</p>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML)))
            self.end_headers()
            self.wfile.write(HTML)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
