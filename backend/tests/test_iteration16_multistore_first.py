"""Tests Iteration 16: Multitienda como primer modal en Enviar a Implementación.

Verifica que el flujo del wizard sea:
project_type → Multitienda (ask/inherited) → Pinpad → Fiscal Printer → ...
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_handle_project_type_select_calls_multistore_first():
    """handleProjectTypeSelect debe invocar advanceToMultistorePhase, NO pinpad_question directo."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    # Localizar handleProjectTypeSelect
    idx = content.find("const handleProjectTypeSelect")
    assert idx > 0
    end = content.find("\n  };\n", idx)
    block = content[idx:end]
    # NO debe llamar a setMultistorePhase('pinpad_question') directamente
    assert "setMultistorePhase('pinpad_question')" not in block, \
        "handleProjectTypeSelect ya no debe ir directo a pinpad_question"
    # Debe llamar a advanceToMultistorePhase (al menos una vez por rama)
    count_adv = block.count("advanceToMultistorePhase()")
    assert count_adv >= 2, f"Esperadas ≥2 llamadas a advanceToMultistorePhase, hubo {count_adv}"


def test_advance_to_multistore_no_pyme_shortcut():
    """advanceToMultistorePhase ya no debe cortocircuitar a pinpad_question si es PYME."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.find("const advanceToMultistorePhase")
    end = content.find("\n  };\n", idx)
    block = content[idx:end]
    # No debe tener el shortcut PYME → pinpad_question
    assert "isPyme" not in block, "Ya no debe haber check de isPyme aquí (Multitienda primero para todos)"
    assert "ask" in block and "inherited" in block, "Debe transicionar a ask o inherited"


def test_confirm_multistore_advances_to_pinpad():
    """confirmMultistore (botón Continuar de Multitienda) debe ir a pinpad_question."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.find("const confirmMultistore")
    end = content.find("\n  };\n", idx)
    block = content[idx:end]
    assert "setMultistorePhase('pinpad_question')" in block


def test_pinpad_advances_to_fiscal_printer():
    """handlePymePinpadAnswer y handlePymePinpadConfirm deben avanzar a fiscal_printer."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    # Ambos handlers deben invocar goToFiscalPrinterPhase()
    idx1 = content.find("const handlePymePinpadAnswer")
    block1 = content[idx1:idx1 + 1500]
    assert "goToFiscalPrinterPhase()" in block1
    idx2 = content.find("const handlePymePinpadConfirm")
    block2 = content[idx2:idx2 + 500]
    assert "goToFiscalPrinterPhase()" in block2


def test_fiscal_printer_no_pyme_sends_directly():
    """handleFiscalPrinterContinue para no-PYME debe llamar handleSendToImplementation."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.find("const handleFiscalPrinterContinue")
    end = content.find("\n  };\n", idx)
    block = content[idx:end]
    assert "handleSendToImplementation(multistoreQuoteId" in block
    # No-PYME ya NO debe volver a llamar advanceToMultistorePhase
    assert "advanceToMultistorePhase()" not in block, \
        "No-PYME ya no debe regresar a Multitienda; ya pasó por ahí al inicio"
