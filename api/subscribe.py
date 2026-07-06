import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from email_storage import subscribe_email


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid request body."})
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

    def _json_response(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
