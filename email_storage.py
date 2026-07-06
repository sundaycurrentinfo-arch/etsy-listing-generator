import csv
import io
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

DATA_DIR = Path(__file__).parent / "data"
EMAILS_CSV = DATA_DIR / "emails.csv"
BLOB_PATH = "emails.csv"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email):
    email = email.strip().lower()
    if not email or not EMAIL_PATTERN.match(email):
        raise ValueError("Please enter a valid email address.")
    return email


def _store_slug():
    store_id = os.environ.get("BLOB_STORE_ID", "").strip()
    if not store_id:
        return None
    return store_id.removeprefix("store_")


def _blob_config(oidc_token=None):
    store_slug = _store_slug()
    token = (oidc_token or os.environ.get("VERCEL_OIDC_TOKEN", "")).strip()
    rw_token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()

    if token and store_slug:
        return {
            "token": token,
            "url": f"https://{store_slug}.private.blob.vercel-storage.com/{BLOB_PATH}",
        }

    if rw_token and store_slug:
        return {
            "token": rw_token,
            "url": f"https://{store_slug}.private.blob.vercel-storage.com/{BLOB_PATH}",
        }

    if rw_token:
        return {
            "token": rw_token,
            "url": f"https://blob.vercel-storage.com/{BLOB_PATH}",
        }

    return None


def _use_blob(oidc_token=None):
    return _blob_config(oidc_token) is not None


def _ensure_local_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not EMAILS_CSV.exists():
        EMAILS_CSV.write_text("email,subscribed_at\n", encoding="utf-8")


def _read_rows_from_csv(content):
    reader = csv.DictReader(io.StringIO(content))
    return [
        {"email": row["email"].strip().lower(), "subscribed_at": row["subscribed_at"]}
        for row in reader
        if row.get("email")
    ]


def _rows_to_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["email", "subscribed_at"])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _read_local_rows():
    _ensure_local_file()
    return _read_rows_from_csv(EMAILS_CSV.read_text(encoding="utf-8"))


def _write_local_rows(rows):
    _ensure_local_file()
    EMAILS_CSV.write_text(_rows_to_csv(rows), encoding="utf-8")


def _blob_get(oidc_token=None):
    config = _blob_config(oidc_token)
    req = request.Request(
        config["url"],
        headers={"Authorization": f"Bearer {config['token']}"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except error.HTTPError as exc:
        if exc.code == 404:
            return "email,subscribed_at\n"
        raise


def _blob_put(content, oidc_token=None):
    config = _blob_config(oidc_token)
    req = request.Request(
        config["url"],
        data=content.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "text/csv",
            "x-api-version": "7",
        },
        method="PUT",
    )
    with request.urlopen(req, timeout=30):
        pass


def _read_rows(oidc_token=None):
    if _use_blob(oidc_token):
        return _read_rows_from_csv(_blob_get(oidc_token))
    return _read_local_rows()


def _write_rows(rows, oidc_token=None):
    content = _rows_to_csv(rows)
    if _use_blob(oidc_token):
        _blob_put(content, oidc_token)
    else:
        _write_local_rows(rows)


def subscribe_email(email, oidc_token=None):
    if os.environ.get("VERCEL") and not _use_blob(oidc_token):
        raise RuntimeError(
            "Email storage is not configured. Connect a Blob store to this project in Vercel Storage."
        )

    email = validate_email(email)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = _read_rows(oidc_token)

    if any(row["email"] == email for row in rows):
        return {"ok": True}

    rows.append({"email": email, "subscribed_at": timestamp})
    _write_rows(rows, oidc_token)
    return {"ok": True}


def export_emails_csv(oidc_token=None):
    if _use_blob(oidc_token):
        content = _blob_get(oidc_token)
    else:
        _ensure_local_file()
        content = EMAILS_CSV.read_text(encoding="utf-8")
    return content


def verify_export_secret(provided):
    secret = os.environ.get("EXPORT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Export is not configured. Add EXPORT_SECRET to your environment.")
    if provided != secret:
        raise PermissionError("Invalid export secret.")
