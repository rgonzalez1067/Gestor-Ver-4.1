"""Iter 327 - Restauración SELECTIVA optimizada (hilo + pymongo + streaming).

Flujo cubierto:
  1) build → build-status (poll) → export-ticket → export (descarga zip)
  2) upload-init → upload-chunk (1 solo chunk, ~43MB en preview)
  3) restore SELECTIVO (collections=["project_sla_config"])  → summary correcto
  4) Mientras/después de restore: /admin/full-backup/info responde 200 (event loop libre)
  5) Restaure múltiples colecciones pequeñas
  6) Colección inexistente → 400
"""

import os
import io
import time
import json
import zipfile
import threading
import pytest
import requests

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")


BASE_URL = _read_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def backup_zip(auth_headers, tmp_path_factory):
    """Construye respaldo total, descarga zip y devuelve (path, manifest)."""
    # 1) build
    r = requests.post(f"{BASE_URL}/api/admin/full-backup/build",
                      headers=auth_headers, timeout=60)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # 2) poll build-status
    deadline = time.time() + 600
    status = None
    while time.time() < deadline:
        s = requests.get(f"{BASE_URL}/api/admin/full-backup/build-status",
                         params={"job_id": job_id}, headers=auth_headers, timeout=30)
        assert s.status_code == 200, s.text
        j = s.json()
        status = j.get("status")
        if status == "ready":
            break
        if status == "error":
            pytest.fail(f"build error: {j.get('error')}")
        time.sleep(5)
    assert status == "ready", f"build no llegó a ready (last={status})"

    # 3) export-ticket
    r = requests.post(f"{BASE_URL}/api/admin/full-backup/export-ticket",
                      headers=auth_headers, json={"job_id": job_id}, timeout=30)
    assert r.status_code == 200, r.text
    ticket = r.json()["ticket"]

    # 4) download
    tmp = tmp_path_factory.mktemp("fb")
    zpath = str(tmp / "full_backup.zip")
    with requests.get(f"{BASE_URL}/api/admin/full-backup/export",
                      params={"ticket": ticket}, stream=True, timeout=600) as resp:
        assert resp.status_code == 200, resp.text[:400]
        with open(zpath, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    size = os.path.getsize(zpath)
    assert size > 1024, f"zip demasiado chico: {size}"

    # leer manifest
    with zipfile.ZipFile(zpath) as zf:
        manifest = json.loads(zf.read("_manifest.json"))
        names = zf.namelist()
    print(f"[backup] size={size} col_files={sum(1 for n in names if n.startswith('collections/'))}")
    return zpath, manifest, names


def _upload(auth_headers, zpath):
    r = requests.post(f"{BASE_URL}/api/admin/full-backup/upload-init",
                      headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    upload_id = r.json()["upload_id"]
    with open(zpath, "rb") as f:
        files = {"file": ("full_backup.zip", f, "application/zip")}
        data = {"upload_id": upload_id, "chunk_index": "0"}
        r = requests.post(f"{BASE_URL}/api/admin/full-backup/upload-chunk",
                          headers=auth_headers, files=files, data=data, timeout=600)
    assert r.status_code == 200, r.text
    return upload_id


def _expected_count(names, zpath, cname):
    """Cuenta docs en la colección leyendo del zip (líneas no vacías ni brackets)."""
    entry = f"collections/{cname}.json"
    if entry not in names:
        return None
    with zipfile.ZipFile(zpath) as zf:
        raw = zf.read(entry).decode("utf-8")
    # el archivo es un array JSON pretty-printed 1 doc/línea o array normal
    raw_stripped = raw.strip()
    try:
        arr = json.loads(raw_stripped)
        if isinstance(arr, list):
            return len(arr)
    except Exception:
        pass
    # fallback conteo por líneas
    n = 0
    for line in raw_stripped.splitlines():
        s = line.strip()
        if not s or s in ("[", "]"):
            continue
        n += 1
    return n


# ---------- TESTS ----------

def test_selective_restore_single_collection(auth_headers, backup_zip):
    zpath, manifest, names = backup_zip
    cname = "project_sla_config"
    if f"collections/{cname}.json" not in names:
        pytest.skip(f"{cname} no está en el respaldo")

    upload_id = _upload(auth_headers, zpath)
    expected = _expected_count(names, zpath, cname)

    # Lanzar en paralelo un GET /info para verificar que el event loop NO se bloquea
    info_results = {"status": None, "elapsed": None}

    def hit_info():
        # esperar un momento para que el restore ya esté corriendo
        time.sleep(0.3)
        t0 = time.time()
        try:
            r = requests.get(f"{BASE_URL}/api/admin/full-backup/info",
                             headers=auth_headers, timeout=10)
            info_results["status"] = r.status_code
        finally:
            info_results["elapsed"] = time.time() - t0

    th = threading.Thread(target=hit_info)
    th.start()

    r = requests.post(f"{BASE_URL}/api/admin/full-backup/restore",
                      headers=auth_headers,
                      data={"upload_id": upload_id, "mode": "merge",
                            "collections": json.dumps([cname])},
                      timeout=600)
    th.join()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["selective"] is True
    assert body["dropped_extra_collections"] == []
    assert body["skipped_collections"] == []
    assert len(body["summary"]) == 1
    entry = body["summary"][0]
    assert entry["name"] == cname
    assert entry["restored"] == expected, f"restored={entry['restored']} expected={expected}"
    print(f"[selective-1] restored={entry['restored']} expected={expected}")

    # /info debe haber respondido 200 durante el restore (event loop libre)
    assert info_results["status"] == 200, f"/info returned {info_results['status']} (event loop bloqueado?)"
    assert info_results["elapsed"] is not None and info_results["elapsed"] < 8, \
        f"/info tardó demasiado: {info_results['elapsed']}s (event loop bloqueado)"
    print(f"[info-during-restore] status=200 elapsed={info_results['elapsed']:.2f}s")


def test_selective_restore_multiple_small_collections(auth_headers, backup_zip):
    zpath, manifest, names = backup_zip
    # Elegimos pequeñas conocidas
    candidates = ["project_sla_config", "company_settings", "email_footer_config", "banks"]
    present = [c for c in candidates if f"collections/{c}.json" in names]
    if len(present) < 2:
        pytest.skip(f"Menos de 2 colecciones candidatas presentes: {present}")
    picks = present[:2]
    expected = {c: _expected_count(names, zpath, c) for c in picks}

    upload_id = _upload(auth_headers, zpath)
    r = requests.post(f"{BASE_URL}/api/admin/full-backup/restore",
                      headers=auth_headers,
                      data={"upload_id": upload_id, "mode": "merge",
                            "collections": json.dumps(picks)},
                      timeout=600)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["selective"] is True
    assert body["skipped_collections"] == []
    assert body["dropped_extra_collections"] == []
    names_restored = {s["name"]: s["restored"] for s in body["summary"]}
    assert set(names_restored.keys()) == set(picks), names_restored
    for c in picks:
        assert names_restored[c] == expected[c], f"{c}: {names_restored[c]} != {expected[c]}"
    print(f"[selective-multi] restored={names_restored} expected={expected}")


def test_selective_restore_nonexistent_collection_returns_400(auth_headers, backup_zip):
    zpath, manifest, names = backup_zip
    upload_id = _upload(auth_headers, zpath)
    r = requests.post(f"{BASE_URL}/api/admin/full-backup/restore",
                      headers=auth_headers,
                      data={"upload_id": upload_id, "mode": "merge",
                            "collections": json.dumps(["__no_existe__"])},
                      timeout=120)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    print(f"[selective-none] 400 detail={r.json().get('detail')}")


def test_info_endpoint_available_after_restore(auth_headers):
    r = requests.get(f"{BASE_URL}/api/admin/full-backup/info",
                     headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
