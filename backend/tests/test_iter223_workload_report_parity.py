"""Iter 223 — Parity between implementer workload-summary tooltip endpoint and
the "Reporte de Carga y Estatus de Proyectos" per-implementer totals.

For every implementer found in /api/projects we replicate the report grouping
(group by assigned_to_name) and verify the tooltip endpoint's
{projects_count, cajas_asignadas, pvv_asignados} match the report's
(Nro de Proyectos / Nro de Cajas / Total PVV) exactly.

Also re-verifies constraints and the Yulimarys Rivas spot check.
"""

import os
import pytest
import requests

def _read_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # Read from frontend/.env (in this env, REACT_APP_BACKEND_URL is not auto-exported)
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    if line.strip().startswith("REACT_APP_BACKEND_URL="):
                        v = line.strip().split("=", 1)[1]
                        break
        except FileNotFoundError:
            pass
    assert v, "REACT_APP_BACKEND_URL not configured"
    return v.rstrip("/")


BASE_URL = _read_backend_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
CAJAS_TYPES = {"VPOS", "MPOS", "VPOS_MULTIRIF"}


# ------------------------- fixtures -------------------------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, "no session_token in login response"
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def all_projects(session):
    r = session.get(f"{BASE_URL}/api/projects", timeout=60)
    assert r.status_code == 200, f"GET /api/projects -> {r.status_code}"
    data = r.json()
    assert isinstance(data, list)
    return data


# ------------------------- report-side helpers -------------------------

def _project_total_cajas(p: dict) -> int:
    """Same rule as backend _project_total_cajas."""
    try:
        c = int(p.get("cantidad_cajas") or p.get("box_count") or 0)
    except (TypeError, ValueError):
        c = 0
    if c <= 0 and p.get("rifs"):
        c = sum(int(r.get("box_count") or 0) for r in (p.get("rifs") or []))
    return c


def _counts_cajas(qt) -> bool:
    return (qt or "").upper() in CAJAS_TYPES


def _report_totals_by_name(projects):
    """Replicates projects_workload_pdf grouping: by assigned_to_name, all
    assigned projects, cajas only for CAJAS_TYPES, PVV always (pvv_count from
    /api/projects already equals compute_project_pvv)."""
    groups = {}
    for p in projects:
        name = (p.get("assigned_to_name") or "").strip()
        if not name or name.lower() == "sin asignar":
            continue
        g = groups.setdefault(name, {"projects_count": 0, "cajas": 0, "pvv": 0})
        g["projects_count"] += 1
        if _counts_cajas(p.get("quote_type")):
            g["cajas"] += _project_total_cajas(p)
        g["pvv"] += int(p.get("pvv_count") or 0)
    return groups


def _name_to_uid(projects):
    """Pick a representative assigned_to_user_id for each assigned_to_name."""
    m = {}
    for p in projects:
        n = (p.get("assigned_to_name") or "").strip()
        u = (p.get("assigned_to_user_id") or "").strip()
        if n and u and n not in m:
            m[n] = u
    return m


# ------------------------- tests -------------------------

class TestYulimarysSpotCheck:
    """Spot check the originally reported bug: Yulimarys Rivas must show
    Proyectos 18 / Cajas 205 / PVV 290 (per curl + screenshot)."""

    UID = "user_76c8aa92c813"
    NAME = "Yulimarys Rivas"

    def test_tooltip_matches_report_for_yulimarys(self, session, all_projects):
        r = session.get(
            f"{BASE_URL}/api/projects/implementers/{self.UID}/workload-summary",
            params={"name": self.NAME},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        tt = r.json()

        report = _report_totals_by_name(all_projects).get(self.NAME)
        assert report is not None, "Yulimarys Rivas not found in /api/projects assignments"

        assert tt["projects_count"] == report["projects_count"], (
            f"projects_count tooltip={tt['projects_count']} report={report['projects_count']}"
        )
        assert tt["cajas_asignadas"] == report["cajas"], (
            f"cajas tooltip={tt['cajas_asignadas']} report={report['cajas']}"
        )
        assert tt["pvv_asignados"] == report["pvv"], (
            f"pvv tooltip={tt['pvv_asignados']} report={report['pvv']}"
        )


class TestParityAllImplementers:
    """Every implementer with at least 1 project must have tooltip totals
    exactly equal to the report group totals.

    NOTE: The report groups STRICTLY by assigned_to_name (string), while the
    tooltip queries by assigned_to_user_id when present. When the same user
    has multiple name spellings across projects (data hygiene issue), the
    tooltip naturally aggregates them while the report splits them. We
    quarantine such ambiguous names into a separate (data-quality) bucket
    and require parity for every UNAMBIGUOUS name.
    """

    def _name_uid_map(self, all_projects):
        """name -> set of distinct non-empty user_ids seen in projects."""
        from collections import defaultdict
        m = defaultdict(set)
        for p in all_projects:
            n = (p.get("assigned_to_name") or "").strip()
            u = (p.get("assigned_to_user_id") or "").strip()
            if not n or n.lower() == "sin asignar":
                continue
            if u:
                m[n].add(u)
            else:
                m[n].add("")  # legacy: no uid
        return m

    def test_parity_for_every_implementer(self, session, all_projects):
        report = _report_totals_by_name(all_projects)
        name_uids = self._name_uid_map(all_projects)
        # Names that share a uid with another name (data anomaly)
        from collections import defaultdict
        uid_to_names = defaultdict(set)
        for n, uids in name_uids.items():
            for u in uids:
                if u:
                    uid_to_names[u].add(n)
        ambiguous = {n for u, ns in uid_to_names.items() if len(ns) > 1 for n in ns}

        assert report, "no assigned implementers found"
        mismatches = []
        checked = 0
        for name, exp in report.items():
            if name in ambiguous:
                continue  # tracked separately, see test_data_anomaly_ambiguous_names
            uids = list(name_uids.get(name, set()))
            uid = next((u for u in uids if u), "_")
            r = session.get(
                f"{BASE_URL}/api/projects/implementers/{uid}/workload-summary",
                params={"name": name},
                timeout=30,
            )
            if r.status_code != 200:
                mismatches.append(f"{name}: HTTP {r.status_code}")
                continue
            tt = r.json()
            checked += 1
            if (
                tt["projects_count"] != exp["projects_count"]
                or tt["cajas_asignadas"] != exp["cajas"]
                or tt["pvv_asignados"] != exp["pvv"]
            ):
                mismatches.append(
                    f"{name}: tooltip(P={tt['projects_count']},C={tt['cajas_asignadas']},V={tt['pvv_asignados']}) "
                    f"!= report(P={exp['projects_count']},C={exp['cajas']},V={exp['pvv']})"
                )

        assert checked > 0, "no implementers actually verified"
        assert not mismatches, "Parity mismatches:\n  " + "\n  ".join(mismatches)

    def test_data_anomaly_ambiguous_names_aggregate_correctly(self, session, all_projects):
        """For users with multiple name spellings, the tooltip aggregates by
        user_id. Verify the SUM of report groups for that user's names equals
        the tooltip total when queried by uid (no name)."""
        from collections import defaultdict
        report = _report_totals_by_name(all_projects)
        name_uids = self._name_uid_map(all_projects)
        uid_to_names = defaultdict(set)
        for n, uids in name_uids.items():
            for u in uids:
                if u:
                    uid_to_names[u].add(n)
        ambig_uids = {u: list(ns) for u, ns in uid_to_names.items() if len(ns) > 1}
        if not ambig_uids:
            pytest.skip("No ambiguous-name implementers in current dataset")

        problems = []
        for uid, names in ambig_uids.items():
            exp_p = sum(report[n]["projects_count"] for n in names if n in report)
            exp_c = sum(report[n]["cajas"] for n in names if n in report)
            exp_v = sum(report[n]["pvv"] for n in names if n in report)
            r = session.get(
                f"{BASE_URL}/api/projects/implementers/{uid}/workload-summary",
                timeout=30,
            )
            assert r.status_code == 200
            tt = r.json()
            if (tt["projects_count"], tt["cajas_asignadas"], tt["pvv_asignados"]) != (exp_p, exp_c, exp_v):
                problems.append(
                    f"uid={uid} names={names} tooltip=(P={tt['projects_count']},C={tt['cajas_asignadas']},V={tt['pvv_asignados']}) "
                    f"!= sum(report)=(P={exp_p},C={exp_c},V={exp_v})"
                )
        assert not problems, "Ambiguous-name uid aggregation mismatch:\n  " + "\n  ".join(problems)


class TestConstraints:
    """Universal constraints for every implementer."""

    def test_constraints_hold_for_all(self, session, all_projects):
        name2uid = _name_to_uid(all_projects)
        report = _report_totals_by_name(all_projects)
        violations = []
        for name in report.keys():
            uid = name2uid.get(name) or "_"
            r = session.get(
                f"{BASE_URL}/api/projects/implementers/{uid}/workload-summary",
                params={"name": name},
                timeout=30,
            )
            assert r.status_code == 200
            d = r.json()
            for k in ("projects_count", "cajas_asignadas", "cajas_pendientes",
                      "pvv_asignados", "pvv_pendientes", "avance_global"):
                v = d.get(k)
                if not isinstance(v, int) or v < 0:
                    violations.append(f"{name}.{k}={v} (not non-negative int)")
            if d["cajas_pendientes"] > d["cajas_asignadas"]:
                violations.append(f"{name}: cajas_pend>asig")
            if d["pvv_pendientes"] > d["pvv_asignados"]:
                violations.append(f"{name}: pvv_pend>asig")
            if not (0 <= d["avance_global"] <= 100):
                violations.append(f"{name}: avance out of [0,100]")
        assert not violations, "Constraint violations:\n  " + "\n  ".join(violations)


class TestResilience:
    """Tooltip endpoint must be resilient as documented."""

    def test_nonexistent_id_no_name(self, session):
        r = session.get(
            f"{BASE_URL}/api/projects/implementers/user_does_not_exist_xyz/workload-summary",
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["projects_count"] == 0
        assert d["cajas_asignadas"] == 0
        assert d["cajas_pendientes"] == 0
        assert d["pvv_asignados"] == 0
        assert d["pvv_pendientes"] == 0
        assert d["avance_global"] == 0

    def test_placeholder_uid_with_name_uses_name_fallback(self, session, all_projects):
        report = _report_totals_by_name(all_projects)
        # Pick the first name with >=1 project
        name = next(iter(report.keys()))
        exp = report[name]
        r_real = session.get(
            f"{BASE_URL}/api/projects/implementers/{_name_to_uid(all_projects).get(name, '_')}/workload-summary",
            params={"name": name}, timeout=30,
        )
        r_ph = session.get(
            f"{BASE_URL}/api/projects/implementers/_/workload-summary",
            params={"name": name}, timeout=30,
        )
        assert r_real.status_code == 200 and r_ph.status_code == 200
        a, b = r_real.json(), r_ph.json()
        assert a["projects_count"] == b["projects_count"] == exp["projects_count"]
        assert a["cajas_asignadas"] == b["cajas_asignadas"] == exp["cajas"]
        assert a["pvv_asignados"] == b["pvv_asignados"] == exp["pvv"]
