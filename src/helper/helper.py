 #!/usr/bin/env python3

import base64
import html
import json
import os
import platform
import re
import shutil
import subprocess
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


HOST = "0.0.0.0"
HELPER_PORT = 8095

PACKAGE_NAME = "TorrServer"
PACKAGE_VAR = "/var/packages/TorrServer/var"
TORRSERVER_BIN = "/var/packages/TorrServer/target/bin/TorrServer"
TORRSERVER_LOG = os.path.join(PACKAGE_VAR, "TorrServer.log")
LOG_MAX_SIZE = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 2

PORT_FILE = os.path.join(PACKAGE_VAR, "torrserver.port")
AUTH_FILE = os.path.join(PACKAGE_VAR, "torrserver.auth")
ACCS_FILE = os.path.join(PACKAGE_VAR, "accs.db")

RESTART_SCRIPT = "/var/packages/TorrServer/scripts/restart-package"


def read_file(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return default


def write_file(path, value):
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        f.write(value)

    os.replace(tmp, path)


def get_dsm_version():
    paths = [
        "/etc.defaults/VERSION",
        "/etc/VERSION",
    ]

    for path in paths:
        try:
            data = {}

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if "=" in line:
                        key, value = line.split("=", 1)
                        data[key.strip()] = value.strip().strip('"')

            version = data.get("productversion", "")
            build = data.get("buildnumber", "")

            if version:
                if build:
                    return "{}-{}".format(version, build)

                return version

        except Exception:
            pass

    return "Unknown"


def get_nas_model():
    model = read_file("/proc/sys/kernel/syno_hw_version", "").strip()

    if model:
        return model

    try:
        data = {}

        with open("/etc.defaults/VERSION", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if "=" in line:
                    key, value = line.split("=", 1)
                    data[key.strip()] = value.strip().strip('"')

        model = data.get("modelname", "").strip()
        if model:
            return model

        unique = data.get("unique", "").strip()
        if unique:
            return unique

    except Exception:
        pass

    return "Unknown"


def get_cpu_model():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if ":" not in line:
                    continue

                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if key == "model name" and value:
                    return value

                if key == "hardware" and value:
                    hardware = value

    except Exception:
        hardware = ""

    try:
        if hardware:
            return hardware
    except Exception:
        pass

    try:
        value = platform.processor().strip()
        if value and not value.isdigit():
            return value
    except Exception:
        pass

    return "Unknown"


def get_memory():
    total = 0
    available = 0

    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()

                if len(parts) < 2:
                    continue

                value = int(parts[1]) * 1024

                if line.startswith("MemTotal:"):
                    total = value

                elif line.startswith("MemAvailable:"):
                    available = value

    except Exception:
        pass

    return total, available


def format_bytes(value):
    if value <= 0:
        return "Unknown"

    units = ["B", "KB", "MB", "GB", "TB"]

    size = float(value)

    for unit in units:
        if size < 1024:
            return "{:.1f} {}".format(size, unit)

        size /= 1024

    return "{:.1f} PB".format(size)


def get_uptime():
    try:
        seconds = float(read_file("/proc/uptime", "0").split()[0])

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days:
            return "{}d {}h {}m".format(days, hours, minutes)

        if hours:
            return "{}h {}m".format(hours, minutes)

        return "{}m".format(minutes)

    except Exception:
        return "Unknown"


def get_load():
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            return f.read().split()[0]

    except Exception:
        return "Unknown"


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


def get_torrserver_version():
    try:
        result = subprocess.run(
            [TORRSERVER_BIN, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )

        output = result.stdout.strip()

        if output:
            return output

    except Exception:
        pass

    return "Unknown"


def get_port():
    port = 8090

    value = read_file(PORT_FILE, "")

    if value.isdigit():
        number = int(value)

        if 1 <= number <= 65535:
            port = number

    return port


def get_auth_enabled():
    return read_file(AUTH_FILE, "0") == "1" and os.path.isfile(ACCS_FILE)


def is_torrserver_running():
    try:
        result = subprocess.run(
            ["pidof", "TorrServer"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )

        return bool(result.stdout.strip())

    except Exception:
        return False


def get_status():
    return "Running" if is_torrserver_running() else "Stopped"


def get_torrserver_uptime():
    try:
        result = subprocess.run(
            ["pidof", "TorrServer"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        pids = result.stdout.strip().split()
        if not pids:
            return "Stopped"

        with open("/proc/{}/stat".format(pids[0]), "r", encoding="utf-8") as f:
            stat_data = f.read().split()

        start_ticks = int(stat_data[21])

        with open("/proc/uptime", "r", encoding="utf-8") as f:
            system_uptime = float(f.read().split()[0])

        clock_ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        elapsed = max(0, int(system_uptime - (start_ticks / clock_ticks)))

        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        minutes = (elapsed % 3600) // 60

        if days:
            return "{}d {}h {}m".format(days, hours, minutes)
        if hours:
            return "{}h {}m".format(hours, minutes)
        return "{}m".format(minutes)

    except Exception:
        return "Unknown"


def restart_package():
    """
    Start the dedicated root restart script through sudo.

    The script itself runs as root, so it survives the package
    stop operation initiated by synopkg.
    """

    if not os.path.isfile(RESTART_SCRIPT):
        return False, "Restart script not found"

    try:
        process = subprocess.Popen(
            [
                "/bin/sudo",
                "-n",
                RESTART_SCRIPT,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

        if process.pid <= 0:
            return False, "Failed to start restart script"

        return True, "Restarting..."

    except Exception as e:
        return False, str(e)


def save_settings(params):
    port = params.get("port", [""])[0].strip()
    auth = params.get("auth", ["0"])[0]
    username = params.get("username", [""])[0]
    password = params.get("password", [""])[0]

    if not port.isdigit():
        return False, "Invalid port"

    port_number = int(port)

    if port_number < 1 or port_number > 65535:
        return False, "Invalid port"

    write_file(PORT_FILE, str(port_number))

    if auth == "1":
        if not username:
            return False, "Username is required"

        if not password:
            return False, "Password is required"

        account = {
            username: password
        }

        with open(ACCS_FILE, "w", encoding="utf-8") as f:
            json.dump(account, f)

        write_file(AUTH_FILE, "1")

    else:
        write_file(AUTH_FILE, "0")

    return True, "Settings saved"


def get_log():
    try:
        with open(TORRSERVER_LOG, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()

        if len(data) > 200000:
            data = data[-200000:]

        return data

    except Exception as e:
        return "Unable to read log: {}".format(e)


def rotate_log_if_needed():
    try:
        if not os.path.isfile(TORRSERVER_LOG):
            return

        if os.path.getsize(TORRSERVER_LOG) < LOG_MAX_SIZE:
            return

        oldest = "{}.{}".format(TORRSERVER_LOG, LOG_BACKUP_COUNT)
        if os.path.exists(oldest):
            os.remove(oldest)

        for number in range(LOG_BACKUP_COUNT - 1, 0, -1):
            source = "{}.{}".format(TORRSERVER_LOG, number)
            target = "{}.{}".format(TORRSERVER_LOG, number + 1)

            if os.path.exists(source):
                os.replace(source, target)

        shutil.copyfile(
            TORRSERVER_LOG,
            "{}.1".format(TORRSERVER_LOG),
        )

        with open(TORRSERVER_LOG, "r+", encoding="utf-8") as f:
            f.truncate(0)

    except Exception:
        pass


def page_header(title="TorrServer"):
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 0;
    background: #f5f5f5;
    color: #222;
}}

.container {{
    max-width: 1000px;
    margin: 30px auto;
    padding: 0 20px;
}}

.card {{
    background: #fff;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.12);
}}

h1 {{
    margin-top: 0;
}}

h2 {{
    margin-top: 0;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

td {{
    padding: 8px 4px;
    border-bottom: 1px solid #eee;
}}

td:first-child {{
    width: 220px;
    font-weight: bold;
}}

input[type=text],
input[type=password],
input[type=number] {{
    width: 100%;
    max-width: 400px;
    box-sizing: border-box;
    padding: 9px;
    border: 1px solid #bbb;
    border-radius: 5px;
}}

button,
.button {{
    display: inline-block;
    border: 0;
    border-radius: 5px;
    padding: 9px 14px;
    cursor: pointer;
    text-decoration: none;
    background: #1677ff;
    color: white;
}}

button.secondary,
.button.secondary {{
    background: #666;
}}

button.danger {{
    background: #c62828;
}}

.nav {{
    margin-bottom: 20px;
}}

.nav a {{
    margin-right: 10px;
}}

.status-running {{
    color: #16803c;
    font-weight: bold;
}}

.status-stopped {{
    color: #c62828;
    font-weight: bold;
}}

pre {{
    white-space: pre-wrap;
    word-break: break-word;
    background: #111;
    color: #ddd;
    padding: 15px;
    border-radius: 6px;
    overflow-x: auto;
}}
</style>
</head>
<body>
<div class="container">
""".format(html.escape(title))


def page_footer():
    return """
</div>
</body>
</html>
"""


def main_page(host):
    status = get_status()

    status_class = (
        "status-running"
        if status == "Running"
        else "status-stopped"
    )

    total_memory, available_memory = get_memory()

    port = get_port()
    auth = get_auth_enabled()

    body = page_header("TorrServer")

    body += """
<div class="nav">
    <a class="button" href="/">Status</a>
    <a class="button secondary" href="/settings">Settings</a>
    <a class="button secondary" href="/logs">Logs</a>
</div>

<div class="card">
<h1>TorrServer</h1>

<table>
<tr>
<td>Status</td>
<td class="{0}">{1}</td>
</tr>
<tr>
<td>Version</td>
<td>{2}</td>
</tr>
<tr>
<td>Web port</td>
<td>{3}</td>
</tr>
<tr>
<td>Authentication</td>
<td>{4}</td>
</tr>
<tr>
<td>Uptime</td>
<td>{12}</td>
</tr>
</table>

<br>

<a class="button" href="http://{13}:{3}/" target="_blank">
Open Web UI
</a>

<form method="post" action="/restart" style="display:inline;margin-left:10px;">
<button class="danger" type="submit">Restart</button>
</form>

</div>

<div class="card">
<h2>System</h2>

<table>
<tr>
<td>DSM</td>
<td>{5}</td>
</tr>
<tr>
<td>NAS model</td>
<td>{6}</td>
</tr>
<tr>
<td>CPU</td>
<td>{7}</td>
</tr>
<tr>
<td>Cores</td>
<td>{8}</td>
</tr>
<tr>
<td>Architecture</td>
<td>{9}</td>
</tr>
<tr>
<td>RAM total</td>
<td>{10}</td>
</tr>
<tr>
<td>RAM available</td>
<td>{11}</td>
</tr>
</table>
</div>
""".format(
        status_class,
        html.escape(status),
        html.escape(get_torrserver_version()),
        port,
        "Enabled" if auth else "Disabled",
        html.escape(get_dsm_version()),
        html.escape(get_nas_model()),
        html.escape(get_cpu_model()),
        get_cpu_cores(),
        html.escape(get_architecture()),
        html.escape(format_bytes(total_memory)),
        html.escape(format_bytes(available_memory)),
        html.escape(get_torrserver_uptime()),
        html.escape(host),
    )

    body += page_footer()

    return body


def settings_page(message=""):
    port = get_port()
    auth = get_auth_enabled()

    body = page_header("TorrServer Settings")

    body += """
<div class="nav">
    <a class="button secondary" href="/">Status</a>
    <a class="button" href="/settings">Settings</a>
    <a class="button secondary" href="/logs">Logs</a>
</div>

<div class="card">
<h1>Settings</h1>
"""

    if message:
        body += "<p>{}</p>".format(html.escape(message))

    body += """
<form method="post" action="/settings">

<p>
<label>
Web port<br>
<input type="number" name="port" min="1" max="65535" value="{}">
</label>
</p>

<p>
<label>
<input type="checkbox" name="auth" value="1" {} onchange="toggleAuth()">
Enable authentication
</label>
</p>

<div id="authFields">

<p>
<label>
Username<br>
<input type="text" name="username" value="">
</label>
</p>

<p>
<label>
Password<br>
<input type="password" name="password" value="">
</label>
</p>

</div>

<button type="submit">Apply</button>

</form>
</div>

<script>
function toggleAuth() {{
    var checkbox = document.querySelector('input[name="auth"]');
    var fields = document.getElementById('authFields');

    fields.style.display = checkbox.checked ? 'block' : 'none';
}}

toggleAuth();
</script>
""".format(
        port,
        "checked" if auth else "",
    )

    body += page_footer()

    return body


def logs_page():
    log = get_log()

    body = page_header("TorrServer Logs")

    body += """
<div class="nav">
    <a class="button secondary" href="/">Status</a>
    <a class="button secondary" href="/settings">Settings</a>
    <a class="button" href="/logs">Logs</a>
</div>

<div class="card">
<h1>TorrServer.log</h1>

<div style="margin-bottom:15px;">
    <a class="button" href="/logs">Refresh</a>
    <a class="button secondary" href="/download-log" style="margin-left:10px;">
        Download
    </a>
</div>

<pre>{}</pre>
</div>
""".format(
        html.escape(log)
    )

    body += page_footer()

    return body


class Handler(BaseHTTPRequestHandler):

    def send_html(self, content, status=200):
        data = content.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            host = self.headers.get("Host", "").split(":")[0]
            self.send_html(main_page(host))
            return

        if path == "/settings":
            self.send_html(settings_page())
            return

        if path == "/logs":
            self.send_html(logs_page())
            return

        if path == "/download-log":
            try:
                with open(TORRSERVER_LOG, "rb") as f:
                    data = f.read()

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/octet-stream"
                )
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="TorrServer.log"'
                )
                self.send_header(
                    "Content-Length",
                    str(len(data))
                )
                self.end_headers()

                self.wfile.write(data)

            except Exception as e:
                self.send_html(
                    "Unable to download log: {}".format(
                        html.escape(str(e))
                    ),
                    500,
                )

            return

        if path == "/restart":
            host = self.headers.get("Host", "").split(":")[0]
            self.send_html(main_page(host))
            return

        self.send_html("Not Found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", "0"))

        body = self.rfile.read(length).decode(
            "utf-8",
            errors="replace",
        )

        params = parse_qs(body)

        if path == "/settings":
            ok, message = save_settings(params)

            if ok:
                self.redirect("/settings")
            else:
                self.send_html(settings_page(message), 400)

            return

        if path == "/restart":
            ok, message = restart_package()

            if ok:
                self.redirect("/")
            else:
                self.send_html(
                    page_header("Restart Error")
                    + """
<div class="card">
<h1>Restart failed</h1>
<p>{}</p>
</div>
""".format(html.escape(message))
                    + page_footer(),
                    500,
                )

            return
            
        self.send_html("Not Found", 404)

    def log_message(self, format_string, *args):
        return


def log_rotation_loop():
    while True:
        rotate_log_if_needed()
        time.sleep(10)


def run():
    server = ThreadingHTTPServer(
        (HOST, HELPER_PORT),
        Handler,
    )

    rotation_thread = threading.Thread(
        target=log_rotation_loop,
        daemon=True,
    )
    rotation_thread.start()

    server.serve_forever()


if __name__ == "__main__":
    run()
