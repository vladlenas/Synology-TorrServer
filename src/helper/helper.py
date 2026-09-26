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
from urllib.parse import parse_qs, urlparse, quote


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
CACHE_PATH_FILE = os.path.join(PACKAGE_VAR, "cache.path")

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


def get_api_auth_header():
    if not get_auth_enabled():
        return None

    try:
        with open(ACCS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        if not accounts:
            return None

        username, password = next(iter(accounts.items()))
        token = base64.b64encode(
            ("{}:{}".format(username, password)).encode("utf-8")
        ).decode("ascii")
        return "Basic {}".format(token)

    except Exception:
        return None


def get_cache_path():
    local_path = read_file(CACHE_PATH_FILE, "")
    if local_path:
        return local_path

    try:
        import urllib.request

        url = "http://127.0.0.1:{}/settings".format(get_port())
        request = urllib.request.Request(
            url,
            data=json.dumps({"action": "get"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        auth_header = get_api_auth_header()
        if auth_header:
            request.add_header("Authorization", auth_header)

        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))

        path = str(data.get("torrentsSavePath", "") or "").strip()
        if path:
            write_file(CACHE_PATH_FILE, path)
        return path

    except Exception:
        return ""


def set_cache_path(cache_path):
    import urllib.request

    url = "http://127.0.0.1:{}/settings".format(get_port())
    payload = {
        "action": "set",
        "sets": {
            "torrentsSavePath": cache_path
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    auth_header = get_api_auth_header()
    if auth_header:
        request.add_header("Authorization", auth_header)

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return False, "Unable to apply cache directory"

        write_file(CACHE_PATH_FILE, cache_path)
        return True, ""

    except Exception as e:
        return False, "Unable to apply cache directory: {}".format(e)


def save_settings(params):
    port = params.get("port", [""])[0].strip()
    auth = params.get("auth", ["0"])[0]
    username = params.get("username", [""])[0]
    password = params.get("password", [""])[0]
    cache_path = params.get("cache_path", [""])[0].strip()

    if not port.isdigit():
        return False, "Invalid port"

    port_number = int(port)

    if port_number < 1 or port_number > 65535:
        return False, "Invalid port"

    write_file(PORT_FILE, str(port_number))

    if cache_path:
        ok, cache_message = set_cache_path(cache_path)
        if not ok:
            return False, cache_message

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
    cache_path = get_cache_path()

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
Cache directory<br>
<div style="display:flex;gap:8px;max-width:520px;">
<input type="text" name="cache_path" value="{}" placeholder="/volume1/..." style="flex:1;">
<button type="button" class="secondary" onclick="openCacheBrowser()">Browse</button>
</div>
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

function openCacheBrowser() {{
    var field = document.querySelector('input[name="cache_path"]');
    var path = field.value.trim();
    if (!path) path = '/';
    window.open('/browse?path=' + encodeURIComponent(path), 'cacheBrowser',
        'width=700,height=650,resizable=yes,scrollbars=yes');
}}
</script>
""".format(
        port,
        html.escape(cache_path),
        "checked" if auth else "",
    )

    body += page_footer()

    return body


def cache_browser_path(path):
    """Return a safe cache-browser path under /volume* only."""
    if not path:
        return "/"

    path = os.path.abspath(path)

    if path == "/":
        return "/"

    if not re.match(r"^/volume[0-9]+(?:/.*)?$", path):
        return "/"

    real = os.path.realpath(path)
    if not re.match(r"^/volume[0-9]+(?:/.*)?$", real):
        return "/"

    if not os.path.isdir(real):
        return "/"

    return real


def cache_browser_page(path):
    path = cache_browser_path(path)

    if path == "/":
        # At the top level show only DSM volumes.
        try:
            names = sorted(
                name for name in os.listdir("/")
                if re.match(r"^volume[0-9]+$", name)
                and os.path.isdir(os.path.join("/", name))
            )
        except OSError:
            names = []
        parent = None
    else:
        try:
            names = sorted(
                name for name in os.listdir(path)
                if os.path.isdir(os.path.join(path, name))
                and not name.startswith(".")
                and not name.startswith("@")
            )
        except OSError:
            names = []
        parent = os.path.dirname(path.rstrip("/")) or "/"

    rows = []
    for name in names:
        child = os.path.join(path, name) if path != "/" else os.path.join("/", name)
        label = html.escape(name)
        rows.append(
            '<div style="margin:6px 0;">'
            '<a class="button secondary" style="width:100%;box-sizing:border-box;text-align:left;" '
            'href="/browse?path={}">{}/</a>'
            '</div>'.format(quote(child, safe=""), label)
        )

    if not rows:
        rows.append('<p>No accessible directories.</p>')

    parent_html = ""
    if parent is not None:
        parent_html = '<a class="button secondary" href="/browse?path={}">..</a>'.format(
            quote(parent, safe="")
        )

    select_js_path = json.dumps(path)

    body = page_header("Select cache directory")
    body += """
<div class="card">
<h1>Select cache directory</h1>
<p><b>Current:</b> <code>{}</code></p>
<div style="margin-bottom:15px;">
{}
</div>
<div style="margin-bottom:15px;">
<button type="button" onclick='selectCache()'>Select this directory</button>
</div>
<div>
{}
</div>
</div>

<script>
function selectCache() {{
    var path = {};
    if (window.opener && !window.opener.closed) {{
        var field = window.opener.document.querySelector('input[name="cache_path"]');
        if (field) {{
            field.value = path;
            field.focus();
        }}
    }}
    window.close();
}}
</script>
""".format(
        html.escape(path),
        parent_html,
        "".join(rows),
        select_js_path,
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

        if path == "/browse":
            query = parse_qs(parsed.query)
            selected_path = query.get("path", ["/"])[0]
            self.send_html(cache_browser_page(selected_path))
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
