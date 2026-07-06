#!/usr/bin/env python3
"""Local development server for the Etsy Listing Generator."""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from email_storage import export_emails_csv, subscribe_email, verify_export_secret
from listing_logic import generate_listing

PUBLIC_DIR = Path(__file__).parent / "public"
ENV_FILE = Path(__file__).parent / ".env"


def load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
PORT = int(os.environ.get("PORT", "3000"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/export-emails":
            self._handle_export(parsed)
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/generate":
            self._handle_generate()
        elif self.path == "/api/subscribe":
            self._handle_subscribe()
        else:
            self.send_error(404)

    def _handle_generate(self):
        body = self._read_json_body()
        if body is None:
            return
        status, payload = generate_listing(body)
        self._json_response(status, payload)

    def _handle_subscribe(self):
        body = self._read_json_body()
        if body is None:
            return

        try:
            result = subscribe_email(body.get("email", ""))
            self._json_response(200, result)
        except ValueError as exc:
            self._json_response(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._json_response(500, {"error": str(exc)})
        except Exception:
            self._json_response(500, {"error": "Something went wrong. Please try again."})

    def _handle_export(self, parsed):
        query = parse_qs(parsed.query)
        secret = query.get("secret", [""])[0]

        try:
            verify_export_secret(secret)
            content = export_emails_csv()
        except PermissionError:
            self._json_response(403, {"error": "Invalid export secret."})
            return
        except RuntimeError as exc:
            self._json_response(500, {"error": str(exc)})
            return

        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header(
            "Content-Disposition", 'attachment; filename="subscribers.csv"'
        )
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid request body."})
            return None

    def _json_response(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        sys.stdout.write(
            "%s - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )


def main():
    server = HTTPServer(("", PORT), Handler)
    print(f"Etsy Listing Generator running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
