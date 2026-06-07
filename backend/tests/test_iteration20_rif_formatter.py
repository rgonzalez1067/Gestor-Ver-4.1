# ruff: noqa
"""Tests Iteration 20 — RIF padding a 9 dígitos.

Regla: el RIF de Venezuela tiene 10 chars (letra + 9 dígitos). Si en BD
viene corto (por truncado de ceros) hay que rellenar a izquierda con ceros.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.rif_formatter import format_rif  # noqa: E402


def test_rif_corto_con_letra_se_rellena():
    assert format_rif("V12345") == "V-000012345"


def test_rif_corto_con_guion_se_rellena():
    assert format_rif("V-12345") == "V-000012345"


def test_rif_completo_no_se_modifica_en_padding():
    assert format_rif("V123456789") == "V-123456789"


def test_rif_con_verificador_preserva_estructura():
    assert format_rif("V-1234567-8") == "V-001234567-8"


def test_rif_solo_numerico_se_rellena():
    assert format_rif("12345") == "000012345"


def test_rif_vacio_devuelve_vacio():
    assert format_rif("") == ""
    assert format_rif(None) == ""
    assert format_rif("   ") == ""


def test_rif_placeholder_se_conserva():
    assert format_rif("N/A") == "N/A"
    assert format_rif("n/a") == "n/a"
    assert format_rif("-") == "-"
    assert format_rif("Sin RIF") == "Sin RIF"


def test_rif_letras_minusculas_se_normalizan():
    assert format_rif("j12345") == "J-000012345"


def test_rif_con_mas_de_9_digitos_no_se_trunca():
    """El padding sólo rellena. Si ya hay 10 dígitos, los conserva."""
    assert format_rif("V1234567890") == "V-1234567890"


def test_rif_jp_caracter_valido():
    """Letras válidas: J, V, E, G, P, C."""
    for letter in "JVEGPC":
        assert format_rif(f"{letter}12345") == f"{letter}-000012345"


def test_rif_con_espacios_en_medio_se_limpia():
    # Espacios y caracteres no numéricos en el cuerpo se ignoran
    assert format_rif("V-12 345-6") == "V-000012345-6"


def test_caso_usuario_v00012345():
    """Caso reportado: cliente con RIF V00012345 debe imprimirse completo."""
    # El usuario menciona "V00012345" lo cual es 8 dígitos → padding a 9
    result = format_rif("V00012345")
    assert result == "V-000012345"
    # Verificar que NO se truncó a "V-12345"
    assert "12345" in result
    assert result.count("0") >= 4
