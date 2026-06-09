# CHANGELOG — MegaNexus

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
