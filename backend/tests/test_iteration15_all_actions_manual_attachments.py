"""Tests Iteration 15: Anexos manuales propagados a TODAS las acciones del modal.

Verifica que cada endpoint workflow acepte el header `x-manual-attachment-ids`
y resuelva los anexos a través de `_resolve_manual_attachments`.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _has_header(content: str, route_signature: str) -> bool:
    """Devuelve True si en el bloque de definición de la ruta se incluye el header."""
    idx = content.find(route_signature)
    if idx < 0:
        return False
    # Inspect the signature line (until the first ':\n' that closes def)
    end = content.find("):\n", idx)
    if end < 0:
        end = idx + 800
    sig = content[idx:end + 3]
    return 'alias="x-manual-attachment-ids"' in sig


def test_all_workflow_endpoints_accept_manual_attachment_header():
    """Los 7 endpoints del wizard deben aceptar el header de anexos manuales."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()

    endpoints = [
        '/quotes/{quote_id}/approve"',
        '/quotes/{quote_id}/configure"',
        '/quotes/{quote_id}/repair-complete"',
        '/quotes/{quote_id}/send-to-implementation"',
        '/quotes/{quote_id}/invoice"',
        '/quotes/{quote_id}/collect"',
        '/quotes/{quote_id}/deliver"',
        '/quotes/{quote_id}/repair-deliver"',
    ]
    failed = []
    for ep in endpoints:
        if not _has_header(content, ep):
            failed.append(ep)
    assert not failed, f"Endpoints sin header x-manual-attachment-ids: {failed}"


def test_all_endpoints_resolve_manual_attachments():
    """Cada endpoint debe llamar a _resolve_manual_attachments(manual_attachment_ids)."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Contar al menos 7 invocaciones (una por endpoint)
    count = content.count("_resolve_manual_attachments(manual_attachment_ids)")
    assert count >= 7, f"Esperadas ≥7 invocaciones a _resolve_manual_attachments, hubo {count}"


def test_approve_merges_manual_with_payment_files():
    """approve: los _manual_attachments deben mezclarse con los payment_files."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "_engine_extra_attachments.extend(_manual_attachments)" in content


def test_collect_merges_manual_with_payment_proofs():
    """collect: manual attachments deben mezclarse con los comprobantes de pago (_engine_extra)."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "_engine_extra.extend(_manual_attachments)" in content


def test_fast_track_approve_merges_manual_attachments():
    """Fast Track approve legacy también debe propagar los anexos."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "merged_ft_attachments" in content
    assert "merged_approval" in content


def test_repair_deliver_uses_custom_message_and_manual_attachments():
    """repair-deliver ya no envía custom_message=None — usa el del header."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Encontrar el llamado para repair-deliver
    idx = content.find('"repair-deliver", quote, current_user')
    assert idx > 0
    block = content[idx:idx + 600]
    assert "custom_message=None" not in block, "repair-deliver no debe forzar custom_message=None"
    assert "custom_message=custom_message" in block
    assert "_resolve_manual_attachments(manual_attachment_ids)" in block
