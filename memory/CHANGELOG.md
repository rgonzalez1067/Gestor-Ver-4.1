# CHANGELOG — MegaNexus

## 2026-06 — Fix def. Full Backup: ZIP corrupto en PRODUCCIÓN ("Unexpected end of archive")
- **Síntoma (prod):** el `.zip` del Respaldo Total descargaba 220 MB pero WinRAR lo veía dañado/vacío ("unpacked size 0 bytes"), solo con la carpeta `collections`. En PREVIEW el mismo ZIP era 100% válido (`testzip()` OK, 76 entradas).
- **RCA:** `GET /admin/full-backup/export` respondía con `StreamingResponse` (chunked, SIN `Content-Length`, `X-Accel-Buffering: no`). El CDN/ingress de producción truncaba el último tramo del stream —el *central directory* del ZIP— dejando el archivo sin índice. Preview no tiene CDN al frente → no se reproducía.
- **Fix:** el export ahora **escribe el ZIP a un archivo temporal en disco del pod** (documento por documento con `bson_dumps` + `batch_size(50)` → memoria O(1)) y lo sirve con **`FileResponse` (Content-Length real)** + `BackgroundTask` de limpieza. Con el tamaño declarado el proxy no puede truncar el final. Mismo patrón que `export-attachments-streamed`. Se mantiene el flujo de ticket (`?ticket=`) para la descarga nativa. Verificado en preview: header-auth y ticket devuelven `Content-Length` y ZIP válido.


## 2026-06 — Fix def. export: descarga NATIVA en streaming a disco (evita freeze del navegador)

- **RCA (deployer):** con el ensamblado en navegador (JSZip), el pod quedaba sano (0 OOM, todas las páginas 200) pero **el navegador se congelaba al ~50%** acumulando todo el ZIP en RAM (base grande: bitacora 66k, email_logs 10k, inbox_messages 7.5k con HTML pesado). Plan A (más RAM del pod) NO aplicaba: el cuello era el navegador.
- **Solución:** volver al export en streaming del servidor (memoria O(1), ~56MB, con `X-Accel-Buffering: no`) pero disparándolo como **descarga NATIVA del navegador** (`<a>` a la URL) → el navegador escribe directo a disco sin acumular en RAM. Funciona en todos los navegadores.
- **Auth para el link nativo:** nuevo `POST /admin/full-backup/export-ticket` → ticket de un solo uso, 5 min (colección `download_tickets`). `GET /admin/full-backup/export?ticket=...` acepta auth por header O por ticket.
- **Validación (preview):** ticket→descarga sin header (como el navegador) = 200, ZIP 43MB válido (`testzip`=OK, 76 entradas); ticket reusado = 401; sin ticket/auth = 401. Frontend recompila OK.
- **⚠️ Requiere REDEPLOY.** Tras redeploy, el export descarga como archivo nativo (aparece en el gestor de descargas del navegador, sin barra interna) y no congela la pestaña.



- **Contexto:** aun con el export en streaming O(1), el pod (tier_0, 512Mi) seguía cayendo por OOM durante exports grandes (baseline alto + ~56-82MB de working set). El usuario eligió la opción sin costo extra.
- **Solución:** el ZIP ya NO se arma en el pod. Nuevo flujo:
  - Backend: `GET /admin/full-backup/collection?name=&after=&max_docs=` → devuelve una PÁGINA de la colección (Extended-JSON separado por comas) paginada por `_id` (índice nativo), cortando a ~8MB por página. Headers `X-Has-More`, `X-Next-After`, `X-Count`. Memoria del pod por request: acotada (~pocos MB).
  - Frontend (`BackupCenter.jsx` → `exportFullDb`): descarga cada colección por páginas y **ensambla el ZIP en el navegador con JSZip**, luego descarga. Barra de progreso 0-80% (descarga) / 80-100% (compresión).
- **Validación:** simulación byte-idéntica al navegador → 81 requests, ZIP 43MB válido (`testzip`=OK), round-trip exacto (ObjectId/tipos/conteos), **pico de memoria del pod solo 25MB** (vs 56-82MB antes; y topado a 8MB por página). testing_agent iter325: frontend 100% (paginación, headers custom legibles en navegador, toast de éxito, sin errores; restore dialog intacto).
- **Restore:** sin cambios (el ZIP ensamblado en navegador tiene el mismo formato `_manifest.json` + `collections/*.json`).
- **⚠️ Requiere REDEPLOY.** Tras el redeploy el export no depende de la memoria del pod → no más OOM/520/truncado.



- **Síntomas:** primero 520 (pod OOMKilled antes del 1er byte); tras un primer intento de streaming, el .zip llegaba **truncado** ("Unexpected end of archive") porque el pod seguía muriendo por OOM a mitad del stream (sin escribir el central directory).
- **RCA (deployer):** OOMKilled real (exit 137) en el pod de 512Mi DURANTE el export.
- **Causa raíz (dos factores):**
  1. Mi primer streaming drenaba el buffer **por conteo de documentos** (cada 200) → con docs grandes (inbox_messages ~240KB c/u) el pico de memoria escalaba ~2x el tamaño del ZIP. Medición corregida (árbol de procesos correcto): delta **95MB** para un ZIP de 41MB.
  2. nginx (mismo contenedor, `proxy_buffering` ON) bufferizaba TODA la respuesta `chunked` (sin `Content-Length`) en RAM del contenedor → a escala de producción llenaba los 512Mi.
- **Fix (`data_migration.py` → `full_backup_export`):**
  - Drenado del buffer **por bytes** (~128KB) en vez de por conteo de docs → memoria O(1) real.
  - Cursor Mongo con `batch_size(50)` → acota la precarga de motor.
  - Header **`X-Accel-Buffering: no`** → nginx hace passthrough en streaming, no bufferiza la respuesta completa.
- **Validación a escala (preview):** colección temporal de **266MB** → ZIP de **217MB**; delta de memoria del backend **82MB** (ya NO escala con el tamaño del ZIP; antes 95MB para 41MB). ZIP válido (`testzip`=OK). Memoria confirmada O(1).
- **⚠️ Requiere REDEPLOY.** Si aún fallara por memoria (baseline de prod alto), plan B: subir tier_0→tier_1 (más RAM) o ensamblar el ZIP por colección en el navegador.



- **Mejora:** cada colección del checklist de restauración muestra ahora **conteo actual del ambiente → conteo del respaldo** (ej. `642 → 640`), resaltando en índigo cuando hay cambio y tachando el valor actual. Las colecciones que no existen en el ambiente se marcan con badge "nueva". Usa `dbInfo.collections` (de `/admin/full-backup/info`) ya cargado + el manifiesto leído con JSZip. Solo frontend (`BackupCenter.jsx`), no destructivo.

## 2026-06 — Respaldo Total: Restauración SELECTIVA (elegir colecciones)

- **Mejora:** restaurar solo las colecciones elegidas del respaldo en lugar de toda la base.
- **Backend `full-backup/restore`:** nuevo Form `collections` (JSON array). Si viene, restaura SOLO esas (drop+insert) y NUNCA borra colecciones fuera de la selección; el borrado de "extras" (modo replace) solo aplica a restauración completa. Respuesta incluye `selective` y `skipped_collections`.
- **Frontend `BackupCenter.jsx`:** al elegir el .zip, se lee el `_manifest.json` en el cliente con **JSZip** y se muestra un checklist de colecciones (todas marcadas por defecto) con "Seleccionar/Deseleccionar todo". En modo selectivo se oculta "Réplica exacta" y el botón cambia a "Restaurar N colección(es)". Mismo gating por texto "RESTAURAR".
- **QA:** backend selectivo probado end-to-end (solo restaura lo seleccionado, no toca `users` ni otras); testing_agent iter324: frontend 100%.



- **Requerimiento:** función para respaldar y restaurar TODAS las colecciones de MongoDB (no solo las ~17 del Centro de Respaldos). Incluye bitácora, correos, notificaciones, plantillas, config, contadores, sesiones, mensajería, etc. Objetivo: clonar un ambiente completo (Producción → Preview) con réplica exacta.
- **Backend `routes/data_migration.py` (nuevos endpoints, admin-only):**
  - `GET /api/admin/full-backup/info` → conteo de colecciones y documentos.
  - `GET /api/admin/full-backup/export` → ZIP con un JSON (MongoDB Extended JSON) por colección + `_manifest.json`. Preserva `_id` (ObjectId), fechas y tipos BSON. Streaming por documento a temp file (bajo consumo de memoria).
  - `POST /api/admin/full-backup/upload-init` + `upload-chunk` → carga por chunks (4MB) para evitar límites del proxy (backup ~43MB).
  - `POST /api/admin/full-backup/restore` (mode `replace`|`merge`) → drop+insert por colección = réplica exacta. `replace` además elimina colecciones que no estén en el respaldo. Preserva la sesión del admin que ejecuta para no perder acceso.
- **Frontend `pages/BackupCenter.jsx`:** tarjeta `full-backup-card` con Exportar/Restaurar, progreso de subida, checkbox "Réplica exacta" y diálogo de confirmación con gating por texto "RESTAURAR".
- **QA:** backend probado end-to-end por el agente (round-trip real con chunks; `_id`/datetime/anidados preservados; restauración completa medida ~4.2s, bajo el límite de 60s del ingress). testing_agent iter323: frontend 100% + backend no destructivo 100%.
- **Formato:** MongoDB Extended JSON (`bson.json_util`) para round-trip sin pérdida.
- **⚠️ La restauración es DESTRUCTIVA (reemplaza toda la BD del ambiente). Requiere REDEPLOY para que el botón Exportar aparezca en producción.**



## 2026-06 — Enrutamiento Taller (x-client-recipients) extendido a "Reparado" y "Pago Validado"

- **Requerimiento:** replicar en las acciones **Reparado** (`repair-complete`) y **Pago Validado reparación** (custom action, ej. `pago_validado_rep`) el mismo ajuste ya aplicado a **Aprobación**: resolución de destinatario por perfilamiento "Taller" (reglas A/B/C) y reenvío vía header HTTP `x-client-recipients`.
- **Backend `routes/quote_actions.py` (`repair_complete`):** nuevo header `client_recipients` (alias `x-client-recipients`); se parsea `client_to_override` y se pasa `client_recipients_override` al `_engine_or_legacy` y al flujo legacy (To = contacto Taller elegido; extras → CC). Se eliminó una reasignación duplicada de `cc_emails` que borraba los extras.
- **Backend `routes/quote_action_customization.py` (`dispatch_custom_action`):** nuevo header `client_recipients`; se pasa `client_recipients_override` a `try_dispatch` (el motor solo lo aplica a filas `client_field`). Alcance confirmado por el usuario: aplica a TODAS las cotizaciones de categoría `repair`.
- **Frontend `pages/Quotes.jsx`:** `handleRepairComplete` ahora async y resuelve Taller A/B/C; nuevos `_openRepairCompleteModal` (inyecta `x-client-recipients` en `emailHeaders`), `resolveTallerForCustom`, `executeCustomAction(...clientRecipients)`, branch `custom:` en `confirmEmailAndProceed` (solo repair), y branches `repair-complete-taller` / `custom-taller` en `handleContactSelectContinue`. Escenario B reutiliza el modal "Seleccionar Destinatarios".
- **QA (testing_agent iter322): 5/5 backend + smoke frontend OK, sin regresiones.** Regresión: `/app/backend/tests/test_iter322_repair_taller_recipient.py`. Sin header → Contacto Principal (no regresión).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Ajuste: Fecha de Vencimiento de Cotizaciones = Emisión + 20 días hábiles

- Cambiado el cálculo de vencimiento de **15 → 20 días hábiles** (excluyendo fines de semana y feriados) en las 4 ocurrencias: `hydrate_pdf_request`, sitios PG y CORP (`quotes.py`) y fallback del generador (`pdf_generator.py`).
- Verificado por curl+pypdf: emisión 08/07/2026 → vencimiento 05/08/2026 (20 hábiles).



- **Bug:** en cotizaciones MPOS (Imple + POS / fast_track), la acción "Configuración" fallaba con 400 "Solo se puede configurar desde estado 'Aprobada'" cuando el proyecto estaba en otro estado (ej. 'Enviada a Imple').
- **Fix (`quote_actions.py` `configure_quote`):** se eliminó la restricción `current_status != 'Aprobada'`. La acción se conserva restringida a `quote_category='fast_track'` (flujo particular MPOS), pero ya no se bloquea por estado.
- **QA (testing_agent iter253): 7/7.** configure devuelve 200 desde 'Enviada a Imple', 'Configurada', 'Facturada', 'Pagada' y 'Aprobada'; categoría non-fast_track sigue devolviendo 400; 404 para inexistente.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Feature CERTIFICADA: Catálogo de Bancos — Fase Previa a Producción + Comentarios por producto

- **Requerimiento:** por cada medio de pago del banco: (1) Switch "Fase Previa a Producción" que lo oculta en Cotizaciones y lo colorea en el resumen (VPOS→naranja claro, Payment Gateway→rojo claro); (2) comentarios producto↔banco con botón 💬, marca visual (•) y tooltip en hover.
- **Backend `models.py`:** `BankProduct` ahora tiene `pre_production: bool` y `comment: str` (persisten vía PUT/GET /api/banks).
- **Frontend `Banks.jsx`:** Switch + botón 💬 por producto en el modal de edición; micro-modal de comentario (`product-comment-modal`); chips de resumen con color pre_production + marca • + Tooltip. `BankDetail.jsx`: paneles VPOS/MPOS y PG/Link con color naranja/rojo + marca • + Tooltip. `Quotes.jsx`: filtros excluyen `p.pre_production` (VPOS y PG) → producto oculto al cotizar.
- **QA (testing_agent iter252): backend 5/5, frontend 100%, sin issues.** Prueba de fuego OK (producto pre_production bloqueado en cotización); colores, marca • y tooltip verificados en /banks y /banks/{id}; convivencia color+comentario OK; regresión OK.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Bug Fix CERTIFICADO: Instrucciones para el Implementador en la Ficha Técnica

- **Bug:** las instrucciones/observaciones del operador no aparecían en la Ficha Técnica (PDF), tanto desde Cotizaciones ("Datos Técnicos e Instrucciones") como desde Proyectos Directos.
- **Causa raíz:** el endpoint de descarga `download_ficha_tecnica` regeneraba el PDF desde el proyecto pero NO mapeaba `implementation_instructions` en el `quote_like` → salía vacío.
- **Fix 1 (`projects.py`):** `download_ficha_tecnica` ahora incluye `implementation_instructions` tomándolo del proyecto (fuente de verdad).
- **Fix 2 (`implementation_pdf.py`):** render robusto — detecta HTML (editor rich-text) vs texto plano (textarea); texto plano escapa `& < >` y convierte saltos de línea a `<br/>`; HTML convierte tags a subset ReportLab y escapa `&` sueltos. Heurística estricta de HTML (solo tags conocidos) para que pseudo-tags como `<server>`/`<admin>` en texto plano se muestren literales y no se eliminen.
- **QA (testing_agent iter250→251): 6/6.** Verificado íntegro en ambas rutas, con caracteres especiales, saltos de línea, viñetas y pseudo-tags; regresión sin instrucciones OK.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Fix: conservar "Datos Técnicos e Instrucciones" y "Asignación del Implementador" en flujo digital

- **Bug:** el bypass anterior (iter248) eliminó de más — quitó también los modales "Datos Técnicos e Instrucciones" (consolidated_data) y "Asignación del Implementador" (confirm_implementer), que SÍ capturan info importante.
- **Fix (`Quotes.jsx`):** nueva `openDigitalImplementationWizard` que abre el wizard directamente en `consolidated_data` (precargando grupo económico/fantasía del cliente), sin pasar por Multitienda/Pinpad/Fiscal; luego sigue el flujo normal consolidated_data → confirm_implementer → creación del proyecto. Se revirtió el bypass total (handleSendToImplementation vuelve a 3 args). El botón "Atrás" de consolidated_data cierra el wizard cuando el producto es digital.
- **QA (testing_agent iter249): 5/5 frontend.** GATEWAY y LINK_PAGO abren en consolidated_data (sin fases prohibidas) → confirm_implementer → proyecto; datos (server/grupo/fantasía/instrucciones) persistidos; regresión VPOS con wizard completo OK; "Atrás" digital cierra sin mostrar Pinpad.

## 2026-07 — Feature CERTIFICADA: Bypass de modales de hardware para productos digitales (Enviar a Implementación)

- **Requerimiento:** al "Enviar a Implementación" cotizaciones tipo Payment Gateway (GATEWAY) y Link de Pago/Tokenizador (LINK_PAGO, sus 3 variantes), omitir los modales de Multitienda, Pinpads e Impresora Fiscal y saltar directo de "Personalizar Comunicación" a la creación del proyecto.
- **Frontend `Quotes.jsx`:** en `confirmEmailAndProceed`, para `send-to-implementation` con quote_type GATEWAY/LINK_PAGO se llama `handleSendToImplementation(..., bypassHardware=true)` (arma body mínimo: `project_type_impl='payment_gateway'`, sin multistore/pinpad/fiscal) en vez de `openMultistoreDialog`. Presenciales (VPOS/MPOS/FAST_TRACK) mantienen el wizard.
- **QA (testing_agent iter248): 3/3 frontend 100%.** GATEWAY y LINK_PAGO → NO aparece `multistore-dialog` tras confirmar `email-modal`; VPOS → wizard aparece (regresión OK). Proyecto creado correctamente y cotización archivada.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Fix: el proyecto ya NO hereda el PDF de la Cotización como anexo

- **Bug:** al enviar a Implementación, el proyecto heredaba los anexos de la cotización (incluido el PDF "Cotización") y aparecían en el visor de Anexos.
- **Fix (`quote_transitions.py` `_create_project_from_quote`):** `attachments = []` (se eliminó la herencia). Ahora `project.attachments` contiene SOLO los anexos subidos en el modal "Personalizar Comunicación" ($push, source='quote_send_to_implementation'), en paridad con Proyectos Directos.
- **QA (testing_agent iter247): 5/5.** Escenario sin anexos → `attachments==[]`; con anexos → solo los del modal (ninguno category='Cotización'/inherited_from='cotización'); descarga y aislamiento OK.
- **Nota:** aplica a proyectos NUEVOS. Proyectos ya creados antes del fix conservan el PDF heredado (fix forward; se puede hacer limpieza puntual si se requiere).



- **Requerimiento:** los archivos adjuntos cargados en el modal "Personalizar Comunicación" al "Enviar a Implementación" desde una cotización deben persistir en el proyecto con la MISMA estructura que Proyectos Directos y ser visibles/descargables desde el botón "Anexos" del Panel de Proyectos.
- **Hallazgo:** el uploader del modal (`EmailManualAttachments`) y la propagación del header `x-manual-attachment-ids` YA existían (los anexos solo iban al correo). Cambio nuevo = **solo backend**.
- **Backend `quote_actions.py`:** nuevo helper `_persist_manual_attachments_to_project(project_id, manual_attachments, user)` que guarda cada anexo vía `save_pdf_dual` en `attachments/{project_id}/...` y hace `$push` a `project.attachments` (mismo esquema: attachment_id, category, filename, url, storage_key, uploaded_by/_name, uploaded_at, file_size, content_type, source='quote_send_to_implementation'). Invocado en `send_quote_to_implementation` tras crear el proyecto (búsqueda por quote_id). Los anexos siguen adjuntándose al correo.
- **Descarga:** reutiliza `GET /api/projects/{project_id}/attachments/{attachment_id}/download` (FS→Object Storage). Botón "Anexos" en ProjectDetail ya aparece cuando `project.attachments` tiene items.
- **QA (testing_agent iter246): 8/8 backend + smoke UI 100%.** Paridad de origen (Directo vs Cotización) y aislamiento sin fuga de datos verificados; 404 correcto para IDs inexistentes.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Feature CERTIFICADA: Fecha de Vencimiento en portada de Cotizaciones (Implementaciones)

- **Requerimiento:** agregar "FECHA DE VENCIMIENTO" en la portada de las cotizaciones comerciales, justo debajo de "FECHA DE EMISIÓN", mismo estilo, formato DD/MM/AAAA. Cálculo: emisión + 15 días hábiles (exclusivo, el día de emisión no cuenta), excluyendo fines de semana y feriados de `db.holidays`. Eliminar el punto "Vigencia de la Propuesta" de Términos y Condiciones.
- **Backend `business_calendar.py`:** nuevo `add_business_days_after(start, n, specific, recurring)` (exclusivo), `compute_expiry_date(start, n=15)` async, snapshot síncrono `get_cached_holiday_sets()`. Validado: Lun 01/09/2025→Lun 22/09/2025; con feriado 22/09→Mar 23/09.
- **Backend `pdf_generator.py`:** `TemplateQuotePDFRequest.fecha_vencimiento`; `_build_modern_cover` renderiza la fila de vencimiento bajo emisión (mismo `meta_label`/`meta_value_med`, padding simétrico); eliminados los 2 bloques "Vigencia de la Propuesta" (generate_vpos PyME y generate_pg) con renumeración de T&C (1.Tiempo Implementación, 2.Forma de Pago, 3.Soporte, 4.Confidencialidad).
- **Backend `quotes.py`:** cálculo en `hydrate_pdf_request` + sitios PG (~356) y CORP (~1178). **`server.py`:** precarga del snapshot de feriados en startup (evita edge-case cold-start).
- **QA (testing_agent iter244): 17/17 backend + frontend smoke 100%.** Verificado VPOS PyME, Gateway y CORP: portada con vencimiento DD/MM/AAAA y sin "Vigencia de la Propuesta"; regresión OK.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Feature CERTIFICADA: Anexos pre-envío en Proyectos Directos

- **Requerimiento:** permitir cargar archivos anexos ANTES de enviar el Proyecto Directo a Implementación. Decisión del usuario: los anexos se adjuntan al correo de Implementación (junto a la Ficha Técnica) Y quedan guardados en el proyecto.
- **Backend (`direct_projects.py`):** nuevo `POST /api/direct-projects/upload-attachment` (staging multipart, valida tipo PDF/imagen/Word/Excel/CSV y tamaño máx 10MB, guarda vía `save_pdf_dual` en `attachments/direct_staging/{id}`). El modelo `DirectProjectCreate` acepta `attachments: list[dict]`; al crear el proyecto se persisten en `project.attachments` y se pasan como `extra_attachments` (base64) a `engine_try_dispatch('send_to_implementation', ...)`. Respuesta incluye `attachments_count`. Hardening: solo se aceptan `storage_key` con prefijo `attachments/direct_staging/`.
- **Frontend (`DirectProjectCreation.jsx`):** tarjeta 'Anexos del Proyecto' con dropzone + selección múltiple, selector de categoría por archivo, validación cliente (tipo/tamaño), y subida secuencial en `doSubmit` antes del POST. Banner de éxito muestra el conteo de anexos.
- **QA (testing_agent iter243): 8/8 backend + frontend E2E 100%.** Verificado upload válido/inválido (.txt→400, >10MB→400), creación con y sin anexos, y persistencia en `project.attachments` (proyecto PRY-2026-07-008-PRI con 2 anexos).
- **Enhancement (mismo día):** visor de anexos en la ficha del Proyecto. Nuevo `GET /api/projects/{project_id}/attachments/{attachment_id}/download` (sirve desde FS→Object Storage). Botón "Anexos" con badge de conteo en el header de `ProjectDetail.jsx` que abre modal (`project-anexos-modal`) con lista descargable/visualizable. Verificado por curl (200/404) y screenshot (modal + 2 filas descargables).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-07 — Feature CERTIFICADA: Módulo de Comunicación Directa + Heartbeat/Reaper

- **Backend (100% — testing_agent iter242, 12/12 pytest):** `POST /api/admin/direct-message` (niveles low/medium/high, recipient_ids o all_online, valida body vacío/sin destinatarios 400, 403 no-admin), CRUD `/api/admin/message-templates`, `GET /api/admin/connected-users`. Heartbeat ping 30s / reaper TTL 90s (`notification_service.ConnectionManager`).
- **Frontend:** `/settings/connected-users` renderiza OK (la "pantalla blanca" del handoff NO era reproducible — ruta correcta es `/settings/connected-users`, no `/connected-users`). Composer (`DirectMessageComposer.jsx`), alerta global bloqueante (`DirectMessageAlert.jsx`).
- **Bug HIGH corregido y verificado:** doble entrega de mensajes (modal/toast duplicado) por StrictMode abriendo 2 WebSockets. Fix quirúrgico: (a) dedupe por `msg.id` con `seenIdsRef` en `DirectMessageAlert.jsx`; (b) guard `if (wsRef.current && wsRef.current.readyState <= 1) return;` en `useNotifications.js`. Verificado por screenshot: OVERLAY COUNT=1, un solo click cierra.
- **Backlog (no bloqueante):** presencia WS multi-worker (colección `ws_presence` Mongo TTL 90s) para que `all_online` y la grilla reflejen todas las réplicas; hydration warnings en Dashboard.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Bug Fix (reincidente): imágenes pegadas DESDE Gmail llegaban rotas al cliente

- **Causa raíz real:** la plantilla "Notificación de Proyecto — Cliente" tenía 5 `<img src="https://mail.google.com/mail/u/1?ui=2&ik=...&view=fimg...">` — imágenes **pegadas directamente desde un correo de Gmail**, cuyas URLs requieren la sesión de Google del autor. Ni el backend ni el destinatario pueden descargarlas → siempre llegan rotas (el autor las ve en la Vista Previa solo porque está logueado en Gmail). El fix anterior (CID) no podía recuperarlas.
- **Backend (`email_service.py`):** nuevo `_is_mail_hosted_img()` (detecta `mail.google.com`, `googleusercontent` fimg/attid, `outlook.live/office`, `/owa/`). `_embed_body_images()` ahora: decodifica `&amp;`; para imágenes de buzón NO intenta descargar (evita latencia) y las **elimina** del HTML (`re.sub` del `<img>`) para que el destinatario no vea el ícono roto; el resto (nuestro storage, data URIs, rutas relativas→absolutas, remotas públicas) se siguen incrustando como adjuntos inline Content-ID (`cid:`).
- **Frontend:** `RichTextEditor` advierte (`toast.warning`) al pegar imágenes copiadas desde un correo; `EmailTemplatesEditor` sube los bitmaps pegados a `/projects/upload-image` (URL absoluta de nuestro storage, que sí se incrusta).
- **⚠️ Importante:** las 5 imágenes de Gmail de esa plantilla son IRRECUPERABLES (no tenemos sus bytes). El fix evita el ícono roto, pero para que esas imágenes APAREZCAN el usuario debe **re-agregarlas** pegando una captura de pantalla o subiéndolas con el botón de imagen (eso las guarda en nuestro storage y se renderizan).
- **QA (testing_agent iteration_206, 4/4 pytest PASS):** plantilla real (5 imgs Gmail) → 0 `mail.google.com` tras embed; `send_email` e2e sin excepción y `email_logs.html_preview` limpio; imágenes nuestras/data/relativas → `cid:bodyimg_` inline; sin descargas innecesarias (<1s).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Bug Fix: imágenes en correos llegaban rotas (rutas relativas / pegadas desde Gmail)

- **Causa raíz:** el cuerpo HTML guardaba rutas de imagen RELATIVAS (`/api/projects/images/...`) o data URIs que Gmail/Outlook no resuelven; además, imágenes pegadas desde Gmail quedaban como URLs autenticadas (`mail.google.com/...`) visibles solo para el autor. El `_embed_body_images` previo solo procesaba `data:`/`http(s)://` y descartaba (`else: continue`) las relativas.
- **Backend (`services/email_service.py · _embed_body_images`):** ahora (1) normaliza rutas relativas a absolutas con `REACT_APP_BACKEND_URL`; (2) embebe como adjuntos inline **Content-ID (`cid:`)** todas las imágenes incrustables: relativas/absolutas de nuestro storage (lookup por `image_id`, cualquier dominio), `data:` base64, y remotas públicas (descarga). Nuevo helper `_download_img_bytes` (devuelve None si requiere auth/no es imagen → no rompe el envío). **Fix de colisión de substring:** el reemplazo `src→cid` ahora es acotado por comillas (`"src"`/`'src'`) para no corromper URLs absolutas que contienen la ruta relativa.
- **Frontend (`RichTextEditor.jsx`):** el editor ya sube screenshots/archivos a nuestro storage (URL absoluta). Nuevo aviso (`toast.warning`) al pegar HTML con imágenes remotas de correo (`mail.google.com`/`googleusercontent.com`/`outlook`) indicando que llegarían rotas y que use captura o el botón de imagen.
- **El serving `GET /projects/images/{filename}` es PÚBLICO** (sin token) — requisito de lectura pública cumplido.
- **QA (testing_agent iteration_205, 4/4 backend PASS + revisión de código):** relativa+absoluta(dominio distinto)+data URI → 3 `cid:bodyimg_` con 3 adjuntos inline; `email_logs.html_preview` contiene `cid:bodyimg_` sin rutas relativas/data: residuales; `mail.google.com` no lanza excepción; `upload-image` devuelve URL absoluta servida públicamente. El backend embebe en TODO flujo de envío (incluye plantillas del editor de Settings que usa Textarea).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Panel de Proyectos: filtro de Cliente ampliado (RIF + Nombre Jurídico + Grupo Económico) con typeahead

- **Backend (`routes/projects.py · get_projects`):** cada proyecto se enriquece con `client_legal_name` (Razón Social) y `client_economic_group` (Grupo Económico, campo real `grupo_economico`) mediante una única consulta batch a `clients` por `client_id` ($in, indexado — sin table scans ni LIKE en servidor).
- **Frontend (`Projects.jsx`):** el campo "Cliente" ahora es un **typeahead** (≥3 caracteres) insensible a mayúsculas y acentos (`norm()` con NFD). Sugiere Grupos Económicos (con ícono) y Clientes con formato **`[RIF] — [Nombre Jurídico] (Grupo: [Grupo])`**, derivados de los proyectos cargados (siempre con resultados reales). Seleccionar un cliente filtra por su RIF; seleccionar un grupo muestra todos los proyectos de ese Grupo. Si no hay coincidencias → "No se encontraron coincidencias para la búsqueda". El filtro de búsqueda se combina (AND) con Estado/Tipo/Patrocinador/Integrador/Fechas. Cierre del dropdown al hacer clic fuera + botón limpiar.
- **QA:** backend curl → 103 proyectos con `client_legal_name`/`client_economic_group`; 29 con grupo (ej. "Grupo Brasero" ×6). Self-test UI: grupo "Brasero" → sugerencia + grilla filtrada; "FORUM" → cliente sugerido; "Grupo Inexistente" → leyenda de sin coincidencias.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Multi-RIF: carga de Excel flexible (toggle "¿Los RIF a cargar serán validados?")

- **UI (`MultiRifDistributionPanel.jsx`, compartido por Cotización VPOS Multi-RIF y Proyectos Directos Multi-RIF):** nuevo selector obligatorio **"¿Los RIF a cargar serán validados?"** SÍ/NO (default **SÍ**, consistente con el histórico), junto a los botones Plantilla/Cargar Excel (`multirif-validate-toggle`, `multirif-validate-yes`, `multirif-validate-no`). Por ser el mismo componente, aplica idéntico en ambas pantallas (impacto cruzado).
- **Flujo SÍ (estándar):** sin cambios — el backend valida que cada RIF exista en clientes; si un RIF no existe, rechaza toda la carga con el error tradicional y autocompleta el Nombre Jurídico desde la BD.
- **Flujo NO (flexible/prospección):** el backend NO consulta la tabla de clientes; acepta cualquier RIF con máscara básica alfanumérica, agrupa por RIF y deja `client_id`/`client_name` vacíos. En la grilla, esas filas muestran el RIF + badge **"No Validado"** (sin forzar la búsqueda de cliente).
- **Backend (`routes/quotes.py · multirif_parse_excel`):** nuevo `validate_rif` (Form, default True); cuando es False omite el índice de clientes (rápido), bifurca la validación y devuelve `validated: bool` por RIF. (`routes/direct_projects.py`): `DirectMultiRifNode.validated`; la validación de creación ya no exige `client_id` cuando `validated=False` (sí exige RIF no vacío) y persiste `validated` en el nodo.
- **Frontend gates:** `validateMultiRif` y la validación de `DirectProjectCreation.jsx` relajan el requisito de cliente cuando `r.validated === false`. La creación de cotización/proyecto tolera `client_id` vacío.
- **QA:** backend curl → NO: 500 RIFs no registrados procesados en ~0.35s, 0 errores, `client_name` vacío, `validated=false`; SÍ: RIF inventado → `ok=false` con "no corresponde a ningún Cliente registrado". Self-test UI (/direct-projects, NO): 500 filas con badge "No Validado", toast "Distribución cargada: 500 RIF(s)", sin excepciones.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Modal Multitienda ("Enviar a Implementación"): carga por Excel SIMPLIFICADA (reutiliza el formato estándar de "Detalle de Sucursales")

- **Simplificación pedida por el usuario:** la carga por Excel del modal multitienda ahora reutiliza el MISMO componente/lógica y formato que el botón "Detalle de Sucursales" del cotizador (`BranchDetailPanel.jsx`): parseo 100% en el navegador con la librería `xlsx`, plantilla estándar **`plantilla_tiendas.xlsx`** (hoja "Tiendas", columnas **Nombre Tienda | Cantidad de Cajas**), reemplazo total de la distribución, validaciones mínimas (ignora filas con cantidad inválida con una advertencia). Así el archivo es estándar y reutilizable en cualquier paso.
- **`QuoteModals.jsx`:** `MultistoreExcelBar` reescrito (sin backend) → botones `Plantilla` (genera `plantilla_tiendas.xlsx` con `XLSX.writeFile`) y `Excel` (lee con `FileReader`/`XLSX.read`, mapea a `{name, box_count}`, `onLoaded` reemplaza `multistoreStores`). El contador de balance y el bloqueo estricto siguen aplicando igual sobre la distribución cargada.
- **Backend:** eliminados los endpoints `GET/POST /quotes/multistore/excel-template|parse-excel` que se habían agregado (ya no se usan; la carga es cliente).
- **QA (self-test E2E preview):** carga del `plantilla_tiendas.xlsx` estándar (Centro 50 + Este 2 = 52) → toast "2 tienda(s) importada(s) (reemplazo total)", grilla con 2 filas, contador verde "Cajas Distribuidas: 52 / Cantidad Inicial Obligatoria: 52" (`data-balanced=true`), botón Confirmar visible. (Reemplaza la versión backend de iteration_128.)
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — Modal Multitienda ("Enviar a Implementación"): carga de distribución por Excel (adicional a la manual)

- **Backend (`routes/quotes.py`):** 2 endpoints nuevos: `GET /quotes/multistore/excel-template` (.xlsx con hoja "Distribucion" `Nombre Sucursal | Cajas` + hoja Instrucciones) y `POST /quotes/multistore/parse-excel` (multipart `file` + `total_boxes`) que parsea con openpyxl y devuelve `{ok, stores:[{name,box_count}], errors[fila], warnings, summary}` SIN persistir. Reporta por fila: nombre vacío, cajas no numéricas/≤0, sucursal duplicada, columnas faltantes/archivo ilegible; advertencia (no bloquea) si la suma ≠ cantidad inicial.
- **Frontend (`QuoteModals.jsx`):** componente `MultistoreExcelBar` (`multistore-excel-bar`) con botones `Plantilla` (descarga) y `Cargar Excel` (input oculto), montado en las fases `collect` e `inherited`. Al cargar OK reemplaza `multistoreStores` (`onLoaded`), muestra toasts de éxito/advertencias y deja que el contador de balance reaccione (rojo/verde) y el bloqueo estricto aplique igual que en la carga manual. Si el Excel tiene errores, NO reemplaza la distribución previa.
- **QA:** backend curl (template 200; válido→3 tiendas; descuadre→warning; filas inválidas→errores por fila). testing_agent iteration_128 → frontend 4/4 PASS (carga válida sum=52 → verde + avanza; descuadre sum=30 → warning + contador rojo + toast de bloqueo exacto sin avanzar; xlsx inválido → toast de error por fila sin reemplazar; fase inherited verificada por código).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Modal Multitienda ("Enviar a Implementación"): scroll 80vh + footer fijo + balance estricto de cajas

- **Layout (`QuoteModals.jsx`):** el `DialogContent` del `multistore-dialog` ahora aplica `max-h-[80vh] flex flex-col overflow-hidden` **solo** en las fases de distribución (`inherited`/`collect`); el resto de fases conservan su tamaño original (sin regresión). Header fijo (DialogHeader), lista de tiendas con scroll interno (`overflow-y-auto flex-1 min-h-0`, thead sticky) y footer fijo (`shrink-0`) con el contador y el botón de acción siempre visibles, incluso con 50+ tiendas.
- **Contador de balance reactivo:** etiqueta "Cajas Distribuidas: [suma] / Cantidad Inicial Obligatoria: [total]" (`collect-balance-counter` / `inherited-balance-counter`, con `data-balanced`), **roja** mientras no cuadra y **verde** (emerald) cuando es exacto.
- **Bloqueo estricto (hard block):** `confirmMultistore` y `confirmInheritedStores` (`Quotes.jsx`) bloquean el avance si `Σ cajas por tienda ≠ cantidad inicial` y muestran el toast exacto: "No se puede continuar: La cantidad de cajas distribuidas (X) no coincide con la cantidad inicial asignada al proyecto (Y). Por favor, ajuste el balance de hardware antes de enviar a implementación." Al cuadrar exacto, avanza a `pinpad_question`. El botón solo se deshabilita por problemas estructurales (0 tiendas / nombre vacío) para que el toast pueda dispararse.
- **Backstop backend (`quote_actions.py · send-to-implementation`):** valida `Σ stores.box_count == cantidad inicial` cuando `is_multistore`; si no cuadra → HTTP 400 con el mismo mensaje (antes de generar PDF/crear proyecto). Verificado por curl: déficit (7/52) y superávit (60/52) → 400 con el mensaje, no destructivo.
- **QA:** backend curl 2/2 (déficit + superávit). testing_agent iteration_127 → frontend: layout ≤80vh + scroll + footer fijo + contador rojo exacto verificados en vivo; toast de bloqueo y estado verde validados por revisión de código de los handlers. 0 issues.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**



## 2026-06 — Reingeniería del semáforo SLA en "En Gestión" (refresco solo por acción válida)

- **Objetivo:** que el Verde del semáforo refleje atención operativa real y auditable en el estado de largo plazo "En Gestión", no la mera inactividad ni comentarios de bitácora.
- **Motor (`project_sla_engine.py`):** nuevo `sla_reference_date(project)`. Para fases iniciales (Por asignar / Asignado) sigue usando `stage_entered_at` (se refresca con el cambio de estado). Para **"En Gestión"** usa `max(stage_entered_at, last_qualified_activity_at)` → el contador (y el color) solo se reinicia con una acción de interacción válida. `evaluate_project` y el panel (`GET /projects` → `business_days_in_state`) usan esta referencia.
- **Disparadores que reinician a Verde (`last_qualified_activity_at = now`):**
  - **Comunicaciones externas:** envío EXITOSO de correo a Cliente o Banco (`_send_sequential_notification`, condicionado a `status in (sent, simulated)` y target client/bank/bank_client).
  - **Evolución operativa:** cualquier avance en la matriz de adquirencia — `PUT /matrix/phase`, `PUT /stores/{id}/matrix/phase` y `POST /matrix/batch-update`.
- **Exclusión estricta — Bitácora:** `POST /projects/{id}/bitacora` solo hace `$push` del comentario; NO toca `last_qualified_activity_at` ni `updated_at` → un comentario manual NO limpia el semáforo (permanece Amarillo/Rojo).
- **QA (self-test):** 4 casos del motor (En Gestión con/sin actividad, actividad más vieja que entered, fase inicial ignora actividad) ✓; end-to-end vía panel API: proyecto En Gestión con 12 días sin interacción → `business_days_in_state=8` (degradado), tras actividad calificada → `0` (Verde) ✓.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — Acceso a "Cotizaciones de Equipos" (caso Anderson Godoy) + herramientas de reparación

- **Causa raíz:** la visibilidad del menú de Cotizaciones de Equipos NO depende del "Override de Acciones", sino de 3 condiciones del usuario: (1) `permissions['cotizaciones'] == 'edit'`, (2) grupo de menú `gestion_comercial` activo, y (3) permiso especial `cotizaciones:equipos` ("Generar Equipos y Accesorios") en sus permisos efectivos (perfil ∪ usuario). Diagnóstico de Anderson Godoy: tenía `cotizaciones='read'` y sin el flag especial → no veía el menú.
- **Solución inmediata (producción, SIN redeploy):** en AdminUsers, para el usuario: poner módulo "Cotizaciones" en "Edición" y activar el permiso especial "Generar Equipos y Accesorios". Los endpoints `PUT /admin/users/{id}/permissions` y `/special-permissions` ya existen en producción. Luego el usuario cierra sesión y vuelve a entrar.
- **Herramientas nuevas (requieren redeploy; útiles para lotes/automatización):**
  - Endpoint admin `POST /api/admin/users/equipment-quotes-access` (body `{identifier, apply}`): diagnostica y, con `apply:true`, repara (otorga el flag, setea cotizaciones=edit, activa el grupo; respeta el techo del perfil). Probado en preview: Anderson pasó de `would_see_menu:false` a `true`.
  - Script standalone `scripts/fix_equipment_quotes_access.py` (dry-run por defecto, `--apply` para escribir) para entornos con acceso a shell.
- **⚠️ Endpoint/script requieren REDEPLOY. La solución vía AdminUsers funciona ya en producción.**


## 2026-06 — Fix: "Enviar a Implementación" en flujo irregular (No-PYME/Corp) perdía el motivo

- **Síntoma:** tras documentar el motivo de la ruptura irregular y completar los modales del wizard, al finalizar el envío a Implementación de una cotización **No-PYME (Corp)** el sistema mostraba `IRREGULAR: Debe proporcionar un motivo para enviar a implementación sin pago registrado` y NO completaba el envío.
- **Causa raíz (`pages/Quotes.jsx`):** en la rama final No-PYME del wizard de implementación, la llamada era `handleSendToImplementation(quoteId, null, storesData)` — pasaba `null` como `exceptionInfo`, por lo que el header `x-exception-reason` nunca se enviaba al backend. La rama PYME sí pasaba `multistoreExceptionInfo` (correcta).
- **Fix:** la rama No-PYME ahora pasa `multistoreExceptionInfo` (motivo capturado en `openMultistoreDialog`), igual que la PYME.
- **Validado:** reproducido el 422 vía API (`send-to-implementation` sin `x-exception-reason` → 422 IRREGULAR); frontend compila. El backend ya aceptaba el motivo por header; solo faltaba que el frontend lo propagara en este camino.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — Fix (3): asunto sin prefijo de Ticket + PRUEBA de imagen CID en envío real

- **Asunto:** por pedido del usuario, se ELIMINÓ por completo el prefijo automático `[Ticket N]`. `_compose_ticket_subject` ahora solo renderiza el asunto del usuario y limpia variables fantasma `{...}` no resueltas; NO añade ningún prefijo. Verificado vía API: `"Avance de Proyecto {N_Proyecto_Real}"` → `"Avance de Proyecto"`.
- **Imágenes (prueba definitiva end-to-end):** se ejecutó un envío REAL por `send_email` (status=sent, method=smtp) con una imagen `/api/projects/images/...` en el cuerpo; el `email_log` confirmó que el HTML enviado contiene `cid:bodyimg_xxx` y que la URL remota desapareció. → El embebido CID funciona de punta a punta EN PREVIEW.
- **⚠️ CONCLUSIÓN:** el código está corregido y probado en PREVIEW. La persistencia del error solo se explica porque la app de PRODUCCIÓN aún no tiene estos cambios. **Requiere REDEPLOY (preview → producción).**


## 2026-06 — Fix (2): asunto con [Ticket] duplicado + refuerzo de imágenes en correos

- **Bug asunto (duplicado + variable fantasma):** el flujo ad-hoc ("Otras Notificaciones") prefijaba `[Ticket N] ` aunque la plantilla del usuario ya incluyera el ticket → quedaba `[Ticket 43243] [Ticket 43243] ...`. Nuevo helper `_compose_ticket_subject(ticket, subject)` que (a) prefija el ticket SOLO si el asunto no lo contiene ya (`[Ticket N]`, `#N` o el número suelto) y (b) elimina variables fantasma `{...}` no resueltas. Aplicado en `preview-adhoc-email` (L~1599) y en el envío ad-hoc (L~2268/2283). Validado vía API: con ticket en plantilla → 1 sola vez; `{N_Proyecto}` inexistente → removido.
- **Bug imágenes (refuerzo):** `_embed_body_images` (email_service) ahora incrusta como **CID inline** CUALQUIER imagen del cuerpo: data URIs, URLs hospedadas por el backend (object storage) y **cualquier URL externa vía httpx** (fallback de descarga, timeout 8s). Antes solo cubría data URIs y URLs `/api/projects/images/`. `MIMEImage` ahora fija el subtipo desde el content-type (evita fallos con webp/jpg). Validado: 3/3 imágenes (data URI + backend + externa) → CID + adjunto inline.
- **⚠️ CAUSA RAÍZ PROBABLE de la persistencia:** el fix previo de imágenes CID estaba solo en PREVIEW. Si se probó en PRODUCCIÓN sin redesplegar, el bug seguía. **Ambos fixes requieren REDEPLOY a producción.**


## 2026-06 — Botones de Notificación de Avance (nivel Proyecto y nivel Banco)

- **Botón A — "Notificación de Avance" (ámbito Proyecto):** en el toolbar de la sección "Matriz de Implementación" del detalle, ubicado entre "Actualización Masiva" y "Notificaciones a Cliente". Abre el modal estándar con `target=client` (matriz completa de todos los bancos) y su propia plantilla preferida (`client_avance`). `data-testid="notif-avance-project-btn"`.
- **Botón B — "Notificación Avances" (ámbito Banco):** en la matriz de adquirencia, a la derecha del botón "Notificaciones" de cada banco (en `SingleBankSection` y `MultistoreBankSection`). Abre el mismo modal con `target=bank` + `bank_name` heredado (matriz filtrada a ese banco) y plantilla preferida `bank_avance`. `data-testid="notif-avance-bank-btn-{banco}"`.
- **Reutilización total:** ambos invocan el modal existente (`openNotifDialog`, ahora con parámetro `prefKey` para la plantilla preferida); el envío usa el flujo `send-notification` actual sin cambios. `markNotifTemplatePreferred` respeta el `prefKey`.
- **Backend (`routes/projects.py`):** `VALID_NOTIF_DESTINATIONS` += `client_avance`, `bank_avance`; `GET /project-notification-preferences` devuelve ambas claves (default = plantilla base de client/bank). El descarte modular reutiliza el override de `Matriz_Seguimiento_Evolutiva` ya existente en `_resolve_notification_email` (re-render de `custom_html` con el token filtrado).
- **QA (self-test E2E):** preferencias incluyen client_avance/bank_avance (PUT 200); botones renderizan en el detalle (toolbar y por banco, proyecto multistore de 3 bancos); `POST /preview-notification` con `target=bank` + token `{Matriz_Seguimiento_Evolutiva}` en custom_html → **solo el bloque del banco seleccionado** (Banco de Venezuela), Bancamiga y Mercantil Panama eliminados; celda y Fase I–IV intactas. Frontend compila.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — {Matriz_Seguimiento_Evolutiva} V3: cabeceras limpias + Fase I–IV + leyenda

- **Limpieza de textos:** eliminadas las palabras estáticas "BLOQUE" y "PRODUCTO" de los encabezados (el título del banco ahora es solo su nombre).
- **Cabecera de 2 niveles:** nombre del producto una sola vez como cabecera fusionada `colspan=4` sobre sus 4 fases; debajo, 4 columnas fijas etiquetadas **Fase I, Fase II, Fase III, Fase IV** (mapeadas a Recibido/Configurado/Testeado/En Producción).
- **Leyenda operativa** al pie de cada tabla de banco (alineada a la izquierda): "Estatus de las Fases: Fase I = Recibido | Fase II = Configurado | Fase III = Testeado | Fase IV = En Producción".
- **Celda intacta:** se mantiene `% avance / Cajas Estimadas / Cajas Recibidas`. Segmentación modular por banco sin cambios.
- **Frontend:** previews (`templateVariables.js`, `RichTextEditor.jsx`) actualizados al layout V3.
- **QA (self-test):** sin "BLOQUE"/"PRODUCTO"; producto con `colspan=4`; exactamente 4 columnas Fase I–IV por producto (8 headers para 2 productos); celda `100% / 5 / 5` y `40% / 5 / 2`; leyenda con equivalencias exactas. Frontend compila.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — {Matriz_Seguimiento_Evolutiva} V2: bloques verticales por banco + celda con cajas

- **Cambio de arquitectura:** se reemplazó la tabla horizontal única (bancos como columnas adyacentes) por **tablas independientes apiladas verticalmente, una por banco** (`<div>` con título "BLOQUE: {Banco}"). Cada tabla: eje vertical = RIF → Tiendas; columnas = Producto×Fase con encabezado "PRODUCTO: {producto} (Fase {fase})".
- **Nueva celda (`_seg_cell_v2`):** cada cruce muestra `% avance / Cajas Estimadas / Cajas Recibidas` (ej. `80% / 10 / 8`; sin recibidas → `0% / 5 / 0`). Estimadas=`expected`, Recibidas=`processed`, % = 100 si completed, si no `processed/expected`. Se eliminó la columna independiente de Cajas (ahora va en la celda).
- **Descarte modular optimizado:** como cada banco es un bloque autocontenido, el filtro al banco destinatario (`bank_filter` en `_resolve_notification_email`, ramas bank/bank_client) emite solo ese bloque; los demás bancos se omiten por completo sin romper el diseño. Aplica en preview y envío.
- **Frontend:** previews (`templateVariables.js`, `RichTextEditor.jsx`) actualizados al layout V2 con el nuevo formato de celda.
- **QA (self-test, criterios V2):** formato de celda `100% / 5 / 5`, `0% / 5 / 0`, `40% / 5 / 2`; disposición vertical (BLOQUE: Banco A y BLOQUE: Banco B apilados); prueba de fuego de segmentación: filtrar a "Banco B" deja solo su bloque (Banco A removido) conservando RIF/tiendas. Frontend compila.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — Nueva variable {Matriz_Seguimiento_Evolutiva} (matriz multinivel modular por banco)

- **Requerimiento:** variable global de reporte bidimensional: eje vertical = RIF → Tienda/Sucursal (+ columna Cajas); eje horizontal = Banco → Producto → Fases (Rec/Conf/Test/Prod) con % de avance por fase. **Modular por banco**: al Cliente muestra todos los bancos; al enviar a un Banco específico elimina los bloques del resto (confidencialidad interbancaria). Basada en 3 modelos Excel aportados (single / multi-tienda / multi-RIF).
- **Backend (`services/project_template_vars.py`):** nuevos `_build_seguimiento_evolutiva_html(project, bank_filter=None)`, `_seg_banks_products` (banco→productos desde `implementation_matrix`, filtrable por banco case-insensitive) y `_seg_rows` (filas RIF/tienda/cajas para multirif/multistore/single). Reutiliza `_phase_cell_value` y las fases canónicas (Recibido/Configurado/Testeado/En Producción → Rec/Conf/Test/Prod). Encabezado de 3 niveles (Banco / Producto / Fases), bandas por RIF, % con semáforo de color. Registrada en `resolve_project_template_vars` (versión completa).
- **Modularidad (`routes/projects.py` · `_resolve_notification_email`):** en las ramas `bank` y `bank_client` (donde se conoce `bank_name`) se **sobreescribe** `Matriz_Seguimiento_Evolutiva` con la versión filtrada al banco destinatario. Aplica en preview (`/preview-notification`) y envío (`/send-notification`).
- **Catálogo + frontend:** registrada en el catálogo de variables (`/projects/{id}/template-variables`), excluida de los mapas simples (es HTML grande), añadida a `other_actions_config.py`, `templateVariables.js` (+ mini-preview hover), `EmailTemplatesEditor.jsx` (4 listas), `RichTextEditor.jsx` (ejemplo) y `projectConstants.js` (ALL_TOKENS).
- **QA (self-test directo, cubre los 5 criterios):** AC1 jerarquía vertical (bandas por RIF + tiendas + cajas exactas); AC2 % por fase reflejan la matriz (40%/100%); AC3 envío a Cliente muestra los 3 bancos; AC4 envío a "Banco B" elimina por completo los bloques de A y C, conservando RIF/tiendas/cajas; filtro case-insensitive; funciona en single/multistore/multirif. Render sobre proyecto real multirif OK; variable presente en el catálogo vía API; frontend compila.
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06 — Nueva función: Calendario Laboral + Motor de Días Hábiles (SLAs/Proyectos)

- **Requerimiento:** sustituir el conteo de días naturales por **días hábiles** (excluye sáb/dom + feriados parametrizados) de forma transversal en el panel de Proyectos y el motor SLA. Decisiones del usuario: 1a=días completos (sin horas); 2a=inicio cuenta como día 1; 3b=permitir feriados recurrentes anuales; 4a=gestión solo Admin; ubicado en **Configuración > Calendario Laboral**.
- **Backend — motor (`services/business_calendar.py`):** `get_holiday_sets()` (caché 30s; sets de fechas específicas 'YYYY-MM-DD' y recurrentes 'MM-DD'), `is_business_day()`, `business_days_between(start,end)` (cuenta el intervalo (start, end] — excluye el día de inicio), `add_business_days(start,n)` (n-ésimo día hábil, inclusivo). `invalidate_holidays_cache()` al crear/eliminar.
- **Backend — CRUD (`routes/calendar.py`, prefijo `/api/calendar`):** `GET /calendar/holidays` (cualquier autenticado), `POST /calendar/holidays` y `DELETE /calendar/holidays/{id}` (**solo Admin** vía `_require_admin`). Unicidad: 409 si la fecha específica ya existe o si ya hay un recurrente con el mismo MM-DD; 400 si la fecha es inválida. Colección `holidays`. Registrado en `server.py` (no mapeado en ROUTE_MODULE_MAP → el handler aplica el admin-only).
- **Integración SLA (`services/project_sla_engine.py`):** `evaluate_project` ahora cuenta días hábiles (`business_days_between`); `run_sla_evaluation` carga los feriados una sola vez por corrida. El estado "Configurado en espera del Cliente" sigue pausado (no entra al semáforo).
- **Integración Panel (`routes/projects.py`):** `GET /projects` inyecta `business_days_in_state` por proyecto (días hábiles desde `stage_entered_at`). El frontend (`pages/Projects.jsx`) usa ese valor en el semáforo SLA con etiqueta "Nd háb." (antes calculaba días naturales en el cliente).
- **Frontend — UI:** nueva página `pages/WorkCalendarConfig.jsx` (ruta `/settings/work-calendar`): formulario (fecha + descripción + switch "Cada año" + Guardar) y grilla cronológica con badge Único/Recurrente y eliminar con confirmación. Tarjeta `work-calendar-card` en `Settings.jsx`.
- **QA:** pytest del testing_agent `tests/test_iteration126_calendar_holidays.py` **14/14 PASS** (list admin/no-admin/unauth, create específico, 409 duplicado específico, recurrente, 409 duplicado recurrente, 400 fecha inválida, RBAC POST/DELETE 403 no-admin, unauth 401, delete admin, 404, business_days_in_state en /projects). Validación directa del motor: **AC#2** (Vie→Lun = 1 día hábil) y **AC#3 crítica** (SLA 3 días hábiles, inicio lunes con martes feriado → vence viernes, elapsed=3). Smoke test UI: página y panel renderizan con etiquetas "d háb.".
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.** La colección `holidays` queda vacía (datos de prueba revertidos); el Admin debe cargar los feriados reales tras desplegar.

### Extensión — Reporte de Carga (PDF) muestra "Días háb." por proyecto
- **Backend (`routes/projects.py` · `projects_workload_pdf`):** se agregó la columna **"Días háb."** (días hábiles transcurridos en el estado actual, calculados con `stage_entered_at` + `business_days_between`, excluyendo sáb/dom + feriados) en ambos modos de agrupación del reporte (por Implementador y por Tipo). Estilo destacado teal. Anchos de columna reajustados. Sin cambios de frontend (el reporte se genera server-side).
- **Validado (curl + pdfplumber):** el PDF (group_by=implementer y group_by=type) muestra el encabezado "DÍAS HÁB." y el valor por fila (ej. "En Gestión 10" = 10 días hábiles). HTTP 200, 8 páginas.


## 2026-06 — Fix: imágenes pegadas en plantillas llegaban rotas al correo (ahora CID inline)

- **Síntoma (reportado por el usuario, con captura):** las imágenes insertadas en una plantilla se veían en Vista Previa pero llegaban **rotas** ("image.png" con ícono roto) en el correo recibido (Outlook/Gmail).
- **Causa raíz:** las imágenes del cuerpo se referenciaban como **URL remota** (`{REACT_APP_BACKEND_URL}/api/projects/images/{id}.ext`); los clientes de correo bloquean o no cargan imágenes remotas (mismo problema que tuvo el logo de firma, resuelto previamente con CID).
- **Fix (`services/email_service.py`):** nuevo helper `_embed_body_images(html, attachments)` invocado en `send_email` (tras el bloque del logo de firma). Escanea los `<img src>` del cuerpo y, para imágenes hospedadas por nuestro backend (`/api/projects/images/{id}` → busca bytes en object storage vía `db.uploaded_images`) o **data URIs** base64, las adjunta como **inline CID** (`cid:bodyimg_*`) y reescribe el `src`. Funciona en SMTP (multipart/related) y Resend (disposition inline), y es **robusto entre entornos** (match por `image_id`, no por host → un template creado en preview se ve bien al enviar desde producción). IDs inexistentes se omiten sin romper el envío.
- **Validado (self-test directo):** data URI → CID + adjunto; URL hospedada real (subida vía `/api/projects/upload-image`) → bytes recuperados de object storage + CID; ID inexistente → HTML intacto, 0 adjuntos; sin `<img>` → sin cambios. Solo afecta el correo ENVIADO (la Vista Previa sigue usando la URL remota y ya funcionaba).
- **⚠️ En PREVIEW; requiere REDEPLOY para producción.**


## 2026-06-13 — Nueva función: carga vía Excel de la distribución Multi-RIF (Tiendas/Sucursales)

- **Backend (`quotes.py`)**: 2 endpoints nuevos:
  - `GET /quotes/multirif/excel-template` → plantilla .xlsx (hoja "Distribucion" + hoja "Instrucciones") con columnas `RIF Cliente | Nombre Sucursal | Cajas`.
  - `POST /quotes/multirif/parse-excel` (multipart `file` + `global_boxes`) → parsea, valida y devuelve `{ok, distribution, errors, warnings, summary}` SIN persistir. Agrupa por RIF (busca el Cliente por RIF), calcula cajas del RIF = suma de sus sucursales.
- **Reporte de errores documentado (fila por fila)**: RIF/sucursal vacíos, Cajas no numérica o ≤0, RIF sin Cliente registrado, sucursal duplicada en el mismo RIF, columnas faltantes / archivo ilegible. Advertencia (no bloquea) si total de cajas ≠ Cajas Globales del lote.
- **Frontend (`MultiRifDistributionPanel.jsx`)**: barra con "Plantilla" (descarga .xlsx) y "Cargar Excel" (input oculto). Al cargar sin errores, **reemplaza** la distribución (`onChange`); muestra `ImportReport` con éxito/advertencias/errores (con número de fila) y resumen (RIFs/sucursales/cajas). Disponible en estado colapsado y expandido.
- **Validado**: curl (plantilla 2 hojas, parseo válido, 4 tipos de error con fila, advertencia por mismatch, resumen) + testing agent (iteration_81, 5/5 escenarios en el wizard VPOS Multi-RIF).


## 2026-06-13 — Fix de rendimiento: latencia al capturar tiendas en proyectos Multi-RIF

- **Causa raíz**: los inputs de la matriz por tienda (`StoreBankSection.jsx`) disparaban la actualización en **cada tecla** (`onChange`), y cada edición ejecutaba un `fetchProject()` que **recargaba TODO el proyecto** (documento grande en Multi-RIF) + re-render completo del árbol. La cascada hacía 4 PUT + 1 GET por dígito.
- **Solución (frontend)**:
  - `StoreBankSection.jsx`: nuevo `QtyInput` con estado local → la escritura es instantánea y se **persiste solo en blur/Enter** (no por tecla).
  - `ProjectDetail.jsx`: `patchStoreMatrixLocal` aplica una **actualización local optimista** (parchea la celda + rollup) en lugar de `fetchProject()` en los 4 handlers de tienda (quantity, cascade, fill, toggle). En error se hace `fetchProject()` para resync.
- **Solución (backend `projects.py` · `update_store_matrix_phase`)**: el PUT ahora retorna `expected/processed/completed` + `rollup_progress`, para que el frontend actualice sin recargar.
- **Validado (iteration_80)**: 100% — escritura fluida, persistencia tras F5, cascada propaga a las 4 fases, botón "T" completa, avance global se actualiza sin recargar. Sin pérdida de datos ni parpadeo.


## 2026-06-13 — Fix: Reporte de Carga (PDF) de Proyectos no contemplaba Multi-RIF

- **Causa (backend `projects.py` · `projects_workload_pdf`)**: los proyectos `quote_type='VPOS_MULTIRIF'` mostraban Cajas "—" (el gate era `qt in ("VPOS","MPOS")`), no sumaban a la carga del implementador, no tenían badge/etiqueta de tipo y no aparecían en la agrupación/filtro por Tipo. Además, en Multi-RIF `cantidad_cajas` viene vacío (el total vive en `rifs`/`stores`).
- **Solución**: nuevos helpers `_counts_cajas` (incluye VPOS_MULTIRIF) y `_project_total_cajas` (cae a `box_count` y a la suma de `rifs.box_count`). Se mapeó VPOS_MULTIRIF en `_TYPE_LABEL`("VPOS-MR")/`_TYPE_FULL_LABEL`("VPOS Multi-RIF")/`_TYPE_BADGE_CSS` y se agregó al `type_order`. El PVV se calcula con el total de cajas correcto. La línea "Filtros aplicados: Tipo" usa la etiqueta completa.
- **Frontend (`WorkloadReportFiltersModal.jsx`)**: el filtro "Tipo de Proyecto" ahora incluye "VPOS Multi-RIF" (chip `filter-type-VPOS_MULTIRIF`) con etiquetas amigables.
- **Validado (curl/PDF)**: prj_e586608e3579 ahora aparece con Cajas=28, PVV=168, badge VPOS-MR; agrupación por Implementador y por Tipo correctas; filtro `quote_type=VPOS_MULTIRIF` OK.


## 2026-06-13 — Mejora: desplegable de usuarios To/CC agrupado por equipo

- **Frontend (`InternalEmailInput.jsx`)**: el desplegable de usuarios internos ahora agrupa por equipo con encabezados sticky y conteo: **Dirección / Ventas / Implementación / Otros** (`TEAM_SECTIONS` + useMemo `grouped`). Solo se muestran las secciones no vacías; al filtrar por texto se re-agrupa. testids: `${testId}-group-<key>`.
- **Validado (iteration_79)**: 100% — TO/CC con headers Dirección(2)/Ventas(6)/Implementación(11), sin 'Otros' (profile strategic), filtro 'gonz' re-agrupa, selección OK.

## 2026-06-13 — Fix: lista de emails (To/CC) en Notificaciones de Proyecto venía corta

- **Causa raíz (frontend `InternalEmailInput.jsx`)**: el dropdown de usuarios internos limitaba a **8** resultados (`.slice(0, 8)`), por lo que aunque el backend devolvía 19 usuarios estratégicos, solo se mostraban 8. Se eliminó el cap: con query vacío muestra TODA la lista y al escribir muestra TODAS las coincidencias (contenedor `max-h-52` con scroll).
- **Backend (`entity_communications.py` · `_is_strategic_profile`)**: filtro `profile=strategic` ahora más robusto e inclusivo — TODO el Equipo de Ventas (cualquier subárea, `dept` empieza por "ventas"), TODA Implementación (cualquier cargo) y Dirección/Directores. Antes excluía Implementación con cargos fuera de {Implementador, Coordinador, Gerente}.
- **Validado**: pytest `tests/test_internal_emails_filter.py` 4/4 + testing agent (iteration_78): TO=19, CC=19, scroll real, filtro 'gonz'=3 coincidencias, selección + chip OK.


## 2026-06-13 — Variable {Matriz_Avance_Proyecto} + Pegado de imágenes en el editor enriquecido

### Variable dinámica {Matriz_Avance_Proyecto}
- **Backend (`project_template_vars.py`)**: nuevos `_phase_cell_value`, `_avance_phase_table`, `_avance_store_block`, `_build_avance_matrix_html`. Registrada en el dict de variables y en el catálogo (`projects.py`). Reglas por celda: Cumplida → `100%` · En proceso → `% real` (processed/expected) · No iniciada → `—`. Jerarquía: Estándar = Banco→Producto→Fases; Multitienda/Multi-RIF antepone Tienda/Sucursal (en Multi-RIF agrupa por RIF). Cabecera con KPI **Avance Global** = `rollup_progress.global_progress` (igual al dashboard). Excluida de los mapas simples de variables (es HTML grande) pero presente en el catálogo.
- **Frontend**: agregada a `templateVariables.js` (+ preview HTML), `EmailTemplatesEditor.jsx` (4 listas de proyecto), `projectConstants.js` ALL_TOKENS (chip clickeable en notificaciones) y `RichTextEditor.jsx` DEFAULT_EXAMPLE_VALUES (Vista Previa de toolbar).
- **Validado**: pytest `tests/test_matriz_avance_proyecto.py` (3/3) + curl `preview-adhoc-email` sobre prj_e586608e3579 (KPI 23%, bloques por RIF/Sucursal, celdas 100%/—) + testing agent (render correcto en Vista Previa del modal).

### Pegado de imágenes (Ctrl+V / drag&drop / botón) en RichTextEditor
- **Frontend (`RichTextEditor.jsx`)**: extensión TipTap `Image`; props `enableImagePaste`(default true) + `imageUploadUrl`(`/projects/upload-image`); `handlePaste`/`handleDrop` capturan el Blob, lo suben e insertan `<img>` con URL absoluta en el cursor; botón de imagen en la toolbar (`${testid}-image`) + input file (`${testid}-image-input`); toast de estado. Disponible en TODAS las plantillas (Notificaciones, Clientes, Cotizaciones, Integradores).
- **Backend (`projects.py` · `upload_image`)**: nueva compresión ligera con Pillow (`_compress_image`): reescala a máx 1600px y recomprime (JPEG q82 / WEBP q82 / PNG optimize; GIF intacto) para aligerar correos.
- **Validado**: curl upload (3000x2000 → ≤1600px, servido HTTP 200) + testing agent (inserción end-to-end 100%, `<img>` con src `/api/projects/images/...`).


## 2026-06-13 — Fix: Actualizaciones individuales por tienda bloqueadas en Multi-RIF ("Este proyecto no es multitienda")

- **Backend (`projects.py` · `update_store_matrix_phase`, línea ~1727)**: `PUT /projects/{id}/stores/{store_id}/matrix/phase` rechazaba `project_type != "multistore"` → "Este proyecto no es multitienda". Esto bloqueaba TODAS las ediciones por celda en el árbol Multi-RIF (cantidad, cascada, marcar fase, toggle), que usan ese mismo endpoint. Ahora acepta `("multistore", "multirif")`. El handler ya opera genéricamente sobre `stores` y recalcula rollup.
- **Permisos**: este endpoint no tenía restricción de rol (solo exige `client_notified`), por lo que admin/implementador puede editar a cualquier nivel. La matriz principal sigue siendo de solo lectura en la UI (locks) para multitienda/Multi-RIF, por diseño.
- **Validado (curl)**: PUT store matrix phase sobre prj_e586608e3579 (Marquez, Configurado, Tarjeta de Crédito/Débito 5/5) → HTTP 200 "Fase de tienda actualizada".

## 2026-06-13 — Fix: Actualización Masiva bloqueada en proyectos Multi-RIF ("Solo proyectos multitienda")

- **Backend (`projects.py` · `batch_update_multistore_matrix`, línea ~1831)**: la validación rechazaba todo proyecto con `project_type != "multistore"`, devolviendo "Solo proyectos multitienda" al aplicar en un proyecto `multirif` (aunque el botón/modal ya se mostraban tras el fix de Fase 5). Ahora acepta `("multistore", "multirif")`. El resto de la lógica (matriz por tienda, rollup, bitácora) es genérica y funciona igual.
- **Validado E2E (curl)**: POST batch-update sobre prj_e586608e3579 (RIF Brasero, fase Recibido, 6 medios, 2 tiendas) → HTTP 200 "Actualización masiva aplicada a 2 tienda(s)". Avance reflejado: Marquez/Centro 25% (1/4 fases), rollup global 12.5%.


## 2026-06-13 — VPOS Multi-RIF · % de avance por RIF (modal Actualización Masiva + árbol)

- **Modal "Actualización Masiva" (`BatchUpdateModal.jsx`)**: el Select de RIF ahora muestra un chip de % por opción (`batch-rif-pct-<rif_id>` y `batch-rif-pct-all`), una mini barra de avance del alcance seleccionado (`batch-rif-progress` / `batch-rif-progress-pct`) y un chip de % por cada tienda en la lista. Avance ponderado por cajas (mismo criterio que el backend/árbol).
- **Árbol Multi-RIF (`MultiRifTree.jsx`)**: cada nodo RIF añade un chip de % con colores semáforo (`multirif-rif-pct-<rif_id>`) junto a la barra existente.
- **Colores semáforo**: 0% rojo · <50% ámbar · ≥50% verde. Reutiliza `weightedProgress`/`calcStoreProgress`. Backend sin cambios.
- **Validado (iteration_76)**: 100% — chips y barra renderizan con valores 0-100 y color correcto; regresión de filtrado Fase 5 intacta (proyecto con matriz vacía → todo 0%/rojo, correcto).


## 2026-06-13 — VPOS Multi-RIF · Fase 4.5 (corrección de bypass) + Ficha Técnica + Fase 5 (filtro RIF en Actualización Masiva)

### Corrección del bypass agresivo (Enviar a Implementación)
- **Frontend (`Quotes.jsx` · `openMultistoreDialog`)**: se REVIRTIÓ el early-return que enviaba directo a implementación. Ahora para `VPOS_MULTIRIF`: abre el wizard, setea `is_multistore=true` + `projectTypeImpl='vpos_mpos'` y enruta a `multistorePhase='pinpad_question'`. Se omite ÚNICAMENTE el modal "¿Es Multitienda?" y se MANTIENEN obligatorios los pasos: Pinpads → Impresora Fiscal → Datos Consolidados (Servidor/Servi) → Confirmación de Implementador. El flujo no-Multi-RIF queda intacto (regresión validada).
- **Frontend (`QuoteModals.jsx` · fase `pinpad_question`)**: el botón "Atrás" cierra el wizard cuando la cotización es `VPOS_MULTIRIF` (es el primer paso), en vez de navegar a fases inexistentes ('collect'/'ask').
- **Validado (iteration_73)**: al "Enviar a Implementación" de un VPOS_MULTIRIF aparece la fase Pinpads (no envío directo). 3/3 tests críticos frontend ✓.

### Ficha Técnica PDF jerárquica Multi-RIF
- **Backend (`implementation_pdf.py`)**: nuevo helper `_build_multirif_table` + render de "DETALLE DE TIENDAS Y SUCURSALES (Multi-RIF)" (Cliente/RIF → Sucursales → Cajas + TOTAL GENERAL) en la sección de Distribución Logística cuando `quote.multirif_distribution` existe (en send-time el campo viene del quote; el formato coincide). Fallback a la tabla plana de sucursales para proyectos normales.
- **Backend (`projects.py` · `download_ficha_tecnica`)**: construye `multirif_distribution` desde `project.rifs` + `project.stores` (agrupando por `rif_id`).
- **Validado**: pytest `tests/test_ficha_multirif.py` (2/2) + curl live de `GET /projects/prj_e586608e3579/ficha-tecnica` → 3 RIFs (Brasero/Barako/Carbon), TOTAL GENERAL=28.

### Fase 5 — Filtro en cascada por RIF en "Actualización Masiva"
- **Frontend (`BatchUpdateModal.jsx`)**: nuevo Select de RIF (Fase → Banco → RIF → Tiendas). Opción "Todos los RIFs" vs RIF específico; al elegir un RIF, la lista "Tiendas a procesar" filtra por `store.rif_id`. Solo se muestra en proyectos Multi-RIF (`project.rifs.length>0`).
- **Frontend (`ProjectDetail.jsx`)**: estados `batchRif`, `handleBatchRifChange` (resetea selección de tiendas), `getBatchFilteredStores`, `toggleAllBatchStores` acotado a tiendas filtradas. **Fix de gating**: el botón "Actualización Masiva" ahora se muestra con `(isMultistore || isMultiRif)` (antes solo `isMultistore`, ocultaba el botón en proyectos `project_type='multirif'`). Backend sin cambios (recibe `store_ids` ya acotados).
- **Validado (iteration_74 detectó gating oculto → corregido → iteration_75)**: 100% del flujo Fase 5 (botón visible, modal, filtrado 4→2→1→1→4, reset de selección) ✓.


## 2026-06-13 — VPOS Multi-RIF · Bypass del modal "¿Es Multitienda?" en Enviar a Implementación

- **Frontend (`Quotes.jsx`)**: `openMultistoreDialog` ahora hace **early-return** cuando `quote_type === 'VPOS_MULTIRIF'`: omite el modal "¿Es Multitienda?" y llama directo a `handleSendToImplementation` (preservando `exceptionInfo` para el flujo irregular). Para el resto de tipos, el modal tradicional Sí/No se mantiene intacto.
- **Integridad de payload**: para Multi-RIF, `handleSendToImplementation` declara `is_multirif:true` + `is_multistore:true` en el body (SIN `stores`), para no enrutar al multistore plano y conservar `project_type="multirif"`.
- **Backend (`quote_actions.py`)**: `SendToImplementationRequest` acepta `is_multirif`; se preserva el `client_name` sintético del Banco para Multi-RIF. El backend solo arma multistore plano con `is_multistore && stores`, por lo que Multi-RIF mantiene su jerarquía de 3 niveles (lo construye `_create_project_from_quote` desde `multirif_distribution`).
- **Validado E2E (backend)**: POST send-to-implementation con body de bypass → HTTP 200 y proyecto creado con `project_type="multirif"`, RIFs/sucursales correctos y nombre del Banco. QA #1 (avanza sin modal) y QA #3 (integridad jerarquía) ✓. QA #2 (modal tradicional preservado) por código sin cambios en esa rama.


## 2026-06-13 — VPOS Multi-RIF · FASE 4: Variables de correo (Distribución + Avance)

Dos variables dinámicas para las plantillas de correo (notificación inicial vs. avances):
- **`{Matriz_MultiRif_Distribucion}`**: tabla HTML jerárquica Cliente (RIF) → Sucursales → Cajas + TOTAL GENERAL. Para la notificación inicial.
- **`{Matriz_MultiRif_Avance}`**: misma tabla + columna **Avance %** por Sucursal, por RIF (ponderado por cajas) y Global. Para correos de avance.
- Implementadas en `project_template_vars.py` (`_build_multirif_distribution_html(with_progress)`, `_multirif_store_progress`, `_multirif_weighted_progress`). Fases canónicas = Recibido/Configurado/Testeado/En Producción.
- Catalogadas en el editor: `projects.py` (endpoint de variables), `templateVariables.js`, `EmailTemplatesEditor.jsx`. Fallback "No aplica" para proyectos no Multi-RIF.
- **Validado:** render directo — jerarquía correcta, TOTAL GENERAL=10, avances 33%/50%/0%/Global 20% (coinciden con el árbol de Fase 3).


## 2026-06-13 — VPOS Multi-RIF · FASE 3: Proyecto "Multi-RIF" + tracking de 3 niveles (P0)

- **Conversión (`quote_transitions._create_project_from_quote`)**: cuando la cotización tiene `is_multirif`, crea proyecto `project_type="multirif"` con: `rifs[]` (metadata del cliente jurídico: rif_id, client_id, rif, client_name, box_count) y `stores[]` **planos** etiquetados con `rif_id` (reutilizan los endpoints/UX multitienda existentes). Cada store recibe una copia profunda (`copy.deepcopy`) de la `implementation_matrix`. La matriz principal es la unión.
- **Nuevo componente `MultiRifTree.jsx`**: árbol colapsable de 3 niveles **Proyecto Global → RIF → Sucursal** con barras de **progreso fraccionado** (verde al 100%). Progreso ponderado por nº de cajas: store = fases completadas/4; RIF = Σ(store×cajas)/Σcajas; Global = ídem global. Cada sucursal se expande al editor de matriz reutilizando `StoreBankSection` (endpoint `/projects/{id}/stores/{storeId}/matrix/phase`).
- **ProjectDetail**: `isMultiRif`; la matriz principal usa modo rollup (solo lectura) como multitienda; se renderiza `MultiRifTree` cuando `project_type==='multirif'` y el cliente fue notificado.
- **Validado:** conversión backend (unit: multirif, 2 RIFs, 3 stores con rif_id e independencia de matrices) + UI (árbol renderizado, progreso 3 niveles correcto 20%/33%/50%, expansión y editor de matriz por sucursal). Pendiente cosmético: warning hidratación.


## 2026-06-13 — VPOS Multi-RIF · PDF de cotización (cliente=Banco + Detalle de Tiendas)

Ajuste del PDF de cotización para Multi-RIF (previo a Fase 3):
- **Portada y Página 2 (Datos del Cliente):** el nombre del cliente ahora es el **nombre del Banco de adquirencia**. Hidratación autoritativa server-side: `hydrate_pdf_request` resuelve el banco desde `sponsoring_bank_id` y fija `cliente_nombre` (y limpia RIF/contacto/dirección) cuando `is_multirif`.
- **Página 5 — "Detalle de Tiendas y Sucursales":** nuevo método `_build_multirif_section()` en `pdf_generator.py` que renderiza una tabla jerárquica Cliente(RIF) → Sucursales → Cajas con TOTAL GENERAL. Invocado en `generate_vpos` (PYME) y `generate_vpos_corp` (CORP).
- `TemplateQuotePDFRequest` extendido con `is_multirif`, `multirif_distribution`, `sponsoring_bank_id/name`. `create_quote_with_pdf` propaga estos campos al `pdf_request`. Frontend (`buildTemplatePdfData` + pdfData inline) envía cliente=banco y la distribución.
- **Validado:** PDF generado directamente y extraído — portada/página 2 = "Banco de Venezuela", sección jerárquica correcta, TOTAL GENERAL = 10.


## 2026-06-13 — VPOS Multi-RIF · FASE 2: Motor de distribución anidada + barra de progreso + limpiezas (P0)

- **Nuevo componente `MultiRifDistributionPanel.jsx`**: motor de distribución Global→RIF→Tienda. Buscador de Cliente/RIF (≥2 chars sobre nombre/RIF), cajas por RIF, sub-sucursales (nombre+cajas). Exporta `validateMultiRif(dist, globalBoxes)`.
- **"Reel" de saldos**: Σsucursales ≤ cajas del RIF (error inline `multirif-rif-error-{i}`); ΣRIFs ≤ Cajas Globales. **Guardado bloqueado** hasta distribuir el 100% (validación en `handleSubmitQuote` con toast).
- **Barra de progreso en vivo** (`multirif-progress-bar` + badge): "asignadas / globales", **azul/ámbar** (faltan), **verde** al 100% ("¡Lote distribuido al 100%!"), **roja** si excede.
- **Ambos paneles disponibles** en Multi-RIF: "Detalle de Sucursales" (convencional) + "Detalle de Tiendas/Sucursales (Multi-RIF)".
- **Persistencia**: `multirif_distribution` `[{client_id, rif, client_name, boxes, stores:[{name,boxes}]}]` enviado en el payload y guardado en la cotización.
- **Limpiezas Fase 1 (solo Multi-RIF)**: ocultos el campo **Bancos/Entes** (siempre 1 banco) y la pregunta **¿Exento de IVA?** (ningún banco exento). Regresión VPOS normal intacta.
- **Validado:** testing_agent iter72 — backend 2/2 pytest, frontend 100% (Reel 12/10 rojo, 5+5 verde, sucursal 6>5 error, bloqueo 7/10). Pendiente cosmético: warning hidratación `data-ve-dynamic`.


## 2026-06-13 — VPOS Multi-RIF · FASE 1: Entrada Comercial + Fundamento de datos (P0, épico 5 fases)

Nueva línea de producto "VPOS Multi-RIF" (lote bancario para múltiples RIFs). Fase 1 entregada:
- **Nuevo tipo `VPOS_MULTIRIF`** en `constants.js` (QUOTE_TYPES), disponible en flujos Pyme y Corporativo.
- **Lógica invertida en el wizard** (`QuoteWizardDialog.jsx`): al elegir el tipo se omite el selector de **Cliente** y se exige **Banco (Adquirencia)** (`multirif-bank-select`); patrocinio **implícito = Sí** (banco = patrocinador absoluto, bloque `multirif-implicit-sponsor` reemplaza la pregunta Sí/No); etiqueta **"Cajas Globales (Lote)"**; el banco de **Medios de Pago se hereda y bloquea** (useEffect → `handleBankSelect`, `select-bank` disabled), filtrando productos de esa entidad; IVA exento conservado.
- **Flags** (`Quotes.jsx`): `isMultiRif`, `isVPOS` lo incluye (pricing = VPOS convencional); `isHeaderComplete` para multi-rif exige `sponsoring_bank_id` en lugar de `client_id`; payload `/quotes/create-with-pdf` envía `client_id:null` + `is_multirif:true`.
- **Backend** (`quotes.py`, `models.py`): `QuoteCreateWithPDF.client_id` ahora opcional; `create-with-pdf` genera `client_name` sintético **"Lote &lt;Banco&gt; (Multi-RIF)"** y persiste `is_multirif` + `multirif_distribution` (placeholder Fase 2). Modelo `Quote` extendido con `is_multirif`/`multirif_distribution`.
- **Validado:** testing_agent iter71 — backend 4/4 pytest, frontend 100% (Pyme + Corp invertidos, regresión VPOS intacta). Pendiente cosmético: warning hidratación `data-ve-dynamic` en QuotesTable (preexistente).

### Roadmap pendiente VPOS Multi-RIF
- **Fase 2 (P0):** Motor de distribución anidada Global→RIF→Tienda + validación de saldos ("Reel"): botón "Detalle de Tiendas/Sucursales (Multi-RIF)", buscador de Cliente/RIF con cajas, sub-sucursales (nombre+cajas), reglas Σtiendas≤RIF y ΣRIFs≤Global, bloqueo hasta 100%. Persistir en `multirif_distribution`.
- **Fase 3 (P0):** Conversión a proyecto tipo "Multi-RIF" + tracking 3 niveles (árbol colapsable Proyecto→RIFs→Sucursales, progreso fraccionado).
- **Fase 4 (P1):** Notificaciones — variable `{Matriz_MultiRif_Distribucion}` (tabla jerárquica Cliente(RIF)→Sucursales→Cajas).
- **Fase 5 (P1):** Actualización Masiva con filtros en cascada (Fase→Banco→RIF→Tiendas), "Todos los RIFs" vs RIF específico.


## 2026-06-13 — Edición Maestra: diff de auditoría en bitácora

Mejora de trazabilidad sobre los overrides de admin (`projects.py` → `master_override_project`):
- Nuevo helper `_master_diff()` que compara los valores anteriores del proyecto contra el override y produce una lista de cambios `{field, label, old, new}` (campos escalares, Estado, Tipo, Banco Patrocinador, Hardware, y resumen Bancos/Productos vía `_summarize_matrix`; en multitienda, diff por tienda).
- La bitácora (`type='master_override'`) ahora guarda: texto legible "N campo(s) modificado(s) por {admin}: Estado: 'X' → 'Y'; ..." **y** la estructura `changes` para trazabilidad programática. Respuesta incluye `changes_count`.
- Validado por curl: detecta solo los campos realmente cambiados (Ticket/Estado/Bancos-Productos) e ignora los iguales.


## 2026-06-13 — Edición Maestra (Super-Admin Overrides) en Módulo de Proyectos (P0)

Función de edición global/permisiva exclusiva para rol Administrador:
- **RBAC:** endpoint `PUT /api/projects/{id}/master-override` bloqueado con **403** para no-admin; icono de **lápiz** (`master-edit-btn-{id}`) visible solo si `isAdmin`, colocado **inmediatamente a la izquierda de la papelera** en la columna Acciones (`Projects.jsx`).
- **Modal `MasterEditDialog.jsx`** (nuevo componente): todos los campos en modo escritura. Dropdowns dinámicos: **Estado** (catálogo 7 estados + valor legacy actual), **Tipo de Proyecto** (VPOS/MPOS/GATEWAY/LINK), **Banco Patrocinador** (catálogo `/banks`). Editor relacional **Banco↔Productos** con multi-selección de medios de pago **filtrados por el Tipo de Proyecto** (flags `vpos_available`/`mpos_available`/`gateway_available`/`link_available`). **Hardware** multi-select desde `/hardware`. **Multitienda**: pestañas por tienda.
- **Override relacional consistente (backend):** reconstruye `banks[]`, `services[]` (items `additional`, preservando precios de los que coinciden) e `implementation_matrix` (preservando datos de fase de pares banco/producto sin cambios). En multitienda reconstruye cada `stores[].implementation_matrix` y la matriz principal como **unión** de las tiendas. Sin registros huérfanos; Ficha Técnica sigue generándose OK. Auditoría en `notes` + `bitacora` (`type='master_override'`).
- **Validado:** testing_agent iter70 — backend 5/5 pytest, frontend 100% (RBAC, posición del icono, dropdowns, filtro de productos por tipo, impacto relacional single + multitienda, ficha técnica). Sin regresiones. Pendiente cosmético: warnings de hidratación `data-ve-dynamic` (preexistente).


## 2026-06-12 — Gestión de Estados, Auditoría de Cierre/Suspensión y Optimización Visual de la Bandeja de Proyectos (P0)

Reingeniería del módulo Proyectos. Reglas confirmadas por el usuario (incluida opción b: el modal de justificación también aplica al reactivar/reabrir):
- **Estado "Anulado":** agregado a `PROJECT_STATUSES` y `PROJECT_MANUAL_STATUSES` (`backend/models.py`).
- **Endpoint `PUT /api/projects/{id}/status` convertido a multipart/form-data** (`backend/routes/projects.py`): campos `new_status` (req), `note`, `change_date`, `file` (opcional). Ahora escribe nota corta (compat) + entrada de bitácora `type='status_change'` con `new_status` y `attachments` (anexo guardado vía `save_pdf_dual` en `/uploads/status_changes/{pid}/`). Modelo `ProjectStatusUpdate` eliminado (dead code).
- **Modal de Justificación (`Projects.jsx`):** comentario OBLIGATORIO (botón Confirmar deshabilitado sin texto) + anexo OPCIONAL. Usa `FormData`. Opción "En Gestión (Reactivar)" visible solo para proyectos en estado cerrado/pausado.
- **Toast recordatorio** "Recuerde cerrar el Ticket en el portal" + aviso ámbar dentro del modal al seleccionar Culminado/Anulado.
- **Filtro por defecto "Activos (ocultar cerrados)"** oculta Suspendido/Culminado/Implementado parcial/Anulado. Opción "Todos los estados" disponible.
- **Nueva columna "Envío a Imple"** (`sent_to_implementation_at`).
- **Eliminación ABSOLUTA de "Proceso Irregular":** KPI card (ahora 5 cards), opción de filtro y badge de fila removidos.
- **Validado:** testing_agent iter69 — backend 4/4 pytest (`test_iteration69_project_status_audit.py`), frontend 100% UI. Sin regresiones. Único pendiente: warnings de hidratación `data-ve-dynamic` (cosmético, sistémico, no bloqueante).


## 2026-06-10 — Fix: producto duplicado ("Débito Inmediato") en Productos por Banco (Proyectos Directos)

El usuario reportó que en el reel de Distribución de Cajas (Proyectos Directos), "Débito Inmediato" aparecía duplicado en los bancos que lo tienen (y, en producción, en todos los bancos).

- Causa: el array `products` de un banco podía contener el mismo `product_name` repetido (en preview: Banco de Venezuela, Banco Plaza, Bancaribe tenían un producto duplicado). El frontend renderiza `bank.products` sin deduplicar.
- Backend `routes/banks.py`: nuevo helper `dedupe_bank_products(bank)` que fusiona productos por `product_name` (OR de banderas `vpos/gateway/mpos/link_available`, conserva primer valor no vacío del resto). Aplicado en `get_banks` y `get_bank_detail` (dedup en lectura → ninguna vista muestra duplicados, también en producción tras redeploy).
- Frontend `DirectProjectCreation.jsx`: `reelBankProducts` ahora deduplica por `product_name` (guard defensivo).
- Limpieza de datos (preview): se persistió la deduplicación en 3 bancos (Banco de Venezuela 8→7, Banco Plaza 10→9, Bancaribe 9→8). Verificado: 0 bancos con duplicados; "Débito Inmediato" solo en los 2 bancos que lo tienen (Banco Plaza, R4), no en todos.
- Pendiente producción: el dedup en lectura oculta duplicados, pero si producción tiene "Débito Inmediato" agregado erróneamente como entrada ÚNICA en bancos que no deberían tenerlo, eso requiere limpieza de datos (quitarlo desde la ficha del banco) ya que no es posible saber automáticamente qué bancos deberían tenerlo.


## 2026-06-10 — PDF Payment Gateway: IVA y Total con IVA en la página 3

Requerimiento del usuario: insertar en la página 3 (INVERSIÓN EN SETUP / ARRANQUE) del PDF de la cotización Payment Gateway el valor del IVA y el total después del IVA.

- `services/pdf_generator.py` `generate_pg()` (~L1752): la tabla de setup de la página 3 antes solo mostraba "TOTAL SETUP" (= subtotal sin IVA). Ahora muestra 3 filas de totales: **SUBTOTAL SETUP**, **IVA (16%)** (o **IVA (Exento)** $0.00 según `iva_exempt`) y **TOTAL SETUP (CON IVA)**. La fila de Total con IVA queda resaltada (azul claro); subtotal e IVA con fondo gris. Zebra de detalle ajustada para excluir las 3 filas de totales.
- Validado generando el PDF PG en proceso (5 páginas): IVA 16% → Subtotal $150 / IVA $24 / Total $174; IVA exento → IVA $0 / Total $150.
- Nota: el endpoint `POST /quotes/{id}/regenerate-pdf` falla (500) para cotizaciones antiguas con `pinpad_model`/`sponsor_bank_name` = None (error de validación Pydantic preexistente, ajeno a este cambio) — posible fix futuro: coaccionar None→"" en `regenerate_quote_pdf`.


## 2026-06-10 — Fix: espaciado correo vs Vista Previa + borrado de plantillas

Dos problemas reportados (PREVIEW). Ambos probados por testing_agent (iteration_56): 4/4 PASS.

**1) Espaciado entre líneas (Gmail) ≠ Vista Previa**
- Causa: las plantillas usan `<p>` y `<p></p>`; la Vista Previa usaba `prose prose-sm` (Tailwind, compacto) pero el correo se enviaba como HTML crudo y Gmail aplica márgenes grandes por defecto a `<p>`.
- Backend `services/email_service.py`: nueva `normalize_email_html(html)` que inyecta `style="margin:0 0 10px 0;line-height:1.5"` en línea a cada `<p>` (sin pisar estilos existentes) y envuelve el cuerpo con tipografía base (Arial 14px, line-height 1.5). Aplicada en `send_email` antes del footer.
- Frontend: nueva clase `.email-render` en `index.css` (mismo espaciado). Los contenedores de Vista Previa (`RichTextEditor.jsx` preview body y `EmailPreviewDialog.jsx`) y el canvas del editor (`.ProseMirror p`) usan ahora ese espaciado en lugar de `prose prose-sm`. Vista Previa y correo quedan homologados (margin 0 0 10px, line-height 1.5). [El render real en Gmail no se puede validar automáticamente].

**2) No se podían eliminar plantillas**
- Causa: las plantillas por defecto (semilla) NO existen en BD; al borrarlas `delete_one` devolvía 0 → 404 → "Error eliminando plantilla".
- Backend `routes/seed_and_templates.py`: `delete_email_template` ahora, si la plantilla no está en BD pero es una semilla conocida (PROJECT_EMAIL_TEMPLATES/EMAIL_TEMPLATES_BY_SEDE/DEFAULT_EMAIL_TEMPLATES), registra un tombstone en `deleted_default_templates` y devuelve 200. `get_email_templates` excluye las tombstoned. `create`/`update`/`reset` limpian el tombstone (permite re-agregarlas). `reset` ahora también contempla PROJECT_EMAIL_TEMPLATES.
- Verificado: borrado de plantilla por defecto (`project_notify_bank`) y custom funcionan, desaparecen y no reaparecen tras refrescar.


## 2026-06-10 — Fix URGENTE: variables de Cotización faltaban en el editor de plantillas del MÓDULO PROYECTOS

El usuario seguía sin ver variables de Cotización (ej. `abreviaturas_medios_pago`) en plantillas de Proyectos. **Causa raíz**: el módulo de Proyectos (botón "Plantillas" en `/projects`) usa un editor DISTINTO — `components/projects/TemplatesAdminDialog.jsx` con su PROPIO diccionario `VAR_GROUPS` — separado del editor de `/settings` (`EmailTemplatesEditor.jsx`) que sí se había homologado. `VAR_GROUPS` no tenía ninguna variable de Cotización.

- `TemplatesAdminDialog.jsx` `VAR_GROUPS`: ahora 6 grupos (49 variables). Nuevos: **"Cotización / Ventas"** (Cotizacion_Nro, quote_number, quote_type, total_usd, Monto_Total, invoice_number, approved_date, abreviaturas_medios_pago, Banco_Patrocinador, company_name, sede_name, Nombre_Ejecutivo, Email_Ejecutivo) y **"Despacho / Equipos / Reparación"** (Modelo_Equipo, Cantidad, Modelo_Pinpad, items_table, services_table, Direccion_Entrega, Lista_Seriales, lista_modelos_seriales, lista_equipos_seriales, modelos_resumen, almacen_custodia). Se agregó `Nombre_Fantasia` y `client_address` al grupo Cliente.
- `projectConstants.js` `ALL_TOKENS` (autocompletado al escribir `{` en TemplateBodyEditor): homologado con todas las variables de Cotización.
- `ProjectDetail.jsx`: las 2 listas inline de "Otras Notificaciones" ahora usan `ALL_TOKENS` (homologación automática).
- `EmailPreviewDialog.jsx`: `QUICK_VARS` ahora deriva de `ALL_TOKENS`.
- Probado por testing_agent (iteration_55): 5/5 PASS. Diálogo "Plantillas" de /projects muestra 49 chips en 6 grupos; click en `abreviaturas_medios_pago` inserta `{abreviaturas_medios_pago}`.



El usuario reportó que NO veía variables de Cotizaciones (ej. `abreviaturas_medios_pago`) en las plantillas de Proyectos. Causa: la homologación previa llenó la sección "Variables de esta plantilla" (`getTemplateVariables`), pero el panel categorizado prominente ("Panel de Variables" / `VARIABLE_CATEGORIES`) no listaba esas variables.

- `components/EmailTemplatesEditor.jsx` `VARIABLE_CATEGORIES`:
  - Categoría "Financiero (Ventas)": agregadas `approved_date`, `abreviaturas_medios_pago`, `Banco_Patrocinador`.
  - Categoría "Implementación (Técnico)": agregado alias `Modelo_Pinpad` (ya tenía Matriz_Sucursales y Patrocinador).
  - Nueva categoría "Despacho / Reparación / Equipos" (icono Box): `Modelo_Equipo`, `Cantidad`, `Lista_Seriales`, `lista_modelos_seriales`, `lista_equipos_seriales`, `modelos_resumen`, `almacen_custodia`.
  - `ICON_MAP` ampliado con `Box`.
- Nota: la variable correcta es `{abreviaturas_medios_pago}` (plural). El backend ya la resuelve en proyectos (verificado: `TDC-TDD/C2P/C@mbioP2C`). El panel categorizado es el mismo para Cotizaciones y Proyectos, por lo que ambos cuerpos quedan homologados también en la vista categorizada.

## 2026-06-10 — Homologación de variables Cotizaciones ↔ Proyectos en plantillas

Requerimiento del usuario: inyectar todas las variables de las plantillas de Cotizaciones en las de Proyectos y dejar ambos cuerpos homologados.

- **Backend (núcleo)** `services/project_template_vars.py` → `resolve_project_template_vars`: ahora hace `return {**quote_vars, **variables}`, donde `quote_vars = _build_template_vars(cotización_original or proyecto)`. Para proyectos regulares se construye desde la cotización (`quote_id` en `quotes`); para Proyectos Directos (`dq_*`, sin cotización en `quotes`) cae al propio proyecto (best-effort). Las variables del proyecto tienen prioridad en claves compartidas. Validado: `Cotizacion_Nro` (COT real), `Nombre_Ejecutivo`, `Email_Ejecutivo`, `Monto_Total`, `abreviaturas_medios_pago`, `company_name`, etc., ahora se resuelven en plantillas de Proyectos.
- **Frontend** `components/EmailTemplatesEditor.jsx`: nueva const `HOMOLOGATED_VARS` (unión deduplicada de TODAS las `BASE_TEMPLATE_VARIABLES` + `VARIABLE_CATEGORIES`). `getTemplateVariables` ahora devuelve `baseVars + SHARED_VARS + HOMOLOGATED_VARS` (deduplicado), de modo que el picker "Variables de esta plantilla" muestra el MISMO conjunto (73 variables) en ambos cuerpos. Se corrigió además `Nombre_Fantasia` faltante en `SHARED_VARS`.
- Probado por testing_agent (iteration_54): 5/5 PASS. Plantillas de Proyecto exponen variables de Cotización (Cotizacion_Nro, Nombre_Ejecutivo, Monto_Total, Nombre_Fantasia, abreviaturas_medios_pago) y las de Cotización exponen variables de Proyecto (Nombre_Implementador, Correo_Implementador, Matriz_Bancos_Productos, Lista_VTID). Click inserta placeholder y el hover-preview funciona en ambos. 73 chips idénticos en ambos.


## 2026-06-10 — Ticket flexible (duplicados con confirmación) + Bancos alfabéticos + variable {Nombre_Fantasia}

Tres requerimientos del usuario. Los 3 probados por testing_agent (iteration_53): 3/3 PASS.

**1) Flexibilizar unicidad del Nro de Ticket de Proyecto**
- Antes `PUT /api/projects/{id}/ticket` bloqueaba con error 400 si el ticket ya existía en otro proyecto.
- Ahora: `TicketNumberUpdate.confirm_duplicate: bool = False`. Si el ticket existe en otro proyecto y `confirm_duplicate=false` → HTTP 409 con `detail={code:'ticket_duplicate', existing_client_fantasy, existing_project_number, message}` (incluye el Nombre de Fantasía del cliente del otro proyecto). Con `confirm_duplicate=true` permite guardar.
- Frontend `ProjectDetail.jsx`: `handleSaveTicket(confirmDuplicate)` captura el 409 y abre un `AlertDialog` (`ticket-duplicate-dialog`) con el mensaje y nombre de fantasía; "Sí, asignar de todos modos" reenvía con `confirm_duplicate=true`. (testids: ticket-duplicate-message/cancel/confirm).

**2) Dropdowns de Bancos en orden alfabético**
- `routes/banks.py` `get_banks`: `banks.sort(key=name.casefold())` antes de devolver. Como TODOS los selectores consumen `/banks`, quedan ordenados globalmente (Cotizaciones, Proyectos Directos, etc.). Verificado: 33 bancos alfabéticos.

**3) Nueva variable {Nombre_Fantasia}**
- Carga el campo `fantasy_name` del cliente. Agregada en los 3 motores: `notification_engine.py` y `workflow_notifications.py` (cotizaciones) y `project_template_vars.py` (proyectos), con fallback a la razón social si no hay fantasía.
- Frontend `EmailTemplatesEditor.jsx`: `Nombre_Fantasia` en `SHARED_VARS` (picker de todas las plantillas) + categoría "Cliente" + ejemplo del preview. También añadida a las listas inline de variables en `ProjectDetail.jsx` (2 lugares) y `EmailPreviewDialog.jsx`.

Nota: persisten warnings de hydration preexistentes (`<tr>`/`<span>`/`<tbody>`) NO relacionados — backlog.


## 2026-06-10 — Mini-preview por hover de variables tipo tabla en el editor de plantillas

Mejora solicitada por el usuario. En el editor de Plantillas de Correo (`EmailTemplatesEditor.jsx`, dentro de `/settings`), al pasar el mouse sobre los chips de variables de tipo tabla/HTML aparece una mini-vista previa de la tabla con datos de ejemplo.

- Nueva constante a nivel de módulo `VARIABLE_PREVIEW_HTML` con el HTML de ejemplo de: `Matriz_Bancos_Productos`, `Matriz_Sucursales`, `items_table`, `services_table`.
- Nuevo componente `MiniPreview` que envuelve el chip con `HoverCard` (shadcn `./ui/hover-card`) solo cuando la variable tiene preview; el resto se renderiza igual. Aplicado en el panel categorizado (`master-var-*`) y en "Variables de esta plantilla" (`spec-var-*`). HoverCard expone `data-testid=var-preview-<key>`.
- El clic del chip (insertar/copiar variable) sigue funcionando (HoverCardTrigger asChild no rompe el onClick).
- Dedupe: `openPreview` (vista previa completa) ahora hace spread de `VARIABLE_PREVIEW_HTML` en `exampleValues` en lugar de mantener copias separadas del HTML (atiende comentario de code review sobre drift).
- Probado por testing_agent (iteration_52): 6/6 aserciones PASS (preview de ambas matrices con tabla y datos, variables no-tabla sin preview, clic sigue insertando, sin regresiones).
- Nota: persisten warnings de hydration preexistentes en `/settings` (`<span>` dentro de `<tbody>` / `<tr>` dentro de `<span>`) NO causados por este cambio — quedan en backlog.


## 2026-06-10 — Variables dinámicas de Cotización en plantillas (Matriz_Bancos_Productos, Matriz_Sucursales, Patrocinador)

El usuario reportó que en las plantillas de Cotizaciones no se cargaba `{Matriz_Bancos_Productos}` y pidió que TODAS las variables que dependen de la cotización estén disponibles, en particular las nuevas `{Patrocinador}` y `{Matriz_Sucursales}`.

Causa raíz: los dos motores que renderizan correos de cotización (`notification_engine._build_template_vars` dinámico y `workflow_notifications.py` legacy) no producían esas variables (solo existían en el entorno de Proyectos via `project_template_vars.py`).

- Nuevo helper compartido `services/quote_template_vars.py` → `build_quote_dynamic_vars(quote, client_fantasy, client_legal)`. Reutiliza `_build_matrix_html` y `_build_stores_matrix_html` de `project_template_vars`. Construye:
  - `Matriz_Bancos_Productos`: desde `additional_items` (o fallback `services[item_type=additional]`), agrupado banco→producto con cantidades.
  - `Matriz_Sucursales`: desde `branch_details [{store_name, quantity}]`, con fila Total; fallback a Sede Principal + cantidad_cajas.
  - `Patrocinador`: "Banco - Procesador" si es patrocinada; si no, nombre de fantasía del cliente (mismo criterio que Proyectos).
- Inyectado en ambos motores: `notification_engine._build_template_vars` (captura `fantasy_name` y mergea las 3 vars) y `workflow_notifications.py` (idem). Resuelto end-to-end (verificado con cotizaciones reales).
- Frontend `EmailTemplatesEditor.jsx`: las 3 variables se agregaron a `SHARED_VARS` (con dedupe por key, así aparecen en el picker de TODAS las plantillas sin duplicar las de Proyecto), a la categoría lateral "Implementación (Técnico)" y a los ejemplos del Preview.
- Verificación de gap Cotizaciones vs Proyectos: el resto de variables exclusivas de Proyecto (Nombre/Correo/Telefono_Implementador, Lista_VTID, Modelo_Seriales_*, Servidor_Instalacion, project_number, ticket_number, etc.) son a nivel de Proyecto y no derivan de una cotización; no faltan variables de cotización adicionales.
- Test de regresión: `backend/tests/test_quote_dynamic_vars.py` (5/5 PASS).


## 2026-06-10 — Campo "Bancos o Entes" editable en Item 1 (Suscripción PDV/Banco)

Requerimiento del usuario (Setup del asistente de Cotización). Antes el Item 1 "Suscripción PDV/Banco" mostraba la columna "Bancos o Entes" como SOLO LECTURA (heredaba el número de bancos del header "Bancos/Entes" de la solicitud original). Por dinámica del negocio ahora debe ser editable.

- `QuoteWizardDialog.jsx` (rama `item.inheritBancos` del Setup, ~línea 1392): se reemplazó el `<div>` de solo lectura por un `<Input>` editable (`data-testid=setup-bancos-inherit-<index>`). Default = valor heredado del header. Al editar manualmente un valor distinto, se marca `item.bancosManual=true` (borde/ícono ámbar, override) y se limpia `totalOverride` para recalcular Total (tarifa × cajas × bancos). Si se reescribe el valor del header, vuelve a estado heredado (azul).
- `Quotes.jsx` (useEffect de propagación header→items, ~línea 630): se agregó `&& !item.bancosManual` para que los cambios del header NO pisen una edición manual del Item 1.
- Alcance: solo el Item 1 del Setup. El item recurrente equivalente ("Derecho de uso de plataforma MServer por PDV / Banco") permanece de solo lectura (no estaba en el requerimiento).
- Probado por testing_agent (iteration_51): 7/7 aserciones PASS (editable, herencia default, propagación mientras no hay override, override manual con indicador ámbar, recálculo de Total, header no pisa el override, reescribir valor del header re-hereda).

### Extensión (mismo día) — Recurrente también editable
A solicitud del usuario, se aplicó el MISMO patrón editable al item recurrente "Derecho de uso de plataforma MServer por PDV / Banco" (rama `inheritBancos` de Recurrentes Básicos, `QuoteWizardDialog.jsx` ~L1644, `data-testid=recurring-basic-bancos-inherit-<index>`) y se añadió `&& !item.bancosManual` a la propagación de Recurrentes Básicos en `Quotes.jsx`. Ahora Setup y Recurrente quedan consistentes: ambos heredan por defecto del header y permiten override manual. Mismo patrón ya validado 7/7 para el Setup.



## 2026-06-10 — Destinatarios Dinámicos por Sesión + Acción "Respuesta del Implementador"

Requerimiento de 2 partes (P0). Ambas partes completadas y probadas (backend curl end-to-end + frontend testing agent iteration_50, 100% PASS).

**Parte 1 — Destinatarios Dinámicos por Sesión**
- Dos nuevos tipos de destinatario en los selectores de configuración de notificaciones:
  - `session_user` ("Usuario generador") → el usuario web activo que dispara la acción (sesión `current_user`).
  - `session_executive` ("Ejecutivo generador") → el ejecutivo creador de la cotización/proyecto (`created_by_user_id`).
- Backend `notification_engine.try_dispatch`: resuelve `session_user` desde `current_user` y `session_executive` desde el creador de la cotización (fallback a `Email_Ejecutivo`). Canal inbox válido cuando hay `user_id` interno.
- Backend `other_actions_engine.dispatch_other_action`: nuevo param `executive_user_id`; resuelve ambos tipos; inbox sólo con `user_id`.
- Validaciones relajadas en `routes/action_notifications.py` (client_field/user/session_user/session_executive) y `routes/other_actions_config.py` (user/session_user/session_executive; user_id sólo exigido para type=user).
- Frontend: `ActionNotificationsConfig.jsx` (selector Tipo con 4 opciones; canal disponible para tipos de sesión) y `OtherActionsConfig.jsx` (nuevo selector Tipo con 3 opciones; user_id sólo requerido para "Usuario interno").

**Parte 2 — Acción "Respuesta del Implementador" (id=implementer_response)**
- Registrada en `OTHER_ACTIONS` (`routes/other_actions_config.py`) → aparece en *Configuración de Otras Acciones*.
- Disparador en background en `PUT /api/projects/{id}/ticket` (`routes/projects.py`): helper `_dispatch_implementer_response`. Se dispara sólo en transición de `ticket_number` vacío → valor y cuando el ejecutor es Implementador (admin permitido para QA). Usa `asyncio.create_task` (no bloquea la respuesta). El "Ejecutivo generador" se resuelve al `created_by_user_id` del proyecto.
- Verificado: registrar ticket despachó `sent_count=2` (session_user=quien registra vía email, session_executive=creador vía inbox). Si el admin no configura la acción, `dispatch_other_action` no envía nada (cero regresión).


## 2026-06-10 — Multi-remitente extendido a todas las áreas

A solicitud del usuario, el esquema de remitente por área (que existía solo para Proyectos e Integradores) se amplió a TODAS las áreas que envían correo, configurables desde *Configuración → Remitentes de Correo*.

- Nuevas áreas: **Cotizaciones PYME**, **Cotizaciones Corporativas**, **Comunicaciones a Clientes**, **Contactos Iniciales**, **Nuevos Productos**, **Inventarios** (además de Proyectos e Integradores).
- `email_service.py`: helper `resolve_sender_for_quote(quote)` elige `cotizaciones_corp` o `cotizaciones_pyme` según `client_segment`.
- Cableado: `quote_actions.py` (8 envíos: repair/FT config/repair complete) y `quote_serials.py` usan el remitente de Cotizaciones por segmento; `client_communications.py` → comunicaciones_clientes; `initial_contact_communications.py` → contactos_iniciales; `new_products.py` → nuevos_productos; `inventory.py` → inventarios.
- `settings.py`: `EMAIL_SENDER_AREAS` con las 8 áreas. La UI las renderiza dinámicamente (sin cambios de estructura).
- Verificado: GET lista 8 áreas; asignar Cotizaciones Corp resuelve al alias y PYME al default; 4 tests `tests/test_email_senders.py` (incl. `resolve_sender_for_quote` por segmento). Config dejada vacía (default) hasta que el admin configure direcciones reales.
- Nota de infraestructura (sigue vigente): con Gmail/Workspace, cada dirección debe estar verificada como "Enviar como" o ser alias de la cuenta SMTP autenticada, de lo contrario Gmail reescribe el From.


## 2026-06-10 — Múltiples remitentes de correo por área (multi-sender)

Solicitud: poder enviar desde más de una dirección remitente. Decisión del usuario: mismo dominio @megasoft.com.ve, remitente fijado automáticamente por área (Proyectos e Integradores), administrado solo por Admin.

- `services/email_service.py`: `resolve_sender_for_area(area)` (con caché ~60s e `invalidate_senders_cache`) lee `db.config{type:email_senders}` y devuelve el remitente asignado al área o `SENDER_EMAIL` por defecto.
- `routes/settings.py`: `GET/PUT /api/config/email-senders` (PUT solo Admin). Valida que todas las direcciones pertenezcan al dominio institucional (mismo que SENDER_EMAIL); guarda lista de remitentes + asignaciones por área.
- Cableado: `routes/projects.py` (notificaciones a Cliente/Banco y Otras Notificaciones) usa `resolve_sender_for_area('proyectos')`; `routes/integrators.py` (asignación y nuevo proyecto de integración) usa `'integradores'`.
- Frontend: nueva página `EmailSendersConfig.jsx` (`/settings/email-senders`) + tarjeta Admin en Settings. Gestión de direcciones (etiqueta/correo/activo) y selector de asignación por área.
- Verificado: GET/PUT (incl. rechazo de dominio ajeno 400), resolver (3 tests `tests/test_email_senders.py`), y E2E real — una notificación de Proyectos salió desde el remitente asignado (registrado en `email_logs`). Config de prueba reseteada a vacío (default) para no forzar buzones inexistentes; el admin define las direcciones reales en la UI.


## 2026-06-09 — Descuentos en PDF de cotizaciones Corporativas

Solicitud: en cotizaciones de clientes Corporativos, reflejar en las matrices de Setup y Recurrente el % de descuento y el monto calculado, restándolo del total (antes no aparecían en el PDF).

- `services/pdf_generator.py`: `_create_items_table` ahora acepta `discount_pct`. Cuando hay descuento, el bloque de totales muestra: Subtotal → **Descuento (X%)** (monto negativo, resaltado en verde) → **Subtotal Neto** → IVA (16%, calculado sobre el neto) → Total. `generate_vpos_corp` (Página 4) pasa `descuento_setup` y `descuento_recurrente` a las tablas SETUP y RECURRENTES MENSUALES.
- El frontend ya enviaba `descuento_setup`/`descuento_recurrente` en `pdf_data` (`buildTemplatePdfData`) y la descarga los lee del registro, por lo que el descuento aparece tanto en vista previa como en el PDF descargado.
- Verificado: render de Página 4 muestra Setup $318→-$31.80(10%)→$286.20 neto→IVA $45.79→Total $331.99 y Recurrente con 5%. Tests: `tests/test_corp_quote_discount_pdf.py` (2 passed). Sin cambios para PYME (default `discount_pct=0`).


## 2026-06-09 — Nuevas variables de plantillas de Proyectos

Solicitud: crear variables para Nombre/Email del Implementador y una Matriz de Sucursales.

- **`{Nombre_Implementador}`** y **`{Correo_Implementador}`**: YA existían (resueltas desde el usuario asignado al proyecto). Se confirmaron operativas.
- **`{Matriz_Sucursales}` (NUEVA):** tabla HTML con columnas *Sucursal* y *Cantidad de Cajas* por cada sucursal del proyecto (+ fila Total si hay más de una). Fallback a Sede Principal/cajas de servicios para proyectos PYME sin sucursales explícitas.
  - Backend: `services/project_template_vars.py` — helper `_build_stores_matrix_html()` + clave `Matriz_Sucursales` en `resolve_project_template_vars`. Registrada en `template-variables` y excluida del panel plano de variables (como `Matriz_Bancos_Productos`).
  - Frontend: agregada a los chips de variables de "Otras Notificaciones" y Notificaciones a Bancos/Clientes, al picker de `TemplatesAdminDialog`, a `ALL_TOKENS` (projectConstants) y al `exampleValues` de `RichTextEditor` (preview en editor).
- Verificado por curl: `Matriz_Sucursales` aparece en available_tags y `preview-adhoc` la renderiza como tabla (token reemplazado).


## 2026-06-09 — Adjuntos en Notificaciones a Bancos/Clientes (iter49)

Extensión solicitada: agregar Cargar Archivos / Cargar Imágenes / Adjuntar Matriz al flujo de Notificaciones a Cliente/Banco (antes solo en "Otras Notificaciones"). Verificado: testing agent iter49 100% frontend + backend por curl (envío real status 'sent' con adjunto + matriz).

- `projects.py`: `POST /projects/{id}/send-notification` convertido a **multipart** (Form + `files` + `attach_matrix`). Helper `_send_sequential_notification` ahora acepta `extra_attachments` (los adjunta al correo vía `send_email`) y `attach_matrix` (agrega la tabla de la matriz al cuerpo HTML). Los adjuntos se guardan en `uploads/notif_emails/{id}` y se registra `attachments_count` en el historial.
- `ProjectDetail.jsx`: estado `notifFiles`/`notifAttachMatrix` + `notifFileInputRef`; panel `notif-attachments-panel` en el modal de notificaciones (botones `notif-attach-files-btn`, `notif-attach-images-btn`, `notif-attach-matrix-btn`). `sendNotification` y el camino Vista Previa→Enviar (`sendFromPreview`, rama sequential) ahora usan FormData multipart para propagar adjuntos + matriz + `to_override`/`template_id`.


## 2026-06-09 — Paquete multidominio: Contactos, Canal Gateway, Mensajería, Branding (iter48)

Verificado E2E (testing agent iter48: 9/9 backend, frontend 100%). Tests: `/app/backend/tests/test_iter48_meganexus_package.py`.

### A) Bug fix — Canal de Cotizaciones Gateway Corporativo
- `quotes.py`: nuevo helper `_resolve_client_segment(client_id, quote_type, fallback)`. Para `GATEWAY`/`LINK_PAGO` el segmento se hereda de la ficha del CLIENTE (`segment='Corporativo'` → `CORP`), no de la sede del ejecutivo. Aplicado en `create_quote` y `create_quote_with_pdf`. Solo afecta cotizaciones NUEVAS (sin migración de históricas).

### B) Borrado masivo/selectivo en Centro de Mensajes
- `inbox.py`: nuevo `POST /api/inbox/batch-delete` (soft-delete por `message_ids`, aislado por usuario).
- `InboxCenter.jsx`: checkbox por fila (`inbox-select-{id}`), 'Seleccionar todo' (`inbox-select-all`), barra con botón papelera (`inbox-bulk-delete-btn`, activo solo con ≥1 selección) y modal de confirmación con conteo (`inbox-bulk-delete-dialog`).

### C) Edición admin-only en 'Contacto Inicial'
- `initial_contacts.py`: nuevo `PUT /api/initial-contacts/{id}` (RBAC: solo admin → 403 a otros). Edita contacto/empresa/teléfono/email/sede/notas, valida sede, registra traza en `bitacora` (action='edited' con deltas).
- `InitialContacts.jsx`: botón 'Editar' (`edit-btn-{id}`) visible solo si `role==='admin'` + modal `edit-contact-modal`.

### D) Homologación de 'Otras Notificaciones'
- `ProjectDetail.jsx`: el modal adhoc se rediseñó para clonar el look & feel del flujo de Notificaciones a Bancos/Clientes (tabla de contactos con checkboxes + 'Seleccionar todos', tarjeta azul de composición, chips TO, input de correo manual, selector de plantilla que carga `body_html`, editor enriquecido con `tableRowActions`, variables colapsables). **Se conservaron** las capacidades potentes: Cargar Archivos, Cargar Imágenes y Adjuntar Matriz de Distribución.

### E) Branding white-label
- `public/index.html`: título → `CRM Gestor - Mega Soft`; removido el badge 'Made with Emergent' (`#emergent-badge`) y meta description actualizada.

### Nota / bug colateral corregido
- Al añadir el PUT de edición se había borrado por accidente el decorador `@router.post('/initial-contacts/{id}/assign')`; el testing agent lo restauró. Verificado.
- Pendiente opcional (sugerido por el usuario): agregar Cargar Archivos/Imágenes/Matriz también al flujo de Notificaciones a Bancos/Clientes (requiere cambios en `send-notification` backend).


## 2026-06-09 — Manejo de Proyectos: 4 requerimientos Frontend (iter47)

Backend ya estaba listo (sesiones previas). Esta sesión implementó el Frontend y validó E2E (testing agent iter47: 5/5 backend + flujos frontend al 100%).

### T1 (P0) — Bug "Otras Notificaciones": cuerpo en blanco al elegir plantilla
- `ProjectDetail.jsx`: `handleTemplateSelect` ahora lee `tpl.body_html || tpl.body || ''` (antes leía `tpl.body`, vacío para plantillas de proyecto).
- Reemplazado el `<Textarea>` del mensaje por `<RichTextEditor>` (data-testid `email-message`), con `maxChars=20000`, `hardLimit={false}`. Removido el límite legacy de 1000 caracteres en `handleSendAdhocEmail`. El backend ya respeta el HTML vía `_adhoc_message_to_html`.

### T2 (P1) — Botón global "Plantillas" en `Projects.jsx`
- Montado `TemplatesAdminDialog` + estado/funciones (emailTemplates, fetchTemplates, openTemplatesAdmin, handleSaveTemplate, handleDeleteTemplate) en `Projects.jsx`.
- Botón en cabecera (data-testid `projects-templates-btn`) gated por `canEdit` (admin o usuarios con edición total en proyectos), según decisión del usuario.
- Se DEJÓ también el botón en el Detalle del Proyecto (`manage-templates-btn`) — el usuario pidió mantenerlo en ambos.

### T3 (P1) — Descarga de Ficha Técnica
- `ProjectDetail.jsx`: nuevo botón en cabecera (data-testid `download-ficha-tecnica-btn`) + handler `downloadFichaTecnica` que hace `GET /api/projects/{id}/ficha-tecnica` con `responseType: 'blob'` y dispara la descarga del PDF.

### T4 (P1) — Multiselect de medios de pago en Actualización Masiva
- `BatchUpdateModal.jsx`: el producto único (string) pasó a checkboxes múltiples (`batch-products-list`, `batch-product-checkbox-{prod}`) dependientes del banco seleccionado.
- `ProjectDetail.jsx`: estado `batchProduct` → `batchProducts` (array), `toggleBatchProduct`, `handleBatchBankChange` (preselecciona todos los medios del banco). Payload envía `product_names` (array) al endpoint que ya lo soporta.

### Notas
- Las URLs de preview viejas del handoff están dormidas; URL correcta del entorno: `https://quote-overhaul.preview.emergentagent.com`.
- Pendiente opcional (a11y polish): agregar `<DialogDescription>` a `templates-dialog` y `batch-update-dialog`. Hydration warnings preexistentes del instrumentador (no del código).


## 2026-06-09 — Borrado de filas "fricción cero" en {Matriz_Bancos_Productos}

### Requerimiento
Eliminación ágil de filas de la matriz dentro del editor de notificación: icono de
papelera por fila, hover en rojo, un solo clic sin confirmación, transición suave,
borrado local/efímero (jamás la BD), y HTML limpio (sin la papelera) en el correo.

### Implementación (`RichTextEditor.jsx` + `index.css`)
- Nueva extensión ProseMirror `TableRowActions` (activada por prop `tableRowActions`):
  - **Widget decorations**: una papelera (`matrix-row-delete`) por fila de datos —
    nunca se serializa en `getHTML()`, por lo que no viaja en el correo.
  - **Scope a la matriz**: solo decora la tabla cuyo encabezado contiene
    "Producto / Servicio" (no las tablas de Datos del Cliente/Banco/Implementación);
    excluye la fila de encabezado.
  - **Borrado fiable vía event delegation** (`handleDOMEvents.mousedown`): el handler
    resuelve el rango PM de la fila **síncronamente** (posAtDOM sobre la última celda,
    sin widget) y lo captura en closure; tras 160 ms de transición despacha
    `tr.delete(from, to)`. Esto resolvió 4 causas raíz sucesivas (listener del widget
    recreado por PM, `posAtDOM(tr)=-1`, `trEl` huérfano post-recomposición).
  - CSS global (`.rte-actions`): gutter para la columna de acción, hover de fila en
    rojo (#ef4444), animación `rte-row-removing`.

### Verificación
- Testing agent iter46: **frontend 100% de criterios críticos**, `retest_needed:False`.
  Borrado 3→2→1, scope solo matriz (3 papeleras), hover rojo, un clic sin diálogo,
  sin errores de consola, integridad de BD (recarga→3 filas), Vista Previa con solo
  las filas conservadas. Iteraciones 42-45 documentan la depuración del borrado.


## 2026-06-09 — {Matriz_Bancos_Productos} editable + variable {Patrocinador}

### Requerimiento
(A) Corregir que `{Matriz_Bancos_Productos}` no se poblaba; (B) hacerla editable en
el editor enriquecido de la notificación (editar celdas + eliminar fila), local sin
tocar la BD; (C) nueva variable condicional `{Patrocinador}`.

### Implementación
- **Backend (`project_template_vars.py`)**: nueva variable `{Patrocinador}` — si el
  proyecto es patrocinado (`sponsored_implementation` + `sponsoring_bank_name`) →
  `Banco` o `Banco - Procesador`; si no → Nombre de Fantasía del cliente (fallback a
  nombre/razón social).
- **Backend (`projects.py`)**:
  - **Bug fix crítico** en `_clean_html_in_braces`: el limpiador consumía etiquetas HTML
    adyacentes a las variables, corrompiendo tablas que seguían a una variable
    (ej. `{Patrocinador}<table>`). Reescrito para limpiar solo DENTRO de las llaves.
  - `_style_email_tables`: re-aplica bordes email-safe a tablas sin estilo (la matriz
    editada en TipTap pierde estilos inline). Aplicado en send y preview.
- **Frontend (`RichTextEditor.jsx`)**: añadido `TableKit` (@tiptap/extension-table) →
  las tablas se renderizan y editan; toolbar con "Agregar fila"/"Eliminar fila"; CSS de
  tabla; `StarterKit` con `link:false, underline:false` (evita duplicados en TipTap v3);
  re-render de toolbar en `selectionUpdate`/`transaction` (v3 no re-renderiza solo).
- **Frontend (`ProjectDetail.jsx`)**: `injectMatrix()` sustituye el token
  `{Matriz_Bancos_Productos}` por la tabla real (matrix_html de `/template-variables`) al
  abrir/cambiar plantilla, volviéndola editable in-situ. Chips `{Patrocinador}` añadidos.
- **TemplatesAdminDialog**: `{Patrocinador}` agregado al diccionario de variables.

### Verificación
- 15 pytest PASS (incl. `tests/test_matrix_and_patrocinador.py`).
- Testing agent Iter40 (backend 100%) + Iter41 RETEST frontend 100% (8/8): matriz
  renderiza como tabla poblada, controles de tabla presentes, eliminar/editar fila
  funcionan, preview con tabla modificada, sin warning de duplicados. `retest_needed:False`.


## 2026-06-09 — Plantilla Preferida + Texto Enriquecido en Notificaciones de Proyecto

### Requerimiento
Migrar las notificaciones de Manejo de Proyectos al motor de Texto Enriquecido y
precargar la "Plantilla Preferida" por destino al abrir cada uno de los 3 botones
(Cliente / Banco / Cliente+Banco), manteniendo el dropdown activo para override.

### Implementación
- **Backend (`projects.py`)**:
  - `_resolve_notification_email(..., override_template_id)`: la plantilla seleccionada
    controla asunto y cuerpo en las 3 ramas (client/bank/bank_client). El prefijo por
    conteo (`[Primer Envío]`, etc.) se conserva.
  - `_get_notification_template`: resuelve la plantilla desde la BD o desde los defaults
    de Proyecto (Texto Enriquecido).
  - `send-notification` y `preview-notification` aceptan `template_id` + `custom_html`
    (cuerpo editado) y re-renderizan variables `{Variable}`.
  - **Preferencias por destino** en `db.config` (`type='project_notification_preferences'`):
    `GET/PUT /api/project-notification-preferences` (solo una preferida por destino).
- **Backend (`seed_and_templates.py`)**: `GET /api/email-templates?context=IMPLEMENTACION`
  ahora incluye las plantillas de Proyecto por defecto (`project_notify_*`).
- **Frontend (`ProjectDetail.jsx`)**: el modal de notificación secuencial ahora trae un
  Dropdown de plantillas (`notif-template-select`) precargado con la preferida (badge
  `★ Preferida`), un editor enriquecido editable (`notif-body-editor`) que se actualiza al
  cambiar de plantilla, y un botón `Marcar preferida` (`mark-preferred-btn`). Vista Previa
  y Enviar usan el contenido del editor + `template_id`.

### Verificación
- 5 pytest `tests/test_project_notification_preferred.py` PASS.
- Testing agent Iter39: backend 100% (5/5 unit + 7/7 HTTP e2e), frontend 100% en flujos
  validados (modal único Cliente+Banco, dropdown, cambio de plantilla actualiza editor,
  marcar preferida persiste y se precarga al reabrir). Sin bugs críticos/menores.

### Nota
- En proyectos con UN solo banco, el botón "Notificaciones a Cliente" (`notifications-btn`)
  se reemplaza por "Notificación Única (Cliente y Banco)" (`notif-bank-client-btn`) — diseño
  preexistente. Warnings de hidratación `data-ve-dynamic` son preexistentes (plataforma).


## 2026-06-09 — P0 Homologación + Aislamiento RBAC del Motor de PDF (Opción A)

### Requerimiento
Previsualizar, Exportar y Guardar deben generar EL MISMO PDF para todos los modelos
(VPOS, MPOS, Payment Gateway, Link de Pago), independientemente del RBAC del usuario.
Antes, usuarios con permisos limitados no cargaban catálogos en el frontend →
`buildTemplatePdfData` enviaba nombres vacíos → PDFs con campos en blanco.

### Solución (server-side desde IDs)
- **`pdf_generator.py`**: `TemplateQuotePDFRequest` ahora acepta IDs opcionales
  (`client_id`, `integrator_id`, `pinpad_id`, `sponsor_bank_id`, `sponsor_processor_id`).
- **`quotes.py`**: nueva función única `hydrate_pdf_request(data)` que resuelve los
  nombres AUTORITATIVOS desde Mongo (`clients`, `integrators`, `hardware`, `banks`)
  usando los IDs. Se invoca en los 3 disparadores: `preview-pdf-with-template`,
  `generate-pdf-with-template` y `create-with-pdf` (rama `data.pdf_data`, con relleno
  de IDs desde el top-level de la cotización).
- **`Quotes.jsx`**: `buildTemplatePdfData` ahora incluye SIEMPRE los IDs en el payload
  (además de los nombres como fallback legacy).

### Verificación
- 4 pytest unitarios `tests/test_pdf_hydration_rbac.py` (hidratación, convergencia
  admin==RBAC, no-op sin IDs, etiqueta "Sin integrador") → PASS.
- E2E: payload con nombres VACÍOS + IDs → PDF contiene cliente/banco/integrador/pinpad reales.
- Previsualizar vs Exportar: 9 páginas, texto idéntico (difieren solo en IDs internos de
  subset de fuentes de ReportLab, invisibles para el usuario).
- Testing agent Iter38: backend 7/7, frontend smoke OK, sin regresiones, `retest_needed:false`.

### Pendiente menor (cosmético, fuera de alcance P0)
- `create-with-pdf` puede retornar `client_name` con commercial vs legal_name en el JSON
  (el PDF sale correcto). Warning de hidratación `data-ve-dynamic` en QuotesTable (preexistente).


## 2026-06-08 — FIX PDF Payment Gateway: recurrentes + paridad Guardar/Previsualizar/Exportar

### Bugs reportados
1. La tabla de "Costos Recurrentes Mensuales" NO se insertaba en el PDF al GUARDAR.
2. El PDF al Guardar difería del de Previsualizar y Exportar (versiones distintas).

### Causa raíz
- `handleSubmitPGQuote` (Quotes.jsx) enviaba `pdf_data: null` a `create-with-pdf`, cayendo en
  la rama backend MÍNIMA (custom, sin la tabla rica) en vez de la rama canónica `data.pdf_data`.
- Previsualizar y Exportar construían cada uno su propio `pdfData` con campos distintos
  (Preview sin `branch_details`/`(vinculado a)`; etc.) → 3 PDFs diferentes.

### Fix (frontend, DRY)
- **Nuevo `buildTemplatePdfData(quoteNumber)`** en Quotes.jsx: único builder del payload
  `TemplateQuotePDFRequest` (incluye `pg_recurring_cost.rangos` desde `getPgFullRecurringTable()`).
- **Guardar** ahora envía `pdf_data: buildTemplatePdfData('')` → cae en la rama canónica del
  backend (DynamicQuotePDFGenerator + append_pg_static_pages + stamp).
- **Previsualizar** y **Exportar** reusan el mismo `buildTemplatePdfData()` → eliminan el drift.

### Verificación (curl + extracción de texto del PDF + testing agent iter37)
- PDF guardado, preview y export: los TRES contienen "COSTOS RECURRENTES MENSUALES".
- Preview y Export: **bytes idénticos** (1,058,188), 8 páginas → output idéntico garantizado.
- UI: Previsualizar retornó 200, 0 errores de runtime tras el refactor.

### Nota
- Deuda de lint pre-existente en Quotes.jsx (react-hooks/immutability, set-state-in-effect) NO
  relacionada con este cambio; la app compila OK (webpack). Pendiente refactor dedicado.



## 2026-06-08 — FIX bug fantasma "(failed)" al crear cotizaciones (PG + Reparaciones)

### Causa raíz (confirmada por testing agent iter34-36)
- El POST create-with-pdf se mostraba "(failed)" / `net::ERR_ABORTED` a ~1.12s aunque el
  **backend SÍ creaba la cotización** (~2s, atómico server-side).
- **Disparador:** `frontend/src/utils/api.js` → ante un 401 en CUALQUIER endpoint
  concurrente (notifications/inbox polling, WS), `handleSessionExpired` ejecutaba
  `window.location.href='/login'` a los 600ms → **navegaba y abortaba el XHR del submit en vuelo**.
- El `toast.error` genérico hacía creer al usuario que falló → reintentaba → duplicados (COT-038..043).

### Fixes aplicados (frontend)
1. **`api.js`**: contador `inFlightCritical` (`markCriticalStart/End`, regex de endpoints
   críticos). `redirectWhenIdle` **difiere** `window.location.href='/login'` hasta que terminen
   los POST críticos (create-with-pdf / generate-equipment-pdf) o pasen 15s → ya no aborta el submit.
2. **`EquipmentQuoteWizard.jsx`**: el `fetch` de generate-equipment-pdf se envuelve con
   `markCriticalStart/End` (mismo blindaje para Reparaciones).
3. **Mensajes claros**: en `Quotes.jsx` y `EquipmentQuoteWizard.jsx`, si `!error.response`
   (conexión interrumpida) → `toast.warning('...la cotización pudo haberse creado, verifique el listado')`
   en vez del error engañoso, + refresco automático.
4. **Botón recurrentes**: `QuoteWizardDialog.jsx` L1218 — la sección "Costos Recurrentes" y su
   botón ahora aparecen con `isPaymentGateway && isHeaderComplete && pgRecurringCostsTable`
   (sin requerir setup items); el botón queda deshabilitado con hint si no hay medios de pago.

### Pendiente / recomendación
- 401 intermitentes durante sesión activa → revisar TTL del JWT / refresh proactivo (cambio de
  auth — requiere integración dedicada).
- Opcional: usar `navigate()` de react-router en vez de `window.location.href` para no abortar
  tampoco los XHR no críticos.



## 2026-06-08 — Cont. BUGFIX Cotizaciones + diagnóstico mejorado

### Fix backend confirmado (repair con modelos)
- `quotes.py` L1833: `{total_units}` → `{_total_units}` (NameError → 500). Verificado 200+PDF.

### Diagnóstico del "error fantasma" (PG y Reparaciones)
- Evidencia DIRECTA del navegador (testing agent Iter34): frontend y backend son **same-origin**
  en el preview → **NO es CORS**. POST /api/quotes/create-with-pdf [GATEWAY] devuelve **200**
  desde el navegador real (crea la cotización). El backend tiene éxito en ambos endpoints.
- **Causa del mensaje de error visible:** los `catch` del frontend mostraban mensajes genéricos
  ("Error al crear cotización Payment Gateway" / "Verifique su conexión") que **ocultaban el
  error real** del backend (un 4xx/5xx o una excepción JS al procesar la respuesta/descarga).
- **Fix aplicado:** ambos `catch` ahora exponen el detalle real:
  - `Quotes.jsx` handleSubmitPGQuote → `error.response?.data?.detail || error.message`.
  - `EquipmentQuoteWizard.jsx` → `error.message` (revela TypeError o interrupción de transferencia).
- Deuda técnica conocida: CORS `allow_origins=['*']` + `allow_credentials=True` (inválido por spec,
  pero inofensivo mientras sea same-origin). Considerar `allow_origin_regex='.*'`.



## 2026-06-08 — BUGFIX P0: Creación de Cotizaciones Reparaciones (y verificación PG)

### Bug crítico Reparaciones (reportado en producción) ✅ FIXED
- **Causa raíz:** `backend/routes/quotes.py` línea 1833 — la f-string del resumen por
  modelo usaba `{total_units}` pero la variable definida (línea 1816) es `_total_units`
  → `NameError` en runtime → HTTP 500 al crear cotización de Reparación CON `repair_models`
  (POST /api/quotes/generate-equipment-pdf). El path legacy (bulk_serials) no entraba al
  bloque y por eso no fallaba.
- **Fix:** `{total_units}` → `{_total_units}`. Verificado: 200 + application/pdf con y sin repair_models.
- Test regresivo: `/app/backend/tests/test_quotes_critical_fix.py` (3/3 PASS).
- Testing agent Iter33: backend 3/3 pytest, frontend 10/10 smoke. Sin 5xx.

### Payment Gateway — verificado sin bug propio en preview
- POST /api/quotes/create-with-pdf con quote_type=GATEWAY crea cotización + PDF (200) en preview.
- El error de PG en producción fue probablemente colateral del 500 de Reparaciones o ya resuelto.
  Requiere **redeploy** para llevar el fix a producción.



## 2026-06-08 — Reel mejorado + verificación Patrocinante (Iter32)

### Reel de Distribución — mejoras UX (Proyectos Directos) ✅
- Nuevo campo "Número de cajas (por producto)" (`dp-reel-quantity`): se precarga con la
  "Cantidad de Cajas" de la cabecera y se sincroniza mientras no se edite manualmente
  (`reelQtyTouched` useRef); editable por lote.
- Botón "Seleccionar todos / Quitar todos" (`dp-reel-select-all`).
- "Agregar al Reel" ahora crea UNA línea por cada producto marcado, cada una con el
  número de cajas indicado (sin merge). Tras agregar, limpia la selección y mantiene el
  banco para continuar el siguiente lote.
- Testing agent Iter32: 13/13 frontend PASS.

### Verificación "Banco Patrocinante" (Definición Comercial) ✅ (sin bug en preview)
- Reproducción E2E (UI→API→DB→ProjectDetail): al elegir Procesador y banco vinculado,
  se guarda `patrocinador_label = "Procesador — Banco"` y se muestra completo en la Ficha
  Técnica (`project-detail-patrocinador`) y en el PDF ("Patrocinador de la Implementacion").
  No se detectó bug en preview. Si persiste en producción → requiere redeploy (código stale/caché).


## 2026-06-08 — Ajustes Proyectos Directos + Mapeo Tipo de Proyecto (Iter31)

### 1. Mapeo "Tipo de Proyecto" en Ficha Técnica (PDF) — P0 ✅
- `backend/services/implementation_pdf.py` (~141-156): nuevo mapeo determinístico por `quote_type.upper()`.
  Valores SEPARADOS por tipo (ya NO existe "VPOS / MPOS" combinado):
  - VPOS → VPOS · MPOS/FAST_TRACK → MPOS · GATEWAY → Payment Gateway
  - LINK_PAGO/LINK → Link de Pago · VPOS_MPOS (legacy) → VPOS
- La UI (`ProjectDetail.jsx` ~979) ya mapeaba correcto; solo el PDF tenía el combinado.
- Test: `/app/backend/tests/test_iter31_implementation_pdf_type_mapping.py` (8/8 PASS).

### 2. Modelo de Pinpad en carga de seriales (Proyectos Directos) — P0 ✅
- `DirectProjectCreation.jsx` `doSubmit`: `payload.pinpad_serials` mapea cada serial
  heredando `form.pinpad_model` cuando la fila no trae modelo. Cubre las 3 vías
  (Excel, lote TextArea, manual). La Matriz de Seriales de la Ficha Técnica ya
  muestra `pp.modelo` (ProjectDetail ~1237) y el PDF (`implementation_pdf.py` ~219).

### 3. Reel de Distribución — UX tipo Cotizador (multiselect por banco) — P1 ✅
- `DirectProjectCreation.jsx`: nuevo panel `dp-reel-selector` (Select de Banco +
  checkboxes de productos disponibles filtrados por tipo de proyecto + botón
  "Agregar al Reel" `dp-reel-add-selected`). Permite agregar múltiples productos a la vez.
  Merge automático de duplicados banco+producto (suma quantity).
- `boxes_grid` ahora inicia vacío (`[]`); grilla muestra filas Banco/Producto como texto,
  Cantidad editable y botón eliminar. Estructura enviada al backend `boxes_grid` intacta.
- Removido `productsForBank` y `addBoxRow` (sin uso). Lint limpio.

### Estado
- Testing agent Iter31: backend 100% (8/8 pytest), frontend Reel 100% (6/6). Sin regresiones.
- Warning de hydration en /direct-projects es preexistente (wrapper `data-ve-dynamic` de plataforma).

### Deuda técnica pendiente
- `DirectProjectCreation.jsx` > 1200 líneas → considerar split (HardwareCard, ReelCard, TechConfigCard).
- `QuoteWizardDialog.jsx` > 2300 líneas → fragmentar por fases.

## 2026-06 — Paridad absoluta de variables en editores de plantillas (P0)
- Creado `/app/frontend/src/components/email/templateVariables.js` como FUENTE ÚNICA DE VERDAD:
  exporta `VARIABLE_CATEGORIES` (6 grupos, 67 variables), `VARIABLE_ICON_MAP` y `VARIABLE_PREVIEW_HTML`.
- `EmailTemplatesEditor.jsx` (Configuración) y `projects/TemplatesAdminDialog.jsx` (Proyectos)
  ahora importan el catálogo compartido; se eliminaron las listas locales duplicadas/desfasadas
  (`VARIABLE_CATEGORIES` y `VAR_GROUPS`).
- Se agregaron 3 variables que faltaban: `Nro_Proyecto`, `Tipo_Proyecto`, `Fecha_Asignacion`.
- Resultado (Testing agent Iter57): paridad EXACTA 100% — 67 chips idénticos en ambos paneles,
  mismos 6 grupos y mismo orden. Cualquier variable nueva debe agregarse SOLO en templateVariables.js.

## 2026-06 — Buscador de variables + inserción según cursor (mejora UX)
- Ambos editores de plantillas (Configuración y Proyectos) tienen ahora un BUSCADOR
  que filtra los chips por key/label/categoría (data-testid `master-var-search` y `var-search`),
  con mensaje "sin resultados" cuando no hay coincidencias.
- INSERCIÓN POR CURSOR: la variable se inserta en el campo activo (Asunto o Cuerpo) en la
  posición exacta del cursor. Antes siempre caía en el cuerpo.
  - Configuración: `activeField` controlado por onFocus de subject/body (textarea + input).
  - Proyectos: subject Input (id `project-tpl-subject`) + `onFocusCapture` sobre el wrapper
    del RichTextEditor (TipTap). `insertVar()` inserta en asunto (selectionStart) o en el
    editor TipTap (insertText en el cursor).
  - Indicador visual "Insertando en: Asunto/Cuerpo" en ambos paneles.
- Verificado por testing agent (Iter58): 100% frontend. Paridad 67 vars/6 grupos intacta.

## 2026-06 — Reingeniería del Ciclo de Vida de Proyectos (P0)
- **Nuevo catálogo de estados** (reemplaza al anterior): Por asignar · Asignado · En Gestión · Suspendido · Implementado parcial · Culminado. `models.PROJECT_STATUSES` + `PROJECT_MANUAL_STATUSES`.
- **Máquina de estados (automatización)**:
  - Creación (cotización y directo) → 'Por asignar' (o 'Asignado' si la ficha del cliente trae Implementador).
  - Asignar Implementador → 'Asignado' (mantiene 'En Gestión' si ya hay ticket — regla de reasignación).
  - Guardar Nro de Ticket → 'En Gestión' (respeta estados manuales).
  - Manuales: Suspendido / Implementado parcial / Culminado (botón 'Cambiar estado', solo estas 3).
- **Auditoría de queries**: dashboard counts, filtros de grilla/stats, reportes HTML, `sponsor_reports.py`, `notification_scheduler.py` (assigned-not-started='Asignado', stalled='En Gestión'), bulk-reassign.
- **Migración de datos**: `scripts/migrate_project_statuses.py` ejecutado → 76 proyectos remapeados (20 Por asignar, 35 Asignado, 21 En Gestión).
- **Nueva variable {Estado_Proyecto}**: en diccionario compartido (Cotizaciones + Proyectos), `project_template_vars.py` y `notification_engine.py` (busca proyecto por quote_id). Inyecta texto plano del estado.
- **Bug fix Vista Previa (EmailPreviewDialog)**: el cuerpo era contentEditable con `dangerouslySetInnerHTML`; cualquier re-render (p.ej. editar Asunto) re-aplicaba el HTML original y borraba ediciones. Fix: `innerHTML` imperativo vía useEffect SOLO cuando cambia el html de origen (lastHtmlRef). Las ediciones del cuerpo ahora persisten al editar el Asunto.
- Frontend: `Projects.jsx` (STATUS_CONFIG, STATUS_TRANSITIONS, matchStatus, stats chips), `ProjectDetail.jsx` (badge), `BulkReassignModal.jsx`, `templateVariables.js`.
- Verificado: testing agent Iter59 → backend 9/9 pytest, frontend validado. Sin regresiones.

## 2026-06 — Fix Vista Previa (cuerpo vacío) + prefijo al final del asunto
- **Bug Vista Previa (EmailPreviewDialog):** el fix imperativo anterior (useEffect+innerHTML) dejaba el cuerpo VACÍO al abrir. Cambiado a `key={sourceHtml}` + `dangerouslySetInnerHTML={{__html: previewData.html}}`: el contenido se muestra al abrir/regenerar la vista previa, y como editar el Asunto NO cambia `previewData.html`, React no re-monta el contentEditable → las ediciones manuales del cuerpo persisten.
- **Prefijo de secuencia al FINAL del asunto:** en notificaciones a Cliente y Banco, '[Primer Envío]'/'[Primer Recordatorio]'/etc. ahora se concatena al final: `f"{raw_subject} [{prefix_label}]"` (client, bank_client, bank — ramas plantilla y fallback en projects.py L716-838).
- Verificado: testing agent Iter60 → backend 3/3 API, fix de UI confirmado por revisión de código.

## 2026-06 — Optimización de latencia de escritura (Multitienda + Instrucciones)
- **Causa:** el estado vivía en Quotes.jsx (componente enorme); cada tecla en inputs controlados por el padre re-renderizaba todo el modal QuoteModals → latencia.
- **Fix Multitienda:** nuevos componentes memo a nivel de módulo en QuoteModals.jsx:
  - `MultistoreRow` (filas heredadas editables): estado LOCAL + debounce 200ms en el nombre + flush en blur; ref extName/extBox evita reset por sync.
  - `MultistoreAddForm` (agregar tienda): estado LOCAL, propaga al padre solo al Agregar/Enter (callback `appendStore`).
  - Handlers estables `commitStore`/`removeStore`/`appendStore` (functional updates).
- **Fix Instrucciones (Enviar a Implementación):** `handleInstrChange` propaga al padre con debounce 250ms (cache en `implLatestRef`) + `flushInstr` síncrono en `onBlur` del contenedor del RichTextEditor → escribir ya no re-renderiza el modal por tecla y no se pierde texto al continuar.
- Verificado: testing agent Iter61 → 100% frontend, funcionalidad intacta, sin pérdida de datos.
- Deuda técnica menor: `addMultistoreStore`/`multistoreNewStore` en Quotes.jsx quedaron obsoletos (la UI usa MultistoreAddForm); eliminar en limpieza futura.

## 2026-06 — Sincronización Set Up → Costos Recurrentes Básicos (cantidad de cajas)
- Helper `propagateBoxesToRecurring` (Quotes.jsx): al cambiar "Número de Cajas" de un ítem de Set Up, propaga el valor al ítem gemelo de Recurrentes Básicos identificado por `sourceServiceId`/`linkedSetupId`/`linkedTo` (y, como fallback, mismo `medio_pago_name` solo para recurrentes SIN vínculo explícito).
- `updateSetupItem` y `updateAdditionalItem` llaman al helper cuando field='cantidad_cajas' (>0), en un ÚNICO setState (sin parpadeo). Limpia `totalOverride` del gemelo para forzar recálculo.
- Flujo UNIDIRECCIONAL: `updateRecurringBasicItem` NO propaga de vuelta a Set Up.
- Recálculo automático de subtotales/totales (son derivados reactivos de quoteData).
- Verificado: testing agent Iter62 → sincronización + recálculo (subtotal $378→$408 al cambiar 10→25 cajas) + independencia + unidireccionalidad. 100%.

## 2026-06 — Homologación de destinatarios + "Para" editable (Modal Notificaciones Proyectos)
- **CC como tokens:** se reemplazó el campo CC de texto plano (comas) por el componente de tokens del cotizador: `InternalEmailInput` (lista buscable de usuarios internos) + botón "+" para externos (Enter o clic) + chips removibles. Estado nuevo `additionalRecipientsList` (array).
- **"Para" (TO) editable en caliente:** input con autocompletar + "+" (`notif-to-input`/`notif-add-to-btn`) para agregar/corregir el correo principal como token, sin alterar el maestro de Cliente/Banco (efímero por envío).
- **Filtro forzado por roles (backend):** `GET /users/internal-emails?profile=strategic` (helper `_is_strategic_profile`) incluye SOLO Directores (cualquier depto), Ventas Pyme/Corporativas, e Implementación (Implementador/Coordinador/Gerente). Aplica SOLO al modal de Proyectos (`InternalEmailInput profile="strategic"`); el cotizador queda sin filtrar. Verificado: 39 totales → 19 estratégicos.
- **Entrega:** `send-notification` usa `to_override` como TO real (correo corregido) y `additional_recipients` como CC.
- `InternalEmailInput` ahora acepta props `profile` (filtra fetch) y `onEnter`.
- Verificado: testing agent Iter63 → backend 4/4, frontend flujo crítico 100%. Test nuevo: backend/tests/test_internal_emails_filter.py.
- Pendiente menor: agregar data-testid al botón final de envío del modal para E2E.

## 2026-06 — Grupos de destinatarios CC reutilizables (Modal Notificaciones Proyectos)
- Nuevos endpoints (entity_communications.py, colección db.cc_groups): GET/POST/DELETE /api/cc-groups. POST deduplica emails (case-insensitive), exige ≥1 válido, 400 si nombre vacío; upsert por nombre (name_lower). Grupos compartidos por el equipo.
- UI en la tarjeta CC del modal de notificación (ProjectDetail.jsx): enlace 'Guardar selección como grupo' (aparece con tokens CC) → input de nombre + Guardar; lista de chips de grupos (cc-group-{id}) con contador, aplicar (merge+dedupe) y eliminar. Carga vía GET al montar.
- Verificado: testing agent Iter64 → backend 7/7 pytest, frontend E2E 100% (guardar/aplicar/persistencia/eliminar). Test: backend/tests/test_cc_groups.py.
- Backlog menor (sugerencia QA): índice único en cc_groups.name_lower; re-fetch de grupos al abrir el modal.

## 2026-06-12 — Homologación modal "Otras Notificaciones" (Adhoc) con CC + Grupos CC
- **Backend** (`projects.py` → `send_adhoc_email`): el endpoint `POST /api/projects/{id}/send-adhoc-email` ahora acepta `additional_recipients` (Form, JSON array) como CC; filtra inválidos, pasa `cc=(cc_list or None)` a `send_email`. Respuesta incluye `cc` y conteo TO+CC. Bitácora persiste `email_detail.cc` y el texto incluye `CC: ...` solo si hay CC. Retrocompatible (sin el campo → cc=[]).
- **Frontend** (`ProjectDetail.jsx`): el modal Adhoc se homologó con el de Notificaciones — campo TO ahora usa `InternalEmailInput` (profile="strategic") en lugar de input plano+datalist; nueva sección CC con tokens (`adhoc-cc-input`), chips removibles y Grupos CC reutilizables (compartidos, endpoints `/api/cc-groups`). `openEmailDialog` resetea el estado CC; envío directo y desde Vista Previa incluyen `additional_recipients`. Se eliminó el estado `internalUsers` (ya no usado).
- Verificado: testing agent Iter65 → backend 7/7 pytest, frontend E2E 100%. Test: `backend/tests/test_adhoc_email_cc.py`.

## 2026-06-12 — Nueva opción "Datos de Imple" (Implementación) con cascada multisucursal
- **Backend** (`clients.py`): `GET /api/implementation/default-coordinator` (resuelve dinámicamente el usuario con perfil "Coordinador de Administracion"); `PUT /api/clients/{id}/imple-data` aplica 5 campos (tipo_servicio=Componentes, integrador, aplicativo, implementador, coordinador) y los replica EN CASCADA a todas las sucursales del mismo RIF (`update_many({rif})`). Modelo `ImpleDataUpdate` en `models.py`. NO incluye Ejecutivo Propietario.
- **RBAC**: módulo `datos_imple` agregado a `permissions_catalog.py` (grupo gestion_implementacion) → aparece en la matriz de perfiles, niveles Inactivo/Consulta/Edición Total.
- **Frontend**: nueva página `pages/DatosImple.jsx` (tabla de clientes con buscador por nombre/RIF/implementador + modal de edición de solo 5 campos, precarga dinámica de Coordinador, aviso de cascada). Ítem en Sidebar `/datos-imple`, ruta en App.js, mapeos en `usePermission.js`.
- Verificado Iter67: cascada en 6 sucursales (RIF J505366220), independencia entre RIF distintos, ausencia de Ejecutivo Propietario, precarga de coordinador. Test: `backend/tests/test_iteration67_datos_imple.py`.

## 2026-06-12 — Reingeniería "Patrocinador de Pinpads" (Proyectos Directos)
- **UI** (`DirectProjectCreation.jsx`): el campo "Patrocinador de Pinpads" ahora es un control de 3 opciones excluyentes — `dp-pinpad-provider`: "El cliente" / "Infraestructura" / "Un Banco". "Un Banco" muestra el selector Procesador→Banco existente (`dp-pinpad-bank`); las otras muestran nota informativa.
- **Backend** (`direct_projects.py`): nuevo campo `pinpad_provider` ('client'|'infrastructure'|'bank'; vacío legacy→bank). Inyecta en la Ficha (Sección B, fila Patrocinador de Pinpads) la glosa "Los Pinpads son suministrados por el Cliente/Infraestructura" (vía sponsor_bank_name) o el banco/procesador estándar. Persiste `pinpad_provider` en el proyecto.
- **Notificación**: nueva acción configurable `notify_infrastructure_pinpads` (catálogo `action_notifications.py`, permitida en `proyectos_directos`). Al crear un Proyecto Directo con provider='infrastructure' se dispara vía el motor (con Ficha Técnica adjunta), igual mecanismo que "Enviar a Implementación". Config sembrada: destinatario dept. Infraestructura (Martín Ochoa), canal inbox — el admin la ajusta en Configuración → Notificaciones.
- Verificado Iter68: 5/5 backend + UI 3 escenarios. Test: `backend/tests/test_iteration68_pinpad_provider.py`.

## 2026-06-13 · Fix P0: Reporte de Avance ahora soporta Multi-RIF
- Causa raíz: el agente previo solo corrigió 1 de 4 compuertas. Faltaba incluir 'multirif' en: catálogos de filtros (project_reports.py L203), encabezado por tienda del PDF (is_multi L280) y agrupación/filtro de tienda en el modal (ProjectProgressReportDialog.jsx L92).
- Fix: extendidas las 4 compuertas a `in ('multistore','multirif')`.
- Bug MEDIO adicional (hallado por testing_agent iter82): tiendas con mismo nombre ("Altamira" x2) colapsaban en un solo grupo por agrupar por label. Solucionado agrupando por `store_id` (backend `_build_matrix_rows` añade `store_id`; PDF y frontend `groupedRows` agrupan por store_id).
- Validado: JSON avance (4 grupos distintos, 2 Altamira separadas), PDF 200/application/pdf (prj_e586608e3579 30KB, prj_5c3999532fcc 32KB, 2 headers Altamira confirmados por extracción), modal UI verificado por testing_agent (frontend 95%, store filter habilitado, agrupación por tienda OK).
- Pendiente P3 (no bloqueante): hydration warnings `<span data-ve-dynamic>` dentro de <tbody>/<tr> (wrapper de instrumentación de plataforma) y warning a11y Radix en el dialog.

## 2026-06-13 · Feature: Filtro por RIF en Reporte de Avance (Multi-RIF)
- Añadido filtro 'RIF / Razón Social' en el modal Reporte de Avance (solo proyectos multirif), con cascada: al seleccionar uno o más RIF, la lista de Tiendas se reduce a las de esos RIF y la tabla/PDF solo muestran esas tiendas.
- Backend (project_reports.py): `_load_project_with_filters` acepta `rifs_csv` y filtra stores por `rif_id`; endpoints avance y PDF aceptan `rifs`; avance expone `available.rifs` (rif_id/rif/client_name/box_count) y `available.stores` incluye `rif_id`; PDF agrega chip 'RIF:'.
- Frontend (ProjectProgressReportDialog.jsx): estado selRifs, cascada storesAvail, toggleRif poda selStores, params.rifs en applyFilters+downloadPdf, reset en useEffect/Limpiar.
- Bug HIGH (iter83): applyFilters no enviaba `rifs` → la vista previa no filtraba. Corregido (iter84 100% PASS: 2 grupos Marquez/Centro, cascada, reset, Limpiar, PDF OK).

## 2026-06-13 · Feature: Agrupación por RIF en tabla del Reporte de Avance
- A pedido del usuario, la tabla (modal + PDF) del Reporte de Avance ahora muestra para proyectos multirif un encabezado por RIF con el número de RIF y el nombre del comercio ('🆔 RIF J501546010 · Brasero El Marqúez'), y debajo SOLO las tiendas correspondientes a ese RIF ('🏬 Marquez', '🏬 Centro').
- Backend (project_reports.py): _build_matrix_rows añade rif_id/rif/rif_name por fila; _load_project_with_filters ordena las tiendas agrupadas por su RIF (rif_order desde proj.rifs); PDF emite filas tr.rif-row (header RIF) + tr.store-row (tienda indentada) con CSS.
- Frontend (ProjectProgressReportDialog.jsx): groupedRows emite items type:'rif' antes de type:'store'; render con data-testid='report-rif-header'.
- Verificado: JSON (orden Brasero→Marquez/Centro; Barako→Altamira; Carbon→Altamira), PDF 200, y UI por testing_agent (iter85, frontend 100%, 7/7 checks PASS incl. filtro RIF).

## 2026-06-13 · Reubicación del botón "Plantillas" + nueva Función Especial
- Eliminado el botón 'Plantillas' (gestor global de plantillas de correo) del panel interno del proyecto (ProjectDetail.jsx); también se removió código muerto: handler openTemplatesAdmin, handleSaveTemplate/handleDeleteTemplate, estados de template, render+import de TemplatesAdminDialog.
- El botón queda SOLO en el panel principal de Proyectos (Projects.jsx), ahora gateado por la nueva función especial 'proyectos:manage_email_templates' (label 'Gestionar Plantillas de Correo'): canManageTemplates = isAdmin || hasSpecial(flag).
- Backend (permissions_catalog.py): agregado a SPECIAL_PERMISSIONS; se expone en GET /api/admin/permission-catalog y es asignable desde Perfiles de Seguridad (y AdminUsers lo hereda).
- Verificado por testing_agent (iter86, frontend 100%, 6/6): botón removido del detalle, presente en panel principal solo con permiso, función visible/asignable en Perfiles, RBAC negativo (srubio no lo ve), resto del panel interno operativo.

## 2026-06-13 · Bugfix: columna "Envío a Imple" (fecha cotización→proyecto) vacía
- Causa raíz: Projects.jsx lee project.sent_to_implementation_at, pero ese timestamp solo se escribía en la cotización (que se elimina en el flujo normal). El proyecto solo tenía created_at → campo siempre vacío.
- Fix backend: quote_transitions.py y direct_projects.py ahora guardan sent_to_implementation_at = now en el documento del proyecto al crearlo.
- Backfill: 78 proyectos existentes actualizados con sent_to_implementation_at = created_at.
- Verificado por curl: GET /api/projects devuelve la fecha poblada en 78/78 proyectos.

## 2026-06-13 · Matriz de SLAs (Semáforo de Tiempos) + Motor de Acciones Automatizadas
- NOMENCLATURA: el semáforo de tiempos de Proyectos usa Verde → Amarillo → Rojo (amber→yellow en el semáforo: bg-yellow-500 / bg-yellow-50). Palabra literal "ámbar" erradicada de comentarios (NotificationBell, MultiRifTree, BatchUpdateModal, DirectProjectCreation). El status pill 'Por asignar' (badge de estado, NO el semáforo) se dejó en amber por estar fuera del alcance acordado.
- MATRIZ SLA CONFIGURABLE (/settings/project-sla): 3 etapas (Sin asignar/por_asignar, Asignado sin desbloquear/asignado, Desbloqueado·En Gestión/en_gestion) × 2 columnas (Días advertencia V→A, Días retraso A→R). Conteo desde que el proyecto entró al estado actual (status_changed_at + fallbacks). Persistencia en project_sla_config (validación retraso≥advertencia). El semáforo de Projects.jsx ahora lee estos umbrales en vivo.
- MOTOR DE ACCIONES (6 triggers): 3 advertencia + 3 retraso (uno por etapa). Cada acción: enabled + plantilla rich-text + canal (Correo/Centro de Mensajes) + destinatario (Generador del proyecto / Cliente externo / Usuario interno). Configs en project_sla_action_configs. Engine services/project_sla_engine.py evalúa color, detecta transiciones V→A y A→R y despacha (send_email / deliver_to_inbox). Scheduler: job diario 08:20 + intervalo cada 30 min. Endpoint POST /api/project-sla/evaluate para evaluación on-demand.
- Backend: status_changed_at agregado en asignación, cambio de estado, master-edit y ticket→En Gestión; backfill de 78 proyectos.
- Verificado: backend e2e por curl (config/catalog/actions/evaluate; prueba real entregó 10 mensajes al Centro de Mensajes al pasar proyectos a amarillo); pytest test_project_sla_engine.py (5/5); testing_agent iter87 frontend 100% (10/10 checks: matriz guarda/valida, 6 triggers, tipos de receptor, evaluar, nomenclatura amarillo sin 'ámbar').

## 2026-06-13 · Nueva variable {Matriz_Avance_Proyecto_Con_Fecha}
- Variante de {Matriz_Avance_Proyecto} que, además del % por fase, muestra debajo de cada % la fecha en que se alcanzó (campo updated_at de cada celda de la implementation_matrix), en sub-línea gris dd/mm/yyyy.
- Backend (project_template_vars.py): builders _avance_phase_table/_avance_store_block/_build_avance_matrix_html refactorizados con flag with_dates (DRY); nuevo helper _fmt_short_date; registrada en resolve_project_template_vars y en el catálogo + listas de exclusión de projects.py.
- Frontend: registrada en templateVariables.js (label+preview), RichTextEditor.jsx (preview), EmailTemplatesEditor.jsx (4 listas) y projectConstants.js (known vars).
- Verificado: render directo (base sin fecha, con_fecha con 100%+10/06/2026 y 50%+11/06/2026), catálogo /template-variables incluye la clave, pytest test_matriz_avance_proyecto.py 5/5, frontend compila.

## 2026-06-13 · Módulo de Consulta de Ventas Avanzada (BI) + Trazabilidad + Excel
- Nueva pestaña 'Consulta Avanzada' en Reportes de Ventas (/reports/sales): filtros acumulativos (rango fecha por created_at, tipo de cotización múltiple por chips, origen), 5 tarjetas de embudo administrativo EXCLUYENTE (enviada/aprobada/facturada/pagada/entregada — cada cotización en su etapa más avanzada vía timestamps sent_to_client_at/approved_at/invoice_number/paid_at/sent_to_implementation_at), KPI CRM 'Conversión de Leads: Contacto a Prospecto', y grilla de trazabilidad.
- Grilla detallada incluye el NOMBRE DEL GENERADOR (creator_name → resolución por uid → updated_by) y la columna 'Progreso Administrativo' con tags encadenados de las estaciones del flujo (CATEGORY_FLOWS).
- Origen: Renovación si parent_quote_id, resto 'Generado por Ejecutivo'. CRM: contactos iniciales convertidos (initial_contacts.is_converted) cuya PRIMERA cotización del cliente cae en el rango.
- Export Excel (.xlsx, openpyxl) de 2 pestañas: Resumen (filtros + 5 totales del funnel + monto + CRM) y Detalle (grilla plana + Generador + Último Paso).
- Backend: endpoints GET /api/reports/sales/advanced, /advanced/filters, /advanced/export en sales_reports.py.
- Verificado: backend e2e curl (219 filas Q2-2026, funnel excluyente enviada129/aprobada19/facturada15/pagada42/entregada2; export 200 2-hojas; 209/219 con generador), pytest test_advanced_sales_report.py 3/3, testing_agent iter88 frontend 100% (filtros, funnel, CRM, grilla con generador, export Excel 18KB, filtro VPOS→73 filas, limpiar chips).

## 2026-06-13 · Consulta Avanzada: cantidades por tipo (cajas/equipos)
- Agregadas 3 columnas a la grilla y al Excel del detalle: 'Cajas' (cantidad_cajas en cotizaciones de Implementación y Fast Track), 'Equipos Rep.' (suma de quantity de equipment_items en Reparación) y 'Equipos Vend.' (equipos vendidos: equipment_items en Equipos, ft_equipment_items en Fast Track). None/— cuando no aplica a la categoría.
- Backend: helper _adv_counts en sales_reports.py; columnas añadidas al export Excel (12 columnas). Frontend: 3 columnas en AdvancedSalesTab.jsx (boxes azul, repair ámbar, sold verde).
- Verificado: curl (VPOS_MULTIRIF→20 cajas, Verifone→30 vendidos, Reparación→13 equipos, FAST_TRACK→1+1; 100 con cajas/49 reparación/81 vendidos), Excel 12 cols, pytest 4/4.

**Campo "Generador" editable en Edición Maestra de Proyectos · 2026-06-16:**
- Reemplazó el enfoque de backfill automático del Generador (descartado: la data migrada/Preview no conserva el origen) por edición MANUAL.
- Backend (routes/projects.py · master-override): `MasterOverridePayload` ahora acepta `generador_user_id`; resuelve el usuario y setea `created_by_user_id` + `created_by_name` (o "—" si "__none__"). Diff de auditoría incluye etiqueta "Generador".
- Frontend (MasterEditDialog.jsx): nuevo Select "Generador (Vendedor)" en sección Clasificación, poblado con `/auth/users` (todos los usuarios activos, orden A-Z). testid `master-generador-select`. Preselecciona por `created_by_user_id`.
- Removidos: botón "Cargar Generador" (Projects.jsx) + endpoint `POST /projects/backfill-generator` + endpoint previo `backfill-impl-date` (este último ya ejecutado en Prod, one-time).
- Validado vía curl: PUT master-override con generador_user_id → created_by_name/created_by_user_id actualizados, changes_count=1. Frontend compila OK. Smoke test visual no corrió (preview env dormido - gate de plataforma).

**Filtrado dinámico de Integradores por Tipo de Proyecto (Cotizaciones + Proyectos Directos) · 2026-06-16:**
- Nuevo helper compartido `frontend/src/utils/integratorModality.js` con `integratorModalityMatch(quoteType)` (DRY, consistencia entre ambos módulos). Reglas por `integration_modality`:
  - Físico (VPOS/VPOS_MULTIRIF/MPOS/FAST_TRACK): REST, Stand Alone, Wrapper, MPOS.
  - Digital (GATEWAY/LINK_PAGO): Bridge PG, Web Link de Pago (No Univ./Univ.), TKN (No Univ./Univ.), PG (No Univ./Univ.). Normalización case-insensitive.
- Ambos módulos ya tenían filtro+reset pero con reglas más restrictivas (VPOS=solo REST, MPOS=solo MPOS, Gateway=solo PG): se ampliaron a la matriz nueva. Se mantiene el filtro de estatus "Certificado" (decisión del usuario) y filtrado LOCAL (decisión del usuario).
- QuoteWizardDialog.jsx: dropdown integrador + lógica de reset en cambio de tipo usan el helper. DirectProjectCreation.jsx: reemplazado INTEGRATOR_MODALITY_MATCH local por el helper.
- Validado: unit test del helper contra valores reales de BD (ALL PASS) + testing_agent frontend 7/7 escenarios PASS (filtrado físico/digital + reset reactivo + toast, en ambos módulos). iteration_103.json.

**Homologación selector Integrador en Cotizaciones (dedup + cascada Aplicativo) · 2026-06-16:**
- Cotizaciones (QuoteWizardDialog) ahora replica el patrón de Proyectos Directos: dropdown de Integrador deduplicado por NOMBRE (aparece una sola vez) + campo "Aplicativo Certificado" en cascada. 1 app = auto-selección (display bloqueado, testid select-integrator-app-locked); 2+ apps = dropdown obligatorio (testid select-integrator-app).
- quoteData ahora incluye integrator_name (init en createNewQuote/resetQuoteForm; derivado al editar desde integrators.find(id).name o 'sin_integrador'). Reset reactivo limpia integrator_name + integrator_id + integrator_app_name al cambiar a modalidad incompatible.
- testids: select-integrator (ahora value=nombre), integrator-option-{slug-nombre}, select-integrator-app, select-integrator-app-locked.
- Validado por testing_agent (iteration_104.json): 5/6 PASS (dedup 124 nombres sin duplicados, auto-lock 1 app, dropdown 2+ apps p.ej. 'Somos Sistemas Software'=AFTIM/AFTIM Mobile, filtro modalidad, reset+toast). Caso edit-load con integrador real NO mecanizable (no hay cotizaciones con integrador real en data actual); lógica confirmada (idéntica a Proyectos Directos).

**Panel de Proyectos: KPIs dinámicos + Avance Global + filtros Integrador/Fechas · 2026-06-16:**
- KPIs reactivos al filtro (client-side, mismo query set scopeado por rol). Regla de Oro (decisión 1a): tarjeta 'Total'=set filtrado completo (incluye estado); tarjetas de estado (Pendientes/En Proceso/Suspendidos/Finalizados) cuentan su estado dentro de los demás filtros (baseFiltered) y siguen como toggles.
- Nuevo widget 'Avance Global' (barra de progreso): promedio de rollup_progress.global_progress (faltante=0%) sobre el set filtrado; reactivo; segmentado por rol vía data ya scopeada (sufijo 'asignados' para Implementador / 'en vista' para resto).
- Nuevos filtros en Projects.jsx: Integrador (popover con búsqueda) y rango de fechas (sent_to_implementation_at), + botón 'Limpiar'. testids: project-integrator-filter/-search/-option-*, project-date-from/-to, project-clear-filters, global-progress-widget/-bar/-value, stat-value-*.
- Sin cambios de backend (datos ya cargados y scopeados por rol; <=1000 proyectos). Validado por testing_agent iteration_105.json: 6/6 PASS (Total reactivo a estado, tarjetas reactivas a integrador, avance recalcula 6%->16% Bigwise->15% En Gestión->12% rango fechas, limpiar restaura).
- NOTA DATA: existen estados legacy no estándar ('Asignado / En Proceso'=49, 'Pendiente por Asignar'=1, 'En proceso/reasignado'=3) que NO entran en los buckets de las tarjetas (igual que el endpoint /projects/stats previo). Por eso Total puede ser > suma de tarjetas. Es data preexistente, no afecta la lógica reactiva.

**Rediseño tarjetas KPI Panel de Proyectos · 2026-06-17:**
- Tarjetas KPI ahora alineadas 1:1 con la taxonomía de estados: Total, Por Asignar, Asignado, En Gestión, Suspendido, Implementado Parcial, Culminado (7 tarjetas, orden por ciclo de vida). Renombrados: Pendientes→Por Asignar, En Proceso→En Gestión; agregados Asignado e Implementado Parcial; Finalizados→Culminado.
- kpi ahora cuenta por estado exacto (countStatus) sobre baseFiltered; filtros de tarjeta usan los keys de estado reales ('Asignado','En Gestión','Implementado parcial','Suspendido','Culminado','Por asignar') sincronizados con el dropdown de estado.
- Layout compacto: grid-cols-4 lg:grid-cols-7, gap-2, p-3, valor text-xl, label text-xs leading-tight. testids: stat-value-{slug}.
- Compila OK. Verificación visual pendiente (preview dormido al momento del cambio).

**Proyectos de Integración: campos 'Productos a Certificar' + 'Correo Adicional Eventual' (CC) · 2026-06-17:**
- UI (Integrators.jsx, wizard renderWizardCoreFields): 'Productos a Certificar' (texto libre, debajo de Tipo de Integración, testid wizard-productos-certificar) y 'Correo Adicional Eventual' (input email opcional con validación EMAIL_RE, testid wizard-correo-eventual + error wizard-correo-eventual-error). Validación bloquea guardar si el correo es inválido (handleWizardSubmit + handleSubmit).
- Modelo: productos_certificar y correo_eventual agregados a IntegratorCreate e Integrator (persisten en la ficha, no alteran el correo maestro).
- Notificación: reutiliza el flujo existente 'new_integration_project' (Configuración de Otras Acciones). notify_new_integration_project agrega variable {Productos_Certificar_Integrador} y arma extra_cc (correo_eventual + recipients del modal). dispatch_other_action ahora acepta extra_cc y lo envía en CC en cada email + lo registra en bitácora (auditoría con integrator_id).
- Plantillas: {Productos_Certificar_Integrador} agregado al catálogo del editor (BASE_TEMPLATE_VARIABLES.new_integration_project) -> insertable; y a la plantilla semilla new_integration_project (fila 'Productos a Certificar').
- Validado: curl backend (crear persiste ambos campos; notify devuelve cc=['gerente@banco.com'], '+1 en copia') + testing_agent iteration_106.json 100% wizard (campos, ubicación, bloqueo por email inválido, éxito con válido).

**Corrección: campos de complemento SOLO en Ampliación de Tipo Vigente · 2026-06-17:**
- Los 2 campos (Productos a Certificar + Correo Adicional Eventual) se movieron de renderWizardCoreFields al bloque 'wizard-expansion-block' (Ampliación). Ahora aparecen ÚNICAMENTE en 'Ampliación de tipo vigente' (Proyecto de complemento); ausentes en 'Nuevo Tipo de Integración' e 'Integrador Nuevo' (flujos originales intactos).
- handleWizardSubmit rama expansion: valida email, persiste vía POST /integrators/{id}/expand (ExpandPayload: productos_certificar, correo_eventual, con trim) y abre el modal de notificación (ejecuta el envío del Proyecto). Rama new/new_type excluye explícitamente esos campos del payload (destructure-and-strip).
- Backend: endpoint /expand ahora acepta y persiste los campos de complemento.
- Validado: curl (expand persiste campos; notify devuelve cc + '+1 en copia') + testing_agent iteration_107.json 5/5 PASS (ausencia en Nuevo Tipo/Integrador Nuevo, presencia en Ampliación, validación email bloquea, guardar válido abre modal de notificación). Dato de prueba revertido.

## 2026-06-20 — Firma Institucional Global homologada en TODA la plataforma
- Propagado `{Firma_Notificacion_Global}` (firma dinámica del usuario que envía, vía `build_signature_html(current_user)`) a los motores de email de:
  - Clientes (`client_communications.py`): preview + send.
  - Integradores y Nuevos Productos (`entity_communications.py`): preview + send (inyección central en `_send_and_log` y en ambos preview).
  - Contactos Iniciales (`initial_contact_communications.py`): preview + send.
- Frontend: variable agregada a los pickers de `ClientEmailDialog.jsx`, `Integrators.jsx` (INTEGRATOR_EMAIL_VARS), `NewProducts.jsx` (NP_EMAIL_VARS) e `InitialContactEmailDialog.jsx`.
- Validado E2E (curl, URL externa) en los 4 módulos: el preview resuelve la firma con razón social institucional + datos del usuario en sesión (Rafael González).
- NOTA: surte efecto en Producción al RE-DESPLEGAR.

## 2026-06-20 — Botón "Homologar plantillas" (insertar firma global en todas las plantillas)
- Backend: nuevo endpoint admin `POST /api/email-templates/append-signature` (`seed_and_templates.py`) que agrega `{Firma_Notificacion_Global}` al pie de TODAS las plantillas (persistidas + predeterminadas) que aún no la tengan. Idempotente; inserta antes de </body>/</html> o al final.
- Frontend: botón `Homologar plantillas` (data-testid `append-signature-button`) dentro de la tarjeta "Logotipo para Pie de Notificaciones" en Configuración (Settings.jsx), fila `append-signature-row`.
- Validado por testing_agent (iteration_120): backend 7/7 (403 no-admin, idempotencia, 4 preview-email resuelven la firma), frontend 100% (botón + POST 200 + toast + contención DOM en la tarjeta del logo).

## 2026-06-20 — Fix: logo roto en la firma de notificaciones
- Causa raíz: backend/.env tenía REACT_APP_BACKEND_URL OBSOLETO (action-key-mismatch.preview... → 404). signature.py arma el <img src> del logo con esa base en runtime, por eso el logo salía roto en los correos.
- Fix: actualizado backend/.env REACT_APP_BACKEND_URL a la URL actual (global-signature-fix.preview...) y reiniciado backend. Verificado: el src renderizado responde HTTP 200 (image, 19825 bytes).
- NOTA producción: al desplegar, el backend debe tener REACT_APP_BACKEND_URL = URL pública de producción para que el logo cargue allí.

## 2026-06-21 — Motor condicional de PDFs Corporativos para PG y Link de Pago
- Backend (config.py): nuevas funciones `apply_corporate_pg_lp_restructure(buffer, quote_type)` y motor unificado `append_quote_static_pages(buffer, quote_type, client_segment)`.
  - PG/LP + PYME: flujo estándar (append_pg_static_pages) — sin cambios.
  - PG + CORP: conserva páginas 1-4 + fusiona anexo_gateway_corp.pdf.
  - LP + CORP: conserva páginas 1-5 + fusiona anexo_link_corp.pdf.
  - VPOS CORP/PYME: sin cambios. Fallback seguro a estándar si falta el anexo.
- quotes.py: los 5 puntos de generación (crear, regenerar, generar/previsualizar con template) usan el motor unificado. El PDF persistido = el que se envía al cliente.
- Anexo corporativo (1 pág, mismo para PG y LP) cargado por el usuario → static_pdfs/anexo_gateway_corp.pdf y anexo_link_corp.pdf.
- Segmento determinado por client_segment (PYME/CORP), definido por el operador al crear la cotización.
- Validado: testing_agent iteration_121 17/17 (unit + e2e preview: PG CORP=5 págs, LP CORP=6 págs, PyME intacto).

## 2026-06-21 — Fix: Modificar cotización Corporativa regeneraba PDF como PyME
- Causa: el flujo "Modificar" guarda vía POST /quotes/create-with-pdf rama `data.pdf_data` (quotes.py ~L276), que usaba `pdf_request.client_segment` tal cual lo envía el frontend; al modificar, el frontend perdía el segmento y mandaba 'PYME', degradando el anexo a estándar (el doc guardado sí resolvía CORP).
- Fix: en los sitios de guardar (site1), generar y previsualizar con template (sites 4/5) ahora el segmento se resuelve autoritativamente desde la ficha del cliente vía `_resolve_client_segment` (PG/LP heredan del cliente; VPOS conserva fallback). 
- Validado E2E (curl URL externa) con cliente corporativo enviando client_segment=PYME: PG -> 5 págs (4 base + anexo corp), LINK_PAGO -> 6 págs (5 base + anexo corp). PyME sin regresión.

## 2026-06-21 — Fix: Modificar cotización PG/Link de Pago inflaba la tabla de recurrentes (+1 producto)
- Causa: al guardar se descarta el flag `fixed` del item base 'Persona Jurídica' (Costo Base); al reabrir en Modificar, `pgMediosPagoCount = pgSetupItems.filter(i=>!i.fixed).length` lo contaba como medio de pago, inflando num_products en +1 en la tabla de recurrentes.
- Fix (frontend, Quotes.jsx ~L3433): al cargar la cotización para modificar se re-etiqueta como `fixed:true` el item base (observacion==='Costo Base' o concepto contiene 'persona jur'). Aplica a GATEWAY y LINK_PAGO.
- Confirmado con data de Mongo (quotes con num_products==setup_items estaban infladas) y validado por testing_agent iteration_122 (2/2): COT-2026-06-078 ahora 4 (antes 5), LINK_PAGO COT-2026-06-155 ahora 1 (antes 2). Re-guardar sana las cotizaciones ya infladas.
- Nota: el fix es en la carga; el flag `fixed` sigue sin persistirse en BD (no necesario, el wizard re-etiqueta en cada modificación).

## 2026-06-21 — Fix: Link de Pago no registraba el costo (total_usd=0) en el proyecto
- Causa: en create_quote_with_pdf (ruta de guardado del wizard, quotes.py L208) la condición de cálculo del total era `== "GATEWAY"`, excluyendo LINK_PAGO; las cotizaciones Link de Pago caían al else (services/hardware vacíos) y guardaban total_usd=0. Al convertir a proyecto se copiaba 0.
- Fix: la condición ahora es `in ("GATEWAY","LINK_PAGO")` → total_usd = subtotal_usd = suma de pg_setup_items (base imponible / Setup Neto), igual que GATEWAY.
- Backfill: 7 cotizaciones LINK_PAGO existentes con total_usd=0 corregidas a la suma de su setup (e.g. 360, 372, 288). No había proyectos LINK_PAGO existentes.
- Verificado por datos: cotizaciones LINK_PAGO ahora reportan total_usd correcto; nuevas LP heredarán el costo al proyecto vía quote_transitions (project.total_usd = quote.total_usd).

## 2026-06-21 — Formato PDF (PyME/Corp) ahora lo gobierna la OPCIÓN DEL MENÚ, no la ficha del cliente
- Requerimiento: el segmento PyME/Corporativo del PDF debe seguir el menú elegido por el operador (Clientes PyME vs Clientes Corporativos), no client.segment.
- Backend (quotes.py _resolve_client_segment): ahora NORMALIZA la selección del operador (fallback) a CORP/PYME y ya NO lee client.segment. Ajustado create_quote (L78/L110) para almacenar el segmento del menú en todos los tipos.
- Frontend (Quotes.jsx modify-load L3402): restaura client_segment desde la cotización guardada (antes se degradaba a PYME al modificar — causa real del bug anterior). QuoteWizardDialog: el badge Corporativo/Pyme ahora se muestra también en modo Modificar.
- Verificado: curl (cliente CORP + menú PyME -> 8 págs PyME; + menú CORP -> 5 págs Corp) y testing_agent iteration_123 (4/4 frontend, interceptando el request real: Modificar preserva CORP/PYME).
- Nota: esto reemplaza la lógica previa donde el segmento se heredaba de la ficha del cliente.

## 2026-06-21 — Fix: Modificar PG/Link de Pago CORP renderizaba PDF PyME (regenerate-pdf fallaba)
- Causa raíz: el flujo "Modificar" (handleSaveEditedQuote) usa POST /quotes/{id}/regenerate-pdf. Esa función construía TemplateQuotePDFRequest pasando None en campos exigidos como string (cliente_address, integrator_name, integrator_app_name, pinpad_model, sponsor_bank_name, notes). En PG/LP esos campos suelen ser None -> 500 de validación -> el PDF corporativo no se regeneraba. En VPOS esos campos están poblados, por eso funcionaba.
- Fix (quotes.py regenerate_quote_pdf): coerción None->"" en esos campos (quote.get(k) or "").
- Verificado por curl: regenerate-pdf en GATEWAY CORP -> 5 págs (corporativo) y LINK_PAGO CORP -> 6 págs (corporativo). Antes daba HTTP 500.
- Resultado: al Modificar una cotización PG/LP Corporativa, el PDF ahora se regenera en formato Corporativo.

## 2026-06-21 — Fix: Exportar PDF (y los 3 botones) inconsistentes con Corporativo
- Causa: el endpoint generate-pdf-with-template (botón "Exportar PDF") había quedado con la lógica VIEJA de anexos (append_pg_static_pages para todo PG/LP), ignorando el segmento -> Exportar daba PyME (8 págs) mientras Previsualizar daba Corp (5 págs).
- Fix: generate-pdf-with-template ahora usa append_quote_static_pages con el segmento resuelto, igual que Previsualizar y Guardar.
- Verificado por curl, los 4 caminos consistentes para GATEWAY CORP=5 / LINK_PAGO CORP=6 / PyME=8:
  - Previsualizar (preview-pdf-with-template): 5/6
  - Exportar (generate-pdf-with-template): 5/6
  - Guardar (create-with-pdf): corporativo
  - Modificar (duplicate -> PUT -> regenerate-pdf): 5 (simulación completa)
- Junto con el fix previo de regenerate-pdf (None->""), el flujo Modificar de PG/LP Corporativo ahora genera correctamente el PDF corporativo.

## 2026-06-21 — Fix definitivo: asimetría de "Exportar PDF" + regresión Modificar Corporativo
- FALLO 1 (causa raíz real): exportCurrentQuoteToPDF (Quotes.jsx L2168) elegía endpoint LEGACY /api/quotes/generate-pdf cuando hasTemplate/useTemplateForPDF era false -> Exportar generaba un PDF desactualizado/PyME, mientras Previsualizar (preview-pdf-with-template) y Guardar (create-with-pdf) daban Corp. Fix: Exportar ahora usa SIEMPRE /api/quotes/generate-pdf-with-template -> los 3 botones idénticos.
- FALLO 2: regenerate-pdf (usado por Modificar) preserva el segmento CORP del registro original y ya no falla por campos None (coerción None->'' en strings y cantidad_cajas None->1).
- Verificado: testing_agent iteration_124, 6/6 pytest -> GATEWAY CORP=5 / LINK_PAGO CORP=6 / PyME=8 en los 3 endpoints; regenerate-pdf conserva CORP en GATEWAY y LINK_PAGO (incl. cotización real quo_05e569ead910).

**Bug fix P0: Pertenencia estática de Cotizaciones al transferir usuario de departamento · 2026-07-16:**
- Regla estricta (opción a acordada con usuario): una cotización pertenece 100% al departamento de ORIGEN (`creator_departamento`). Si el creador se transfiere de departamento, sus cotizaciones NO lo siguen al nuevo depto (ni él ni su nuevo equipo las ven).
- routes/quotes.py:
  - `_dept_visibility_or`: el fallback por `created_by_user_id` (miembros actuales + self) ahora aplica SOLO a históricos legacy sin origen (`_LEGACY_NO_ORIGIN`). Afecta ramas gerente/ejecutivo/perfil RBAC.
  - Bloque Ventas Corporativas (GET /quotes): fallback por team_ids condicionado a legacy.
  - Bloque Coordinador: rama ejecutivos por origen + propias del coordinador ancladas al depto de origen + fallback legacy.
  - GET /quotes/{id} (detalle): acceso anclado a `creator_departamento` sin bypass por ser el creador (estricto); fallback al depto actual del creador solo para legacy sin origen.
- Verificado con query real contra Mongo (quote origen 'Operaciones'): leak al nuevo depto = 0; visibilidad al depto origen = 1. Backend levanta OK.

**Bug fix P0: Coexistencia de Integradores ante Ambiente de Pruebas (no canibalizar perfil comercial) · 2026-07-16:**
- Root cause: `assign_test_environment` sobrescribía `integrator_status` de 'Certificado' a 'En proceso' (el wizard de cotizaciones QuoteWizardDialog.jsx:841 filtra por status==='Certificado' → integrador bloqueado para cotizar). Y `close_integrator_project` (bypass test_environment) ponía `integrator_status='Cerrado'` → archivaba/canibalizaba el registro maestro.
- Fix routes/integrators.py:
  - `assign_test_environment`: PRESERVA `integrator_status` actual (solo activa 'En proceso' si estaba Cerrado/vacío); setea `project_scope='test_environment'` + fechas; guarda snapshot `status_before_test_env`/`scope_before_test_env`. El badge morado/contador se deriva de project_scope, no del status.
  - `close` (test_environment): restaura `integrator_status` al snapshot previo (fallback 'En proceso', nunca 'Cerrado'), `project_scope=None` (sale de la cola de proyectos), unset de campos test env; NO archiva ni borra el documento maestro.
- Coexistencia lograda: integrador visible en Grilla de Integradores + Vista de Proyectos, elegible para cotizaciones durante y después del test env.
- Verificado testing_agent iter277: 7/7 backend OK (incluye regresión de cierre estándar new/component). Regresión: tests/test_iter277_integrator_test_env_persistence.py.

**Bug fix: Actions Override en Cotizaciones de Equipos — autorización estable por email (no por user_id volátil) · 2026-07-16:**
- Root cause: la autorización se evaluaba contra `allowed_user_ids` (IDs volátiles). agodoy@megasoft.com.ve fue borrado+recreado (user_id viejo user_a8e3874291c8 → nuevo user_54999f93a974); el override `equipos|clientes_pyme|approve` retenía su ID obsoleto y `allowed_user_emails` no estaba denormalizado → bloqueado. La UI de config mostraba "Todos los usuarios" porque no resuelve IDs obsoletos (restricción fantasma invisible al admin pero aplicada por el motor).
- Fix backend routes/quote_action_customization.py `_attach_allowed_emails`: PODA los allowed_user_ids que no resuelven a un usuario actual y devuelve `allowed_user_emails = union(emails resolubles en vivo, emails denormalizados guardados)`. Sirve a list_overrides y list_custom_actions.
- Fix frontend components/quotes/QuotesTable.jsx (`getActionMeta`, `getCustomActionsFor`): el gate de restricción usa `allowed_user_emails` (trim+lowercase, identidad estable) en vez de `allowed_user_ids` crudos. "vacío = todos". Match por correo (sobrevive a recreación de usuarios).
- Resultado: si la lista de autorizados aparece vacía (o solo IDs obsoletos), la acción es para TODOS (agodoy incluido); si hay usuarios válidos autorizados, restringe correctamente (regresión: 'approve' sigue solo para joliveros → agodoy disabled con tooltip).
- Verificado testing_agent iter278: backend 5/5 + frontend E2E con agodoy (send_to_client/collect/factura/etc ENABLED, approve DISABLED correcto, 0 errores 403). Credenciales agodoy en test_credentials.md.

**Backlog (acordado 2026-07-16):** Botón "Sanear referencias obsoletas" en Configuración (usa endpoint admin existente /api/admin/executives/reassign + /api/admin/executives/orphaned) para limpiar/reasignar de un clic IDs obsoletos en overrides/cotizaciones/proyectos de usuarios recreados. NO es requisito del fix (el pruning en lectura ya resuelve el síntoma); es higiene de datos preventiva. Prioridad: P3.

**Bug fix (REFUERZO) Actions Override Equipos — poda de autorizados a usuarios ACTUALES · 2026-07-16:**
- Ampliación de la causa raíz: además de IDs obsoletos, los overrides retenían CORREOS denormalizados (allowed_user_emails) de usuarios ya inexistentes (borrados/recreados). Esos autorizados "fantasma" no se ven en la UI (resuelve por usuario actual) pero el motor los aplicaba → agodoy bloqueado aunque la config se viera vacía.
- Fix routes/quote_action_customization.py `_attach_allowed_emails`: autorizados EFECTIVOS = (emails vivos por id ∪ emails denormalizados) ∩ correos de usuarios ACTUALES. Si queda vacío ⇒ "todos". Poda ids y correos de cuentas inexistentes; sincroniza enforcement con la UI de configuración.
- Verificado testing_agent iter279: backend 5/5 (incluye inyección de correo fantasma en Mongo → podado a []; mixed ghost+valid → conserva solo el válido) + frontend E2E con agodoy. Sin regresiones (approve sigue restringido a joliveros, usuario válido).
- IMPORTANTE: requiere REDEPLOY para llegar a producción; al desplegar, las restricciones fantasma se auto-sanan en la primera lectura de overrides.

**UI/UX Vista de Integradores — layout extendido + doble scrollbar + separación de iconos · 2026-07-16:**
- pages/Integrators.jsx (100% frontend):
  - (A) Layout extendido: colgroup corregido a 11 columnas (se agregó header/columna 'Cert.' que faltaba; colSpan vacío 10→11); tabla minWidth 1400px con tableLayout fixed; en 1920x1080 la columna 'Acciones' queda visible sin scroll lateral.
  - (B) Separación de iconos: celda 'Acciones' con border-l + padding-left y gap-1.5; celda 'Cert.' con pr-3. Gap real medido ~28px (target 8-10px), sin solapamiento con el botón de desglose de matriz (Award).
  - (C) Doble barra de scroll horizontal SINCRONIZADA: barra superior (data-testid integrators-top-scroll) + contenedor inferior (integrators-bottom-scroll) con refs topScrollRef/bottomScrollRef y handlers handleTopScroll/handleBottomScroll (flag scrollSyncing anti-loop). Sincronización bidireccional verificada.
- Verificado testing_agent iter280: A/B/C OK + regresión (expand de matriz, carga de grilla). Sin regresiones. Requiere REDEPLOY para producción.

**Feature: Visor (Preview) + Descarga de documentos en Biblioteca de Comunicación y Comunicador Masivo · 2026-07-16:**
- Backend routes/entity_communications.py: nuevo GET /api/entity-documents/{document_id}/download con params `inline` (attachment vs inline) y `token` (query, para auth de iframe/img que no envían header). Usa load_attachment_bytes (disco+Mongo) y devuelve Response con Content-Disposition + filename original. 401 sin auth, 404 si no existe/no localizable.
- Frontend components/DocumentViewerModal.jsx (NUEVO): modal lightbox (iframe para PDF, img para PNG/JPG, fallback para otros) + helper downloadEntityDocument (descarga blob autenticada respetando nombre/extensión). DialogDescription sr-only para a11y.
- Integrado en: pages/EntityTemplatesConfig.jsx (tarjetas de documentos, botones entity-doc-view/download) y components/MassCommunicationDialog.jsx (filas del repositorio, botones mass-doc-view/download con stopPropagation para no alterar el checkbox).
- Verificado testing_agent iter281: backend 6/6 (attachment/inline/token/401/404/round-trip PDF bytes) + frontend E2E (visor abre/cierra 4x sin crash, regresión crítica del checkbox intacta). Sin issues. Requiere REDEPLOY para producción.

**Bug fix: remitente de correos a Integradores (usaba gestor@ global en vez del área configurada) · 2026-07-16:**
- Root cause: routes/entity_communications.py `_send_and_log` y `send_mass_communication` llamaban a send_email SIN pasar `sender`, cayendo al SENDER_EMAIL global (gestor@megasoft.com.ve) en vez del remitente asignado al área 'integradores' (impl_merchant@megasoft.com.ve).
- Fix: se importó resolve_sender_for_area; `_send_and_log` recibe `sender` y lo propaga; send_integrator_email pasa sender=resolve_sender_for_area('integradores'); send_new_product_email pasa 'nuevos_productos'; send_mass_communication resuelve mass_sender y lo usa en to=[mass_sender] + sender=mass_sender (BCC intacto).
- Verificado testing_agent iter282: 4/4 backend. email_logs 'from'==impl_merchant@ para envío individual y masivo; SMTP real 'sent'. Requiere REDEPLOY para producción.

**Feature: Tooltips 'Resumen de Avance' en KPIs de Proyectos · 2026-07-16:**
- pages/Projects.jsx (100% frontend): hover sobre cada tarjeta KPI muestra tooltip oscuro (delay 200ms) con desglose Al día (verde) / Retraso Medio (amarillo) / Retraso Crítico (rojo) + Total.
- Cálculo: `_avanceLevel` clasifica por `business_days_in_state` (backend, calendario laboral) vs umbrales SLA por etapa (warning_days/delay_days, slaConfig, fallback 2/4). Estados terminales (Culminado/Implementado parcial/Anulado/Cancelado/Finalizado) → 'al_dia' (no muestran crítico falso).
- Consistencia garantizada: cada tarjeta desglosa su MISMO subset (Total→filtered; estados→baseFiltered.filter(status)) ⇒ suma == total de la tarjeta.
- Verificado testing_agent iter283: prueba de fuego matemática PASSED en las 7 tarjetas; tooltip aparece/desaparece sin residuos; click filtra; sin errores de consola. Requiere REDEPLOY para producción.

**Bug fix (UI): footer fijo + scroll interno en editor de Plantillas de Integradores · 2026-07-16:**
- pages/EntityTemplatesConfig.jsx: DialogContent del editor de plantillas ahora es flex-column con max-h-[90vh] y p-0; header/footer con shrink-0; cuerpo (entity-template-body) flex-1 min-h-0 overflow-y-auto (scroll interno); DialogFooter con border-t + bg-white (sticky por ser último ítem no-growing). Botón Guardar con data-testid entity-template-save-btn.
- Resuelve el desborde del botón 'Guardar' fuera del viewport en plantillas con mucho HTML; ya no requiere zoom-out.
- Verificado testing_agent iter284 a 1366x768 y 1280x720 (inyectando ~12k chars): Guardar visible, scroll interno independiente, footer fijo, clickeable, sin empujar la página. Sin regresiones. Requiere REDEPLOY.

**Feature: Certificado PDF V4 — inyección por frases-ancla sobre nuevo template · 2026-07-16:**
- routes/integrators.py `_generate_integration_certificate_pdf`: reescrito el estampado para el nuevo formato V4 (landscape 842x595). Motor de matching por FRASE (`_find_phrase` sobre pdfplumber extract_words) + reportlab overlay alineado a la línea base del template.
- Inyecciones: (A) "Certifica al" → {Tipo de Integrador} = 'Comercio' si integrator_type empieza por 'comerc', si no 'Integrador'; (B) {Nombre} CENTRADO en la línea inferior; (C) "bajo la" (fallback "con la") → "{Componente} - Versión {Versión}" (Modal 1); (D) "con su aplicativo" → {app_name}; (E) "Medios de pago certificados" → productos_str (medios 'C' unidos por ' / ', con wrap si excede el ancho).
- Degradación segura: si el template no tiene las frases V4 (p.ej. plantilla vieja), cae al certificado autónomo/overlay existente.
- Verificado por generación directa + extracción de texto real (pdfplumber) para tipo Integrador y Comercio: las 5 inyecciones aparecen tras sus frases guía. Requiere REDEPLOY para producción (el template V4 ya está en el depósito).

**Feature: Certificado PDF V5 — tipografía y multilínea · 2026-07-16:**
- routes/integrators.py `_generate_integration_certificate_pdf`:
  - A. {Tipo de Integrador} en Times-Bold 32pt FIJO (sin autoajuste), contiguo a "Certifica al".
  - B. {Componente} - Versión {Versión} en Times-Roman (cuerpo serif) con ajuste horizontal hasta antes de "del Ecosistema" (2ª línea).
  - C. Medios_certificados en Helvetica (equivalente nativo de Arial MT) 20pt FIJO; PROHIBIDO recortar/reducir fuente → word-wrap multilínea automático usando el ancho útil de la página (1ª línea tras la etiqueta, siguientes desde el x0 de la etiqueta).
  - Nombre centrado en Times-Bold.
- Verificado por generación directa + inspección char-level (pdfplumber): tipo=Times-Bold 32pt; medios=Helvetica 20pt; prueba de estrés 10 medios → 3 líneas sin recorte ni overflow (max x1 796.6 ≤ 842). Requiere REDEPLOY.

**Bug fix P0 · Certificado PDF V5 — línea técnica y medios de pago · 2026-06:**
- routes/integrators.py `_generate_integration_certificate_pdf`:
  - Línea técnica (Componente - Versión): antes se anclaba tras "bajo la" y se desbordaba el borde derecho (palabra "Rest" en x≈843 > página 842). Ahora se ancla a la frase estática " del Ecosistema" (nuevo helper `_find_phrase_first`) y fluye desde el margen izquierdo del párrafo ("Por haber") hasta justo antes de "del", con Times-Roman 14pt (autoshrink a floor 8). Fallback a "bajo la" si no existe el ancla.
  - Medios de pago: bajado de 20pt a Helvetica 18pt con word-wrap y margen de seguridad derecho ampliado (w-92 ≈ 750pt en vez de w-45 ≈ 797). Listas largas envuelven sin desbordar.
- Verificado (self-test, render real sobre PDF de muestra + extracción de coordenadas): línea técnica termina en x=566.3 < "del"(572.3); medios de pago max x=731.4 << 750. Sin overflow.

**Feature P0 · Certificado PDF V7 — reestructuración tipográfica y auto-escala de medios · 2026-06:**
- routes/integrators.py `_generate_integration_certificate_pdf` reescrito según spec V7 (verificado contra template base real de db.config con render del código real):
  - A. Tipo de Integrador: Times-Roman 28pt regular, contiguo a "Certifica al".
  - B. Nombre del Integrador: Times-Bold 28pt, CENTRADO (línea inferior). Auto-shrink solo si excede ancho.
  - C. Componente/Versión: Helvetica-Bold (Arial) 19pt, CENTRADO en la línea en blanco (cuerpo L2, top≈253), calculada por interlineado entre anclas "por haber" y "del ecosistema".
  - D. Nombre del Aplicativo: Helvetica-Bold 19pt, CENTRADO en línea en blanco (cuerpo L4, top≈301).
  - E. Medios de pago: Helvetica-Bold 19pt base, word-wrap máx 3 líneas con REDUCCIÓN DINÁMICA de fuente (auto-scale 19→floor 9) hasta caber; margen derecho físico 715pt. Nunca trunca palabras.
  - F. Fecha: nuevo ancla "Caracas," → inyecta fecha del servidor (UTC-4 Venezuela) en formato extendido español, Times-Roman 16pt.
  - Nuevo ancla a_caracas; se reutiliza _find_phrase_first para el interlineado del cuerpo.
- Verificado (self-test, código real): Prueba A (3 medios) 1 línea 19pt; Prueba B (12 medios) 3 líneas auto-escaladas a 12pt sin overflow ni truncado. Todo <= página 842.

**Bug fix · Variable `Interfaz_Integrada` no visible en editor de plantillas · 2026-06:**
- Causa raíz: el editor de plantillas (EmailTemplatesEditor / TemplatesAdminDialog) toma su paleta de la fuente única frontend `VARIABLE_CATEGORIES` (templateVariables.js), no del catálogo backend. La variable solo se había añadido al backend.
- Fix: `Interfaz_Integrada` agregada a VARIABLE_CATEGORIES → categoría 'Implementación (Técnico)' (label 'Interfaz integrada (Componente - Versión)'), disponible en ambos editores de plantillas.
- Verificado testing_agent iter285: 3/3 (backend catálogo + paleta editor + hint OtherActionsConfig). 100%.

**UI · Rediseño del menú de Configuración General (Settings.jsx) · 2026-06:**
- Los 9 accesos de configuración (Footer, Remitentes, Calendario, Notificaciones Push, Acciones de Cotizaciones, Otras Acciones, SLA, Centro de Respaldos, Usuarios Conectados) se reemplazaron por un GRID moderno de 2-por-fila (grid-cols-1 md:grid-cols-2), tiles clicables uniformes con chip de icono a color por acento, hover lift+shadow, rounded-xl. Se eliminó la mezcla de marcos (azul border-2 / amarillo / ninguno) → borde uniforme border-slate-200.
- 'Anexos Corporativos de Cotización' (CorporateAnexosCard) MOVIDO desde su ubicación previa a DENTRO del colapsable 'Configuración General' (debajo del grid).
- Tarjeta 'Refresco del Reporte de Embudo': marco amarillo border-2 → border neutro border-slate-200 (mantiene acento ámbar en icono/botón).
- Iconos nuevos importados: Bell (Notificaciones), Gauge (SLA). Rutas y data-testid de navegación preservados.
- Verificado self-test: render del grid + Anexos/Funnel dentro de General + navegación de tiles OK (/settings/other-actions, /settings/project-sla).

**UI · Barra de progreso porcentual en restauración de anexos ZIP (Cotizaciones) · 2026-06:**
- QuotesBundleMigrationModal.jsx (pestaña Importar → "2. Restaurar anexos (ZIP)"): se añadió una barra de progreso porcentual DEBAJO del monitor de texto que muestra el avance global de la importación.
- Estado nuevo `zipPct`. Se hace un PRE-PASS que carga todos los ZIP y suma el total de entradas (totalEntriesAll) para calcular % global; durante la subida un contador global `doneAll` actualiza `setZipPct(round(doneAll/totalEntriesAll*100))`.
- Barra: track emerald-100 + fill emerald-600 con transición suave; label 'Progreso de importación' + '{zipPct}%'. testids: bundle-import-attachments-progressbar / -pct.
- Verificado self-test (importación real de ZIP de 60 archivos): barra visible y evolucionando en vivo (0% → 3% → ...) junto al monitor de texto.

**UI · Mejora: ETA + contadores en barra de importación de anexos ZIP · 2026-06:**
- QuotesBundleMigrationModal.jsx: bajo la barra de progreso se añadió una fila con contador de restaurados (verde 'N OK') y fallidos (rojo si >0, gris si 0) + tiempo estimado restante (ETA) con spinner.
- Estado `zipStats {restored, skipped, eta}`; ETA = (totalEntriesAll - doneAll) / ritmo actual (items/seg calculado desde startTs). Helper fmtEta() formatea 'Xm YYs' / 'Ys'.
- testids: bundle-import-attachments-restored / -failed / -eta.
- Verificado self-test (import real de ZIP 120 archivos): fila en vivo "1 OK · 0 fallidos · ETA 1m 07s" al 1%, actualizándose con el avance.

**Feature (FASE 1) · Reestructuración Gestión de Taller V2 · 2026-07:**
- Sidebar: 'Gestión de Taller' ahora es grupo desplegable con 'Consulta de Taller' (/taller-equipos) y 'Recepción de Equipos' (/taller-recepcion). usePermission ROUTE_MODULE_MAP y MODULE→GROUP actualizados.
- Nueva página frontend TallerRecepcion.jsx: formulario simplificado (clon de reparaciones SIN 'Descripción de Falla' ni 'Fecha Estimada de Entrega'): cliente + modelos (POS/Pinpad) + seriales + resumen de validación + confirmar.
- Backend POST /api/taller/recepcion (quote_taller.py): inserta taller_equipos con estatus 'Recibido' (schema canónico: taller_equipo_id, modelo, modelo_id, fecha_ingreso, fecha_entrega) y dispara evento configurable.
- Nuevo evento 'Otras Acciones' taller_recepcion_equipos (other_actions_config.py) con variables (Nombre_Cliente, Equipos_Recibidos, etc.); notifica taller + cliente en copia (extra_cc).
- Permisos (permissions_catalog.py): módulo 'taller_equipos' renombrado 'Consulta de Taller' + nuevo 'taller_recepcion' 'Recepción de Equipos' (niveles Inactivo/Consulta/Edición Total). Header de TallerEquipos renombrado 'Consulta de Taller'. ESTATUS_OPTIONS +Recibido +Cotizado.
- Verificado: testing_agent iter286 100% backend+frontend; fix de alineación de campos y rename aplicados y re-verificados por curl.
- PENDIENTE FASE 2: trazabilidad en Cotización de Reparaciones ('Seleccionar de Equipos en Taller' → Recibido→Cotizado al emitir → En Reparación al aprobar; normalizar 'En reparación'→'En Reparación').

**Feature (Modo Oscuro FASE 2) · Cobertura de tintes de color y refinamiento · 2026-06:**
- index.css: bloque central `.dark` ampliado para remapear utilidades de color claras que la Fase 1 no cubría (bg-*-50/-100 y textos -600..-900) a tintes sutiles sobre fondo oscuro conservando el matiz semántico. Cubre blue/indigo/violet/purple/fuchsia/emerald/green/teal/cyan/sky/amber/yellow/orange/red/rose/pink.
- Añadidos selectores de atributo `[class*="bg-<c>-50/"]` / `-100/` para capturar variantes con opacidad (p.ej. bg-green-50/50) que no matchean las clases planas.
- Bordes de color (-100/-200) → tinte translúcido; hover:bg-slate/gray-50/100 → neutros oscuros.
- InboxCenter.jsx: SLA_STYLES con variantes dark: para filas/chips (verde/ámbar/rojo) — eliminado el tinte turbio en el Centro de Mensajes.
- Bug corregido: tarjetas "Comunicación enviada" del modal Bitácora (bg-green-50/50 + texto slate-400) quedaban ilegibles en oscuro; ahora tinte verde sutil + texto legible.
- Enfoque: cobertura centralizada en index.css (NO migración archivo-por-archivo de 181 componentes, descartada por riesgo/tiempo). Light mode intacto (todo scope .dark).
- Verificado self-test (screenshots): Dashboard, Clientes, modal Bitácora, Cotizaciones en modo oscuro. USER VERIFICATION PENDING.

**Bug fix (Modo Oscuro) · Contraste en contactos heredados (ficha de sucursal) · 2026-06:**
- Síntoma: en modo oscuro, la sección 'Contactos Globales del Principal (solo lectura)' de una sucursal mostraba nombres/correos casi invisibles (texto claro sobre fondo claro).
- Causa raíz: las filas usaban `bg-white/70` (blanco translúcido) no cubierto por los overrides `.dark`, mientras el texto slate-600/700 sí se aclaraba.
- Fix (index.css): `.dark [class*="bg-white/60".."/95"] { background-color: rgba(51,65,85,0.55) !important; }` — mapea blancos translúcidos de alta opacidad a superficie oscura. Los overlays de baja opacidad (/10../30) sobre gradientes quedan intactos.
- Verificado por testing_agent iter297 (100% frontend, modo claro sin regresión). Repro branch: cli_dc77d71c6d98 (parent INVERSIONES COLD 2024).

**UI · Orden jerárquico de contactos en ficha de cliente · 2026-06:**
- Clients.jsx: reordenados los bloques de contactos en el diálogo de edición para seguir jerarquía: 1) Contactos heredados del Grupo Económico, 2) Contactos Globales del Principal (solo lectura, si es sucursal), 3) Contactos de esta Sucursal/propios (locales).
- Antes el orden era Principal → Locales → Grupo. testids del bloque de grupo renombrados a inherited-group-contact-* para evitar colisión con inherited-contact-* del Principal.
- Verificado self-test (screenshots): cliente con grupo (Corporación Alfa QA) muestra Grupo primero; sucursal sin grupo (INVERSIONES COLD 2024) muestra Principal→Locales sin errores.

**Feature (V6) · Matriz_Contactos_Facturacion (contactos de facturación multinivel) · 2026-06:**
- Nuevo servicio `services/billing_contacts.py`: compute_billing_matrix(client_id) consolida contactos con propósito 'facturacion' en 3 niveles jerárquicos (Grupo Económico → RIF Principal → Sucursal), extrae SOLO {nombre, email}, dedup por email (case-insensitive) preservando jerarquía. render_billing_matrix_html() → 'Nombre <email>' por línea (escapado). build_billing_matrix_var(quote) para el motor de plantillas.
- Decisiones del usuario: filtro ESTRICTO (solo contactos con 'facturacion' explícito; legacy sin propósito NO se incluyen), dedup=SÍ, uso = SOLO variable en plantilla (sin auto-CC).
- Persistencia: se almacena `Matriz_Contactos_Facturacion` (lista JSON) en el doc de la cotización en create_quote, create_quote_with_pdf y update_quote (routes/quotes.py).
- Motor de plantillas: variable `{Matriz_Contactos_Facturacion}` expuesta en notification_engine._build_template_vars y workflow_notifications (usados por la acción approve). Usa la matriz almacenada; si falta, la recalcula en vivo.
- Frontend: variable agregada al catálogo unificado (templateVariables.js, categoría Cliente).
- Verificado (self-test e2e con API real + aserciones): POST /api/quotes almacena JSON solo con nombre+email (QA #1); el motor de aprobación renderiza 'Carlos Mendoza <cmendoza@...>' por línea (QA #2); filtro estricto, 3 niveles, orden jerárquico y dedup OK. Datos de prueba sembrados y eliminados sin tocar datos reales.

**Bug fix (Modo Oscuro) · Contraste en cuadrante 'Estatus y Definición Legal' (ficha de cliente) · 2026-06:**
- Síntoma: en modo oscuro, el primer cuadrante del formulario de cliente mantenía fondo claro (verde/amarillo) y las etiquetas quedaban invisibles.
- Causa raíz: el cuadrante usaba estilo INLINE backgroundColor (#f0fdf4/#fefce8), no sobrescribible por reglas .dark.
- Fix (Clients.jsx ~1045): reemplazado el style inline por classNames condicionales (bg-green-50/border-green-200/text-green-700 para 'Cliente'; bg-yellow-50/border-yellow-200/text-yellow-700 para otros), que ya tienen overrides .dark. Añadido border-yellow-100/200 a index.css.
- Verificado por testing_agent iter298 (100% frontend): ambos estados legibles en oscuro; modo claro sin regresión.

**Bug fix (Modo Oscuro) · Contraste en asistente de Cotizaciones (QuoteWizardDialog) · 2026-06:**
- Panel 'Detalles de Integración y Hardware': usaba gradiente claro (from-slate-50 to-blue-50) no cubierto por overrides .dark → etiquetas invisibles. Fix: dark:from-slate-900 dark:to-slate-800 dark:border-slate-700 (línea ~831).
- Panel 'Resumen Ejecutivo': chips/encabezados bg-blue-200 / bg-green-200 / bg-amber-400 con text-slate-900 quedaban ilegibles en oscuro. Fix: dark:bg-blue-500/25, dark:bg-green-500/25, dark:bg-amber-500/25 (líneas ~2280,2286,2294,2306-2308).
- Verificado por testing_agent iter299 (100% frontend): fondos oscuros + texto legible en oscuro; modo claro sin regresión (gradiente y chips vibrantes originales conservados).

**Bug fix (Modo Oscuro) · Contraste en editor de Plantillas de Correo (EmailTemplatesEditor) · 2026-06:**
- Los encabezados de acordeón 'Plantillas Personalizadas' (gradiente violet-50→fuchsia-50) y 'Plantillas de Proyecto (Implementación)' (gradiente orange-50→teal-50) usaban gradientes claros no cubiertos por overrides .dark → texto invisible en oscuro.
- Fix: variantes dark: en gradientes/bordes de ambos encabezados (~918/1078) y cuerpos expandibles (~929/1089): dark:from-violet-900/30 dark:to-fuchsia-900/30 y dark:from-orange-900/30 dark:to-teal-900/30, con dark:border-*-900.
- Verificado por testing_agent iter300 (100% frontend): fondos con tinte oscuro + títulos/contadores legibles; modo claro sin regresión.

**Feature+Fix · Flujo de Cierre de Proyecto de Integración (V6.1) · 2026-06:**
- (A) Envío garantizado de correos de cierre: services/other_actions_engine.dispatch_other_action ahora acepta guaranteed_to y SIEMPRE notifica a esos correos (To), aunque la acción 'Otras Acciones' no tenga recipientes configurados; dedupe para no duplicar (To+CC). routes/integrators.close_integrator_project construye guaranteed_close = contacts[].email + email de la ficha del integrador + adicionales del Modal 2. Verificado con test unitario (mock send_email): escenario QA de 4 destinatarios alcanzados sin duplicados.
- (B) Anexos acumulativos: Integrators.jsx handleCloseFilesAdd hace append con dedupe (nombre+tamaño), reset del input para re-seleccionar, lista con eliminar por archivo (removeCloseFile). Antes sobreescribía la selección.
- (C) Vista Previa del Certificado: nuevo endpoint POST /api/integrators/{id}/close/preview (pre-render PDF sin cerrar). Nuevo modal de aprobación (iframe blob) entre Modal 1 y Modal 2: 'Modificar' regresa al Modal 1 conservando datos, 'Aprobar' avanza al Modal 2. Verificado endpoint (200 application/pdf) y flujo UI.
- Verificado por testing_agent iter301 (Partes B y C 100%, endpoint preview OK). Nota: el modelo Contact (models.py) es estricto (name/phone/email); seeds/legacy con otro shape pueden romper GET /api/integrators (pre-existente, no modificado).

**Bug fix (Modo Oscuro) · Contraste en el editor 'Contenido del Mensaje' (RichTextEditor) · 2026-06:**
- Síntoma: en modales de notificación/Personalizar Comunicación, el texto del cuerpo del correo se veía oscuro sobre fondo oscuro (invisible). La Vista Previa sí se veía bien.
- Causa: el área editable del RichTextEditor heredaba fondo oscuro del tema, pero el texto del correo (colores oscuros) no se aclaraba.
- Fix: RichTextEditor.jsx wrapper con clase 'rte-root'; index.css fuerza '.dark .rte-root .ProseMirror { background:#fff; color:#1f2937 }' (+ enlaces #2563eb). El lienzo del editor es SIEMPRE claro (documento), barra/contador siguen el tema. Global para todas las instancias (QuoteModals, ProjectDetail, plantillas cliente/entidad, TemplatesAdminDialog).
- Verificado por testing_agent iter302 (100% frontend, estilos computados; modo claro sin regresión).

**Feature · Indicador de Cobro Recurrente ($) en Proyectos con RBAC por equipo · 2026-06:**
- Backend: PUT /api/projects/{id}/cobro-recurrente (routes/projects.py). RBAC: ADMIN o usuario de Ventas cuyo equipo (departamento → CORP/PyME) coincida con el equipo del proyecto (client_segment). Implementación/otras → 403. Persiste cobro_recurrente_status + cobro_recurrente_by + cobro_recurrente_by_name + cobro_recurrente_at (UTC). Helper _user_sales_team.
- Middleware (server.py): override de ruta que permite el PUT /cobro-recurrente sin permiso 'edit' del módulo (Ventas solo necesita ver la grilla; Implementación conserva la edición general). El handler valida equipo (defensa en profundidad).
- Frontend (Projects.jsx): botón $ (DollarSign) en la celda de acciones. Verde sólido si activo, gris si inactivo; deshabilitado + tooltip 'Acción exclusiva para el equipo comercial asignado al proyecto' si el usuario no es del equipo. canToggleCobro = isAdmin || userSalesTeam===client_segment. Update + toast + persistencia.
- REGRESIÓN corregida: la edición inicial borró por error el decorador @router.get('/projects/stats') → 404 que tumbaba toda la grilla. Restaurado. Se mantiene .catch() defensivo en fetchProjects (stats) para resiliencia.
- Verificado: backend por curl (CORP:CORP=200/PYME=403; PYME:PYME=200/CORP=403; IMPL=403; ADMIN=200; persistencia OK) y frontend por testing_agent iter303 (feature 100%: verde/gris, disabled+tooltip, persistencia tras F5).
- QA users desechables (password Test1234!): qa_corp/qa_pyme/qa_impl @megasoft.com.ve (ver test_credentials.md).

**Feature · Filtro de Cobro Recurrente en grilla de Proyectos · 2026-06:**
- Projects.jsx: nuevo Select 'Cobro: Todos/Cobrado/Pendiente' (data-testid project-cobro-filter) que filtra client-side por cobro_recurrente_status. Integrado con hasActiveFilters y el botón 'Limpiar'.
- Verificado (screenshot): 'Cobrado' muestra solo proyectos con $ en verde. Solo frontend.

**UI · Indicador $ por defecto en ROJO (pendiente) · 2026-06:** Projects.jsx: estado off del botón de cobro recurrente cambiado de gris a rojo sólido (bg-rose-600); on sigue en verde (bg-emerald-600). Verificado por screenshot.

**Fix (Infra/Anexos) · Persistencia de anexos de cotizaciones cross-deploy · 2026-06:**
- Causa raíz: anexos servidos FS-local-first; tras cada deploy el disco del pod queda vacío → todo se servía desde Object Storage (lento) y los archivos que quedaron solo en disco (no subidos a storage) se perdían. El respaldo/restore del disco era innecesario (Object Storage ya persiste) y por eso crecía.
- Fix: (1) Cache-warming — al servir desde Object Storage se reescribe el PDF en el disco del pod (attachments.py y quote_history.py) → próximas aperturas instantáneas. (2) Auto-sanación — al servir desde disco se sube en 2º plano a Object Storage (idempotente). (3) Backfill ejecutado en PREVIEW: 805 anexos → 653 ya en storage, 147 subidos, 5 irrecuperables (perdidos en deploy previo, cotización COT-2026-04-037-PYME).
- Verificado: curl (borrado del archivo local → descarga 200 desde storage + recreación en disco) y testing_agent iter304 (2/2 descargas UI 200/application/pdf/%PDF).
- ACCIONES EN PRODUCCIÓN (pendientes del usuario): (a) redeploy para llevar el código; (b) ejecutar UNA vez POST /api/admin/attachments/recover-to-storage (paginado dry_run=false) para backfill de TODOS los anexos de producción; (c) confirmar con Soporte que APP_ENV en producción es estable/'production' (el namespace pdfs/{APP_ENV} depende de ella). Tras (a)+(b), ya NO se requiere respaldo/restore del disco.
