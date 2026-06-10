"""Regresión: resolvedor de remitente por área (multi-sender)."""
import asyncio
from config import SENDER_EMAIL
from services import email_service as es


def _set_cache(doc):
    es._SENDERS_CACHE["doc"] = doc
    es._SENDERS_CACHE["fetched_at"] = 9e18  # nunca expira durante el test


def test_resolver_default_when_empty():
    _set_cache({})
    assert asyncio.get_event_loop().run_until_complete(es.resolve_sender_for_area("proyectos")) == SENDER_EMAIL
    es.invalidate_senders_cache()


def test_resolver_uses_assignment_when_active():
    _set_cache({
        "senders": [
            {"email": "implementacion@megasoft.com.ve", "active": True},
            {"email": "integradores@megasoft.com.ve", "active": True},
        ],
        "assignments": {"proyectos": "implementacion@megasoft.com.ve", "integradores": "integradores@megasoft.com.ve"},
    })
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(es.resolve_sender_for_area("proyectos")) == "implementacion@megasoft.com.ve"
    assert loop.run_until_complete(es.resolve_sender_for_area("integradores")) == "integradores@megasoft.com.ve"
    # Área sin asignación -> default
    assert loop.run_until_complete(es.resolve_sender_for_area("cotizaciones")) == SENDER_EMAIL
    es.invalidate_senders_cache()


def test_resolver_ignores_inactive_sender():
    _set_cache({
        "senders": [{"email": "implementacion@megasoft.com.ve", "active": False}],
        "assignments": {"proyectos": "implementacion@megasoft.com.ve"},
    })
    assert asyncio.get_event_loop().run_until_complete(es.resolve_sender_for_area("proyectos")) == SENDER_EMAIL
    es.invalidate_senders_cache()


def test_quote_resolver_by_segment():
    _set_cache({
        "senders": [
            {"email": "pyme@megasoft.com.ve", "active": True},
            {"email": "corp@megasoft.com.ve", "active": True},
        ],
        "assignments": {"cotizaciones_pyme": "pyme@megasoft.com.ve", "cotizaciones_corp": "corp@megasoft.com.ve"},
    })
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(es.resolve_sender_for_quote({"client_segment": "CORP"})) == "corp@megasoft.com.ve"
    assert loop.run_until_complete(es.resolve_sender_for_quote({"client_segment": "PYME"})) == "pyme@megasoft.com.ve"
    # Sin segmento -> tratado como PYME
    assert loop.run_until_complete(es.resolve_sender_for_quote({})) == "pyme@megasoft.com.ve"
    es.invalidate_senders_cache()
