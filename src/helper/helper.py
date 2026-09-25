#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import os
import re
import urllib.parse
import urllib.request


HOST = "0.0.0.0"
PORT = 8091

CONFIG_DIR = "/var/packages/TorrServer/var"

PORT_CONFIG = os.path.join(
    CONFIG_DIR,
    "torrserver.port"
)

AUTH_CONFIG = os.path.join(
    CONFIG_DIR,
    "torrserver.auth"
)

ACCS_DB = os.path.join(
    CONFIG_DIR,
    "accs.db"
)

TORRSERVER_LOG = os.path.join(
    CONFIG_DIR,
    "TorrServer.log"
)

DEFAULT_TORRSERVER_PORT = 8090


def read_file(path):
    try:
        with open(
            path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as f:
            return f.read()
    except Exception:
        return ""


def write_file(path, content):
    try:
        os.makedirs(
            os.path.dirname(path),
            exist_ok=True
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(content)

        return True

    except Exception:
        return False


def get_port():
    port = DEFAULT_TORRSERVER_PORT

    value = read_file(PORT_CONFIG).strip()

    if value.isdigit():
        try:
            saved_port = int(value)

            if 1 <= saved_port <= 65535:
                port = saved_port

        except ValueError:
            pass

    return port


def get_auth_enabled():
    value = read_file(AUTH_CONFIG).strip()

    return value == "1" and os.path.isfile(ACCS_DB)


def get_credentials():
    try:
        with open(
            ACCS_DB,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return "", ""

        if not data:
            return "", ""

        username = next(iter(data))
        password = data.get(
            username,
            ""
        )

        return str(username), str(password)

    except Exception:
        return "", ""


def save_settings(
    port,
    auth_enabled,
    username,
    password
):
    if not write_file(
        PORT_CONFIG,
        "{}\n".format(port)
    ):
        return False, "Unable to save port"

    if not write_file(
        AUTH_CONFIG,
        "1\n" if auth_enabled else "0\n"
    ):
        return False, "Unable to save authorization state"

    if username:
        credentials = {
            username: password
        }

        try:
            with open(
                ACCS_DB,
                "w",
                encoding="utf-8"
            ) as f:
                json.dump(
                    credentials,
                    f,
                    ensure_ascii=False
                )
                f.write("\n")

        except Exception:
            return False, "Unable to save credentials"

    return True, ""


def get_dsm_info():
    data = {}

    version = read_file(
        "/etc.defaults/VERSION"
    )

    for line in version.splitlines():
        match = re.match(
            r'^([A-Za-z0-9_]+)="(.*)"$',
            line
        )

        if match:
            data[match.group(1)] = match.group(2)

    synoinfo = read_file(
        "/etc.defaults/synoinfo.conf"
    )

    for key in (
        "platform_name",
        "product",
        "unique"
    ):
        match = re.search(
            r'^' + re.escape(key) + r'="([^"]*)"',
            synoinfo,
            re.MULTILINE
        )

        if match:
            data[key] = match.group(1)

    return data


def get_cpu_info():
    cpuinfo = read_file(
        "/proc/cpuinfo"
    )

    model = "Unknown"
    cores = 0

    for line in cpuinfo.splitlines():
        if line.startswith("model name"):
            parts = line.split(
                ":",
                1
            )

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
    meminfo = read_file(
        "/proc/meminfo"
    )

    values = {}

    for line in meminfo.splitlines():
        parts = line.split()

        if len(parts) >= 2:
            try:
                values[
                    parts[0].rstrip(":")
                ] = int(parts[1])
            except ValueError:
                pass

    total = values.get(
        "MemTotal",
        0
    )

    available = values.get(
        "MemAvailable",
        values.get(
            "MemFree",
            0
        )
    )

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
    uptime = read_file(
        "/proc/uptime"
    ).split()

    if not uptime:
        return "Unknown"

    try:
        seconds = int(
            float(uptime[0])
        )

        days = seconds // 86400
        seconds %= 86400

        hours = seconds // 3600
        seconds %= 3600

        minutes = seconds // 60

        if days:
            return "{} d {} h {} min".format(
                days,
                hours,
                minutes
            )

        if hours:
            return "{} h {} min".format(
                hours,
                minutes
            )

        return "{} min".format(
            minutes
        )

    except (ValueError, TypeError):
        return "Unknown"


def get_load():
    loadavg = read_file(
        "/proc/loadavg"
    ).split()

    if not loadavg:
        return "Unknown"

    return loadavg[0]


def get_architecture():
    try:
        return os.uname().machine
    except Exception:
        return "Unknown"


def get_torrserver():
    port = get_port()

    url = "http://127.0.0.1:{}/".format(
        port
    )

    try:
        request = urllib.request.Request(
            url + "echo",
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=2
        ) as response:

            status = response.getcode()

            version = response.read().decode(
                "utf-8",
                errors="replace"
            ).strip()

            if status == 200:
                return True, version

    except Exception:
        pass

    return False, "Unknown"


def get_log():
    try:
        with open(
            TORRSERVER_LOG,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as f:

            lines = f.readlines()

        return "".join(
            lines[-100:]
        )

    except Exception as e:
        return "Unable to read log: {}".format(e)


def esc(value):
    return html.escape(
        str(value)
    )


def row(name, value):
    return """
        <div class="row">
            <div class="label">__NAME__</div>
            <div class="value">__VALUE__</div>
        </div>
    """.replace(
        "__NAME__",
        esc(name)
    ).replace(
        "__VALUE__",
        esc(value)
    )


def card(title, content):
    return """
        <div class="card">
            <div class="card-title">__TITLE__</div>
            <div class="card-content">
                __CONTENT__
            </div>
        </div>
    """.replace(
        "__TITLE__",
        esc(title)
    ).replace(
        "__CONTENT__",
        content
    )


def make_html(message=""):
    dsm = get_dsm_info()

    cpu_model, cpu_cores = get_cpu_info()

    mem_total, mem_available = get_memory_info()

    architecture = get_architecture()
    uptime = get_uptime()
    load = get_load()

    torrserver_running, torrserver_version = (
        get_torrserver()
    )

    torrserver_port = get_port()
    auth_enabled = get_auth_enabled()

    username, password = get_credentials()

    if torrserver_running:
        ts_status = "Running"
        ts_status_class = "status-running"
    else:
        ts_status = "Stopped"
        ts_status_class = "status-stopped"

    system_content = ""

    system_content += row(
        "DSM",
        dsm.get(
            "productversion",
            "Unknown"
        )
    )

    system_content += row(
        "Build",
        dsm.get(
            "buildnumber",
            "Unknown"
        )
    )

    system_content += row(
        "Model",
        dsm.get(
            "product",
            "Unknown"
        )
    )

    system_content += row(
        "Platform",
        dsm.get(
            "platform_name",
            "Unknown"
        )
    )

    system_content += row(
        "Architecture",
        architecture
    )

    system_content += row(
        "CPU",
        cpu_model
    )

    system_content += row(
        "CPU cores",
        cpu_cores
    )

    system_content += row(
        "RAM",
        "{} / {}".format(
            format_memory(
                mem_available
            ),
            format_memory(
                mem_total
            )
        )
    )

    system_content += row(
        "Uptime",
        uptime
    )

    system_content += row(
        "Load",
        load
    )

    auth_status = (
        "Enabled"
        if auth_enabled
        else "Disabled"
    )

    torrserver_content = """
        <div class="status-line">
            <span class="status-dot __STATUS_CLASS__"></span>
            <span>__STATUS__</span>
        </div>

        __VERSION_ROW__

        __PORT_ROW__

        __AUTH_ROW__

        <div class="button-row">
            <a
                class="button primary"
                href="#"
                onclick="window.open(
                    'http://' +
                    window.location.hostname +
                    ':__PORT__/',
                    '_blank'
                ); return false;"
            >
                Open TorrServer Web UI
            </a>
        </div>
    """.replace(
        "__STATUS_CLASS__",
        ts_status_class
    ).replace(
        "__STATUS__",
        esc(ts_status)
    ).replace(
        "__VERSION_ROW__",
        row(
            "Version",
            torrserver_version
        )
    ).replace(
        "__PORT_ROW__",
        row(
            "Web port",
            torrserver_port
        )
    ).replace(
        "__AUTH_ROW__",
        row(
            "Authorization",
            auth_status
        )
    ).replace(
        "__PORT__",
        str(torrserver_port)
    )

    auth_checked = (
        "checked"
        if auth_enabled
        else ""
    )

    auth_disabled = (
        ""
        if auth_enabled
        else "disabled"
    )

    settings_content = """
        <form
            method="post"
            action="/api/settings"
        >

            <div class="form-row">
                <label for="port">
                    Web port
                </label>

                <input
                    id="port"
                    name="port"
                    type="number"
                    min="1"
                    max="65535"
                    value="__PORT__"
                    required
                >
            </div>

            <div class="form-row checkbox-row">
                <label>
                    <input
                        type="checkbox"
                        name="auth_enabled"
                        value="1"
                        __AUTH_CHECKED__
                        onchange="toggleAuthFields()"
                    >
                    Enable authorization
                </label>
            </div>

            <div class="form-row">
                <label for="username">
                    Username
                </label>

                <input
                    id="username"
                    name="username"
                    type="text"
                    value="__USERNAME__"
                    __AUTH_DISABLED__
                    autocomplete="username"
                >
            </div>

            <div class="form-row">
                <label for="password">
                    Password
                </label>

                <input
                    id="password"
                    name="password"
                    type="password"
                    value="__PASSWORD__"
                    __AUTH_DISABLED__
                    autocomplete="new-password"
                >
            </div>

            <div class="button-row">
                <button
                    class="button primary"
                    type="submit"
                >
                    Apply
                </button>
            </div>

            <div class="settings-note">
                Restart the TorrServer package after applying
                port or authorization changes.
            </div>

        </form>

        __MESSAGE__
    """.replace(
        "__PORT__",
        str(torrserver_port)
    ).replace(
        "__AUTH_CHECKED__",
        auth_checked
    ).replace(
        "__USERNAME__",
        esc(username)
    ).replace(
        "__PASSWORD__",
        esc(password)
    ).replace(
        "__AUTH_DISABLED__",
        auth_disabled
    ).replace(
        "__MESSAGE__",
        (
            '<div class="message">'
            + esc(message)
            + '</div>'
            if message
            else ""
        )
    )

    log_content = """
        <div class="log-toolbar">
            <button
                class="button secondary"
                onclick="location.reload();"
            >
                Refresh
            </button>
        </div>

        <pre class="log">__LOG__</pre>
    """.replace(
        "__LOG__",
        esc(
            get_log()
        )
    )

    system_card = card(
        "System Information",
        system_content
    )

    torrserver_card = card(
        "TorrServer",
        torrserver_content
    )

    settings_card = card(
        "Settings",
        settings_content
    )

    page = """<!doctype html>
<html>
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

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
            font-weight: 600;
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
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .card {
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            box-shadow:
                0 1px 2px
                rgba(0, 0, 0, 0.04);
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
            border: 0;
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

        .button.secondary {
            background: #e8edf5;
            color: #333;
        }

        .button.secondary:hover {
            background: #dce3ee;
        }

        .form-row {
            padding: 10px 0;
        }

        .form-row label {
            display: block;
            margin-bottom: 6px;
            color: #777;
        }

        .checkbox-row label {
            color: #333;
            margin-bottom: 0;
        }

        input[type="number"],
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 9px 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
            background: #fff;
            color: #333;
            font-size: 14px;
        }

        input:disabled {
            background: #f1f1f1;
            color: #999;
        }

        .settings-note {
            margin-top: 12px;
            color: #777;
            font-size: 12px;
            line-height: 1.5;
        }

        .message {
            margin-top: 14px;
            padding: 10px 12px;
            background: #edf4ff;
            border-radius: 5px;
            color: #245;
        }

        .log-card {
            grid-column: 1 / -1;
        }

        .log-toolbar {
            margin-bottom: 10px;
        }

        .log {
            margin: 0;
            padding: 14px;
            max-height: 420px;
            overflow: auto;
            background: #1f2328;
            color: #d7dce2;
            border-radius: 5px;
            font-family:
                "SFMono-Regular",
                Consolas,
                "Liberation Mono",
                monospace;
            font-size: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
        }

        @media (max-width: 700px) {
            body {
                padding: 12px;
            }

            .grid {
                grid-template-columns: 1fr;
            }

            .log-card {
                grid-column: auto;
            }
        }
    </style>

    <script>
        function toggleAuthFields() {
            var enabled =
                document.querySelector(
                    'input[name="auth_enabled"]'
                ).checked;

            document.getElementById(
                'username'
            ).disabled = !enabled;

            document.getElementById(
                'password'
            ).disabled = !enabled;
        }

        window.addEventListener(
            'DOMContentLoaded',
            toggleAuthFields
        );
    </script>
</head>

<body>
    <div class="container">

        <div class="header">
            <div class="icon">TS</div>

            <div>
                <h1>TorrServer</h1>
                <p>
                    Synology package control panel
                </p>
            </div>
        </div>

        <div class="grid">

            __SYSTEM_CARD__

            __TORRSERVER_CARD__

            __SETTINGS_CARD__

            <div class="card log-card">
                <div class="card-title">
                    TorrServer Log
                </div>

                <div class="card-content">
                    __LOG_CONTENT__
                </div>
            </div>

        </div>

    </div>
</body>
</html>
"""

    page = page.replace(
        "__SYSTEM_CARD__",
        system_card
    ).replace(
        "__TORRSERVER_CARD__",
        torrserver_card
    ).replace(
        "__SETTINGS_CARD__",
        settings_card
    ).replace(
        "__LOG_CONTENT__",
        log_content
    )

    return page


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urllib.parse.urlparse(
            self.path
        )

        if parsed.path == "/":

            query = urllib.parse.parse_qs(
                parsed.query
            )

            message = query.get(
                "message",
                [""]
            )[0]

            content = make_html(
                message
            ).encode(
                "utf-8"
            )

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

            self.wfile.write(
                content
            )

            return

        if parsed.path == "/api/status":

            running, version = (
                get_torrserver()
            )

            data = json.dumps({
                "running": running,
                "version": version,
                "port": get_port(),
                "auth_enabled": (
                    get_auth_enabled()
                )
            }).encode(
                "utf-8"
            )

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(data))
            )

            self.send_header(
                "Cache-Control",
                "no-cache"
            )

            self.end_headers()

            self.wfile.write(
                data
            )

            return

        if parsed.path == "/api/log":

            data = get_log().encode(
                "utf-8"
            )

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(data))
            )

            self.send_header(
                "Cache-Control",
                "no-cache"
            )

            self.end_headers()

            self.wfile.write(
                data
            )

            return

        self.send_error(404)

    def do_POST(self):

        if self.path != "/api/settings":
            self.send_error(404)
            return

        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            body = self.rfile.read(
                content_length
            ).decode(
                "utf-8",
                errors="replace"
            )

            form = urllib.parse.parse_qs(
                body
            )

            port_value = (
                form.get(
                    "port",
                    [""]
                )[0].strip()
            )

            username = (
                form.get(
                    "username",
                    [""]
                )[0]
            )

            password = (
                form.get(
                    "password",
                    [""]
                )[0]
            )

            auth_enabled = (
                form.get(
                    "auth_enabled",
                    [""]
                )[0] == "1"
            )

            if not port_value.isdigit():
                raise ValueError(
                    "Invalid port"
                )

            port = int(
                port_value
            )

            if port < 1 or port > 65535:
                raise ValueError(
                    "Port must be between 1 and 65535"
                )

            username = username.strip()

            if auth_enabled:

                if not username:
                    raise ValueError(
                        "Username is required"
                    )

                if not password:
                    raise ValueError(
                        "Password is required"
                    )

            else:

                old_username, old_password = (
                    get_credentials()
                )

                if not username:
                    username = old_username

                if not password:
                    password = old_password

            success, error = save_settings(
                port,
                auth_enabled,
                username,
                password
            )

            if not success:
                raise RuntimeError(
                    error
                )

            message = (
                "Settings saved. "
                "Restart the TorrServer package "
                "to apply the changes."
            )

            self.send_response(303)

            self.send_header(
                "Location",
                "/?message=" +
                urllib.parse.quote(
                    message
                )
            )

            self.end_headers()

        except Exception as e:

            message = (
                "Error: {}".format(e)
            )

            content = make_html(
                message
            ).encode(
                "utf-8"
            )

            self.send_response(400)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(content))
            )

            self.end_headers()

            self.wfile.write(
                content
            )

    def log_message(
        self,
        format,
        *args
    ):
        pass


def main():
    server = HTTPServer(
        (HOST, PORT),
        Handler
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
