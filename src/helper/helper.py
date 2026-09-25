#!/bin/python3

import base64
import json
import os
import platform
import re
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer


CONFIG_DIR = "/var/packages/TorrServer/var"
PORT_CONFIG = os.path.join(CONFIG_DIR, "torrserver.port")
AUTH_CONFIG = os.path.join(CONFIG_DIR, "torrserver.auth")
ACCS_DB = os.path.join(CONFIG_DIR, "accs.db")
TORRSERVER_LOG = os.path.join(CONFIG_DIR, "TorrServer.log")

DEFAULT_PORT = 8090
HELPER_PORT = 8091


def get_port():
    try:
        with open(PORT_CONFIG, "r") as f:
            port = int(f.read().strip())

        if 1 <= port <= 65535:
            return port
    except Exception:
        pass

    return DEFAULT_PORT


def get_auth_enabled():
    try:
        with open(AUTH_CONFIG, "r") as f:
            enabled = f.read().strip() == "1"

        return enabled and os.path.isfile(ACCS_DB)
    except Exception:
        return False


def get_credentials():
    try:
        with open(ACCS_DB, "r") as f:
            data = json.load(f)

        if isinstance(data, dict) and data:
            username = next(iter(data))
            password = data[username]
            return username, password
    except Exception:
        pass

    return "", ""


def save_settings(port, auth_enabled, username, password):
    with open(PORT_CONFIG, "w") as f:
        f.write(str(port))

    with open(AUTH_CONFIG, "w") as f:
        f.write("1" if auth_enabled else "0")

    if username:
        data = {
            username: password
        }

        with open(ACCS_DB, "w") as f:
            json.dump(data, f)


def get_dsm_version():
    try:
        with open("/etc.defaults/VERSION", "r") as f:
            data = f.read()

        match = re.search(r'productversion="([^"]+)"', data)

        if match:
            return match.group(1)

    except Exception:
        pass

    return "Unknown"


def get_nas_model():
    try:
        with open("/etc.defaults/synoinfo.conf", "r") as f:
            data = f.read()

        match = re.search(r'product="([^"]+)"', data)

        if match:
            return match.group(1)

        match = re.search(r'platform_name="([^"]+)"', data)

        if match:
            return match.group(1)

    except Exception:
        pass

    return "Unknown"


def get_cpu():
    try:
        with open("/proc/cpuinfo", "r") as f:
            data = f.read()

        model = re.search(r'model name\s*:\s*(.+)', data)

        if model:
            return model.group(1).strip()

        model = re.search(r'Processor\s*:\s*(.+)', data)

        if model:
            return model.group(1).strip()

    except Exception:
        pass

    return platform.processor() or "Unknown"


def get_cpu_cores():
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def get_architecture():
    try:
        return platform.machine()
    except Exception:
        return "Unknown"


def get_memory():
    total = 0
    available = 0

    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()

                if len(parts) < 2:
                    continue

                if parts[0] == "MemTotal:":
                    total = int(parts[1]) * 1024

                elif parts[0] == "MemAvailable:":
                    available = int(parts[1]) * 1024

    except Exception:
        pass

    return total, available


def format_bytes(value):
    if value <= 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]

    size = float(value)

    for unit in units:
        if size < 1024:
            return "%.1f %s" % (size, unit)

        size /= 1024

    return "%.1f PB" % size


def get_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            seconds = int(float(f.read().split()[0]))

        days = seconds // 86400
        seconds %= 86400

        hours = seconds // 3600
        seconds %= 3600

        minutes = seconds // 60

        if days:
            return "%dd %dh %dm" % (days, hours, minutes)

        if hours:
            return "%dh %dm" % (hours, minutes)

        return "%dm" % minutes

    except Exception:
        return "Unknown"


def get_load():
    try:
        with open("/proc/loadavg", "r") as f:
            return f.read().split()[0]
    except Exception:
        return "Unknown"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_torrserver():
    port = get_port()

    try:
        request = urllib.request.Request(
            "http://127.0.0.1:%d/echo" % port
        )

        username, password = get_credentials()

        if get_auth_enabled() and username:
            credentials = ("%s:%s" % (username, password)).encode("utf-8")
            encoded = base64.b64encode(credentials).decode("ascii")
            request.add_header(
                "Authorization",
                "Basic %s" % encoded
            )

        with urllib.request.urlopen(request, timeout=2) as response:
            version = response.read().decode("utf-8").strip()

        return True, version

    except Exception:
        return False, ""


def read_log():
    try:
        with open(TORRSERVER_LOG, "r", errors="replace") as f:
            lines = f.readlines()

        return "".join(lines[-100:])

    except Exception as e:
        return "Unable to read log: %s" % e


def restart_package():
    try:
        command = (
            "/bin/sleep 1; "
            "/bin/sudo -n /usr/syno/bin/synopkg stop TorrServer "
            "> /dev/null 2>&1; "
            "/bin/sleep 2; "
            "/bin/sudo -n /usr/syno/bin/synopkg start TorrServer "
            "> /dev/null 2>&1"
        )

        subprocess.Popen(
            [
                "/bin/sh",
                "-c",
                command
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True
        )

        return True, ""

    except Exception as e:
        return False, str(e)


HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>TorrServer</title>

<style>
body {
    margin: 0;
    padding: 0;
    background: #f5f5f5;
    color: #222;
    font-family: Arial, Helvetica, sans-serif;
}

.container {
    max-width: 900px;
    margin: 30px auto;
    padding: 0 20px;
}

h1 {
    margin-bottom: 25px;
}

.card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.card h2 {
    margin-top: 0;
}

.row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #eee;
}

.row:last-child {
    border-bottom: 0;
}

.label {
    font-weight: bold;
}

button {
    border: 0;
    border-radius: 6px;
    padding: 10px 16px;
    cursor: pointer;
    font-size: 14px;
    margin-right: 8px;
}

.primary {
    background: #1677ff;
    color: white;
}

.secondary {
    background: #e9e9e9;
    color: #222;
}

.danger {
    background: #d9534f;
    color: white;
}

input[type="text"],
input[type="number"],
input[type="password"] {
    width: 100%;
    box-sizing: border-box;
    padding: 9px;
    margin-top: 5px;
    margin-bottom: 12px;
    border: 1px solid #ccc;
    border-radius: 5px;
}

label {
    display: block;
    margin-bottom: 5px;
}

.checkbox {
    display: flex;
    align-items: center;
    margin: 12px 0;
}

.checkbox input {
    margin-right: 8px;
}

pre {
    background: #111;
    color: #eee;
    padding: 15px;
    border-radius: 6px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 500px;
}

.message {
    background: #e8f4ff;
    border: 1px solid #b7dcff;
    padding: 10px;
    border-radius: 6px;
    margin-bottom: 20px;
}

.status-ok {
    color: #198754;
    font-weight: bold;
}

.status-error {
    color: #dc3545;
    font-weight: bold;
}
</style>

<script>
function openWebUI() {
    window.open(
        "http://" + window.location.hostname + ":" + CURRENT_PORT,
        "_blank"
    );
}

function restartTorrServer() {
    if (!confirm("Restart TorrServer?")) {
        return;
    }

    const button = document.getElementById("restartButton");

    button.disabled = true;
    button.innerText = "Restarting...";

    fetch("/api/restart", {
        method: "POST"
    })
    .then(function() {
        setTimeout(function() {
            window.location.reload();
        }, 5000);
    })
    .catch(function() {
        setTimeout(function() {
            window.location.reload();
        }, 5000);
    });
}
</script>

</head>

<body>

<div class="container">

<h1>TorrServer</h1>

MESSAGE

<div class="card">

<h2>System</h2>

<div class="row">
    <span class="label">DSM</span>
    <span>DSM_VERSION</span>
</div>

<div class="row">
    <span class="label">NAS</span>
    <span>NAS_MODEL</span>
</div>

<div class="row">
    <span class="label">CPU</span>
    <span>CPU_MODEL</span>
</div>

<div class="row">
    <span class="label">Cores</span>
    <span>CPU_CORES</span>
</div>

<div class="row">
    <span class="label">Architecture</span>
    <span>ARCH</span>
</div>

<div class="row">
    <span class="label">RAM</span>
    <span>RAM_INFO</span>
</div>

<div class="row">
    <span class="label">Uptime</span>
    <span>UPTIME</span>
</div>

<div class="row">
    <span class="label">Load</span>
    <span>LOAD</span>
</div>

</div>


<div class="card">

<h2>TorrServer</h2>

<div class="row">
    <span class="label">Status</span>
    <span>TORR_STATUS</span>
</div>

<div class="row">
    <span class="label">Version</span>
    <span>TORR_VERSION</span>
</div>

<div class="row">
    <span class="label">Web port</span>
    <span>CURRENT_PORT</span>
</div>

<div class="row">
    <span class="label">HTTP Auth</span>
    <span>AUTH_STATUS</span>
</div>

<br>

<button class="primary" onclick="openWebUI()">
    Open Web UI
</button>

<button
    class="danger"
    id="restartButton"
    onclick="restartTorrServer()">
    Restart TorrServer
</button>

</div>


<div class="card">

<h2>Settings</h2>

<form method="POST" action="/api/settings">

<label>
    Web port
    <input
        type="number"
        name="port"
        min="1"
        max="65535"
        value="CURRENT_PORT"
        required>
</label>

<div class="checkbox">
    <input
        type="checkbox"
        name="auth"
        value="1"
        AUTH_CHECKED
        id="auth">
    <label for="auth">Enable HTTP authentication</label>
</div>

<label>
    Username
    <input
        type="text"
        name="username"
        value="USERNAME"
        autocomplete="off">
</label>

<label>
    Password
    <input
        type="password"
        name="password"
        value="PASSWORD"
        autocomplete="off">
</label>

<button class="primary" type="submit">
    Apply
</button>

</form>

</div>


<div class="card">

<h2>Logs</h2>

<pre>LOG_CONTENT</pre>

<form method="GET" action="/">
    <button class="secondary" type="submit">
        Refresh
    </button>
</form>

</div>

</div>

<script>
const CURRENT_PORT = PORT_NUMBER;
</script>

</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/status":

            running, version = get_torrserver()

            self.send_json({
                "running": running,
                "version": version,
                "port": get_port(),
                "auth": get_auth_enabled()
            })

            return

        if parsed.path == "/api/log":

            self.send_json({
                "log": read_log()
            })

            return

        if parsed.path == "/":

            query = urllib.parse.parse_qs(parsed.query)
            message = query.get("message", [""])[0]

            running, version = get_torrserver()

            if running:
                status = (
                    '<span class="status-ok">Running</span>'
                )
            else:
                status = (
                    '<span class="status-error">Stopped</span>'
                )

            auth_enabled = get_auth_enabled()

            if auth_enabled:
                auth_status = (
                    '<span class="status-ok">Enabled</span>'
                )
            else:
                auth_status = "Disabled"

            username, password = get_credentials()

            total_memory, available_memory = get_memory()

            html = HTML

            html = html.replace(
                "MESSAGE",
                (
                    '<div class="message">%s</div>' % message
                    if message else ""
                )
            )

            html = html.replace(
                "DSM_VERSION",
                get_dsm_version()
            )

            html = html.replace(
                "NAS_MODEL",
                get_nas_model()
            )

            html = html.replace(
                "CPU_MODEL",
                get_cpu()
            )

            html = html.replace(
                "CPU_CORES",
                str(get_cpu_cores())
            )

            html = html.replace(
                "ARCH",
                get_architecture()
            )

            html = html.replace(
                "RAM_INFO",
                "%s / %s available" % (
                    format_bytes(total_memory),
                    format_bytes(available_memory)
                )
            )

            html = html.replace(
                "UPTIME",
                get_uptime()
            )

            html = html.replace(
                "LOAD",
                get_load()
            )

            html = html.replace(
                "TORR_STATUS",
                status
            )

            html = html.replace(
                "TORR_VERSION",
                version if version else "Unknown"
            )

            html = html.replace(
                "CURRENT_PORT",
                str(get_port())
            )

            html = html.replace(
                "PORT_NUMBER",
                str(get_port())
            )

            html = html.replace(
                "AUTH_STATUS",
                auth_status
            )

            html = html.replace(
                "AUTH_CHECKED",
                "checked" if auth_enabled else ""
            )

            html = html.replace(
                "USERNAME",
                username.replace('"', "&quot;")
            )

            html = html.replace(
                "PASSWORD",
                password.replace('"', "&quot;")
            )

            html = html.replace(
                "LOG_CONTENT",
                (
                    read_log()
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
            )

            body = html.encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(body))
            )
            self.end_headers()

            self.wfile.write(body)

            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/restart":

            success, error = restart_package()

            self.send_json({
                "success": success,
                "error": error
            })

            return

        if parsed.path == "/api/settings":

            try:
                content_length = int(
                    self.headers.get("Content-Length", "0")
                )

                body = self.rfile.read(content_length)

                data = urllib.parse.parse_qs(
                    body.decode("utf-8")
                )

                port = int(
                    data.get("port", [DEFAULT_PORT])[0]
                )

                if port < 1 or port > 65535:
                    raise ValueError("Invalid port")

                auth_enabled = (
                    data.get("auth", ["0"])[0] == "1"
                )

                username = data.get(
                    "username",
                    [""]
                )[0].strip()

                password = data.get(
                    "password",
                    [""]
                )[0]

                if auth_enabled and not username:
                    raise ValueError(
                        "Username is required when authentication is enabled"
                    )

                save_settings(
                    port,
                    auth_enabled,
                    username,
                    password
                )

                message = (
                    "Settings saved. "
                    "Restart TorrServer to apply changes."
                )

                location = (
                    "/?message=" +
                    urllib.parse.quote(message)
                )

                self.send_response(303)
                self.send_header("Location", location)
                self.end_headers()

            except Exception as e:

                message = "Error: %s" % e

                location = (
                    "/?message=" +
                    urllib.parse.quote(message)
                )

                self.send_response(303)
                self.send_header("Location", location)
                self.end_headers()

            return

        self.send_response(404)
        self.end_headers()


def main():

    server = HTTPServer(
        ("0.0.0.0", HELPER_PORT),
        Handler
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
