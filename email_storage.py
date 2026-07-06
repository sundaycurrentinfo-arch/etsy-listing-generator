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


def _blob_config():
    rw_token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if not rw_token:
        return None

    store_slug = _store_slug()
    if store_slug:
        return {
            "token": rw_token,
            "url": f"https://{store_slug}.private.blob.vercel-storage.com/{BLOB_PATH}",
        }

    return {
        "token": rw_token,
        "url": f"https://blob.vercel-storage.com/{BLOB_PATH}",
    }


def _use_blob():
    return _blob_config() is not None


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


def _blob_get():
    config = _blob_config()
    req = request.Request(
        config["url"],
        headers={"Authorization": f"Bearer {config['token']}"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except error.HTTPError as exc:
        if exc.code == 404:
            return "email,subscribed_at\n"
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Could not read email storage ({exc.code}).") from exc


def _blob_put(content):
    config = _blob_config()
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
    try:
        with request.urlopen(req, timeout=15):
            pass
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Could not save email ({exc.code}).") from exc


def _read_rows():
    if _use_blob():
        return _read_rows_from_csv(_blob_get())
    return _read_local_rows()


def _write_rows(rows):
    content = _rows_to_csv(rows)
    if _use_blob():
        _blob_put(content)
    else:
        _write_local_rows(rows)


def subscribe_email(email):
    if os.environ.get("VERCEL") and not _use_blob():
        raise RuntimeError(
            "Email storage is not configured. Add BLOB_READ_WRITE_TOKEN in Vercel Environment Variables."
        )

    email = validate_email(email)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = _read_rows()

    if any(row["email"] == email for row in rows):
        return {"ok": True}

    rows.append({"email": email, "subscribed_at": timestamp})
    _write_rows(rows)
    return {"ok": True}


def export_emails_csv():
    if _use_blob():
        return _blob_get()
    _ensure_local_file()
    return EMAILS_CSV.read_text(encoding="utf-8")


def verify_export_secret(provided):
    secret = os.environ.get("EXPORT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Export is not configured. Add EXPORT_SECRET to your environment.")
    if provided != secret:
        raise PermissionError("Invalid export secret.")
