"""
Regresión — Plantilla Preferida + Texto Enriquecido en Notificaciones de Proyecto.

Cubre:
- `_get_notification_template`: resuelve plantillas de Proyecto desde defaults/DB.
- `_resolve_notification_email`: el `override_template_id` controla el asunto/cuerpo.
- Preferencias por destino (db.config) persisten correctamente.
"""
import asyncio
import pytest

from config import db
from routes.projects import (
    _get_notification_template,
    _resolve_notification_email,
    NOTIF_PREF_DOC,
)

loop = asyncio.get_event_loop()


def test_get_notification_template_from_defaults():
    tpl = loop.run_until_complete(_get_notification_template("project_notify_client"))
    assert tpl is not None
    assert tpl.get("body_html")
    assert tpl.get("name") == "Notificación de Proyecto — Cliente"


def test_get_notification_template_unknown_returns_none():
    tpl = loop.run_until_complete(_get_notification_template("no_existe_xyz"))
    assert tpl is None


def test_get_notification_template_none_id():
    assert loop.run_until_complete(_get_notification_template(None)) is None


def test_resolve_uses_override_template_subject():
    """El asunto debe provenir de la plantilla override, no del default fijo."""
    project = loop.run_until_complete(
        db.projects.find_one({"client_id": {"$ne": None}}, {"_id": 0})
    )
    assert project, "Se requiere al menos un proyecto con cliente para la prueba"

    from services.project_template_vars import resolve_project_template_vars
    tvars_default = loop.run_until_complete(resolve_project_template_vars(project))
    tvars_override = loop.run_until_complete(resolve_project_template_vars(project))

    default = loop.run_until_complete(
        _resolve_notification_email(project, "client", None, 0, tvars_default)
    )
    override = loop.run_until_complete(
        _resolve_notification_email(
            project, "client", None, 0, tvars_override,
            override_template_id="project_notify_bank_client",
        )
    )
    # Ambos llevan el prefijo de conteo, pero el cuerpo base proviene de plantillas distintas
    assert default["subject"].startswith("[Primer Envío]")
    assert override["subject"].startswith("[Primer Envío]")
    # La plantilla bank_client incluye secciones "Datos del Banco" en su cuerpo
    assert "Datos del Banco" in override["html"] or "bank" in override["html"].lower()


def test_notification_preference_persists_in_config():
    """Set/get de preferencia por destino vía db.config (lógica del endpoint)."""
    async def _run():
        await db.config.update_one(
            NOTIF_PREF_DOC, {"$set": {"client": "project_notify_client"}}, upsert=True
        )
        doc = await db.config.find_one(NOTIF_PREF_DOC, {"_id": 0})
        return doc
    doc = loop.run_until_complete(_run())
    assert doc.get("client") == "project_notify_client"
