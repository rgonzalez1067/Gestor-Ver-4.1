"""Backend test — Importación de Integradores con campos de seguimiento.

Valida:
 - Coordinador válido (cargo 'Coordinador' + depto 'Implementación') se guarda.
 - Coordinador inválido → fila rechazada con mensaje específico.
 - Fecha de Inicio con formato distinto a DD/MM/AAAA → fila rechazada.
 - Los 4 campos nuevos se persisten correctamente.
"""
import io
import os
import pytest
import requests
import pandas as pd

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}

CREATED_NAMES = ["QA_IMP_VALIDO", "QA_IMP_COORD_INVALIDO", "QA_IMP_FECHA_INVALIDA"]


def _login():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login()}"})
    yield s
    # cleanup: borrar integradores de prueba creados
    r = s.get(f"{API}/integrators", timeout=30)
    if r.status_code == 200:
        for it in r.json():
            if it.get("name") in CREATED_NAMES:
                s.delete(f"{API}/integrators/{it['integrator_id']}", timeout=30)


def _coordinator_name(sess):
    r = sess.get(f"{API}/integrators/coordinators", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data, "No hay Coordinadores de Implementación para la prueba"
    return data[0]["name"]


def _build_xlsx(rows):
    cols = ["Nombre", "Tipo", "Aplicativo", "Modalidad de Integración", "Estatus",
            "Tipo de Integracion", "Coordinador", "Fecha de Inicio del Proyecto",
            "Nombre del Proyecto", "Observaciones"]
    df = pd.DataFrame(rows, columns=cols)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_import_with_followup_fields(sess):
    coord = _coordinator_name(sess)
    rows = [
        # Válida
        {"Nombre": "QA_IMP_VALIDO", "Tipo": "Integrador", "Aplicativo": "QAApp",
         "Modalidad de Integración": "PG Universal", "Estatus": "En proceso",
         "Tipo de Integracion": "PG", "Coordinador": coord,
         "Fecha de Inicio del Proyecto": "10/01/2026",
         "Nombre del Proyecto": "Proyecto QA Uno", "Observaciones": "Nota QA"},
        # Coordinador inválido
        {"Nombre": "QA_IMP_COORD_INVALIDO", "Tipo": "Integrador", "Aplicativo": "QAApp2",
         "Modalidad de Integración": "PG Universal", "Estatus": "En proceso",
         "Tipo de Integracion": "PG", "Coordinador": "Persona Inexistente QA",
         "Fecha de Inicio del Proyecto": "11/01/2026",
         "Nombre del Proyecto": "X", "Observaciones": ""},
        # Fecha con formato inválido (ISO en vez de DD/MM/AAAA)
        {"Nombre": "QA_IMP_FECHA_INVALIDA", "Tipo": "Integrador", "Aplicativo": "QAApp3",
         "Modalidad de Integración": "PG Universal", "Estatus": "En proceso",
         "Tipo de Integracion": "PG", "Coordinador": coord,
         "Fecha de Inicio del Proyecto": "2026-01-12",
         "Nombre del Proyecto": "Y", "Observaciones": ""},
    ]
    xlsx = _build_xlsx(rows)
    files = {"file": ("import_qa.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = sess.post(f"{API}/integrators/import", files=files, timeout=120)
    assert r.status_code == 200, r.text
    result = r.json()
    errors = result.get("errors", [])
    err_text = " | ".join((e.get("message", "") if isinstance(e, dict) else str(e)) for e in errors)

    # Mensaje específico de coordinador inválido
    assert "Coordinador no encontrado o cargo inválido" in err_text, f"Falta error coordinador. Errores: {err_text}"
    # Error de formato de fecha
    assert "Fecha de Inicio" in err_text and "DD/MM/AAAA" in err_text, f"Falta error de fecha. Errores: {err_text}"

    # La fila válida se guardó con los 4 campos
    allints = sess.get(f"{API}/integrators", timeout=30).json()
    valido = next((i for i in allints if i.get("name") == "QA_IMP_VALIDO"), None)
    assert valido, "La fila válida no se guardó"
    assert valido.get("coordinador") == coord
    assert valido.get("project_start_date") == "2026-01-10", valido.get("project_start_date")
    assert valido.get("project_name") == "Proyecto QA Uno"
    assert valido.get("observations") == "Nota QA"

    # Las filas inválidas NO deben haberse guardado
    assert not any(i.get("name") == "QA_IMP_COORD_INVALIDO" for i in allints), "Fila con coordinador inválido NO debió guardarse"
    assert not any(i.get("name") == "QA_IMP_FECHA_INVALIDA" for i in allints), "Fila con fecha inválida NO debió guardarse"
