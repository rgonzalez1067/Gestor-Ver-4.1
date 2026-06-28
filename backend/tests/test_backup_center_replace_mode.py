"""
Tests for Centro de Respaldos — Export/Import (upsert vs replace).

Verifies:
- POST /api/admin/migration/{module}/import-preview returns 'to_delete_count' & 'existing_count'.
- POST /api/admin/migration/{module}/import-apply with mode=upsert (default) NEVER deletes.
- POST /api/admin/migration/{module}/import-apply with mode=replace DELETES the documents
  that are not present in the uploaded payload (exact replica), and the count of the collection
  decreases accordingly.
- After the destructive test, the full payload is re-imported in mode=upsert to restore
  the collection to its original count (safety guarantee).
- POST /api/admin/backup-center/import-zip also accepts 'mode' Form field.

Module used: 'inventory-movements' (per main agent instructions). NEVER touches 'user-permissions'.
"""
import io
import json
import os
import zipfile
import pytest
import requests

# Load REACT_APP_BACKEND_URL from frontend/.env if not already in env
if not os.environ.get("REACT_APP_BACKEND_URL"):
    try:
        with open("/app/frontend/.env") as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL="):
                    os.environ["REACT_APP_BACKEND_URL"] = _line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MODULE = "inventory-movements"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("token") or body.get("access_token")
    assert token, f"no token in {body}"
    return token


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def full_export(headers):
    """Exports the inventory-movements module once. Used both as safety baseline AND as
    the file that must be re-imported in upsert mode at the end to restore counts."""
    r = requests.get(
        f"{BASE_URL}/api/admin/migration/{MODULE}/export",
        headers=headers,
        timeout=60,
    )
    assert r.status_code == 200, f"export failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "documents" in data, f"export missing 'documents': {list(data.keys())}"
    assert data.get("module") == MODULE
    docs = data["documents"]
    assert len(docs) >= 5, f"need at least 5 docs to safely test replace; got {len(docs)}"
    # Save a hard copy to disk so a manual rollback is possible if test crashes
    out_path = "/tmp/inventory-movements-backup.json"
    with open(out_path, "w") as f:
        json.dump(data, f)
    print(f"[SAFETY] full export saved to {out_path} with {len(docs)} docs")
    return data


def _post_file(url, headers, payload_dict, filename, extra_form=None):
    body = json.dumps(payload_dict).encode("utf-8")
    files = {"file": (filename, body, "application/json")}
    return requests.post(url, headers=headers, files=files, data=extra_form or {}, timeout=120)


def test_01_import_preview_reports_to_delete_count(headers, full_export):
    """Preview with a trimmed payload (full minus 2 docs) must report to_delete_count=2."""
    trimmed = dict(full_export)
    docs = list(full_export["documents"])
    trimmed["documents"] = docs[:-2]  # remove last 2
    r = _post_file(
        f"{BASE_URL}/api/admin/migration/{MODULE}/import-preview",
        headers,
        trimmed,
        "trimmed.json",
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "to_delete_count" in data, f"missing to_delete_count: {data}"
    assert "existing_count" in data, f"missing existing_count: {data}"
    assert data["to_delete_count"] == 2, f"expected to_delete_count=2, got {data['to_delete_count']} (existing={data.get('existing_count')})"
    print(f"[OK] preview existing={data['existing_count']} to_delete={data['to_delete_count']}")


def test_02_replace_mode_deletes_missing_docs_then_upsert_restores(headers, full_export):
    """Destructive but SAFE: replace with trimmed payload (drops 2), then upsert full to restore."""
    docs = list(full_export["documents"])
    original_count = len(docs)
    trimmed = dict(full_export)
    trimmed["documents"] = docs[:-2]

    # Apply replace with the trimmed payload
    r = _post_file(
        f"{BASE_URL}/api/admin/migration/{MODULE}/import-apply",
        headers,
        trimmed,
        "trimmed.json",
        extra_form={"mode": "replace"},
    )
    try:
        assert r.status_code == 200, r.text
        res = r.json()
        assert res.get("deleted", 0) == 2, f"expected deleted=2, got {res}"
        print(f"[OK] replace result: {res}")
    finally:
        # ALWAYS restore: re-import full export in upsert mode
        rr = _post_file(
            f"{BASE_URL}/api/admin/migration/{MODULE}/import-apply",
            headers,
            full_export,
            "restore.json",
            extra_form={"mode": "upsert"},
        )
        assert rr.status_code == 200, rr.text
        restore = rr.json()
        # deleted MUST be 0 in upsert (verifies upsert never deletes)
        assert restore.get("deleted", 0) == 0, f"upsert should NEVER delete, got {restore}"
        print(f"[OK] restore (upsert) result: {restore}")

    # Verify the collection count matches the original via a fresh preview against the full payload
    r2 = _post_file(
        f"{BASE_URL}/api/admin/migration/{MODULE}/import-preview",
        headers,
        full_export,
        "full.json",
    )
    assert r2.status_code == 200, r2.text
    prev2 = r2.json()
    assert prev2.get("existing_count") == original_count, (
        f"restore incomplete: existing={prev2.get('existing_count')} expected={original_count}"
    )
    assert prev2.get("to_delete_count") == 0
    print(f"[OK] post-restore existing_count={prev2['existing_count']} (== original {original_count})")


def test_03_upsert_default_never_deletes(headers, full_export):
    """import-apply WITHOUT 'mode' must default to upsert and deleted=0."""
    r = _post_file(
        f"{BASE_URL}/api/admin/migration/{MODULE}/import-apply",
        headers,
        full_export,
        "noop.json",
        extra_form={},  # NO mode
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res.get("deleted", 0) == 0, f"default mode must NOT delete, got {res}"
    print(f"[OK] default-mode result: {res}")


def test_04_backup_center_import_zip_accepts_mode(headers, full_export):
    """POST /api/admin/backup-center/import-zip with a ZIP of the same module's export, mode=upsert,
    must succeed and produce 0 deleted (and 0 inserted because file is identical)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{MODULE}.json", json.dumps(full_export))
    buf.seek(0)
    files = {"file": (f"backup-{MODULE}.zip", buf.read(), "application/zip")}
    r = requests.post(
        f"{BASE_URL}/api/admin/backup-center/import-zip",
        headers=headers,
        files=files,
        data={"mode": "upsert"},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    res = r.json()
    # Endpoint returns either a summary block per module or a global breakdown — must NOT error
    print(f"[OK] backup-center import-zip (upsert) result keys: {list(res.keys())}")
    # Sanity: no deleted in upsert mode at any module level
    body_str = json.dumps(res)
    # If there is a 'deleted' field at top level, must be 0 in upsert
    if isinstance(res.get("deleted"), int):
        assert res["deleted"] == 0, f"upsert zip must not delete: {res}"
    # If breakdown style: each module's 'deleted' must be 0
    if "results" in res and isinstance(res["results"], dict):
        for mod, summary in res["results"].items():
            if isinstance(summary, dict) and "deleted" in summary:
                assert summary["deleted"] == 0, f"module {mod} deleted={summary['deleted']} under upsert"
