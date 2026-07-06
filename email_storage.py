import csv
import io
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

DATA_DIR = Path(__file__).parent / "data"
EMAILS_CSV = DATA_DIR / "emails.csv"
BLOB_PATH = "emails.csv"
BLOB_API = "https://vercel.com/api/blob"
API_VERSION = "12"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email):
    email = email.strip().lower()
    if not email or not EMAIL_PATTERN.match(email):
        raise ValueError("Please enter a valid email address.")
    return email


def _blob_token():
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()


def _store_id():
    store_id = os.environ.get("BLOB_STORE_ID", "").strip()
    if store_id:
        return store_id.removeprefix("store_")

    token = _blob_token()
    parts = token.split("_")
    if len(parts) > 3 and parts[3]:
        return parts[3]

    return None


def _use_blob():
    return bool(_blob_token())


def _blob_headers(extra=None):
    headers = {
        "Authorization": f"Bearer {_blob_token()}",
        "x-api-version": API_VERSION,
    }

    store_id = _store_id()
    if store_id:
        headers["x-vercel-blob-store-id"] = store_id

    if extra:
        headers.update(extra)

    return headers


def _blob_private_url():
    store_id = _store_id()
    if not store_id:
        raise RuntimeError("Could not determine Blob store ID.")
    return f"https://{store_id}.private.blob.vercel-storage.com/{BLOB_PATH}"


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
    req = request.Request(
        _blob_private_url(),
        headers=_blob_headers(),
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except error.HTTPError as exc:
        if exc.code == 404:
            return "email,subscribed_at\n"
        raise RuntimeError(f"Could not read email storage ({exc.code}).") from exc


def _blob_put(content):
    put_url = f"{BLOB_API}/?{parse.urlencode({'pathname': BLOB_PATH})}"
    req = request.Request(
        put_url,
        data=content.encode("utf-8"),
        headers=_blob_headers(
            {
                "x-vercel-blob-access": "private",
                "x-content-type": "text/csv",
                "x-allow-overwrite": "1",
                "x-add-random-suffix": "0",
            }
        ),
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            resp.read()
    except error.HTTPError as exc:
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
