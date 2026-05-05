"""Test que las variables de cliente en plantillas se resuelven desde el documento `clients`.
Valida que `Nombre_Cliente`, `Datos_Contacto`, `Email_Contacto`, `Telefono_Contacto`,
`Direccion_Cliente` se rellenen aunque la cotización no las tenga denormalizadas.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')


async def _seed():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    client = {
        "client_id": "test_cli_tpl_001",
        "rif": "J777777",
        "legal_name": "Empresa Plantilla Test, C.A.",
        "fantasy_name": "Plantilla Test",
        "address": "Calle Bolívar #42 Caracas",
        "contacts": [{
            "full_name": "María González",
            "email": "maria@plantilla.test",
            "phone": "+58-414-9999999",
        }],
    }
    await db.clients.update_one({"client_id": client["client_id"]}, {"$set": client}, upsert=True)


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.clients.delete_many({"client_id": "test_cli_tpl_001"})


def test_workflow_template_vars_from_client():
    """Llama a la lógica de resolución de variables sin enviar correo real."""
    asyncio.run(_seed())
    try:
        # Importar después de seed para asegurar contexto
        from services.workflow_notifications import send_workflow_notification

        # Spy: intercept _resolve_template y send_email para no enviar correo real
        from services import workflow_notifications as wn

        captured = {}

        async def _fake_send(**kwargs):
            captured["html"] = kwargs.get("html_content") or kwargs.get("html") or ""
            captured["subject"] = kwargs.get("subject", "")
            return {"success": True, "to": kwargs.get("to", [])}

        original_send_email = wn.send_email
        wn.send_email = _fake_send

        # Plantilla con todas las variables que vamos a validar
        async def _fake_resolve_template(action, segment):
            return {
                "subject": "Cot {nro_cotizacion} - {Nombre_Cliente}",
                "body_html": (
                    "Cliente: {Nombre_Cliente}<br>"
                    "Contacto: {Datos_Contacto}<br>"
                    "Email: {Email_Contacto}<br>"
                    "Tel: {Telefono_Contacto}<br>"
                    "Dir: {Direccion_Cliente}"
                ),
            }

        original_resolve = wn._resolve_template
        wn._resolve_template = _fake_resolve_template

        # Mock _resolve_recipients y push del email para evitar dependencias
        async def _fake_recipients(*a, **kw):
            return ["test@dest.com"]
        original_resolve_recipients = wn._resolve_recipients
        wn._resolve_recipients = _fake_recipients

        try:
            quote = {
                "quote_id": "qid_tpl_001",
                "quote_number": "COT-TPL-001",
                "client_id": "test_cli_tpl_001",
                # client_name/phone/email NO denormalizados → deben venir de clients
                "client_segment": "PYME",
                "sede": "PYME",
                "quote_type": "VPOS",
            }
            asyncio.run(send_workflow_notification(action="approve", quote=quote, current_user={}))
        finally:
            wn.send_email = original_send_email
            wn._resolve_template = original_resolve
            wn._resolve_recipients = original_resolve_recipients

        html = captured.get("html", "")
        subj = captured.get("subject", "")
        assert "Plantilla Test" in subj or "Plantilla Test" in html, f"Nombre_Cliente esperado, html={html!r} subj={subj!r}"
        assert "María González" in html, f"Datos_Contacto debe aparecer, html={html!r}"
        assert "maria@plantilla.test" in html, f"Email_Contacto debe aparecer, html={html!r}"
        assert "+58-414-9999999" in html, f"Telefono_Contacto debe aparecer, html={html!r}"
        assert "Calle Bolívar #42 Caracas" in html, f"Direccion_Cliente debe aparecer, html={html!r}"
    finally:
        asyncio.run(_cleanup())
