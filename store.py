# Day 5: NEW FILE. Tracks uploaded docs: hash, local file path, saved extraction.
# Files are saved on local disk (uploads/ folder), NOT on any cloud platform.
import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
UPLOAD_DIR = BASE / "uploads"  # local disk only
DB_PATH = BASE / "claim_poc.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conn():
    UPLOAD_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    # one row per unique file (sha512 is the unique key)
    c.execute("""CREATE TABLE IF NOT EXISTS uploaded_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            sha512 TEXT NOT NULL UNIQUE,
            file_path TEXT NOT NULL,
            doc_type TEXT,
            classify_reason TEXT,
            extracted_data TEXT,
            policy_clauses TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error TEXT,
            created_at TEXT,
            updated_at TEXT
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON uploaded_docs(sha256)")
    return c


def hashes(data: bytes):
    """Returns (sha256, sha512) of the file bytes."""
    return hashlib.sha256(data).hexdigest(), hashlib.sha512(data).hexdigest()


def find_by_hash(sha512: str):
    """Duplicate check: is this exact file already in the database?"""
    with closing(_conn()) as c:
        return c.execute(
            "SELECT * FROM uploaded_docs WHERE sha512 = ?", (sha512,)
        ).fetchone()


def find_by_path(file_path: str):
    with closing(_conn()) as c:
        return c.execute(
            "SELECT * FROM uploaded_docs WHERE file_path = ?", (file_path,)
        ).fetchone()


def save_file(name: str, data: bytes, sha256: str) -> str:
    """Save the uploaded file on local disk and return its path."""
    UPLOAD_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    path = UPLOAD_DIR / f"{sha256[:16]}_{safe}"
    path.write_bytes(data)
    return str(path)


def create_record(name: str, sha256: str, sha512: str, file_path: str) -> int:
    now = _now()
    with closing(_conn()) as c:
        cur = c.execute(
            """INSERT INTO uploaded_docs
               (file_name, sha256, sha512, file_path, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'PENDING', ?, ?)""",
            (name, sha256, sha512, file_path, now, now),
        )
        c.commit()
        return cur.lastrowid


def save_extraction(record_id, doc_type, reason, extraction_json, clauses_json):
    """Save the extraction result in the doc's own record."""
    with closing(_conn()) as c:
        c.execute(
            """UPDATE uploaded_docs
               SET doc_type = ?, classify_reason = ?, extracted_data = ?,
                   policy_clauses = ?, status = 'EXTRACTED', error = NULL,
                   updated_at = ?
               WHERE id = ?""",
            (doc_type, reason, extraction_json, clauses_json, _now(), record_id),
        )
        c.commit()


def mark_failed(record_id: int, error: str):
    with closing(_conn()) as c:
        c.execute(
            "UPDATE uploaded_docs SET status = 'FAILED', error = ?, updated_at = ? WHERE id = ?",
            (error, _now(), record_id),
        )
        c.commit()
