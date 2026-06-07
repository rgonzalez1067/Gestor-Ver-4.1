# ruff: noqa
"""Iteration 21 — Departamento Operaciones ve sus PROPIAS cotizaciones
+ las MPOS PYME (UNIÓN, no reemplazo).

Bug previo (Feb 2026): el filtro REEMPLAZABA el scope departamental por
solo MPOS PYME, dejando a los usuarios de Operaciones sin ver sus propios
casos de Equipos / Reparaciones. Fix: unión vía $or a nivel MongoDB.
"""
import os
import sys
import asyncio
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import db  # noqa: E402


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _build_ops_query_like_endpoint(user_id, dept_user_ids, user_sede):
    """Reproduce la construcción del query del endpoint /api/quotes para
    un usuario Analista del Departamento Operaciones.

    Feb 2026 v3 — Operaciones es un dept de soporte transversal con
    lectura universal sobre repair + equipment + MPOS PYME, sin filtro de
    creator (cubre cotizaciones legacy con created_by_user_id huérfanos).
    """
    query = {"archived": {"$ne": True}}
    cargo = "analista"
    is_ops_dept = True

    if "director" not in cargo:
        query["client_segment"] = user_sede
        query["created_by_user_id"] = {"$in": dept_user_ids}

    if is_ops_dept and "director" not in cargo:
        scope_keys = ("created_by_user_id", "client_segment")
        ops_dept_scope = {k: query.pop(k) for k in scope_keys if k in query}
        ops_repair_scope = {"quote_category": "repair"}
        ops_equipment_scope = {"quote_category": "equipment"}
        ops_mpos_scope = {
            "client_segment": "PYME",
            "$or": [
                {"quote_category": "fast_track"},
                {"quote_type": "FAST_TRACK"},
            ],
        }
        or_branches = []
        if ops_dept_scope:
            if "$or" in query:
                ops_dept_scope["$or"] = query.pop("$or")
            or_branches.append(ops_dept_scope)
        or_branches.extend([ops_repair_scope, ops_equipment_scope, ops_mpos_scope])
        query["$or"] = or_branches
    return query


def test_ops_ve_sus_propias_cotizaciones_de_equipos_y_reparaciones():
    """Cotización de Equipos creada POR un usuario Operaciones debe ser visible."""
    suffix = uuid.uuid4().hex[:8]
    ops_user_id = f"usr_ops_{suffix}"
    ops_sede = "PYME"

    async def runner():
        # Seed: 1 cotización de Equipos creada por el usuario Operaciones (no MPOS)
        own_quote_id = f"q_ops_own_{suffix}"
        await db.quotes.insert_one({
            "quote_id": own_quote_id,
            "quote_number": f"COT-TEST-{suffix}-EQ",
            "client_segment": ops_sede,
            "quote_category": "equipment",
            "quote_type": "EQUIPMENT",
            "created_by_user_id": ops_user_id,
            "quote_status": "Borrador",
            "archived": False,
        })

        # Seed: 1 MPOS PYME creada por OTRO usuario (Ventas Pyme)
        mpos_quote_id = f"q_mpos_{suffix}"
        await db.quotes.insert_one({
            "quote_id": mpos_quote_id,
            "quote_number": f"COT-TEST-{suffix}-MPOS",
            "client_segment": "PYME",
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "created_by_user_id": "usr_vendedor_pyme_xyz",
            "quote_status": "Aprobada",
            "archived": False,
        })

        # Seed: 1 MPOS CORP creada por otro (NO debe verse — segmento incorrecto)
        corp_quote_id = f"q_corp_{suffix}"
        await db.quotes.insert_one({
            "quote_id": corp_quote_id,
            "quote_number": f"COT-TEST-{suffix}-CORP",
            "client_segment": "CORP",
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "created_by_user_id": "usr_vendedor_corp_xyz",
            "quote_status": "Aprobada",
            "archived": False,
        })

        try:
            query = _build_ops_query_like_endpoint(
                user_id=ops_user_id,
                dept_user_ids=[ops_user_id],  # depto sólo tiene a este user en el test
                user_sede=ops_sede,
            )
            visible_ids = set()
            async for q in db.quotes.find(query, {"_id": 0, "quote_id": 1}):
                visible_ids.add(q["quote_id"])

            # Su propia cotización de Equipos DEBE ser visible (este era el bug)
            assert own_quote_id in visible_ids, (
                "REGRESIÓN: el usuario Operaciones NO ve su propia cotización de Equipos. "
                f"visible_ids={visible_ids}"
            )
            # La MPOS PYME ajena DEBE ser visible (extra read access)
            assert mpos_quote_id in visible_ids, (
                f"El usuario Ops debería ver MPOS PYME ajenas. visible_ids={visible_ids}"
            )
            # La MPOS CORP NO debe verse (segmento incorrecto)
            assert corp_quote_id not in visible_ids, (
                f"Las MPOS CORP NO deben ser visibles. visible_ids={visible_ids}"
            )
        finally:
            await db.quotes.delete_many({"quote_id": {"$in": [own_quote_id, mpos_quote_id, corp_quote_id]}})

    _run(runner())


def test_ops_ve_cotizaciones_de_su_compañero_de_operaciones():
    """Otra cotización de Reparaciones creada por un COMPAÑERO del mismo
    departamento (Operaciones) también debe ser visible para el usuario."""
    suffix = uuid.uuid4().hex[:8]
    ops_user_a = f"usr_ops_a_{suffix}"
    ops_user_b = f"usr_ops_b_{suffix}"

    async def runner():
        # Reparación creada por compañero del mismo depto
        repair_id = f"q_rep_b_{suffix}"
        await db.quotes.insert_one({
            "quote_id": repair_id,
            "quote_number": f"COT-TEST-{suffix}-REP",
            "client_segment": "PYME",
            "quote_category": "repair",
            "quote_type": "REPAIR",
            "created_by_user_id": ops_user_b,
            "quote_status": "Aprobada",
            "archived": False,
        })

        try:
            query = _build_ops_query_like_endpoint(
                user_id=ops_user_a,
                dept_user_ids=[ops_user_a, ops_user_b],
                user_sede="PYME",
            )
            visible_ids = set()
            async for q in db.quotes.find(query, {"_id": 0, "quote_id": 1}):
                visible_ids.add(q["quote_id"])

            assert repair_id in visible_ids, (
                "REGRESIÓN: usuario Ops no ve la cotización Reparación creada por su "
                f"compañero de departamento. visible_ids={visible_ids}"
            )
        finally:
            await db.quotes.delete_many({"quote_id": repair_id})

    _run(runner())


def test_ops_no_ve_equipos_de_otros_departamentos():
    """Las cotizaciones de Equipos creadas por usuarios fuera de Operaciones
    (ej. Ventas Pyme) NO deben aparecer."""
    suffix = uuid.uuid4().hex[:8]
    ops_user_id = f"usr_ops_{suffix}"

    async def runner():
        # Equipos creada por Ventas Pyme (no Operaciones)
        foreign_id = f"q_foreign_{suffix}"
        await db.quotes.insert_one({
            "quote_id": foreign_id,
            "quote_number": f"COT-TEST-{suffix}-EQ-VP",
            "client_segment": "PYME",
            "quote_category": "equipment",
            "quote_type": "EQUIPMENT",
            "created_by_user_id": "usr_ventas_pyme_xyz",
            "quote_status": "Borrador",
            "archived": False,
        })

        try:
            query = _build_ops_query_like_endpoint(
                user_id=ops_user_id,
                dept_user_ids=[ops_user_id],
                user_sede="PYME",
            )
            visible_ids = set()
            async for q in db.quotes.find(query, {"_id": 0, "quote_id": 1}):
                visible_ids.add(q["quote_id"])

            assert foreign_id not in visible_ids, (
                "Las cotizaciones de Equipos creadas por otros departamentos NO deben "
                f"ser visibles para Operaciones. visible_ids={visible_ids}"
            )
        finally:
            await db.quotes.delete_many({"quote_id": foreign_id})

    _run(runner())


def test_ops_ve_cotizaciones_legacy_con_creator_huerfano():
    """Feb 2026 v3 — Las cotizaciones legacy importadas vía CSV tienen
    `created_by_user_id` sintético (orphan: no existe en `users`). Operaciones
    debe verlas igualmente porque coordina ese trabajo, independientemente
    de quién las creó. Aplica a categorías: repair, equipment, fast_track."""
    suffix = uuid.uuid4().hex[:8]
    ops_user_id = f"usr_ops_{suffix}"
    fantasma = f"user_orphan_{suffix}"

    async def runner():
        # 3 cotizaciones legacy con creator huérfano
        repair_id = f"q_legacy_rep_{suffix}"
        equip_id = f"q_legacy_eq_{suffix}"
        ft_id = f"q_legacy_ft_{suffix}"
        await db.quotes.insert_one({
            "quote_id": repair_id, "quote_number": f"COT-LEGACY-{suffix}-REP",
            "client_segment": "PYME", "quote_category": "repair", "quote_type": "REPAIR",
            "created_by_user_id": fantasma, "quote_status": "Aprobada",
            "archived": False, "imported_by": "admin@megasoft.com.ve",
        })
        await db.quotes.insert_one({
            "quote_id": equip_id, "quote_number": f"COT-LEGACY-{suffix}-EQ",
            "client_segment": "PYME", "quote_category": "equipment", "quote_type": "EQUIPMENT",
            "created_by_user_id": fantasma, "quote_status": "Aprobada",
            "archived": False, "imported_by": "admin@megasoft.com.ve",
        })
        await db.quotes.insert_one({
            "quote_id": ft_id, "quote_number": f"COT-LEGACY-{suffix}-FT",
            "client_segment": "PYME", "quote_category": "fast_track", "quote_type": "FAST_TRACK",
            "created_by_user_id": fantasma, "quote_status": "Aprobada",
            "archived": False, "imported_by": "admin@megasoft.com.ve",
        })

        try:
            query = _build_ops_query_like_endpoint(
                user_id=ops_user_id, dept_user_ids=[ops_user_id], user_sede="PYME",
            )
            visible_ids = set()
            async for q in db.quotes.find(query, {"_id": 0, "quote_id": 1}):
                visible_ids.add(q["quote_id"])
            assert repair_id in visible_ids, f"REGRESIÓN: Reparación legacy con orphan creator no visible. visible_ids={visible_ids}"
            assert equip_id in visible_ids, f"REGRESIÓN: Equipo legacy con orphan creator no visible. visible_ids={visible_ids}"
            assert ft_id in visible_ids, f"REGRESIÓN: MPOS legacy con orphan creator no visible. visible_ids={visible_ids}"
        finally:
            await db.quotes.delete_many({"quote_id": {"$in": [repair_id, equip_id, ft_id]}})

    _run(runner())


def test_ops_no_ve_implementation_de_otros_departamentos():
    """Las cotizaciones `implementation` (VPOS/PG no MPOS) creadas por otros
    departamentos NO deben aparecer para Operaciones (no es su ámbito)."""
    suffix = uuid.uuid4().hex[:8]
    ops_user_id = f"usr_ops_{suffix}"

    async def runner():
        foreign_impl = f"q_foreign_impl_{suffix}"
        await db.quotes.insert_one({
            "quote_id": foreign_impl, "quote_number": f"COT-VP-{suffix}",
            "client_segment": "PYME", "quote_category": "implementation",
            "quote_type": "VPOS", "created_by_user_id": "usr_ventas_pyme_xyz",
            "quote_status": "Aprobada", "archived": False,
        })
        try:
            query = _build_ops_query_like_endpoint(
                user_id=ops_user_id, dept_user_ids=[ops_user_id], user_sede="PYME",
            )
            visible_ids = set()
            async for q in db.quotes.find(query, {"_id": 0, "quote_id": 1}):
                visible_ids.add(q["quote_id"])
            assert foreign_impl not in visible_ids, (
                "VPOS de Ventas Pyme NO debe ser visible para Ops. visible_ids contiene impl_id"
            )
        finally:
            await db.quotes.delete_one({"quote_id": foreign_impl})

    _run(runner())
