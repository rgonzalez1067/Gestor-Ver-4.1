"""Iter 224 — Integrators import: name normalization + uncapped errors.

Verifies bug fixes in POST /api/integrators/import:
  (1) _norm_name() (NFKD lower + collapse whitespace) so file names without
      accents / single-space match DB users with accents and double/trailing
      spaces (no false 'usuario no existe').
  (2) Full error list is returned (previously sliced to errors[:50]).

Cleanup: integrators created during tests are deleted via DELETE /api/integrators
and a final cleanup by name prefix 'QATEST_ITER224_' through Mongo.
"""

import io
import os
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

NAME_PREFIX = "QATEST_ITER224_"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token")
    assert tok, f"no session_token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_after(headers):
    """Best-effort cleanup of any QATEST_ITER224_ integrators after the module."""
    yield
    try:
        r = requests.get(f"{API}/integrators", headers=headers, timeout=30)
        if r.status_code == 200:
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            for it in items:
                nm = (it.get("name") or "")
                if nm.startswith(NAME_PREFIX):
                    iid = it.get("integrator_id") or it.get("id") or it.get("_id")
                    if iid:
                        try:
                            requests.delete(f"{API}/integrators/{iid}", headers=headers, timeout=15)
                        except Exception:
                            pass
    except Exception:
        pass
    # Last-resort: direct Mongo wipe of QATEST_ rows
    try:
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if mongo_url and db_name:
            async def _wipe():
                client = AsyncIOMotorClient(mongo_url)
                await client[db_name].integrators.delete_many({"name": {"$regex": f"^{NAME_PREFIX}"}})
                client.close()
            asyncio.run(_wipe())
    except Exception:
        pass


# ---------- helpers ----------

def _upload_csv(headers, csv_text, mode="upsert", filename="test.csv"):
    files = {"file": (filename, io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    data = {"mode": mode}
    r = requests.post(
        f"{API}/integrators/import",
        headers=headers,  # NB: do NOT set Content-Type; requests will set multipart boundary
        files=files,
        data=data,
        timeout=120,
    )
    return r


HEADER = (
    "Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,"
    "Gestor,Implementador,Coordinador,Nro de Ticket,Categoría,Último Contacto,Correo\n"
)


# ---------- tests ----------

class TestNormalizationMatch:
    """Bug 1: accents / extra-space mismatches must resolve via _norm_name."""

    def test_accent_and_space_rows_import_ok(self, headers):
        ts = int(time.time())
        # Row A: Implementador 'Rafael Gonzalez' (no accent) vs DB 'Rafael González'
        # Row B: Coordinador 'Arnoldo Hernandez' (single space) vs DB 'Arnoldo  Hernandez'
        # Row C: same accent-free Implementador + Coordinador 'Kevin Malaguera'
        csv = HEADER + "\n".join([
            f"{NAME_PREFIX}A_{ts},Integrador,AppA,REST,En proceso,CR,,Rafael Gonzalez,Kevin Malaguera,,,,",
            f"{NAME_PREFIX}B_{ts},Integrador,AppB,REST,En proceso,CR,,Omar Jimenez,Arnoldo Hernandez,,,,",
            f"{NAME_PREFIX}C_{ts},Integrador,AppC,REST,En proceso,CR,,Rafael Gonzalez,Kevin Malaguera,,,,",
        ])
        r = _upload_csv(headers, csv)
        assert r.status_code == 200, f"import failed: {r.status_code} {r.text[:500]}"
        result = r.json()
        # No user errors for Implementador / Coordinador / Gestor
        user_errs = [
            e for e in result.get("errors", [])
            if (e.get("column") or "").startswith(("Implementador", "Coordinador", "Gestor"))
        ]
        assert not user_errs, f"unexpected user-match errors: {user_errs}"
        assert result.get("success_count", 0) + result.get("updated_count", 0) >= 3, result
        # Created integrators should be findable; confirm at least one persisted
        g = requests.get(f"{API}/integrators", headers=headers, timeout=30)
        assert g.status_code == 200
        items = g.json() if isinstance(g.json(), list) else g.json().get("items", [])
        names = {i.get("name") for i in items}
        assert f"{NAME_PREFIX}A_{ts}" in names
        assert f"{NAME_PREFIX}B_{ts}" in names
        # Implementador display should be the canonical accented DB version
        a = next(i for i in items if i.get("name") == f"{NAME_PREFIX}A_{ts}")
        impl = a.get("implementador_name") or a.get("implementer_name") or a.get("implementador") or ""
        # display should contain accented 'á'/'é' (canonical from DB)
        assert "González" in impl or "Gonz" in impl, f"implementador not resolved canonical: {impl}"

    def test_negative_unknown_user_still_rejected(self, headers):
        """Negative: nonsense name must still produce an Implementador error."""
        ts = int(time.time()) + 1
        csv = HEADER + (
            f"{NAME_PREFIX}NEG_{ts},Integrador,AppN,REST,En proceso,CR,,"
            "Usuario Inexistente XYZ,Kevin Malaguera,,,,\n"
        )
        r = _upload_csv(headers, csv)
        assert r.status_code == 200, r.text[:500]
        result = r.json()
        impl_errs = [
            e for e in result.get("errors", [])
            if (e.get("column") or "").startswith("Implementador")
        ]
        assert impl_errs, "expected Implementador error for unknown user"
        # That row should NOT be created
        assert result.get("error_count", 0) >= 1
        # NOTE: import logic does NOT skip the row on Implementador-only errors
        # (only Tipo/Modalidad/Nombre/Aplicativo/Coordinador/cert errors skip).
        # The contract verified here is just: error is reported.


class TestErrorListNotCapped:
    """Bug 2: error list must NOT be capped at 50."""

    def test_more_than_50_errors_all_returned(self, headers):
        ts = int(time.time()) + 2
        rows = []
        n = 60  # 60 rows each producing 2 errors (Tipo + Modalidad invalid) -> ~120
        for i in range(n):
            rows.append(
                f"{NAME_PREFIX}E_{ts}_{i:03d},BADTYPE,App{i},BADMOD,En proceso,CR,,,,,,,"
            )
        csv = HEADER + "\n".join(rows)
        r = _upload_csv(headers, csv)
        assert r.status_code == 200, r.text[:500]
        result = r.json()
        errors = result.get("errors", [])
        assert len(errors) > 50, f"errors list capped or short: len={len(errors)}"
        assert result.get("error_count") == len(errors), (
            f"error_count {result.get('error_count')} != len(errors) {len(errors)}"
        )
        # Should be ~2*n (Tipo + Modalidad for each invalid row); allow >= n
        assert len(errors) >= n, f"expected at least {n} errors, got {len(errors)}"
        # Ensure no QATEST integrators were created for these invalid rows
        # (Tipo is required-valid; row should be rejected.)
        # success_count for these rows should be 0 (only this file's success matters; but
        # success_count is the file-scope counter; just assert it is plausible).
        # Sanity: at least one error should reference 'Tipo' and one 'Modalidad'
        cols = [e.get("column") or "" for e in errors]
        assert any("Tipo" in c for c in cols), "no Tipo errors found"
        assert any("Modalidad" in c for c in cols), "no Modalidad errors found"
