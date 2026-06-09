# CHANGELOG — MegaNexus

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
- Las URLs de preview viejas del handoff están dormidas; URL correcta del entorno: `https://tech-spec-downloader.preview.emergentagent.com`.
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
