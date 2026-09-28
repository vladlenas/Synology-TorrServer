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
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote


HOST = "0.0.0.0"
HELPER_PORT = 8095
HELPER_HTTPS_PORT = 8096

PACKAGE_NAME = "TorrServer"
PACKAGE_VAR = "/var/packages/TorrServer/var"
HELPER_TLS_CERT_FILE = os.path.join(PACKAGE_VAR, "server.pem")
HELPER_TLS_KEY_FILE = os.path.join(PACKAGE_VAR, "server.key")
TORRSERVER_BIN = "/var/packages/TorrServer/target/bin/TorrServer"
TORRSERVER_LOG = os.path.join(PACKAGE_VAR, "TorrServer.log")

LOG_FILES = {
    "TorrServer.log": os.path.join(PACKAGE_VAR, "TorrServer.log"),
    "TorrServer.log.1": os.path.join(PACKAGE_VAR, "TorrServer.log.1"),
}
LOG_MAX_SIZE = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 2

PORT_FILE = os.path.join(PACKAGE_VAR, "torrserver.port")
AUTH_FILE = os.path.join(PACKAGE_VAR, "torrserver.auth")
ACCS_FILE = os.path.join(PACKAGE_VAR, "accs.db")
CACHE_PATH_FILE = os.path.join(PACKAGE_VAR, "cache.path")
HTTPS_FILE = os.path.join(PACKAGE_VAR, "torrserver.https")
HTTPS_PORT_FILE = os.path.join(PACKAGE_VAR, "torrserver.https.port")
FORCE_HTTPS_FILE = os.path.join(PACKAGE_VAR, "torrserver.force.https")
SSL_MODE_FILE = os.path.join(PACKAGE_VAR, "torrserver.ssl.mode")
SSL_CERT_FILE = os.path.join(PACKAGE_VAR, "torrserver.ssl.cert")
SSL_KEY_FILE = os.path.join(PACKAGE_VAR, "torrserver.ssl.key")

SSL_CERT_MODE_SELF = "self"
SSL_CERT_MODE_DSM = "dsm"
SSL_CERT_MODE_MANUAL = "manual"

RESTART_SCRIPT = "/var/packages/TorrServer/scripts/restart-package"
CERTIFICATE_HELPER = "/var/packages/TorrServer/scripts/certificate-helper"


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


def get_https_enabled():
    return read_file(HTTPS_FILE, "0") == "1"


def get_https_port():
    port = 8091

    value = read_file(HTTPS_PORT_FILE, "")

    if value.isdigit():
        number = int(value)

        if 1 <= number <= 65535:
            port = number

    return port


def get_force_https():
    return read_file(FORCE_HTTPS_FILE, "0") == "1"


def get_ssl_mode():
    mode = read_file(SSL_MODE_FILE, SSL_CERT_MODE_SELF).strip().lower()
    if mode not in (SSL_CERT_MODE_SELF, SSL_CERT_MODE_DSM, SSL_CERT_MODE_MANUAL):
        return SSL_CERT_MODE_SELF
    return mode


def get_ssl_paths():
    return read_file(SSL_CERT_FILE, "").strip(), read_file(SSL_KEY_FILE, "").strip()


def get_dsm_certificates():
    try:
        result = subprocess.run(
            ["/bin/sudo", "-n", CERTIFICATE_HELPER],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        result_items = []

        for item in data:
            subscriber = str(item.get("subscriber", "") or "").strip()
            service = str(item.get("service", "") or "").strip()

            for cert_item in item.get("certs", []):
                cert = str(cert_item.get("cert", "") or "").strip()
                chain = str(cert_item.get("chain", "") or "").strip()
                key = str(cert_item.get("key", "") or "").strip()

                if not cert or not key:
                    continue

                if "/ECC-" in cert:
                    cert_type = "ECC"
                elif "/RSA-" in cert:
                    cert_type = "RSA"
                else:
                    cert_type = "Certificate"

                label = subscriber or service or "DSM"

                result_items.append({
                    "label": "{} ({})".format(label, cert_type),
                    "cert": chain or cert,
                    "key": key,
                })

        unique = []
        seen = set()

        for item in result_items:
            pair = (item["cert"], item["key"])
            if pair in seen:
                continue
            seen.add(pair)
            unique.append(item)

        return sorted(unique, key=lambda item: item["label"].lower())

    except Exception:
        return []

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
        pass

    return "/volume1/downloads"


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
    https = params.get("https", ["0"])[0]
    https_port = params.get("https_port", ["8091"])[0].strip()
    force_https = params.get("force_https", ["0"])[0]
    ssl_mode = params.get("ssl_mode", [SSL_CERT_MODE_SELF])[0].strip().lower()
    ssl_cert = params.get("ssl_cert", [""])[0].strip()
    ssl_key = params.get("ssl_key", [""])[0].strip()

    if ssl_mode not in (SSL_CERT_MODE_SELF, SSL_CERT_MODE_DSM, SSL_CERT_MODE_MANUAL):
        return False, "Invalid certificate mode"

    if ssl_mode == SSL_CERT_MODE_MANUAL and (not ssl_cert or not ssl_key):
        return False, "Certificate and key paths are required"

    if ssl_mode == SSL_CERT_MODE_DSM:
        valid = {(x["cert"], x["key"]) for x in get_dsm_certificates()}
        if (ssl_cert, ssl_key) not in valid:
            return False, "Invalid DSM certificate selection"

    if not port.isdigit():
        return False, "Invalid port"

    port_number = int(port)

    if port_number < 1 or port_number > 65535:
        return False, "Invalid port"

    if not https_port.isdigit():
        return False, "Invalid HTTPS port"

    https_port_number = int(https_port)

    if https_port_number < 1 or https_port_number > 65535:
        return False, "Invalid HTTPS port"

    if https == "1" and https_port_number == port_number:
        return False, "HTTPS port must differ from Web port"

    write_file(PORT_FILE, str(port_number))
    write_file(HTTPS_PORT_FILE, str(https_port_number))
    write_file(HTTPS_FILE, "1" if https == "1" else "0")
    write_file(FORCE_HTTPS_FILE, "1" if force_https == "1" and https == "1" else "0")
    write_file(SSL_MODE_FILE, ssl_mode)
    write_file(SSL_CERT_FILE, ssl_cert)
    write_file(SSL_KEY_FILE, ssl_key)

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
    return get_log_by_name("TorrServer.log")


def get_log_path(name):
    return LOG_FILES.get(name)


def get_log_by_name(name):
    log_path = get_log_path(name)
    if not log_path:
        return "Invalid log file"

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()

        if len(data) > 200000:
            data = data[-200000:]

        return data

    except FileNotFoundError:
        return "Log file not found: {}".format(name)
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
* {{
    box-sizing: border-box;
}}

body {{
    font-family: Arial, Helvetica, sans-serif;
    margin: 0;
    background: #eef0f3;
    color: #222;
    font-size: 14px;
}}

.container {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 14px 18px 30px;
}}

.nav {{
    display: flex;
    gap: 6px;
    margin: 0 0 10px 0;
}}

.nav a {{
    margin: 0;
}}

.card {{
    background: #fff;
    border: 1px solid #d6d9de;
    border-radius: 6px;
    padding: 20px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,.08);
}}

.card h1 {{
    margin: 0 0 18px;
    font-size: 25px;
    font-weight: 600;
}}

.card h2 {{
    margin: 0 0 12px;
    font-size: 20px;
    font-weight: 600;
}}

.section-title {{
    margin: 22px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #d9dce1;
    font-size: 18px;
    font-weight: 600;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

td {{
    padding: 9px 6px;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: middle;
}}

td:first-child {{
    width: 230px;
    font-weight: 600;
}}

input[type=text],
input[type=password],
input[type=number],
select {{
    height: 36px;
    width: 100%;
    max-width: 520px;
    padding: 7px 10px;
    border: 1px solid #bfc4cb;
    border-radius: 3px;
    background: #fff;
    color: #222;
    font-size: 14px;
}}

input:focus,
select:focus {{
    outline: none;
    border-color: #1677ff;
    box-shadow: 0 0 0 2px rgba(22,119,255,.12);
}}

button,
.button {{
    display: inline-block;
    min-height: 36px;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 8px 15px;
    cursor: pointer;
    text-decoration: none;
    background: #1677ff;
    color: #fff;
    font-size: 14px;
    line-height: 18px;
}}

button:hover,
.button:hover {{
    filter: brightness(.96);
}}

button.secondary,
.button.secondary {{
    background: #6b6f75;
}}

button.danger,
.button.danger {{
    background: #d32f2f;
}}

.nav .button {{
    min-height: 34px;
    padding: 7px 16px;
    border-radius: 4px;
}}

.nav .button.secondary {{
    background: #666;
}}

.nav .button.active {{
    background: #1677ff;
}}

.status-running {{
    color: #16803c;
    font-weight: 600;
}}

.status-stopped {{
    color: #c62828;
    font-weight: 600;
}}

.notice {{
    background: #fff7d6;
    border: 1px solid #e6cf75;
    border-left: 4px solid #e0b100;
    border-radius: 4px;
    padding: 12px 14px;
    margin-bottom: 16px;
    color: #5f4b00;
}}

.notice strong {{
    color: #4d3d00;
}}

.form-row {{
    margin-bottom: 16px;
}}

.form-row label {{
    display: block;
    margin-bottom: 6px;
    font-weight: 600;
}}

.help {{
    margin-top: 6px;
    color: #6b7280;
    font-size: 13px;
}}

.actions {{
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #d9dce1;
}}

pre {{
    white-space: pre-wrap;
    word-break: break-word;
    background: #111;
    color: #ddd;
    padding: 15px;
    border-radius: 4px;
    overflow-x: auto;
    min-height: 180px;
    margin: 0;
    font-family: Consolas, "Courier New", monospace;
    font-size: 13px;
    line-height: 1.35;
}}

.toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 14px;
}}

.toolbar select {{
    width: auto;
    min-width: 220px;
}}

.checkbox-row {{
    margin: 8px 0;
}}


.app-shell {{
    display: flex;
    min-height: calc(100vh - 28px);
    margin: -14px -18px -30px;
    background: #f1f5f9;
}}

.app-sidebar {{
    width: 220px;
    flex: 0 0 220px;
    background: #ffffff;
    border-right: 1px solid #d6dee8;
    padding: 18px 10px;
}}

.app-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 12px 20px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 12px;
}}

.app-icon {{
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: linear-gradient(135deg, #1d7ff2, #4b9cff);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    box-shadow: 0 2px 5px rgba(0,0,0,.16);
}}

.app-name {{
    font-size: 17px;
    font-weight: 600;
    color: #17233b;
}}

.side-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    height: 44px;
    margin: 3px 0;
    padding: 0 13px;
    border-radius: 5px;
    color: #30415e;
    text-decoration: none;
    font-size: 14px;
}}

.side-item:hover {{
    background: #edf5ff;
}}

.side-item.active {{
    background: #e5f1ff;
    color: #1167c9;
    box-shadow: inset 3px 0 0 #1677ff;
}}

.side-icon {{
    width: 22px;
    text-align: center;
    font-size: 18px;
}}

.app-content {{
    flex: 1;
    min-width: 0;
    padding: 28px 28px 36px;
}}

.app-title {{
    font-size: 28px;
    font-weight: 600;
    color: #17233b;
    margin-bottom: 16px;
}}

.status-banner {{
    min-height: 104px;
    background: #fff;
    border: 1px solid #d9e1eb;
    border-radius: 7px;
    box-shadow: 0 1px 3px rgba(30,50,80,.06);
    display: flex;
    align-items: center;
    padding: 18px 22px;
    margin-bottom: 18px;
}}

.status-symbol {{
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: #24b34b;
    color: #fff;
    font-size: 38px;
    line-height: 58px;
    text-align: center;
    margin-right: 18px;
}}

.status-text {{
    flex: 1;
}}

.status-text .status-running,
.status-text .status-stopped {{
    font-size: 23px;
}}

.status-subtitle {{
    color: #627089;
    margin-top: 5px;
    font-size: 14px;
}}

.light-button {{
    background: #eaf3ff !important;
    color: #1a3f70 !important;
    border-color: #d4e5f8 !important;
}}

.dashboard-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
}}

.dashboard-card {{
    background: #fff;
    border: 1px solid #d9e1eb;
    border-radius: 7px;
    box-shadow: 0 1px 3px rgba(30,50,80,.06);
    padding: 20px 22px;
    min-width: 0;
}}

.dashboard-card-title {{
    display: flex;
    align-items: center;
    gap: 11px;
    font-size: 19px;
    font-weight: 600;
    color: #17233b;
    padding-bottom: 13px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 4px;
}}

.metric-icon {{
    width: 34px;
    height: 34px;
    border-radius: 7px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #edf3fa;
    color: #354b68;
    font-size: 11px;
    font-weight: 700;
}}

.metric-table td {{
    padding: 9px 2px;
    border-bottom: 1px solid #e4e9ef;
}}

.metric-table td:first-child {{
    width: 46%;
    font-weight: 400;
    color: #40536f;
}}

.metric-table td:last-child {{
    color: #1d2e49;
}}

.metric-card {{
    min-height: 190px;
}}

.usage-layout {{
    display: flex;
    align-items: center;
    gap: 18px;
    padding-top: 12px;
}}

.usage-value {{
    width: 72px;
    flex: 0 0 72px;
    font-size: 30px;
    font-weight: 600;
    color: #1c2f4e;
}}

.usage-chart,
.network-chart {{
    position: relative;
    height: 105px;
    flex: 1;
    overflow: hidden;
    border-left: 1px solid #e4eaf1;
    border-bottom: 1px solid #e4eaf1;
}}

.chart-grid {{
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(to bottom, #edf1f6 1px, transparent 1px),
        linear-gradient(to right, #f2f5f8 1px, transparent 1px);
    background-size: 100% 25%, 20% 100%;
}}

.chart-line {{
    position: absolute;
    left: 0;
    right: 0;
    bottom: 10%;
    height: 3px;
    background: #2e91f7;
    transform: skewY(-2deg);
    box-shadow:
        35px -3px 0 -1px #2e91f7,
        70px 2px 0 -1px #2e91f7,
        105px -5px 0 -1px #2e91f7,
        140px 1px 0 -1px #2e91f7,
        175px -7px 0 -1px #2e91f7,
        210px 0 0 -1px #2e91f7,
        245px -3px 0 -1px #2e91f7;
}}

.memory-layout {{
    padding-top: 12px;
}}

.memory-value {{
    font-size: 30px;
    font-weight: 600;
    color: #1c2f4e;
    margin-bottom: 12px;
}}

.memory-bar {{
    height: 14px;
    background: #e4ebf3;
    border-radius: 7px;
    overflow: hidden;
    margin-bottom: 10px;
}}

.memory-fill {{
    height: 100%;
    background: #3298f5;
    border-radius: 7px;
}}

.memory-details {{
    color: #64748b;
    line-height: 1.55;
}}

.network-card {{
    grid-column: 1 / -1;
}}

.network-layout {{
    display: flex;
    gap: 26px;
    align-items: center;
    padding-top: 12px;
}}

.network-values {{
    display: flex;
    gap: 38px;
    min-width: 290px;
}}

.network-rate {{
    display: grid;
    grid-template-columns: auto auto;
    column-gap: 8px;
    align-items: center;
}}

.network-rate .network-arrow {{
    grid-row: 1 / 3;
    font-size: 32px;
    font-weight: 600;
}}

.network-rate strong {{
    font-size: 22px;
}}

.network-rate small {{
    color: #64748b;
    font-size: 13px;
}}

.upload {{
    color: #1677ff;
}}

.download {{
    color: #20a04b;
}}

.network-chart {{
    height: 115px;
}}

.network-line {{
    position: absolute;
    left: 0;
    right: 0;
    bottom: 18%;
    height: 3px;
    background: #2e91f7;
    box-shadow:
        55px -4px 0 0 #27a94d,
        95px 1px 0 0 #2e91f7,
        145px -7px 0 0 #27a94d,
        205px 3px 0 0 #2e91f7,
        260px -10px 0 0 #27a94d,
        320px 1px 0 0 #2e91f7,
        380px -14px 0 0 #27a94d;
}}

.settings-layout {{
    max-width: 980px;
}}

.settings-card {{
    background: #fff;
    border: 1px solid #d9e1eb;
    border-radius: 7px;
    box-shadow: 0 1px 3px rgba(30,50,80,.06);
    margin-bottom: 16px;
    overflow: hidden;
}}

.settings-card-title {{
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 15px 18px;
    border-bottom: 1px solid #e2e8f0;
    font-size: 18px;
    font-weight: 600;
    color: #17233b;
}}

.settings-card-body {{
    padding: 18px 20px;
}}

.settings-card .form-row {{
    display: grid;
    grid-template-columns: 190px minmax(0, 1fr);
    align-items: center;
    gap: 18px;
    margin-bottom: 14px;
}}

.settings-card .form-row label {{
    margin: 0;
    color: #30415e;
}}

.settings-card input[type=text],
.settings-card input[type=password],
.settings-card input[type=number],
.settings-card select {{
    max-width: 620px;
}}

.settings-card .checkbox-row {{
    margin: 0 0 14px;
}}

.settings-card .checkbox-row label {{
    color: #30415e;
}}

.settings-card .help {{
    margin: 4px 0 0;
    color: #64748b;
}}

.settings-card .actions {{
    margin: 0;
    padding: 16px 20px;
    background: #f8fafc;
}}

.logs-card {{
    background: #fff;
    border: 1px solid #d9e1eb;
    border-radius: 7px;
    box-shadow: 0 1px 3px rgba(30,50,80,.06);
    padding: 18px;
}}

.logs-toolbar {{
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 14px;
}}

.logs-toolbar select {{
    width: 220px;
}}

.logs-toolbar button,
.logs-toolbar .button {{
    min-height: 36px;
}}

.logs-output {{
    min-height: 520px;
    max-height: calc(100vh - 250px);
    overflow: auto;
    background: #101820;
    border: 1px solid #0b1117;
    color: #d8dee7;
    padding: 16px;
    border-radius: 5px;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    line-height: 1.42;
}}

@media (max-width: 800px) {{
    .container {{
        padding: 10px;
    }}

    .app-shell {{
        margin: -10px -10px -30px;
    }}

    .app-sidebar {{
        width: 170px;
        flex-basis: 170px;
    }}

    .app-content {{
        padding: 18px 14px 28px;
    }}

    .dashboard-grid {{
        grid-template-columns: 1fr;
    }}

    .settings-card .form-row {{
        grid-template-columns: 1fr;
        gap: 6px;
    }}

    .settings-card input[type=text],
    .settings-card input[type=password],
    .settings-card input[type=number],
    .settings-card select {{
        max-width: 100%;
    }}

    .logs-toolbar {{
        align-items: stretch;
        flex-direction: column;
    }}

    .logs-toolbar select {{
        width: 100%;
    }}

    .network-card {{
        grid-column: auto;
    }}

    .network-layout {{
        flex-direction: column;
        align-items: stretch;
    }}

    .network-values {{
        min-width: 0;
    }}
}}


.web-ui-actions {{
    display: flex;
    gap: 10px;
    align-items: flex-start;
}}

.web-ui-action {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
}}

.web-ui-address {{
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
}}

.button.disabled {{
    opacity: 0.42;
    cursor: default;
    pointer-events: none;
}}

.web-ui-address.disabled {{
    color: #94a3b8;
}}

.info-card {{
    position: relative;
    grid-column: 1 / -1;
}}

.info-maintainer-top {{
    position: absolute;
    top: 18px;
    right: 20px;
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
}}

.info-layout {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding-top: 12px;
}}

.info-text {{
    min-width: 180px;
}}

.info-title {{
    font-size: 18px;
    font-weight: 600;
    color: #1d2e49;
}}

.info-subtitle {{
    margin-top: 5px;
    color: #64748b;
    font-size: 14px;
}}

.info-links {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
}}

.info-link {{
    display: inline-flex;
    align-items: center;
    min-height: 34px;
    padding: 0 12px;
    border: 1px solid #d6e0ec;
    border-radius: 6px;
    background: #f7f9fc;
    color: #294766;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
}}

.info-link:hover {{
    background: #edf3fa;
    border-color: #c7d5e5;
}}

.info-donate {{
    background: #fff5e9;
    border-color: #f3d5b1;
    color: #a85c13;
}}

.info-donate:hover {{
    background: #ffecd6;
    border-color: #e8bf8e;
}}

@media (max-width: 800px) {{
    .info-layout {{
        flex-direction: column;
        align-items: stretch;
    }}

    .info-links {{
        justify-content: flex-start;
    }}

    .info-maintainer-top {{
        position: static;
        margin-bottom: 8px;
    }}
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


def app_sidebar(active):
    items = [
        ("./", "▥", "Status", "status"),
        ("./settings", "⚙", "Settings", "settings"),
        ("./logs", "▤", "Logs", "logs"),
    ]

    parts = ['<div class="app-sidebar">']
    for href, icon, label, key in items:
        cls = "side-item active" if key == active else "side-item"
        parts.append(
            '<a class="{}" href="{}"><span class="side-icon">{}</span><span>{}</span></a>'.format(
                cls, href, icon, label
            )
        )
    parts.append("</div>")
    return "".join(parts)



def get_network_usage():
    try:
        rx = 0
        tx = 0

        with open("/proc/net/dev", "r", encoding="utf-8") as f:
            for line in f:
                if ":" not in line:
                    continue

                interface, data = line.split(":", 1)
                interface = interface.strip()

                if interface == "lo":
                    continue

                values = data.split()

                if len(values) >= 9:
                    rx += int(values[0])
                    tx += int(values[8])

        return rx, tx

    except Exception:
        return 0, 0


def format_rate(bytes_per_second):
    if bytes_per_second < 1024:
        return "{} B/s".format(int(bytes_per_second))

    if bytes_per_second < 1024 * 1024:
        return "{:.1f} KB/s".format(bytes_per_second / 1024.0)

    return "{:.1f} MB/s".format(
        bytes_per_second / (1024.0 * 1024.0)
    )


def get_network_rates():
    rx1, tx1 = get_network_usage()
    time.sleep(0.15)
    rx2, tx2 = get_network_usage()

    interval = 0.15

    return (
        max(0, (rx2 - rx1) / interval),
        max(0, (tx2 - tx1) / interval),
    )


def main_page(host):
    status = get_status()

    port = get_port()
    auth = get_auth_enabled()
    https = get_https_enabled()
    https_port = get_https_port()

    https_button_class = "" if https else " disabled"
    https_href = "https://{}:{}/".format(host, https_port) if https else "#"
    https_disabled_attr = "" if https else ' aria-disabled="true" tabindex="-1"'

    status_class = (
        "status-running"
        if status == "Running"
        else "status-stopped"
    )

    body = page_header("TorrServer")

    body += """
<div class="app-shell">

<div class="app-sidebar">
    <a class="side-item active" href="./">
        <span class="side-icon">▥</span>
        <span>Status</span>
    </a>

    <a class="side-item" href="./settings">
        <span class="side-icon">⚙</span>
        <span>Settings</span>
    </a>

    <a class="side-item" href="./logs">
        <span class="side-icon">▤</span>
        <span>Logs</span>
    </a>
</div>

<div class="app-content">

<div class="app-title">Status</div>

<div class="status-banner">
    <div class="status-symbol">✓</div>
    <div class="status-text">
        <div class="{0}">{1}</div>
        <div class="status-subtitle">TorrServer is running normally.</div>
    </div>
    <div class="web-ui-actions">
        <div class="web-ui-action">
            <a class="button light-button"
               href="http://{2}:{3}/"
               target="_blank">
                🌐 Open HTTP ↗
            </a>
            <div class="web-ui-address">http://{2}:{3}</div>
        </div>

        <div class="web-ui-action">
            <a class="button light-button{14}"
               href="{15}"
               target="_blank"{16}
               onclick="{17}">
                🔒 Open HTTPS ↗
            </a>
            <div class="web-ui-address{18}">https://{2}:{19}</div>
        </div>
    </div>
</div>

<div class="dashboard-grid">

<div class="dashboard-card">
    <div class="dashboard-card-title">
        <span class="metric-icon server-icon">TS</span>
        <span>TorrServer</span>
    </div>

    <table class="metric-table">
        <tr>
            <td>Version</td>
            <td>{4}</td>
        </tr>
        <tr>
            <td>Web port</td>
            <td>{5}</td>
        </tr>
        <tr>
            <td>HTTPS</td>
            <td>{6}</td>
        </tr>
        <tr>
            <td>Authentication</td>
            <td>{7}</td>
        </tr>
        <tr>
            <td>Uptime</td>
            <td>{8}</td>
        </tr>
    </table>
</div>

<div class="dashboard-card">
    <div class="dashboard-card-title">
        <span class="metric-icon system-icon">▣</span>
        <span>System</span>
    </div>

    <table class="metric-table">
        <tr>
            <td>DSM</td>
            <td>{9}</td>
        </tr>
        <tr>
            <td>NAS model</td>
            <td>{10}</td>
        </tr>
        <tr>
            <td>CPU</td>
            <td>{11}</td>
        </tr>
        <tr>
            <td>Cores</td>
            <td>{12}</td>
        </tr>
        <tr>
            <td>Architecture</td>
            <td>{13}</td>
        </tr>
    </table>
</div>


<div class="dashboard-card info-card">
    <div class="info-maintainer-top">synology package maintained by vladlenas</div>

    <div class="dashboard-card-title">
        <span class="metric-icon">i</span>
        <span>Information</span>
    </div>

    <div class="info-layout">
        <div class="info-text">
            <div class="info-title">TorrServer MatriX</div>
            <div class="info-subtitle">Project, SPK package and support</div>
        </div>

        <div class="info-links">
            <a class="info-link" href="https://github.com/YouROK/TorrServer" target="_blank" rel="noopener noreferrer">Project ↗</a>
            <a class="info-link" href="https://grigi.lt/" target="_blank" rel="noopener noreferrer">SPK Repository ↗</a>
            <a class="info-link" href="https://github.com/vladlenas/Synology-TorrServer" target="_blank" rel="noopener noreferrer">SPK Project ↗</a>
            <a class="info-link" href="https://github.com/vladlenas/Synology-TorrServer/issues" target="_blank" rel="noopener noreferrer">SPK Issues ↗</a>
            <a class="info-link info-donate" href="https://github.com/YouROK/TorrServer#donate" target="_blank" rel="noopener noreferrer">♥ Donate ↗</a>
        </div>
    </div>
</div>


</div>
</div>
</div>
""".format(
        status_class,
        html.escape(status),
        html.escape(host),
        port,
        html.escape(get_torrserver_version()),
        port,
        "Enabled" if https else "Disabled",
        "Enabled" if auth else "Disabled",
        html.escape(get_torrserver_uptime()),
        html.escape(get_dsm_version()),
        html.escape(get_nas_model()),
        html.escape(get_cpu_model()),
        get_cpu_cores(),
        html.escape(get_architecture()),
         https_button_class,
         https_href,
         https_disabled_attr,
         "return false;" if not https else "",
         " disabled" if not https else "",
         https_port,
    )

    body += page_footer()
    return body


def settings_page(message=""):
    port = get_port()
    auth = get_auth_enabled()
    cache_path = get_cache_path()
    https = get_https_enabled()
    https_port = get_https_port()
    force_https = get_force_https()
    ssl_mode = get_ssl_mode()
    ssl_cert, ssl_key = get_ssl_paths()
    dsm_certs = get_dsm_certificates()

    if not dsm_certs:
        dsm_certs = [{
            "label": "system (Certificate)",
            "cert": "/usr/syno/etc/certificate/system/default/fullchain.pem",
            "key": "/usr/syno/etc/certificate/system/default/privkey.pem",
        }]

    body = page_header("TorrServer Settings")

    body += """
<div class="app-shell">

{sidebar}

<div class="app-content">

<div class="app-title">Settings</div>

<div class="notice">
<strong>After changing settings:</strong> first click <b>Save</b>, then click <b>Restart</b>.
<br>
Some changes require a restart of the TorrServer service to take effect.
</div>
""".format(sidebar=app_sidebar("settings"))

    if message:
        body += '<div class="notice">{}</div>'.format(html.escape(message))

    body += """
<div class="settings-layout">

<form method="post" action="./settings">

<div class="settings-card">
    <div class="settings-card-title">
        <span class="metric-icon">TS</span>
        <span>TorrServer</span>
    </div>
    <div class="settings-card-body">

        <div class="form-row">
            <label for="webPort">Web port (HTTP)</label>
            <input id="webPort" type="number" name="port" min="1" max="65535" value="{}">
        </div>

        <div class="form-row">
            <label for="cachePath">Cache directory</label>
            <div style="display:flex;gap:8px;max-width:620px;">
                <input id="cachePath" type="text" name="cache_path" value="{}" placeholder="/volume1/...">
                <button type="button" class="secondary" onclick="openCacheBrowser()">Browse</button>
            </div>
        </div>

    </div>
</div>

<div class="settings-card">
    <div class="settings-card-title">
        <span class="metric-icon">🔒</span>
        <span>HTTPS</span>
    </div>
    <div class="settings-card-body">

        <div class="checkbox-row">
            <label>
                <input type="checkbox" name="https" value="1" {} onchange="toggleHttps()">
                Enable HTTPS
            </label>
        </div>

        <div class="form-row">
            <label for="httpsPort">HTTPS port</label>
            <input id="httpsPort" type="number" name="https_port" min="1" max="65535" value="{}">
        </div>

        <div class="checkbox-row">
            <label>
                <input type="checkbox" name="force_https" value="1" {} {}>
                Force HTTPS (redirect HTTP to HTTPS)
            </label>
        </div>

    </div>
</div>

<div class="settings-card">
    <div class="settings-card-title">
        <span class="metric-icon">▣</span>
        <span>SSL Certificate</span>
    </div>
    <div class="settings-card-body">

        <div class="form-row">
            <label for="sslMode">Certificate source</label>
            <select name="ssl_mode" id="sslMode" onchange="toggleSslMode()">
                <option value="self" {}>TorrServer self-signed</option>
                <option value="dsm" {}>DSM certificate</option>
                <option value="manual" {}>Manual paths</option>
            </select>
        </div>

        <div id="dsmCertificateFields" class="form-row">
            <label for="sslDsm">DSM certificate</label>
            <select id="sslDsm">
                {}
            </select>
        </div>

        <div id="manualCertificateFields">
            <div class="form-row">
                <label for="sslCert">SSL Certificate path</label>
                <input id="sslCert" type="text" name="ssl_cert" value="{}" placeholder="/volume1/.../fullchain.pem">
            </div>

            <div class="form-row">
                <label for="sslKey">SSL Key path</label>
                <input id="sslKey" type="text" name="ssl_key" value="{}" placeholder="/volume1/.../privkey.pem">
            </div>
        </div>

        <div class="help">
            The selected source will be synchronized to TorrServer server.pem/server.key.
        </div>

    </div>
</div>

<div class="settings-card">
    <div class="settings-card-title">
        <span class="metric-icon">●</span>
        <span>Authentication</span>
    </div>
    <div class="settings-card-body">

        <div class="checkbox-row">
            <label>
                <input type="checkbox" name="auth" value="1" {} onchange="toggleAuth()">
                Enable authentication
            </label>
        </div>

        <div id="authFields">
            <div class="form-row">
                <label for="username">Username</label>
                <input id="username" type="text" name="username" value="" {}>
            </div>

            <div class="form-row">
                <label for="password">Password</label>
                <input id="password" type="password" name="password" value="" {}>
            </div>
        </div>

    </div>

    <div class="actions">
        <button type="submit">Save</button>
        <button type="submit" formaction="./restart" class="danger">Restart</button>
    </div>
</div>

</form>
</div>

<script>
function toggleHttps() {{
    var enabled = document.querySelector('input[name="https"]').checked;
    document.getElementById('httpsPort').disabled = !enabled;
    document.getElementById('sslMode').disabled = !enabled;
    document.getElementById('sslDsm').disabled = !enabled;
}}

function toggleSslMode() {{
    var mode = document.getElementById('sslMode').value;
    document.getElementById('dsmCertificateFields').style.display =
        mode === 'dsm' ? 'grid' : 'none';
    document.getElementById('manualCertificateFields').style.display =
        mode === 'manual' ? 'block' : 'none';
}}

function syncDsmCertificate() {{
    var selected = document.getElementById('sslDsm');
    if (!selected || !selected.value) return;

    var value = selected.value.split('|');
    if (value.length === 2) {{
        document.querySelector('input[name="ssl_cert"]').value = value[0];
        document.querySelector('input[name="ssl_key"]').value = value[1];
    }}
}}

document.getElementById('sslDsm').addEventListener('change', syncDsmCertificate);

if (document.getElementById('sslDsm').value) {{
    syncDsmCertificate();
}}

function toggleAuth() {{
    var checkbox = document.querySelector('input[name="auth"]');
    var fields = document.getElementById('authFields');
    var inputs = fields.querySelectorAll('input');

    for (var i = 0; i < inputs.length; i++) {{
        inputs[i].disabled = !checkbox.checked;
    }}
}}

function openCacheBrowser() {{
    var field = document.querySelector('input[name="cache_path"]');
    var path = field.value.trim();
    if (!path) path = '/';
    window.open('/browse?path=' + encodeURIComponent(path), 'cacheBrowser',
        'width=700,height=650,resizable=yes,scrollbars=yes');
}}

toggleHttps();
toggleSslMode();
toggleAuth();
</script>
""".format(
        port,
        html.escape(cache_path or "/volume1/downloads"),
        "checked" if https else "",
        https_port,
        "checked" if force_https else "",
        "" if https else "disabled",
        "selected" if ssl_mode == SSL_CERT_MODE_SELF else "",
        "selected" if ssl_mode == SSL_CERT_MODE_DSM else "",
        "selected" if ssl_mode == SSL_CERT_MODE_MANUAL else "",
        "".join(
            '<option value="{}|{}" {}>{}</option>'.format(
                html.escape(item["cert"], quote=True),
                html.escape(item["key"], quote=True),
                "selected" if (item["cert"], item["key"]) == (ssl_cert, ssl_key) else "",
                html.escape(item["label"])
            )
            for item in dsm_certs
        ),
        html.escape(ssl_cert, quote=True),
        html.escape(ssl_key, quote=True),
        "checked" if auth else "",
        "" if auth else "disabled",
        "" if auth else "disabled",
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
            'href="./browse?path={}">{}/</a>'
            '</div>'.format(quote(child, safe=""), label)
        )

    if not rows:
        rows.append('<p>No accessible directories.</p>')

    parent_html = ""
    if parent is not None:
        parent_html = '<a class="button secondary" href="./browse?path={}">..</a>'.format(
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
    body = page_header("TorrServer Logs")

    body += """
<div class="app-shell">

{sidebar}

<div class="app-content">

<div class="app-title">Logs</div>

<div class="logs-card">

<div class="logs-toolbar">
    <select id="logSelect">
        <option value="TorrServer.log">TorrServer.log</option>
        <option value="TorrServer.log.1">TorrServer.log.1</option>
    </select>

    <button type="button" onclick="openLog()">↻ Refresh</button>

    <a class="button secondary"
       id="downloadButton"
       href="./download-log?name=TorrServer.log">
        ↓ Download
    </a>
</div>

<pre id="logContent" class="logs-output">Loading TorrServer.log...</pre>

</div>
</div>
</div>

<script>
function openLog() {{
    var name = document.getElementById("logSelect").value;
    document.getElementById("logContent").textContent = "Loading " + name + "...";

    var basePath = window.location.pathname.substring(
        0,
        window.location.pathname.lastIndexOf("/") + 1
    );

    fetch(basePath + "read-log?name=" + encodeURIComponent(name))
        .then(function(response) {{
            if (!response.ok) {{
                throw new Error("HTTP " + response.status);
            }}
            return response.text();
        }})
        .then(function(data) {{
            document.getElementById("logContent").textContent = data;
            document.getElementById("downloadButton").href =
                basePath + "download-log?name=" + encodeURIComponent(name);
        }})
        .catch(function(error) {{
            document.getElementById("logContent").textContent =
                "Unable to read log: " + error;
        }});
}}

document.getElementById("logSelect").addEventListener("change", openLog);
window.addEventListener("load", openLog);
</script>
""".format(sidebar=app_sidebar("logs"))

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

    def send_text(self, content, status=200):
        data = content.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
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

        if path == "/read-log":
            query = parse_qs(parsed.query)
            name = query.get("name", [""])[0]
            log_path = get_log_path(name)

            if not log_path:
                self.send_text("Invalid log file", 400)
                return

            self.send_text(get_log_by_name(name))
            return

        if path == "/download-log":
            query = parse_qs(parsed.query)
            name = query.get("name", [""])[0]
            log_path = get_log_path(name)

            if not log_path:
                self.send_text("Invalid log file", 400)
                return

            try:
                with open(log_path, "rb") as f:
                    data = f.read()

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/octet-stream"
                )
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="{}"'.format(name)
                )
                self.send_header(
                    "Content-Length",
                    str(len(data))
                )
                self.end_headers()

                self.wfile.write(data)

            except FileNotFoundError:
                self.send_text("Log file not found: {}".format(name), 404)
            except Exception as e:
                self.send_text(
                    "Unable to download log: {}".format(str(e)),
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
    http_server = ThreadingHTTPServer(
        (HOST, HELPER_PORT),
        Handler,
    )

    servers = [http_server]

    # DSM Desktop is normally served over HTTPS.  An HTTP iframe would be
    # blocked by the browser as mixed content, so expose the same helper over
    # HTTPS as well. The package certificate-helper keeps server.pem/server.key
    # synchronized with the selected DSM/TorrServer certificate.
    if os.path.isfile(HELPER_TLS_CERT_FILE) and os.path.isfile(HELPER_TLS_KEY_FILE):
        try:
            https_server = ThreadingHTTPServer(
                (HOST, HELPER_HTTPS_PORT),
                Handler,
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(HELPER_TLS_CERT_FILE, HELPER_TLS_KEY_FILE)
            https_server.socket = context.wrap_socket(
                https_server.socket,
                server_side=True,
            )
            servers.append(https_server)
        except Exception as exc:
            print("Helper HTTPS disabled: {}".format(exc), flush=True)

    rotation_thread = threading.Thread(
        target=log_rotation_loop,
        daemon=True,
    )
    rotation_thread.start()

    threads = []
    for server in servers:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    run()
