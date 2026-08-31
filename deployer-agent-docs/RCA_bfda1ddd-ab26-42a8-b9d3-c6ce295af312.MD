# RCA — 500 sin `detail` en POST /api/admin/full-backup/upload-manifest (restauración modular de `inbox_messages`)

**App:** admin-control-center-21 · **Run activo:** bfda1ddd-ab26-42a8-b9d3-c6ce295af312 · **Template:** fastapi_react_mongo_shadcn (farm, Cloudflare frontend) · **Tier:** tier_0 (Starter)

## Veredicto: NO es corrupción de ZIP ni BadZipFile/JSONDecodeError. Es OOMKilled (memoria).

El pod backend está siendo **OOMKilled (exit 137)** de forma repetida bajo el límite de **512Mi** de tier_0. El proceso worker muere por SIGKILL del kernel **a mitad de la request** de ensamblado/lectura del backup, por eso el cliente recibe un **500 genérico sin `detail` y sin traceback**. Un `BadZipFile` o `JSONDecodeError` habría dejado un traceback Python en los logs — **no existe ninguno**, lo cual confirma que la excepción no viene del código sino del OOM killer del sistema operativo.

## Evidencia de producción (no reproducible en preview)

1. **kill_findings (get_pod_events):**
   - `pod ...-dtqsn OOMKilled (exit 137) at 2026-08-31T14:10:10Z, restarts=1`
   - `pod ...-pf8x9 OOMKilled (exit 137) at 2026-08-31T16:43:20Z, restarts=2`
   - Readiness/Liveness probe failed: `GET http://.../health: context deadline exceeded` (54–55 veces) — el pod bajo presión de memoria deja de responder al health check justo cuando procesa el backup.
2. **Tier (get_tier):** tier_0 — `memory: 200Mi` request, **`memory_limit: 512Mi`**, cpu_limit 250m, **replicas: 2**, hpa/vpa deshabilitados.
3. **Logs (fetch_app_logs):** NINGÚN traceback Python, NINGÚN `BadZipFile`, NINGÚN `JSONDecodeError`, NINGÚN log de error de GridFS. Sólo tráfico normal + los OOM/probe-timeouts. El 500 no deja rastro en el log de la app = muerte por SIGKILL, no excepción capturada/no-capturada.
4. **Mongo (mongo_query list_collections en `admin-control-center-21-test_database`):**
   - Buckets GridFS de respaldos **presentes y escribibles**: `backups.files` y `backups.chunks` (=> `_BACKUP_BUCKET="backups"` OK).
   - `inbox_messages` **existe**.
   - `fb_uploads` / `fb_upload_chunks` **no aparecen** en el listado actual (probablemente transitorias: se crean durante la subida y se limpian tras el ensamblado). No es el bloqueo; la escritura de chunks funciona (el flujo llega hasta upload-manifest).

## Causa raíz mecánica

`_assemble_upload_to_gridfs_sync()` junta todos los chunks de `fb_upload_chunks` y `_read_backup_manifest_sync()` hace `zipfile.ZipFile(stream)` sobre el stream GridFS. En la ruta actual el ensamblado/lectura **materializa el backup completo en memoria del proceso**. El backup modular de `inbox_messages` (en preview ~5 segmentos / 1997 docs) supera, sumado al RSS base de FastAPI + APScheduler + demás, el techo de **512Mi** de tier_0 → el kernel mata el worker → 500 sin `detail`.

Por qué sólo falla en producción: el entorno de preview no tiene ese límite de 512Mi; ahí el mismo código termina el ensamblado y la lectura sin tocar techo.

## Respuestas puntuales a lo solicitado

1. **Traceback exacto:** no existe — es OOMKilled (exit 137 / SIGKILL), no una excepción Python. Descartados `BadZipFile`, `JSONDecodeError` y errores de GridFS como causa del 500.
2. **Límite de body del ingress:** NO es la causa. El template sirve nginx con `client_max_body_size 100M` y la subida es **por chunks** (cada `upload-chunk` es un POST pequeño e independiente), así que no hay truncamiento por body-limit. El ZIP no llega corrupto; se ensambla completo y muere al cargarlo en memoria.
3. **Múltiples réplicas:** SÍ, `replicas: 2`. El estado (chunks) vive en Mongo compartido, por lo que el enrutamiento init/chunk/manifest entre réplicas es funcionalmente correcto y NO causa el fallo. El problema es que el ensamblado se resuelve en la memoria de **un** pod con techo de 512Mi.
4. **Buckets/colecciones:** `backups.files` + `backups.chunks` existen y son escribibles; `inbox_messages` existe. Sin problema de permisos/existencia.

## Remediación recomendada (por prioridad)

1. **Fix inmediato (infra):** subir de **tier_0 (512Mi) → tier_1+** desde el Panel de Deployment → Resources. Da headroom para el ensamblado/lectura del backup. Es la palanca que elimina el OOM sin tocar código.
2. **Fix de código (robustez de memoria, recomendado en paralelo):** evitar materializar el ZIP completo en RAM:
   - Ensamblar los chunks escribiéndolos **directamente al GridFS bucket en streaming** (write chunk-by-chunk), no concatenando en un buffer/bytes en memoria.
   - Leer el manifiesto con un stream **seekable** sobre el archivo GridFS: `zipfile` sólo necesita el *central directory* (final del archivo) + la entrada del manifiesto, no el ZIP entero; usar un wrapper con `seek()` sobre el `GridOut` evita cargar cientos de MB.
   - Aplicar la misma estrategia de streaming en `_restore_full_backup_sync`.
3. **Hardening ya planificado (bueno, pero NO resuelve el OOM):** envolver `zipfile.ZipFile(...)` y la lectura del manifiesto en `try/except (zipfile.BadZipFile, json.JSONDecodeError)` → `HTTPException(400, detail=...)`. Útil para dar mensaje claro ante ZIP realmente corrupto, pero el 500 actual es OOM y seguirá ocurriendo hasta subir memoria y/o hacer streaming. **Importante:** un OOMKill NO es capturable con try/except — el proceso muere por SIGKILL antes de que Python pueda manejar nada.

## Nota sobre verificación

Diagnóstico basado en evidencia de producción (pod events + tier + logs + estado de Mongo), **no reproducido en sandbox**: un OOM ligado al límite de 512Mi del tier no es reproducible en el pod eph (tiene un piso de recursos superior y no lleva los secretos/DB reales). La evidencia de OOMKilled x2 en ambas réplicas es concluyente.
