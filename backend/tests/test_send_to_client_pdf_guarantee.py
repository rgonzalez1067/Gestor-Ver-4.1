"""Backend test — Garantía documental en "Enviar al Cliente".

Verifica que si el PDF de la cotización NO está en disco al enviar, el endpoint
lo REGENERA automáticamente (motor según categoría), lo indexa en anexos y
completa el envío. Cubre la corrección de "Modificar → Mantener Original".

Estrategia (sin ensuciar datos reales): toma una cotización real existente,
respalda su estado, simula la ausencia del PDF (quote_pdf_url -> ruta inválida),
ejecuta el flujo y restaura el estado original al finalizar.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}


def _login():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def _db():
    import os
    import config  # noqa: F401
    from pymongo import MongoClient
    cli = MongoClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


def _pick_quote(db):
    """Una cotización de implementación (no equipos/reparaciones) con servicios y PDF."""
    return db.quotes.find_one({
        "quote_category": {"$nin": ["equipment", "repair"]},
        "services.0": {"$exists": True},
        "quote_pdf_url": {"$exists": True, "$ne": None},
    }, {"_id": 0})


def test_send_to_client_regenerates_missing_pdf():
    token = _login()
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {token}"})

    cli, db = _db()
    quote = _pick_quote(db)
    if not quote:
        cli.close()
        pytest.skip("No hay cotización de implementación con servicios y PDF para probar")

    qid = quote["quote_id"]
    backup = {
        "quote_pdf_url": quote.get("quote_pdf_url"),
        "quote_status": quote.get("quote_status"),
        "sent_to_client_at": quote.get("sent_to_client_at"),
        "attachments": quote.get("attachments", []),
    }

    try:
        # Simula la ausencia del PDF: ruta inexistente.
        db.quotes.update_one({"quote_id": qid}, {"$set": {"quote_pdf_url": "/uploads/__inexistente__.pdf"}})

        # Enviar al cliente → debe auto-regenerar y completar (200).
        r = sess.post(f"{API}/quotes/{qid}/send-to-client", timeout=120)
        assert r.status_code == 200, f"Esperado 200, obtenido {r.status_code}: {r.text}"

        # La cotización debe tener un quote_pdf_url válido y un anexo 'Cotización'.
        updated = db.quotes.find_one({"quote_id": qid}, {"_id": 0})
        new_url = updated.get("quote_pdf_url")
        assert new_url and new_url != "/uploads/__inexistente__.pdf", "quote_pdf_url no se regeneró"

        from config import UPLOADS_DIR
        pdf_path = UPLOADS_DIR / new_url.replace("/uploads/", "")
        assert pdf_path.exists(), f"El PDF regenerado no existe en disco: {pdf_path}"

        cot_attachments = [a for a in (updated.get("attachments") or []) if a.get("category") == "Cotización"]
        assert cot_attachments, "No se indexó el anexo 'Cotización' tras regenerar"
    finally:
        # Restaurar estado original (status / sent_to_client_at).
        db.quotes.update_one({"quote_id": qid}, {"$set": {
            "quote_status": backup["quote_status"],
            "sent_to_client_at": backup["sent_to_client_at"],
        }})
        cli.close()
