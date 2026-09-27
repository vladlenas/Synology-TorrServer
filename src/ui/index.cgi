#!/usr/bin/env python3

import os
import sys
import http.client
from urllib.parse import parse_qs, urlencode


BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8095


def send_response(status, headers, body):
    status_text = {
        200: "OK",
        302: "Found",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
        502: "Bad Gateway",
    }.get(status, "OK")

    print("Status: {} {}".format(status, status_text))

    for name, value in headers:
        lname = name.lower()

        if lname in (
            "connection",
            "keep-alive",
            "transfer-encoding",
            "content-encoding",
        ):
            continue

        print("{}: {}".format(name, value))

    print()
    sys.stdout.buffer.write(body)


def proxy():
    query = parse_qs(
        os.environ.get("QUERY_STRING", ""),
        keep_blank_values=True
    )

    path = query.get("path", ["/"])[0]

    if not path.startswith("/"):
        path = "/" + path

    forwarded_query = []

    for key, values in query.items():
        if key == "path":
            continue

        for value in values:
            forwarded_query.append(
                "{}={}".format(
                    key,
                    value
                )
            )

    if forwarded_query:
        path += "?" + "&".join(forwarded_query)

    method = os.environ.get("REQUEST_METHOD", "GET").upper()

    body = b""

    if method in ("POST", "PUT", "PATCH"):
        try:
            length = int(
                os.environ.get("CONTENT_LENGTH", "0")
            )
        except ValueError:
            length = 0

        if length > 0:
            body = sys.stdin.buffer.read(length)

    headers = {
        "Host": "{}:{}".format(
            BACKEND_HOST,
            BACKEND_PORT
        )
    }

    content_type = os.environ.get("CONTENT_TYPE")

    if content_type:
        headers["Content-Type"] = content_type

    cookie = os.environ.get("HTTP_COOKIE")

    if cookie:
        headers["Cookie"] = cookie

    try:
        connection = http.client.HTTPConnection(
            BACKEND_HOST,
            BACKEND_PORT,
            timeout=30
        )

        connection.request(
            method,
            path,
            body=body if body else None,
            headers=headers
        )

        response = connection.getresponse()

        response_body = response.read()

        response_headers = []

        for name, value in response.getheaders():
            lname = name.lower()

            if lname == "location":
                if value.startswith("/"):
                    value = "index.cgi?path=" + value

            response_headers.append(
                (name, value)
            )

        content_type_header = None

        for name, value in response_headers:
            if name.lower() == "content-type":
                content_type_header = value
                break

        # Helper HTML contains absolute paths such as:
        #   href="/settings"
        #   fetch("/read-log?...").
        #
        # Rewrite them so they stay inside this CGI proxy.
        if (
            content_type_header
            and "text/html" in content_type_header
        ):
            text = response_body.decode(
                "utf-8",
                errors="replace"
            )

            proxy_prefix = "index.cgi?path="

            text = text.replace(
                'href="/"',
                'href="{}%2F"'.format(proxy_prefix)
            )

            for item in (
                "/settings",
                "/logs",
                "/browse",
                "/read-log",
                "/download-log",
                "/restart",
            ):
                text = text.replace(
                    'href="{}"'.format(item),
                    'href="{}{}"'.format(
                        proxy_prefix,
                        item
                    )
                )

                text = text.replace(
                    'href="{}?'.format(item),
                    'href="{}{}?'.format(
                        proxy_prefix,
                        item
                    )
                )

                text = text.replace(
                    'fetch("{}?'.format(item),
                    'fetch("{}{}?'.format(
                        proxy_prefix,
                        item
                    )
                )

            response_body = text.encode("utf-8")

            response_headers = [
                (name, value)
                for name, value in response_headers
                if name.lower() != "content-length"
            ]

            response_headers.append(
                (
                    "Content-Length",
                    str(len(response_body))
                )
            )

        send_response(
            response.status,
            response_headers,
            response_body
        )

        connection.close()

    except Exception as exc:
        message = (
            "TorrServer Helper proxy error: {}".format(exc)
        ).encode("utf-8")

        send_response(
            502,
            [
                (
                    "Content-Type",
                    "text/plain; charset=utf-8"
                ),
                (
                    "Content-Length",
                    str(len(message))
                )
            ],
            message
        )


if __name__ == "__main__":
    proxy()
