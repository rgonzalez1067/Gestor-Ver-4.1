"""
Iteration 308 - Portal de Integradores V3
Backend tests:
  - GET /api/integrators/import/template column order (AI..AN)
  - PUT /api/integrators/{id} persists 3 new fields (accespay_product, comercios_relacionados, componente_version)
  - POST /api/integrators/import upsert Prueba A (match & UPDATE, no duplicate)
  - POST /api/integrators/import upsert Prueba B (mismatch modality & INSERT)
  - No prior records are deleted
"""
import io
import os
import uuid
import pytest
import requests
import pandas as pd

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = 'rgonzalez@megasoft.com.ve'
ADMIN_PW = 'admin123'

TAG = f"QATESTV3_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope='module')
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={'email': ADMIN_EMAIL, 'password': ADMIN_PW},
                      timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return r.json()['session_token']


@pytest.fixture(scope='module')
def headers(token):
    return {'Authorization': f'Bearer {token}'}


# --- 1) Template column order ---
def test_template_column_order(headers):
    r = requests.get(f"{BASE_URL}/api/integrators/import/template", headers=headers, timeout=30)
    assert r.status_code == 200, r.text[:200]
    df = pd.read_excel(io.BytesIO(r.content), sheet_name='Plantilla')
    cols = list(df.columns)
    # Find last product column "Producto Lysto" (assumed present) then AI..
    # Instead, just assert relative order:
    def idx(name):
        assert name in cols, f"missing column {name}: cols={cols}"
        return cols.index(name)

    # AH is Producto Lysto per spec; AI onward
    i_lysto = idx('Lysto')
    i_accespay = idx('Producto AccesPay')
    i_proj = idx('Nombre del Proyecto')
    i_obs = idx('Observaciones')
    i_com = idx('Comercios relacionados')
    i_ver = idx('Versión Componente')
    i_contact = idx('Nombre del Contacto Principal')
    assert i_lysto < i_accespay < i_proj < i_obs < i_com < i_ver < i_contact, (
        f"order wrong: lysto={i_lysto}, accespay={i_accespay}, proj={i_proj}, "
        f"obs={i_obs}, com={i_com}, ver={i_ver}, contact={i_contact}"
    )
    # Confirm literal AI..AN excel letters (index 34 == AI = 0-based)
    # A=0 -> AA=26 -> AI=34, AJ=35, AK=36, AL=37, AM=38, AN=39
    assert i_accespay == 34, f"AccesPay must be column AI (idx 34), got {i_accespay}"
    assert i_proj == 35, f"Nombre del Proyecto must be AJ (35), got {i_proj}"
    assert i_obs == 36, f"Observaciones must be AK (36), got {i_obs}"
    assert i_com == 37, f"Comercios relacionados must be AL (37), got {i_com}"
    assert i_ver == 38, f"Versión Componente must be AM (38), got {i_ver}"
    assert i_contact == 39, f"Contacto Principal must be AN (39), got {i_contact}"


# --- 2) PUT persists 3 new fields (manual edit API) ---
@pytest.fixture(scope='module')
def base_integrator(headers):
    """Create a disposable integrator that both PUT and Import tests share."""
    payload = {
        'name': f'{TAG}_INTEG',
        'integrator_type': 'Integrador',
        'app_name': 'AppV3Test',
        'integration_modality': 'PG Universal',
        'integrator_status': 'En proceso',
    }
    r = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=headers, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    iid = data.get('integrator_id') or data.get('id')
    assert iid
    yield {**payload, 'integrator_id': iid}

    # cleanup: delete any doc with same base name (all variants)
    try:
        # Attempt delete of just this record
        requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=30)
    except Exception:
        pass


def test_put_persists_v3_fields(headers, base_integrator):
    iid = base_integrator['integrator_id']
    payload = {
        'name': base_integrator['name'],
        'integrator_type': base_integrator['integrator_type'],
        'app_name': base_integrator['app_name'],
        'integration_modality': base_integrator['integration_modality'],
        'integrator_status': 'En proceso',
        'accespay_product': 'Sí',
        'comercios_relacionados': '7',
        'componente_version': 'v9.9.9',
    }
    r = requests.put(f"{BASE_URL}/api/integrators/{iid}", json=payload, headers=headers, timeout=30)
    assert r.status_code == 200, f"PUT failed {r.status_code} {r.text[:300]}"
    # GET back
    r2 = requests.get(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=30)
    assert r2.status_code == 200
    d = r2.json()
    assert d.get('accespay_product') == 'Sí', d
    assert d.get('comercios_relacionados') == '7', d
    assert d.get('componente_version') == 'v9.9.9', d


# Helper to build xlsx bytes
def _build_xlsx(rows):
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='Plantilla')
    buf.seek(0)
    return buf


def _import(headers, xlsx_bytes, mode='upsert'):
    files = {'file': ('test.xlsx', xlsx_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    data = {'mode': mode}
    r = requests.post(f"{BASE_URL}/api/integrators/import", headers=headers, files=files, data=data, timeout=60)
    return r


# --- 3) Prueba A: MATCH & UPDATE ---
def test_import_upsert_match_update(headers, base_integrator):
    # snapshot count of records having this name
    name = base_integrator['name']

    row = {
        'Nombre': name,
        'Tipo': 'Integrador',
        'Aplicativo': 'AppV3Test',
        'Modalidad de Integración': 'PG Universal',
        'Estatus': 'En proceso',
        'Producto AccesPay': 'Sí-Actualizado',
        'Comercios relacionados': '99',
        'Versión Componente': 'v2.5',
    }
    r = _import(headers, _build_xlsx([row]))
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get('updated_count') == 1, body
    assert body.get('success_count') == 0, body

    # Confirm no duplicate: only 1 record with this composite
    r2 = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=30)
    assert r2.status_code == 200
    matches = [i for i in r2.json()
               if i.get('name') == name
               and i.get('app_name') == 'AppV3Test'
               and i.get('integration_modality') == 'PG Universal']
    assert len(matches) == 1, f"expected 1 matching record, got {len(matches)}"
    m = matches[0]
    assert m.get('accespay_product') == 'Sí-Actualizado', m
    assert m.get('comercios_relacionados') == '99', m
    assert m.get('componente_version') == 'v2.5', m


# --- 4) Prueba B: MISMATCH modality => INSERT ---
def test_import_upsert_mismatch_insert(headers, base_integrator):
    name = base_integrator['name']
    row = {
        'Nombre': name,
        'Tipo': 'Integrador',
        'Aplicativo': 'AppV3Test',           # same name+type+app
        'Modalidad de Integración': 'REST',  # different modality
        'Estatus': 'En proceso',
        'Producto AccesPay': 'No',
        'Comercios relacionados': '3',
        'Versión Componente': 'v0.1',
    }
    r = _import(headers, _build_xlsx([row]))
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get('success_count') == 1, body
    assert body.get('updated_count') == 0, body

    # Now must have exactly 2 records for this name (PG Universal + REST)
    r2 = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=30)
    matches = [i for i in r2.json() if i.get('name') == name]
    assert len(matches) == 2, f"expected 2, got {len(matches)}: {[(m.get('integration_modality'), m.get('integrator_id')) for m in matches]}"
    modalities = sorted(m.get('integration_modality') for m in matches)
    assert modalities == ['PG Universal', 'REST'], modalities

    # Original (PG Universal) still has the values updated by Prueba A (proves no delete)
    orig = [m for m in matches if m.get('integration_modality') == 'PG Universal'][0]
    assert orig.get('componente_version') == 'v2.5', "original UPDATE lost => data was overwritten/deleted"


# --- 5) cleanup extra records created for name TAG ---
def test_zzz_cleanup(headers):
    r = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=30)
    assert r.status_code == 200
    for i in r.json():
        if i.get('name', '').startswith(TAG):
            iid = i.get('integrator_id') or i.get('id')
            if iid:
                requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=30)
