"""Iter215 - Backup Center: 3 nuevas entidades de Inventario
(inventory-warehouses, inventory-serial-assignments, inventory-movement-audits).
Pruebas NO destructivas: cualquier replace se hace contra el mismo export
y luego se restaura el dataset con upsert del export completo.
"""
import io
import json
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-impl-filter.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

NEW_ENTITIES = [
    ("inventory-warehouses", "warehouses", "warehouse_id", 2),
    ("inventory-serial-assignments", "serial_assignments", "assignment_id", 6),
    ("inventory-movement-audits", "inventory_movement_audits", "audit_id", 3),
]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"Login fail: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("session_token") or j.get("token") or j.get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_entities_lists_new_3(headers):
    r = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    ents = {e["module"]: e for e in r.json().get("entities", [])}
    for module, _coll, _key, _expected in NEW_ENTITIES:
        assert module in ents, f"Falta entidad {module} en backup-center/entities"
        assert "count" in ents[module]
    # Reportar conteos para diagnóstico
    print({m: ents[m]["count"] for m, _, _, _ in NEW_ENTITIES})


@pytest.mark.parametrize("module,collection,key,expected", NEW_ENTITIES)
def test_export_each_new_entity(headers, module, collection, key, expected):
    r = requests.get(f"{BASE_URL}/api/admin/migration/{module}/export", headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("module") == module
    assert data.get("collection") == collection
    assert data.get("key") == key
    assert isinstance(data.get("documents"), list)
    # No exigimos el conteo exacto si cambió, pero advertimos
    print(f"{module} count={data.get('count')} (expected~{expected})")


@pytest.mark.parametrize("module,collection,key,expected", NEW_ENTITIES)
def test_import_apply_same_file_non_destructive(headers, module, collection, key, expected):
    # 1) Export completo
    r = requests.get(f"{BASE_URL}/api/admin/migration/{module}/export", headers=headers, timeout=60)
    assert r.status_code == 200
    payload = r.json()
    count_before = payload.get("count", 0)

    # 2) Preview con el mismo archivo -> to_delete_count debe ser 0
    files = {"file": (f"{module}.json", json.dumps(payload).encode("utf-8"), "application/json")}
    pr = requests.post(
        f"{BASE_URL}/api/admin/migration/{module}/import-preview", headers=headers, files=files, timeout=60
    )
    assert pr.status_code == 200, pr.text
    pdata = pr.json()
    assert pdata.get("to_delete_count", 0) == 0, f"to_delete_count != 0 con mismo archivo: {pdata}"
    assert pdata.get("to_create_count", 0) == 0

    # 3) Apply upsert (no destructivo, sin cambios)
    files = {"file": (f"{module}.json", json.dumps(payload).encode("utf-8"), "application/json")}
    data = {"mode": "upsert"}
    ar = requests.post(
        f"{BASE_URL}/api/admin/migration/{module}/import-apply",
        headers=headers, files=files, data=data, timeout=120,
    )
    assert ar.status_code == 200, ar.text
    adata = ar.json()
    assert adata.get("deleted", 0) == 0

    # 4) Reverificar conteo via entities
    r2 = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=headers, timeout=30)
    ents = {e["module"]: e for e in r2.json().get("entities", [])}
    assert ents[module]["count"] == count_before, (
        f"Conteo cambió tras upsert idempotente. before={count_before} after={ents[module]['count']}"
    )


def test_export_zip_includes_new_entities(headers):
    selected = [m for m, _, _, _ in NEW_ENTITIES]
    r = requests.post(
        f"{BASE_URL}/api/admin/backup-center/export-zip",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps({"modules": selected}),
        timeout=120,
    )
    assert r.status_code == 200, r.text
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    for m in selected:
        assert f"{m}.json" in names, f"ZIP no contiene {m}.json. Tiene: {names}"
    # Guardar a tmp para reuso
    tmp_path = "/tmp/iter215_backup.zip"
    with open(tmp_path, "wb") as f:
        f.write(r.content)
    return tmp_path


def test_zip_import_preview_recognizes_new(headers):
    selected = [m for m, _, _, _ in NEW_ENTITIES]
    r = requests.post(
        f"{BASE_URL}/api/admin/backup-center/export-zip",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps({"modules": selected}),
        timeout=120,
    )
    assert r.status_code == 200
    zip_bytes = r.content
    files = {"file": ("backup.zip", zip_bytes, "application/zip")}
    pr = requests.post(
        f"{BASE_URL}/api/admin/backup-center/import-preview-zip",
        headers=headers, files=files, timeout=60,
    )
    assert pr.status_code == 200, pr.text
    pdata = pr.json()
    modules_in_preview = {e["module"] for e in pdata.get("entities", [])}
    for m in selected:
        assert m in modules_in_preview, f"Preview-zip no reconoce {m}: {pdata}"


def test_zip_import_apply_same_file_non_destructive(headers):
    # Conteos previos
    r0 = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=headers, timeout=30)
    before = {e["module"]: e["count"] for e in r0.json().get("entities", [])}

    selected = [m for m, _, _, _ in NEW_ENTITIES]
    r = requests.post(
        f"{BASE_URL}/api/admin/backup-center/export-zip",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps({"modules": selected}),
        timeout=120,
    )
    assert r.status_code == 200
    files = {"file": ("backup.zip", r.content, "application/zip")}
    data = {"mode": "upsert"}
    ar = requests.post(
        f"{BASE_URL}/api/admin/backup-center/import-zip",
        headers=headers, files=files, data=data, timeout=180,
    )
    assert ar.status_code == 200, ar.text
    res = ar.json()
    assert res.get("total_deleted", 0) == 0

    # Conteos posteriores intactos
    r1 = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=headers, timeout=30)
    after = {e["module"]: e["count"] for e in r1.json().get("entities", [])}
    for m, _, _, _ in NEW_ENTITIES:
        assert before[m] == after[m], f"{m} count changed: {before[m]} -> {after[m]}"


def test_replace_reversible_on_inventory_warehouses(headers):
    """Export warehouses (2), elimina 1 doc -> preview debe dar to_delete_count=1,
    replace debe deleted=1. Luego restaura con upsert del export completo."""
    module = "inventory-warehouses"

    # Export completo
    r = requests.get(f"{BASE_URL}/api/admin/migration/{module}/export", headers=headers, timeout=60)
    assert r.status_code == 200
    full = r.json()
    docs = full.get("documents", [])
    if len(docs) < 2:
        pytest.skip("warehouses tiene <2 docs, no se puede probar replace reversible")

    # Trimmed payload con 1 doc menos (conserva los demás)
    trimmed = dict(full)
    trimmed["documents"] = docs[:-1]
    trimmed["count"] = len(trimmed["documents"])

    # Preview con trimmed: to_delete_count=1
    files = {"file": (f"{module}_trimmed.json", json.dumps(trimmed).encode("utf-8"), "application/json")}
    pr = requests.post(
        f"{BASE_URL}/api/admin/migration/{module}/import-preview",
        headers=headers, files=files, timeout=60,
    )
    assert pr.status_code == 200, pr.text
    assert pr.json().get("to_delete_count") == 1, pr.json()

    # Apply replace -> deleted=1
    files = {"file": (f"{module}_trimmed.json", json.dumps(trimmed).encode("utf-8"), "application/json")}
    data = {"mode": "replace"}
    ar = requests.post(
        f"{BASE_URL}/api/admin/migration/{module}/import-apply",
        headers=headers, files=files, data=data, timeout=120,
    )
    assert ar.status_code == 200, ar.text
    assert ar.json().get("deleted") == 1, ar.json()

    # Restaurar con upsert del export COMPLETO
    files = {"file": (f"{module}_full.json", json.dumps(full).encode("utf-8"), "application/json")}
    data = {"mode": "upsert"}
    rr = requests.post(
        f"{BASE_URL}/api/admin/migration/{module}/import-apply",
        headers=headers, files=files, data=data, timeout=120,
    )
    assert rr.status_code == 200, rr.text

    # Verificar conteo restaurado
    rc = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=headers, timeout=30)
    ents = {e["module"]: e for e in rc.json().get("entities", [])}
    assert ents[module]["count"] == len(docs), (
        f"warehouses NO restaurado: esperado={len(docs)} got={ents[module]['count']}"
    )
