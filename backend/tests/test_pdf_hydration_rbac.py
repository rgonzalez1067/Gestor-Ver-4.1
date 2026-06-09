"""
Regresión P0 — Homologación / Aislamiento RBAC del motor de PDF.

Verifica que `hydrate_pdf_request` resuelve los nombres autoritativos desde Mongo
usando solo los IDs (escenario de un usuario con RBAC limitado cuyo frontend NO
cargó los catálogos y por ende envía los nombres en blanco). Garantiza que
Previsualizar / Exportar / Guardar generen el MISMO documento.
"""
import asyncio
import pytest

from services.pdf_generator import TemplateQuotePDFRequest
from routes.quotes import hydrate_pdf_request

CLIENT_ID = "cli_2aa0ea072c7f"      # 10 DE NOVIEMBRE, C.A. / J505015214
INTEGRATOR_ID = "int_7c555185aa22"  # Equinoccio Agency
HARDWARE_ID = "hwr_3b365a77248a"    # Morefun MF960
BANK_ID = "bnk_3997d471d939"        # Banco de Venezuela


def test_hydration_fills_empty_names_from_ids():
    """RBAC limitado: nombres vacíos + IDs válidos -> nombres resueltos desde la BD."""
    req = TemplateQuotePDFRequest(
        cliente_nombre="",               # frontend RBAC envía vacío
        cliente_rif="",
        integrator_name="",
        pinpad_model="",
        sponsor_bank_name="",
        client_id=CLIENT_ID,
        integrator_id=INTEGRATOR_ID,
        pinpad_id=HARDWARE_ID,
        sponsor_bank_id=BANK_ID,
    )
    asyncio.get_event_loop().run_until_complete(hydrate_pdf_request(req))

    assert req.cliente_nombre == "10 DE NOVIEMBRE, C.A."
    assert req.cliente_rif == "J505015214"
    assert req.integrator_name == "Equinoccio Agency"
    assert req.pinpad_model == "Morefun MF960"
    assert req.sponsor_bank_name == "Banco de Venezuela"


def test_hydration_is_authoritative_admin_equals_rbac():
    """Admin (con nombres) y RBAC (sin nombres) convergen al MISMO resultado."""
    admin_req = TemplateQuotePDFRequest(
        cliente_nombre="10 DE NOVIEMBRE, C.A.",
        cliente_rif="J505015214",
        integrator_name="Equinoccio Agency",
        pinpad_model="Morefun MF960",
        sponsor_bank_name="Banco de Venezuela",
        client_id=CLIENT_ID, integrator_id=INTEGRATOR_ID,
        pinpad_id=HARDWARE_ID, sponsor_bank_id=BANK_ID,
    )
    rbac_req = TemplateQuotePDFRequest(
        cliente_nombre="", cliente_rif="", integrator_name="",
        pinpad_model="", sponsor_bank_name="",
        client_id=CLIENT_ID, integrator_id=INTEGRATOR_ID,
        pinpad_id=HARDWARE_ID, sponsor_bank_id=BANK_ID,
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(hydrate_pdf_request(admin_req))
    loop.run_until_complete(hydrate_pdf_request(rbac_req))

    for field in ("cliente_nombre", "cliente_rif", "integrator_name",
                  "pinpad_model", "sponsor_bank_name"):
        assert getattr(admin_req, field) == getattr(rbac_req, field)


def test_hydration_no_ids_is_noop():
    """Sin IDs, conserva lo que envíe el frontend (no rompe flujos legacy)."""
    req = TemplateQuotePDFRequest(
        cliente_nombre="Cliente Legacy", cliente_rif="J123",
        integrator_name="Integrador X",
    )
    asyncio.get_event_loop().run_until_complete(hydrate_pdf_request(req))
    assert req.cliente_nombre == "Cliente Legacy"
    assert req.cliente_rif == "J123"
    assert req.integrator_name == "Integrador X"


def test_hydration_sin_integrador_label():
    """integrator_id == 'sin_integrador' -> etiqueta amigable por defecto."""
    req = TemplateQuotePDFRequest(
        cliente_nombre="X", integrator_id="sin_integrador", integrator_name="",
    )
    asyncio.get_event_loop().run_until_complete(hydrate_pdf_request(req))
    assert req.integrator_name == "Sin integrador por el momento"
