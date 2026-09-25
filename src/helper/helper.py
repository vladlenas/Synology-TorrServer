#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import os
import re
import subprocess
import urllib.parse


HOST = "0.0.0.0"
PORT = 8091

TORRSERVER_PORT = 8090
TORRSERVER_URL = "http://127.0.0.1:8090/"


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def get_dsm_info():
    data = {}

    version = read_file("/etc.defaults/VERSION")

    for line in version.splitlines():
        match = re.match(r'^([A-Za-z0-9_]+)="(.*)"$', line)
        if match:
            data[match.group(1)] = match.group(2)

    synoinfo = read_file("/etc.defaults/synoinfo.conf")

    for key in ("platform_name", "product", "unique"):
        match = re.search(
            r'^' + re.escape(key) + r'="([^"]*)"',
            synoinfo,
            re.MULTILINE
        )
        if match:
            data[key] = match.group(1)

    return data


def get_cpu_info():
    cpuinfo = read_file("/proc/cpuinfo")

    model = "Unknown"
    cores = 0

    for line in cpuinfo.splitlines():
        if line.startswith("model name"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                model = parts[1].strip()
            break

    for line in cpuinfo.splitlines():
        if line.startswith("processor"):
            cores += 1

    if cores == 0:
        cores = os.cpu_count() or 1

    return model, cores


def get_memory_info():
    meminfo = read_file("/proc/meminfo")

    values = {}

    for line in meminfo.splitlines():
        parts = line.split()

        if len(parts) >= 2:
            try:
                values[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                pass

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))

    return total, available


def format_memory(kb):
    if kb <= 0:
        return "Unknown"

    gb = kb / 1024 / 1024

    if gb >= 1:
        return "{:.1f} GB".format(gb)

    mb = kb / 1024
    return "{:.0f} MB".format(mb)


def get_uptime():
    uptime = read_file("/proc/uptime").split()

    if not uptime:
        return "Unknown"

    try:
        seconds = int(float(uptime[0]))

        days = seconds // 86400
        seconds %= 86400

        hours = seconds // 3600
        seconds %= 3600

        minutes = seconds // 60

        if days:
            return "{} d {} h {} min".format(days, hours, minutes)

        if hours:
            return "{} h {} min".format(hours, minutes)

        return "{} min".format(minutes)

    except (ValueError, TypeError):
        return "Unknown"


def get_load():
    loadavg = read_file("/proc/loadavg").split()

    if not loadavg:
        return "Unknown"

    return loadavg[0]


def get_architecture():
    try:
        return os.uname().machine
    except Exception:
        return "Unknown"


def get_torrserver():
    try:
        import urllib.request

        request = urllib.request.Request(
            TORRSERVER_URL + "echo",
            method="GET"
        )

        with urllib.request.urlopen(request, timeout=2) as response:
            status = response.getcode()
            version = response.read().decode("utf-8", errors="replace").strip()

            if status == 200:
                return True, version

    except Exception:
        pass

    return False, "Unknown"


def get_package_status():
    """
    Read TorrServer package status through synopkg.

    This is only a read operation.
    Start/stop/restart will be implemented separately.
    """

    try:
        result = subprocess.run(
            [
                "/usr/syno/bin/synopkg",
                "status",
                "TorrServer"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=3
        )

        output = result.stdout.strip()

        if '"status":"running"' in output:
            return "running"

        if '"status":"stop"' in output:
            return "stopped"

    except Exception:
        pass

    return "unknown"


def esc(value):
    return html.escape(str(value))


def card(title, content):
    return """
    <div class="card">
        <div class="card-title">{}</div>
        <div class="card-content">
            {}
        </div>
    </div>
    """.format(title, content)


def row(name, value):
    return """
    <div class="row">
        <div class="label">{}</div>
        <div class="value">{}</div>
    </div>
    """.format(esc(name), esc(value))


def make_html():
    dsm = get_dsm_info()

    cpu_model, cpu_cores = get_cpu_info()
    mem_total, mem_available = get_memory_info()

    architecture = get_architecture()
    uptime = get_uptime()
    load = get_load()

    torrserver_running, torrserver_version = get_torrserver()
    package_status = get_package_status()

    if torrserver_running:
        ts_status = "Running"
        ts_status_class = "status-running"
    else:
        ts_status = "Stopped"
        ts_status_class = "status-stopped"

    if package_status == "running":
        package_status_text = "Running"
    elif package_status == "stopped":
        package_status_text = "Stopped"
    else:
        package_status_text = "Unknown"

    system_content = (
        row("DSM", dsm.get("productversion", "Unknown")) +
        row("Build", dsm.get("buildnumber", "Unknown")) +
        row("Model", dsm.get("product", "Unknown")) +
        row("Platform", dsm.get("platform_name", "Unknown")) +
        row("Architecture", architecture) +
        row("CPU", cpu_model) +
        row("CPU cores", cpu_cores) +
        row(
            "RAM",
            "{} / {}".format(
                format_memory(mem_available),
                format_memory(mem_total)
            )
        ) +
        row("Uptime", uptime) +
        row("Load", load)
    )

    torrserver_content = """
        <div class="status-line">
            <span class="status-dot {}"></span>
            <span>{}</span>
        </div>
        {}
        {}
        {}
        <div class="button-row">
            <a class="button primary" href="{}" target="_blank">
                Open TorrServer Web UI
            </a>
        </div>
    """.format(
        ts_status_class,
        esc(ts_status),
        row("Version", torrserver_version),
        row("Web port", TORRSERVER_PORT),
        row("Package", package_status_text),
        TORRSERVER_URL
    )

    return """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TorrServer</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 24px;
            background: #f3f4f6;
            color: #333;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Arial,
                sans-serif;
            font-size: 14px;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            align-items: center;
            margin-bottom: 22px;
        }

        .icon {
            width: 48px;
            height: 48px;
            border-radius: 10px;
            background: #e8edf5;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 14px;
            font-size: 24px;
        }

        .header h1 {
            margin: 0;
            font-size: 22px;
            font-weight: 500;
            color: #222;
        }

        .header p {
            margin: 4px 0 0;
            color: #777;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .card {
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
        }

        .card-title {
            padding: 14px 16px;
            background: #f8f9fa;
            border-bottom: 1px solid #e1e1e1;
            font-size: 16px;
            font-weight: 500;
            color: #333;
        }

        .card-content {
            padding: 8px 16px 16px;
        }

        .row {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }

        .row:last-child {
            border-bottom: 0;
        }

        .label {
            color: #777;
        }

        .value {
            color: #333;
            text-align: right;
            word-break: break-word;
        }

        .status-line {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 0;
            font-size: 16px;
            font-weight: 500;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }

        .status-running {
            background: #35a854;
        }

        .status-stopped {
            background: #d93025;
        }

        .button-row {
            padding-top: 14px;
        }

        .button {
            display: inline-block;
            padding: 9px 16px;
            border-radius: 5px;
            text-decoration: none;
            font-size: 14px;
            cursor: pointer;
        }

        .button.primary {
            background: #1677ff;
            color: #fff;
        }

        .button.primary:hover {
            background: #0d66dc;
        }

        @media (max-width: 700px) {
            body {
                padding: 12px;
            }

            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
    <div class="container">

        <div class="header">
            <div class="icon">TS</div>
            <div>
                <h1>TorrServer</h1>
                <p>Synology package control panel</p>
            </div>
        </div>

        <div class="grid">

            {}
            
            {}

        </div>

    </div>
</body>
</html>
""".format(
        card("System Information", system_content),
        card("TorrServer", torrserver_content)
    )


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            content = make_html().encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(content))
            )
            self.send_header(
                "Cache-Control",
                "no-cache"
            )
            self.end_headers()

            self.wfile.write(content)
            return

        if parsed.path == "/api/status":
            running, version = get_torrserver()

            data = (
                '{{"running":{},"version":"{}"}}'
                .format(
                    "true" if running else "false",
                    version.replace('"', '\\"')
                )
            ).encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(data))
            )
            self.end_headers()

            self.wfile.write(data)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
