import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from email_storage import export_emails_csv, verify_export_secret


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        secret = query.get("secret", [""])[0]

        try:
            verify_export_secret(secret)
            oidc_token = self.headers.get("x-vercel-oidc-token")
            content = export_emails_csv(oidc_token=oidc_token)
        except PermissionError:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Invalid export secret."}')
            return
        except RuntimeError as exc:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error":"{exc}"}}'.encode("utf-8"))
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
