# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.


### Iteration 52: Contacto Inicial — Fecha último/próximo contacto + Twin Scrollbar — Feb 2026

**Backend** (`routes/initial_contacts.py`):
- `InitialContactDocument` extendido con `next_contact_date: Optional[str]`.
- Endpoint `POST /initial-contacts/{id}/document` ahora actualiza:
  - `last_contact_date = now` (automático en cada gestión documentada).
  - `next_contact_date = data.next_contact_date` solo si el agente la informa (no sobrescribe con vacío).

**Frontend** (`pages/InitialContacts.jsx`):
- 2 nuevas columnas en la grilla, posicionadas **inmediatamente a la derecha** de "Fecha límite de contacto": "Fecha último contacto" y "Fecha próximo contacto". Render con `--/--/----` cuando son nulos (evita errores de render).
- Modal "Documentar Gestión" ahora incluye campo opcional `<input type="date">` para "Fecha próximo contacto".

**Componente nuevo** `components/TwinScrollTable.jsx`:
- Wrapper con barras de desplazamiento horizontal **arriba + abajo** de la tabla.
- Sincronización 1:1 vía refs + flag `syncingRef` (previene bucles infinitos) + `requestAnimationFrame` para release.
- `ResizeObserver` actualiza el spacer superior cuando el contenido cambia (filas dinámicas).
- Tabla forzada a `min-w-[1500px]` con `whitespace-nowrap` en cada `<th>` para que el ancho mínimo sea autoajustable y nunca haya solapamiento.

**Validación e2e**: documentación + fecha próxima persistida correctamente en backend; columnas visibles con datos reales en preview; sin runtime errors.



### Iteration 51: Fix Matriz cruzada Equipos + descuento en PDF — Feb 2026

**Bug 1 — Subcategorías de Implementaciones aparecían bajo Equipos** (`pages/ActionNotificationsConfig.jsx::BusinessTypeAccordion`):
- Causa: la matriz renderizaba TODAS las subcategorías sin filtrar por `allowedMap` cuando `business.has_sub=true`.
- Fix: aplicar el mismo filtro que ya tenía el bloque Override — `subCategories.filter((s) => (allowedMap[`${business.id}|${s.id}`] || []).length)`.
- Resultado: bajo "Equipos y Accesorios" sólo aparecen "Clientes Pyme" y "Clientes Corporativos".

**Bug 2 — Descuento no se reflejaba en el PDF impreso al cliente** (`routes/quotes.py::generate_equipment_quote_pdf`):
- `EquipmentQuotePDFRequest` extendido con `discount_type`, `discount_value`, `discount_amount_usd`.
- Cálculo del PDF aplica descuento **antes** del IVA (afecta la base imponible): `subtotal → −descuento → base → +IVA → TOTAL`.
- Si el cliente envía `discount_amount_usd` ya calculado se prefiere para evitar discrepancias de redondeo.
- Línea "Descuento (X%):" o "Descuento:" agregada al bloque de totales del PDF con color ámbar (`#c2410c`).
- El doc Mongo de la cotización guarda `discount_type`, `discount_value`, `discount_amount_usd` para auditoría/reporte.

**Validación**: PDF generado con `pdftotext` confirma presencia de "Descuento (10%):" entre Subtotal e IVA. Screenshot de la Matriz muestra solo 2 subcategorías bajo Equipos.



### Iteration 50: Equipos PYME/CORP + Descuento + Override drill-down — Feb 2026

**1. Dropdown "Equipos y Accesorios"** (`components/quotes/NewQuoteButtons.jsx`):
- Botón ahora abre dropdown con 2 opciones idénticas a Implementaciones: Clientes Pymes / Clientes Corporativos.
- `Quotes.jsx` propaga el segmento (`PYME`/`CORP`) al `EquipmentQuoteWizard` vía `equipmentWizardSegment`.

**2. Campo Descuento** (`components/EquipmentQuoteWizard.jsx`):
- Sólo visible en modo Equipos (no en Reparaciones).
- Toggle `%` / `$` + input con validación (no excede 100% ni el subtotal).
- Footer de la tabla muestra **Subtotal → Descuento → TOTAL** con línea ámbar para el descuento.
- Payload incluye `discount_type`, `discount_value`, `discount_amount_usd`, `subtotal_usd`, `total_usd`, `client_segment`, `sede`.

**3. Subcategorías Equipos** (`routes/action_notifications.py` + `notification_engine.py`):
- `BUSINESS_TYPES.equipos.has_sub = True`.
- Nuevas subcategorías: `clientes_pyme` (Clientes Pyme) y `clientes_corp` (Clientes Corporativos).
- `ALLOWED_ACTIONS_BY_BIZ_SUB`: ambas subcategorías heredan las mismas 5 acciones; `equipos|None` se mantiene para legacy compat.
- `_quote_to_biz_sub()`: para cotizaciones de Equipos ahora deriva `clientes_pyme`/`clientes_corp` según `sede`/`client_segment`.
- Migración idempotente al startup (`equipos_subcat_v1`): clona configs y overrides de `equipos|None` a ambas subcategorías.

**4. Override de Acciones drill-down** (`pages/ActionNotificationsConfig.jsx::BusinessOverridesBlock`):
- Refactor completo: al expandir un negocio con subcategorías, se muestra **solo la lista de subcategorías** como pills clickeables. Las acciones aparecen únicamente cuando el usuario selecciona una subcategoría.
- Reduce drásticamente el render inicial (antes: todas las subcats × todas las actions). Negocios sin subcategoría (Reparaciones, Proyectos Directos) mantienen el render directo.

**Validación e2e** (screenshots): dropdown PYME/CORP funcional, wizard abre con chip "Segmento: Pyme", drill-down de Override muestra subcategorías → click → acciones. Sin runtime errors. Backend tests `tests/test_iteration42_inbox_center.py` siguen 1/1 PASSED.



### Iteration 48: Centro de Mensajes → Chat Continuo (WhatsApp Style) — Feb 2026

**Refactorización mayor** del modelo de mensajería interna: las respuestas user-to-user ya NO crean filas duplicadas. Cada par de usuarios + asunto comparte UN solo hilo donde se anexan mensajes cronológicamente.

**Modelo de datos** (Mongo):
- `conversations`: cabecera del hilo 1:1 `{conversation_id, participants[sorted], participants_meta, subject, subject_normalized, last_message_at, last_preview, unread_for[user_id], deleted_for[user_ids], created_at}`. Índice único en (`participants`, `subject_normalized`).
- `conversation_messages`: mensajes individuales `{message_id, conversation_id, from_user_id, from_user_name, body_plain, created_at, read_by[user_ids]}`.

**Backend** (`/app/backend/`):
- `services/conversation_service.py` — `find_or_create_conversation()`, `append_message()` (incrementa unread, revive si fue soft-borrado), `mark_conversation_read()`, `migrate_legacy_user_messages()` (idempotente, corre al startup).
- `routes/inbox.py`:
  - `POST /api/inbox/send` reescrito → un hilo por par de usuarios + asunto normalizado. Múltiples destinatarios = N hilos 1:1.
  - `GET /api/inbox/me` merges: notificaciones del sistema (`type:"notification"`) + conversaciones del usuario (`type:"conversation"`) ordenadas por timestamp.
  - `GET /api/inbox/conversations/{id}/messages` — historial completo + auto-marca como leído.
  - `POST /api/inbox/conversations/{id}/messages` — anexa al hilo.
  - `DELETE /api/inbox/conversations/{id}` — soft-delete sólo para el usuario actual (el otro participante sigue viendo; si responde, el hilo "revive").
- `server.py` startup: crea índices y migra automáticamente los mensajes user-to-user heredados (Iter46/47).

**Frontend**:
- `components/ChatThread.jsx` — Dialog modal con burbujas (violeta a la derecha = mías, blancas a la izquierda = del otro), header gradient, timestamp por mensaje, autoscroll al fondo, textarea fija abajo, Enter envía / Shift+Enter nueva línea, optimistic UI en el envío, archivado de hilo con confirmación.
- `components/InboxCenter.jsx` — render condicional por `type`: notificaciones usan iframe expandible existente; conversaciones muestran avatar + nombre + chip "Chat · {asunto}" + preview + badge rojo de no-leídos → click abre `ChatThread`. Botón papelera ahora archiva el hilo completo.

**Tests** (`tests/test_iteration42_inbox_center.py`): suite ampliada con 8 nuevas validaciones Iter48 → **1/1 PASSED**:
- Hilo único: 4 mensajes consecutivos producen 1 sola fila en bandeja.
- Cronología: messages ordenados asc.
- Asunto diferente entre mismos usuarios = hilos separados.
- Soft-delete sólo para el usuario actual (el doc persiste, el otro lo sigue viendo).
- Protección self-message (400 si destinatario = sender).
- Summary cuenta hilos.

**Validación e2e** (screenshot): UI con burbujas alineadas estilo WhatsApp, envío exitoso con preview actualizándose en bandeja, no se duplican filas, sin runtime errors.



### Iteration 47: Botón "Responder" en mensajes user-to-user — Feb 2026

**Nueva capacidad UX** del Centro de Mensajes: cada mensaje recibido **de otro usuario** ahora muestra un botón **"Responder"** violeta debajo del cuerpo. Los mensajes generados por el sistema (notificaciones de cotizaciones/proyectos) **no** muestran el botón — la respuesta solo aplica a comunicación humana.

**Frontend** (`components/InboxCenter.jsx` + `components/NewMessageDialog.jsx`):
- `NewMessageDialog` ahora acepta prop `initialData = {recipients, subject, body}` y resetea el formulario con esos valores al abrirse.
- `InboxCenter` añade `handleReply(msg)` que:
  - Pre-rellena el destinatario con el `from_user_id` original.
  - Prefija el asunto con `Re:` (idempotente — no duplica si ya está).
  - Inserta una cita estilo email: `----- Mensaje original -----` + `De: {nombre}` + cada línea con `> `.
- Botón solo se renderiza si `msg.is_user_message && msg.from_user_id`.

**Backend**: sin cambios — reutiliza `POST /api/inbox/send` existente.

**Validación e2e**: confirmado por screenshot:
- Mensaje user-to-user → muestra "Responder" → click abre modal pre-relleno con destinatario, asunto "Re: ..." y body con cita.
- Mensaje del sistema → **no** muestra el botón.
- Sin runtime errors.



### Iteration 46: Mensajería interna user-to-user en el Centro de Mensajes — Feb 2026

**Nueva capacidad**: ahora los usuarios pueden enviarse mensajes directos entre sí desde el mismo Centro de Mensajes (estilo WhatsApp, sin email externo).

**Backend** (`/app/backend/routes/inbox.py`):
- Nuevo endpoint **`POST /api/inbox/send`** con payload `{recipient_user_ids: [str], subject, body}`. Inserta una copia individual en la bandeja de cada destinatario (hasta 50 por envío).
- Anti-XSS: el `body` se escapa con `html.escape()` y se envuelve en `<pre style="white-space:pre-wrap">` para preservar saltos de línea sin permitir HTML del cliente.
- Cada mensaje persistido lleva marcadores `is_user_message=True`, `from_user_id`, `from_user_name`, `from_user_email`, `body_plain` (para búsquedas futuras).
- Reutiliza todo el ciclo de vida existente: SLA, leer/no-leer, soft-delete.

**Frontend**:
- `components/NewMessageDialog.jsx` — modal con multi-select (chips removibles), buscador de usuarios (excluye al sender), asunto (≤200), textarea (≤4000) con contador.
- `components/InboxCenter.jsx` — botón **"Nuevo mensaje"** en el header (junto a refresh), chip violeta **"De: {nombre}"** en cada mensaje user-to-user para distinguirlo de notificaciones del sistema.

**Tests** (`tests/test_iteration42_inbox_center.py`): suite ampliada con:
- Envío a múltiples destinatarios (verifica `is_user_message`, `from_user_id`, render del body, count).
- Validación `recipient_user_ids` vacía → 422.
- Anti-XSS: HTML del body se escapa (`<script>` → `&lt;script&gt;`).

**Validación e2e**: modal funcional, envío exitoso (toast), chip "De:" visible, body con saltos de línea preservados, sin runtime errors.



### Iteration 45: Fix definitivo "Script error" + iframe sandbox para HTML de correos — Feb 2026

**Diagnóstico real** (gracias al feedback iterativo del usuario y a capturar `pageerror` con Playwright):

1. **El cuerpo HTML del correo es un documento completo** (`<!DOCTYPE><html><head><body>`). Inyectarlo dentro de un `<div>` vía `dangerouslySetInnerHTML` producía HTML inválido y posibles errores de hidratación.
2. **Causa raíz del "Script error." opaco**: axios tenía un bug interno al procesar respuestas de error 4xx cuando `responseType: 'blob'`:
   ```
   Failed to read the 'responseText' property from 'XMLHttpRequest':
   The value is only accessible if the object's 'responseType' is '' or 'text' (was 'blob').
   ```
   El TypeError rebotaba a `window.onerror` y la React Error Overlay lo reportaba como "Script error." sin contexto.

**Fixes** (`InboxCenter.jsx`):
- **Render del body**: nuevo componente `EmailHtmlFrame.jsx` que monta el HTML en un **`<iframe srcDoc sandbox="allow-same-origin">`**. Aísla los estilos del email, elimina hidratación inválida, bloquea cualquier JS embebido y mide el `scrollHeight` para ajustar altura dinámica (mín 120px, máx 1600px).
- **Descarga del adjunto**: reemplazo de `axios.get({responseType: 'blob'})` por **`fetch()` nativo**. Manejo explícito de 410/404/401 con toasts amigables. Limpieza diferida del blob URL.

**Validación e2e**:
- Caso descarga válida → `Cotizacion_OK.pdf` descargado correctamente.
- Caso mensaje legacy (410) → toast amigable "*Este adjunto pertenece a un mensaje antiguo y ya no está disponible.*", **sin runtime error**.
- Console limpia: solo el `Failed to load resource: 410` informativo de red, ya no aparece `Script error.`.



### Iteration 44: Fix descarga PDF + Header llamativo + Banner post-login — Feb 2026

**Bug fix — Descarga de adjuntos rompía con "Script error"** (`InboxCenter.jsx::handleDownloadAttachment`):
- Causa raíz: `a.remove()` y `URL.revokeObjectURL()` ejecutados síncronamente justo después del `a.click()` interferían con el descargador del navegador y producían un error opaco interceptado por la React Error Overlay.
- Fix: limpieza diferida con `setTimeout(250ms)`, doble-click bloqueado vía estado `downloading[key]`, re-envoltura defensiva del binario en `new Blob([data], { type })`, manejo explícito de 404/410.
- UX: botón muestra spinner durante descarga + toast `"Descargando {filename}"`.

**Header Centro de Mensajes — color más llamativo**:
- Cabecera repintada con gradiente `from-indigo-600 via-violet-600 to-fuchsia-600`, ícono `Inbox` sobre fondo glass, contador "sin leer" en blanco bold, halo decorativo `blur-3xl` sutil.

**Banner post-login con conteo sin leer**:
- Nuevo helper `utils/inboxWelcome.js::showInboxWelcomeToast()` consulta `GET /api/inbox/me/summary` después del login y emite un `toast.message` durante 7s: *"Rafael, tienes N mensajes sin leer · Revisa tu Centro de Mensajes en el Dashboard."*.
- Integrado en ambas rutas de autenticación: `pages/Auth.jsx` (email/password) y `components/AuthCallback.jsx` (Google OAuth).
- Best-effort: si el endpoint falla, el login no se interrumpe.

**Validación e2e** (screenshot tool): descarga del PDF de muestra sin runtime errors, banner visible en `/quotes` tras login, header con gradiente vibrante en Dashboard. Tests backend `tests/test_iteration42_inbox_center.py` siguen pasando (1/1).



### Iteration 43: Descarga de Adjuntos en el Centro de Mensajes — Feb 2026

**Mejora UX del Centro de Mensajes** (Iter42): los anexos enviados con cada notificación ahora son **descargables** desde la bandeja interna.

**Backend** (`/app/backend/`):
- `services/inbox_service.py` — `deliver_to_inbox()` ahora persiste por cada anexo: `filename`, `size_bytes`, `mime_type` (auto-inferido por extensión: pdf/jpg/png/xlsx/csv) y **`content_b64`** (el binario original codificado).
- `routes/inbox.py`:
  - `GET /api/inbox/me` — **aliviado**: nunca devuelve `content_b64` en el listado (sólo metadatos).
  - `GET /api/inbox/{id}/attachments/{idx}` — nuevo endpoint que devuelve el binario con `Content-Type` correcto y `Content-Disposition: attachment` (soporta nombres UTF-8 vía RFC 5987). Devuelve **410 Gone** si el mensaje es legacy sin `content_b64`.

**Frontend** (`/app/frontend/src/components/InboxCenter.jsx`):
- Sección **"Adjuntos (N)"** dentro de cada mensaje expandido con botones pill clickeables (icono `Download`, nombre, tamaño humanizado KB/MB).
- Descarga via blob (`responseType: 'blob'` + `URL.createObjectURL`) preservando el filename original.
- Toast amigable cuando el adjunto no está disponible (mensajes legacy).

**Tests** (`/app/backend/tests/test_iteration42_inbox_center.py`) consolidados en **1/1 PASSED**: cubren los 4 escenarios end-to-end (smoke, SLA + soft-delete, persistencia `delivery_channel`, descarga de adjuntos con 200/404/410).



### Iteration 42: Centro de Mensajes — Bandeja Interna del Usuario — Feb 2026

**Nuevo módulo** que reemplaza el correo electrónico como canal de despacho cuando el admin lo decide en la matriz de configuración.

**Backend** (`/app/backend/`):
- **Colección nueva** `inbox_messages` (soft-delete vía `deleted_at`).
- `services/inbox_service.py::deliver_to_inbox(...)` — análogo a `send_email()`, persiste el mensaje con el footer global anexado y metadatos de adjuntos.
- `routes/inbox.py` — endpoints user-facing:
  - `GET /api/inbox/me` — listado con `sla_color` calculado en backend (verde ≤24h · amarillo 24-48h · rojo >48h).
  - `GET /api/inbox/me/summary` — contadores `{total, unread, by_sla}`.
  - `PATCH /api/inbox/{id}/read` — idempotente.
  - `DELETE /api/inbox/{id}` — soft delete.
- `routes/action_notifications.py` — modelo `RecipientRow` ahora incluye `delivery_channel: "email" | "inbox"`. Cliente externo (`client_field`) se fuerza a `email`.
- `services/notification_engine.py` — bifurcación: si `delivery_channel == "inbox"` y destinatario interno, omite SMTP/Resend e inserta en `inbox_messages`. Los CCs siempre van por correo.

**Frontend** (`/app/frontend/`):
- `components/InboxCenter.jsx` — bandeja full-width en `Dashboard.jsx` entre KPIs y Actividad Reciente. Borde lateral coloreado por SLA. Render del cuerpo con `dangerouslySetInnerHTML` (HTML controlado por admin). Marcar leído solo al expandir.
- `pages/ActionNotificationsConfig.jsx` — nueva columna **"Canal"** en la matriz por fila destinatario; dropdown Email/Centro de Mensajes habilitado solo para usuarios internos.

**Tests** (`/app/backend/tests/test_iteration42_inbox_center.py`) — 3/3 PASSED:
1. Smoke endpoints `/inbox/me` y `/summary`.
2. SLA verde/amarillo/rojo + soft-delete.
3. Persistencia de `delivery_channel` + forzado a `email` para `client_field`.



### Iteration 41: Ocultar sección redundante "Seriales (Implementación)" — Feb 2026

**Cambio de UI en `ProjectDetail.jsx`**:
- Se envuelve el bloque "Seriales (Implementación)" en un renderizado condicional.
- **Condición**: solo se muestra cuando `(project.pinpad_serials || []).length === 0 && (project.equipments || []).length === 0`.
- **Razón**: si los seriales ya vienen precargados desde "POS/Pinpad (Inventario)" o desde "Modelo y Seriales de Equipos", la captura manual es redundante y crea confusión al implementador.
- **Validación**: probado con `prj_e7c29c064f93` (100 pinpads precargados → sección oculta) y `prj_af473b25a253` (sin precargas → sección visible).
- **Archivo**: `/app/frontend/src/pages/ProjectDetail.jsx` (~línea 1179).



### Iteration 39: Diferenciación visual Proyectos Directos · Bloqueo Detalle sin implementador · Métrica PVV en Reportes — Feb 2026

**4 cambios coordinados para mejorar gobernanza y análisis operativo del módulo Proyectos**:

**A. Diferenciación visual — Proyectos Directos** (`Projects.jsx`):
- Fila completa con fondo **ámbar suave** (`bg-amber-50/70`) cuando `project.direct_project=true`.
- **Badge "Directo"** con ícono `Zap` (rayo) en la columna cliente, junto al RIF, color ámbar corporativo.
- Atributos `data-testid="project-direct-badge"` y `data-direct-project="true"` para tests y filtros futuros.

**B. Bloqueo de seguridad — Detalle sin implementador** (`Projects.jsx`):
- Botón ojo (Detalle) ahora se **deshabilita** si `assigned_to_name` está vacío.
- Click no responde (`disabled=true`, cursor-not-allowed, opacidad 60%).
- Tooltip explicativo: *"Detalle no disponible: el proyecto debe tener un implementador asignado"*.
- Activación automática al asignar implementador (depende de `hasAssignee`).

**C. Nuevos campos informativos en Detalle del Proyecto** (`ProjectDetail.jsx`):
- En sección Implementación, debajo de Integrador/Aplicativo, se agregan **Nro de Cajas** y **Nro de PVV** read-only en grid de 2 columnas.
- PVV destacado en color índigo bold con label *"Cajas × Bancos × Productos"*.
- Valor heredado del backend (no recalculado en frontend).

**D. Helper de PVV** (`services/project_pvv.py` — nuevo módulo):
```python
PVV = Cajas × Σ(productos_por_banco_en_matriz)
```
- Homologado con la fórmula del Resumen Ejecutivo del cotizador comercial ("Total de Terminales Virtuales").
- Si `implementation_matrix` está vacía → PVV = cantidad_cajas (proyecto en estado inicial).
- Inyectado automáticamente en `GET /api/projects` y `GET /api/projects/{id}` como `pvv_count`.

**E. Reporte de Carga PDF** (`routes/projects.py`):
- **Nueva columna "PVV"** en la tabla de cada implementador (color índigo bold para destacar).
- **Total PVV** en la línea de resumen de cada implementador (junto a Nro de Proyectos y Nro de Cajas).
- **Total PVV global** en el subtítulo del reporte.
- **Ranking ordenado por PVV descendente** (en lugar de cajas) — desempate por número de proyectos y luego por cajas.
- Título del ranking actualizado: *"Ranking de Carga — Implementadores por PVV"*.
- Tarjetas del ranking ahora muestran "**X PVV** · N proyecto(s) · M caja(s)".
- CSS ajustado: columna `c-pvv` (7%) + clase `td.pvv` con color índigo.

**Testing**:
- Backend: 7/7 PASS (helper, GET /projects, GET /projects/{id}, workload PDF).
- Frontend E2E: 7/7 PASS (9 filas direct con bg ámbar, 9 badges, 10 botones disabled + 42 enabled, navegación bloqueada, PVV mostrado en detalle).



### Iteration 38: Refinamientos finales Proyectos Directos — Reglas de Validación, UX Carga Continua y Nomenclatura PRY-XXXX — Feb 2026

**Cambios solicitados por el usuario tras pruebas de campo**:

**A. Seriales Pinpad — Modelo OPCIONAL** (backend + frontend):
- Modelo `DirectProjectSerial.modelo` ahora es `Optional[str] = ""`.
- La grilla de seriales en UI ahora muestra **solo el campo Serial** (eliminado input Modelo por fila).
- Nuevo **TextArea de carga rápida** (`data-testid='dp-bulk-serials-text'`): el operador pega seriales separados por línea, coma, ; o tab → botón "Agregar al lote" los integra en bloque.
- Plantilla Excel simplificada a una sola columna `Serial`.
- Excel parser **acepta dos layouts**: (a) legacy `[Modelo, Serial]` o (b) simplificado `[Serial]` solamente. Auto-detección por columnas presentes.

**B. Reglas de Consistencia — Reingeniería**:
- ❌ **Eliminada**: validación `suma(boxes_grid[*].quantity) == cantidad_cajas`. La grilla ahora es **INDEPENDIENTE** de la cabecera (refleja la realidad comercial: un banco puede tener más productos que cajas físicas).
- ✅ **Mantiene** (multitienda): `suma(stores[*].box_count) == cantidad_cajas`.
- ✅ **Nueva validación HARD** (VPOS/MPOS): `len(pinpad_serials) == cantidad_cajas`. Consistencia de inventario simétrica.
- Badge dinámico junto a "Seriales Pinpad" muestra `N / cantidad_cajas` (verde si match, rojo si no).
- El header del Reel ya no muestra `X/Y` relativo a la cabecera — solo `Total grilla: X` informativo.

**C. UX Carga Continua post-submit**:
- Tras un POST exitoso, el sistema **NO redirige** a `/projects/{id}`.
- Se ejecuta **reset integral del formulario** (`setForm(INITIAL_FORM)` + `setBulkSerialsText('')`).
- El foco del cursor regresa automáticamente al **combobox Cliente** vía `useImperativeHandle(.focus)` exposed en `ClientCombobox`.
- **Banner verde sticky** (`data-testid='dp-last-created-banner'`) muestra el `PRY-XXXX` recién creado, indica si el correo se envió o no, ofrece botón **Ver Proyecto** + botón cerrar.
- Optimizado para captura consecutiva sin recargar pantalla.

**D. Numeración estándar PRY-XXXX** (cambio sobre Iter34/35):
- Eliminada la sobreescritura a `PRD-XXXX`. Ahora los proyectos directos comparten la **secuencia estándar `PRY-YYYY-MM-NNN-SEDE`** del resto del sistema.
- `_create_project_from_quote` asigna PRY- internamente; el endpoint mantiene `origin='direct'` y `direct_project=true` como flags de auditoría.

**E. Backend completo**:
- POST `/api/direct-projects` → crea PRY-, genera Ficha Técnica PDF (reusando `generate_implementation_pdf` del flujo regular), dispara notificación vía motor dinámico leyendo configuración de `Configuración de Acciones → Proyectos Directos → send_to_implementation`.

**Testing**:
- Backend pytest 9/10 PASS → corregido el caso del Excel solo-Serial → 10/10 verificado manualmente con curl.
- Frontend E2E iter16: 11/11 escenarios PASS (combobox reset+focus, banner PRY-2026-05-035-PRI, URL no redirige, form reseteado, badge dinámico, validaciones visibles, grilla independiente).



### Iteration 37: Bug Fixes Multitienda + Reingeniería UX modal "inherited" — Feb 2026

**Tres fixes coordinados en el flujo de Multitienda del cotizador**:

**A. BUG FIX — Parser Excel "Detalle de Tiendas"** (`BranchDetailPanel.jsx`):
- **Root cause**: línea 58 descartaba TODA fila cuyo nombre contuviera "tienda" → bloqueaba nombres legítimos como "Tienda Los Chaguaramos", "Tienda Av. Urdaneta", etc. Heurística rota.
- **Fix**: detección de cabecera por COLUMNA B (Cantidad debe ser número válido > 0). Nunca por columna A. También: soporte para floats (3.0), strings con espacios y comas decimales.
- **Validado** con el Excel real del usuario (7 filas, todas con prefijo "Tienda") → 7/7 importadas correctamente.

**B. BUG FIX — Asincronía modal "Control Multitienda"** (`Quotes.jsx`):
- **Root cause**: stale closure de `multistoreQuoteId`. El `setTimeout(() => handleProjectTypeSelect(inferred), 0)` se ejecutaba antes de que React committeara el `setMultistoreQuoteId(quoteId)` → cuando `advanceToMultistorePhase` leía el state, era `null` → GET `/quotes/null` → 404 → fallback a fase `ask` (incorrecto). Esto forzaba al usuario a pulsar "Volver" para refrescar.
- **Fix**: `openMultistoreDialog` ahora pasa `quoteId` EXPLÍCITO al setTimeout. `handleProjectTypeSelect` y `advanceToMultistorePhase` aceptan `overrideQuoteId` como primer parámetro y lo usan en cascada (`effectiveQuoteId = overrideQuoteId || multistoreQuoteId`). Adicionalmente, `advanceToMultistorePhase` ahora hace **GET fresco** a `/api/quotes/{id}` en lugar de leer del state `quotes` cacheado.

**C. REINGENIERÍA UX — Fase "inherited" editable** (`QuoteModals.jsx`):
- Eliminados los botones binarios "No, Modificar" + "Sí, Confirmar y Enviar".
- La grilla ahora muestra **inputs editables inline** (nombre + cantidad de cajas).
- Nuevos controles: botón **"+ Agregar Sucursal"** (agrega fila en blanco), botón **Eliminar** (`Trash2`) por fila, total recalculado en vivo en el footer.
- Botón único final: **"Conformar Distribución"** (habilitado solo cuando todas las filas tienen nombre + cantidad).
- Esto homologa el comportamiento del módulo Proyectos Directos y permite modificaciones de última hora sin reiniciar el wizard.

**Testing**: Frontend E2E iter15 → 100% PASS (3/3 escenarios + parser validado).



### Iteration 36: Bug Fix RBAC — Operaciones recupera acciones en Reparaciones (regla restrictiva ahora SOLO aplica a MPOS Imple+POS) — Feb 2026

**Bug reportado**: la implementación previa bloqueó al Departamento de Operaciones para ejecutar acciones en TODAS sus cotizaciones (Reparaciones, Equipos, Implementación). La regla "solo Configuración" debía aplicar exclusivamente a cotizaciones `fast_track` (MPOS Imple+POS) originadas por Ventas Pyme.

**Causa raíz** (`/app/frontend/src/components/quotes/QuotesTable.jsx` L318):
```js
const canEditNonConfig = canEdit && !opsReadonly;  // ← incorrecto: aplicaba a todo
```

**Fix mínimo** (cambio quirúrgico de 1 línea):
```js
const canEditNonConfig = canEdit && !(opsReadonly && isFastTrack);
```

Ahora la matriz de comportamiento queda alineada con el requerimiento:

| Categoría | Origen / Sede | Acciones para Operaciones |
|---|---|---|
| MPOS (Imple+POS) — `fast_track` | Ventas Pyme | **Solo "Configuración"** (resto deshabilitado) |
| Reparaciones — `repair` | Operaciones | **Override estándar** según estado del registro |
| Equipos — `equipment` | Cualquier sede | **Override estándar** según estado del registro |
| Implementación — `implementation` | Cualquier sede | **Override estándar** según estado del registro |

**Validación E2E** (Playwright con `ragg1008@hotmail.com` / Operaciones / Coordinador):
- Reparación COT-2026-05-240-PYME: menú dropdown muestra los 8 ítems estándar habilitables según override (Modificar, Enviar al Cliente, Aprobación, Factura, Registrar pago, Pago validado, Entregada, Eliminar) ✅
- MPOS Imple+POS COT-2026-05-192-PYME: menú restringido a 2 ítems técnicos (Configuración + Validar Pago) ✅
- Equipos: sin restricción ✅

**Tests pytest**: `/app/backend/tests/test_iteration36_ops_dept_actions.py` — 11/11 PASS validando el invariant `canEditNonConfig` para repair/equipment/implementation/fast_track × ops/non-ops × can_edit true/false.

**Persistencia auditoría**: el cambio es puramente de visibilidad/habilitación UI. No altera bitácora, históricos ni datos persistidos. Las acciones ya ejecutadas previamente permanecen intactas (criterio de aceptación 3).



### Iteration 35: Proyectos Directos v2 — Cascada Integrador→App, dropdown Pinpad, reel rediseñado, Excel robusto — Feb 2026

**Refinamientos sobre Iter34** según requerimiento del usuario:

**A. Cascada Integrador → Aplicación** (`DirectProjectCreation.jsx`):
- Dropdown 1: nombres únicos de integradores (`distinct name`). 242 opciones.
- Dropdown 2: "Aplicación" se habilita solo cuando hay integrador elegido; muestra exclusivamente las apps de ese integrador (agrupa por nombre, separa por app_name). Header indica cuántas apps existen (ej. "Aplicación (2)").
- Persiste el `integrator_id` del documento específico (apto+integrador exacto).

**B. Depuración**:
- ❌ Eliminado campo "Link Payment Gateway (opcional)".
- ❌ Eliminada sección "Seriales Equipos (otros)" — solo queda Seriales Pinpad.

**C. Modelo Pinpad como dropdown** filtrado:
- Carga `/api/hardware` y filtra `type ∈ {Pinpad, POS}` AND `asset_type = 'Bien'`.
- En el ambiente actual: **16 modelos válidos** disponibles.

**D. Seriales Pinpad — carga interactiva**:
- Tras parsear el Excel, las filas se renderizan en una grilla editable con `Modelo + Serial` por fila, botón Eliminar individual y botón "Vaciar" para limpiar todo.
- Bullet visual explicativo: *"Tras cargar el Excel se listan aquí — puedes auditar y eliminar registros erróneos antes de enviar."*
- Counter badge muestra cantidad total cargada.

**E. Bug Fix Excel multitienda** (`direct_projects.py` → `excel_parse_branches`):
- Lector ahora es **read_only** (`load_workbook(..., read_only=True)`) → no falla con archivos grandes / corruptos parcialmente.
- **Auto-detección de cabecera**: si la fila 1 tiene un entero válido > 0 en columna B, se procesa como data (no como header).
- Maneja: floats (3.0), strings ("3"), espacios alrededor, filas vacías intercaladas, comas decimales.
- Excel sin cabecera ✅ + con cabecera ✅ ambos casos testeados E2E.
- Tras subir, la UI renderiza **inmediatamente** una grilla con `# / Sucursal / Cantidad Cajas / Eliminar` (no solo lista plana) — homologa el patrón de la grilla principal.

**F. Reel de Distribución de Cajas — reingeniería**:
- Cada fila ahora es: `{quantity, bank_name, product_name, store_name?}` (antes era 1 fila estática por caja).
- Suma de `quantity` debe coincidir con `cantidad_cajas` (validación frontend + backend, 400 si no).
- Counter visible en el header: `{totalEnGrilla}/{cantidadCajas}` (verde si match, rojo si no).
- **Filtro condicional dinámico de Productos**: al elegir el banco en una fila, el dropdown de productos muestra solo los productos del banco que tienen activo el flag de availability según el `quote_type` (`vpos_available` / `mpos_available` / `gateway_available` / `link_available`) — homologa la lógica del cotizador principal.
- Al cambiar el banco de una fila, el producto se auto-limpia (puede no existir en el nuevo banco).
- Al cambiar el `quote_type` (VPOS → GATEWAY), todos los productos de la grilla se limpian (cambia el filtro de availability).

**G. Backend changes** (`direct_projects.py`):
- Modelo `DirectProjectBox`: `quantity` (≥1) en lugar de `caja_nro`.
- Modelo `DirectProjectCreate`: removidos `payment_gateway_link` y `equipment_serials`.
- Validación: suma de `boxes_grid[*].quantity` debe igualar `cantidad_cajas` (400 si no).
- Parsers de Excel (branches + serials) robustos a cabecera ausente, espacios, floats.

**Testing**:
- Backend: 8/8 PASS (`/app/backend/tests/test_iteration191_direct_projects_v2.py`).
- Frontend E2E (Playwright): confirmadas las opciones del Pinpad dropdown (16), Integrator cascade (242 → 2 al elegir Spartan Tech C.A.), reel funcionando con cantidad.



### Iteration 34: Módulo "Proyectos Directos" — Creación de proyectos sin cotización previa — Feb 2026

**Objetivo (P0)**: Operaciones puede crear proyectos de implementación directos saltando las fases de Contacto Inicial y Cotización, todo desde una sola UI sin modales intermedios.

**Backend** (`/app/backend/routes/direct_projects.py` — nuevo módulo):
- `POST /api/direct-projects`: endpoint principal. Recibe payload completo (cliente, definición comercial, HW, multitienda, grilla [Caja+Banco+Producto]), construye una "cotización fantasma" en memoria (NO se persiste en `quotes`), reutiliza `_create_project_from_quote` para armar el proyecto y luego sobreescribe el `project_number` al formato **`PRD-YYYY-MM-NNN-SEDE`** (secuencia separada de `PRY-`). Genera Ficha Técnica PDF via `generate_implementation_pdf` y dispara notificación automática vía el motor dinámico.
- `GET /api/direct-projects/excel-templates/{serials|branches}`: plantillas Excel descargables.
- `POST /api/direct-projects/excel-parse/{serials|branches}`: parsea Excel y devuelve JSON.
- Validaciones: VPOS/MPOS requiere `pinpad_model`; grilla debe tener exactamente `cantidad_cajas` filas; en multitienda la suma de cajas por sucursal debe coincidir con `cantidad_cajas`.
- Marca el proyecto con `origin='direct'`, `direct_project=true`, persiste `boxes_grid` para auditoría.

**Catálogo de permisos** (`permissions_catalog.py`):
- Nuevo módulo granular `proyectos_directos` bajo `gestion_implementacion`. Asignable independiente vía Permisos de Usuarios.

**Motor de notificaciones**:
- `action_notifications.py`: nuevo `BUSINESS_TYPES` entry `proyectos_directos` (sin sub-categoría) con allowed action `send_to_implementation`. La pestaña Matriz de Configuración de Acciones lo expone automáticamente para que el admin mapee destinatarios/plantilla.
- `notification_engine._quote_to_biz_sub`: reconoce `quote_category='direct_project'` y lo mapea a `proyectos_directos`.

**Frontend** (`/app/frontend/src/pages/DirectProjectCreation.jsx` — nueva página):
- Ruta `/direct-projects` (link en Sidebar bajo "Gestión de Implementación"), gateado por permiso `proyectos_directos`.
- Cards: Datos Cliente (autocompleta Grupo Económico + Fantasía editables al seleccionar cliente), Definición Comercial, Hardware (condicional VPOS/MPOS), Multitienda, Grilla Dinámica de Cajas, Instrucciones.
- `ClientCombobox` con búsqueda por substring.
- `ExcelUploader`: botones "Plantilla" (download) + "Cargar Excel" en seriales Pinpad, seriales Equipos y sucursales multitienda.
- Grilla se auto-ajusta al cambiar Cantidad de Cajas.
- Lista de errores en tiempo real; submit deshabilitado mientras haya errores.
- Tras enviar, redirige a `/projects/{id}` con toast confirmando si la notificación fue dispatched o no había config configurada.

**Testing E2E** (`/app/backend/tests/test_iteration190_direct_projects.py` + Playwright):
- Backend 11/11 PASS: creación PRD-YYYY-MM-NNN, validaciones 400, GATEWAY sin pinpad, templates Excel descargables, parseo Excel, catálogo expone proyectos_directos, RBAC 403 para usuario sin permiso.
- Frontend: renderiza todas las secciones, autofill cliente funciona, Hardware desaparece para GATEWAY/LINK_PAGO, grilla se sincroniza con cantidad_cajas, errores visibles, submit deshabilitado con errores, sidebar muestra link bajo Gestión de Implementación.



### Iteration 33: ZIP Paginado por LOTES — Garantía operativa para deploy — Feb 2026

**Decisión arquitectónica**: dado que el dataset productivo creció a 422 anexos (~250 MB) y solo va a crecer, el ZIP Paginado pasó de "ZIP único grande con streaming" a **"N ZIPs pequeños secuenciales"** para garantizar 0% riesgo de OOM independientemente del crecimiento del dataset.

**Implementación** (`ContingencyAttachmentsExport.jsx`):
- `BATCH_SIZE = 75` archivos por ZIP (~40-60 MB por lote — calibrado para fit en cualquier browser).
- Bucle externo: divide `allItems` en lotes; bucle interno: descarga + agrega al ZIP del lote actual.
- Cada lote dispara su propia descarga: `quotes_attachments_{ts}_part_NN_of_MM.zip`.
- Pausa de 500ms entre lotes para que el browser libere memoria completamente (GC + revoke ObjectURL).
- `manifest.json` local en cada ZIP (autocontenido).
- `quotes_attachments_{ts}_manifest_global.json` final con índice consolidado: `total_batches`, `batch_size`, `files_included` (con `batch` field), `files_missing`.
- Mismo flujo `STORE` + `buf = null` + guards defensivos de Iter32.

**UX**: el botón es el MISMO; el admin solo recibe N archivos en lugar de 1 (más una pausa visible "Pausando 500ms antes del siguiente lote..." entre cada).

**Memoria pico CONSTANTE** sin importar el tamaño del dataset:

| Dataset | Lotes | Memoria pico | Riesgo OOM |
|---|---|---|---|
| 422 anexos hoy (~250 MB) | 6 ZIPs | ~60 MB | 0% |
| 1000 anexos (~600 MB) | 14 ZIPs | ~60 MB | 0% |
| 5000 anexos (~3 GB) | 67 ZIPs | ~60 MB | 0% |

**Verificación E2E (Playwright, 3 archivos reales)**:
- 2 descargas exactas (1 ZIP `part_01_of_01.zip` 3.5 MB + 1 manifest global 0.6 KB).
- ZIP contiene 3 PDFs reales íntegros + manifest local.
- Manifests local/global cuadran: `total_batches=1, total_included=3, total_missing=0, batch_size=75`.
- Toast verde *"ZIP descargado en 1 lotes · 3 archivos · revisar manifest_global.json"* visible.
- 0 page errors.



### Iteration 32: Bugfix REAL `ZIP Paginado de Anexos` — OOM en datasets grandes — Feb 2026

**Aclaración**: el "Script error." reportado anteriormente venía del botón **ZIP Paginado**, no JSON Paginado (corrección hecha en Iter31 también fue válida pero el bug crítico estaba aquí).

**Root cause real**:
- El dataset de producción tiene **422 anexos ≈ 226 MB conocidos** (probablemente >250 MB con los `size: None`).
- El handler comprimía todo en memoria con `compression: 'DEFLATE'` y luego `generateAsync({type:'blob'})` exigía ~500-600 MB de RAM combinada (todas las arrayBuffers vivas + blob comprimido en memoria + buffers internos de pako).
- V8 disparaba OOM/string overflow → `window.onerror` reportaba "Script error." sin stack (CORS).

**Fix completo** (`/app/frontend/src/components/ContingencyAttachmentsExport.jsx`):
1. **`compression: 'STORE'`** (sin deflate) → ~30% menos RAM y ~5x más rápido. Los PDFs ya están comprimidos internamente, deflate no aporta nada en este caso.
2. **`generateInternalStream` + File System Access API (`showSaveFilePicker`)** → escribe ZIP directo a disco en chunks de ~64KB. Nunca arma el archivo completo en RAM. Soportado en Chrome/Edge 86+ (mayoría del uso admin).
3. **Fallback `generateAsync(blob)` con STORE** para browsers viejos.
4. **`buf = null` + `setTimeout(0)` cada 25 archivos** → ayuda al GC + evita "Page Unresponsive".
5. **Filtro defensivo** `items.filter(it => typeof it.path === 'string' && it.path.length > 0)` — sin crash si la API devuelve items malformados.
6. **Guard** `r?.data?.arrayBuffer` — sin crash si endpoint devuelve JSON de error en lugar de blob.
7. **try/catch por archivo** con `missing.push(...)`, AbortError handling, `console.error('[ZIP Paginado]')` para diagnóstico.
8. Toast informativo *"Descarga cancelada"* si el usuario cierra el File System picker.

**Memoria pico estimada**: de **~600MB (riesgo OOM)** → **~30MB** (1 archivo activo + chunks de 64KB escribiendo a disco).

**Verificación E2E (Playwright + intercept de attachments-list a 3 items)**:
- ZIP descargado correctamente · 3 PDFs + manifest.json · 3.5MB
- PDFs binarios íntegros dentro del ZIP (`first 8 bytes` = headers PDF válidos)
- `manifest.mode = paginated-browser`, `total_included=3`, `total_missing=0`
- **0 page errors** · Toast verde visible



### Iteration 31: Bugfix `JSON Paginado` — "Uncaught Script error." — Feb 2026

**Issue reportado** (con screenshot): al ejecutar **Descargar JSON Paginado (Recomendado)** en `/settings`, el overlay rojo de CRA mostraba `Uncaught runtime errors: Script error.` y el archivo no se descargaba.

**Root cause**:
- `handleDownloadPaged` armaba un objeto JS gigante con TODAS las colecciones (`quotes`+`quote_history`+`projects`) y luego ejecutaba `JSON.stringify(result, null, 2)`. La serialización monolítica con indentado consume ~3-4x el tamaño final del archivo.
- Cuando el dataset crecía (151 quotes con history extenso), V8 lanzaba `RangeError: Invalid string length` u OOM. El error era **asíncrono** y escapaba al `try/catch` propio, propagándose a `window.onerror` como **"Script error."** genérico (sin stack por CORS).

**Fix** (`/app/frontend/src/components/ContingencyAttachmentsExport.jsx`):
1. **Serialización por documento**: cada `doc` se `JSON.stringify` individualmente y se push a un array de Blob parts; nunca existe un string JS completo del bundle.
2. **Sin indentado** (`JSON.stringify(d)` plano) → ~40% menos memoria.
3. **`new Blob(parts, …)`** recibe el array directamente y une los chunks a nivel de bytes nativos — sin string intermedio masivo.
4. **try/catch por documento**: si uno tiene referencia circular, se sustituye por `null` con `console.warn`, sin abortar el bundle completo.
5. Mejor logging: `console.error('[JSON Paginado] error:', e)` para diagnóstico futuro.

**Verificación E2E (Playwright)**:
- Descarga exitosa: `quotes_bundle_data_paged_2026-05-27T01-24-51.json` (2.1 MB).
- Contenido: 151 quotes + 67 quote_history + 42 projects, schema_version=1, JSON válido `json.load` sin error.
- **0 errores en `page.on('pageerror')`** — el overlay rojo ya no aparece.
- Toast verde: *"JSON paginado descargado · 151 quotes, 67 quote_history, 42 projects"* visible.



### Iteration 30: Limpieza Visual del Menú de Configuración — Feb 2026

**Objetivo**: Depurar la pantalla `/settings` removiendo funciones obsoletas y encapsulando bloques masivos en acordeones colapsables para descargar visualmente la página.

**Depuración**:
- 🗑️ Removido el bloque "Base de Datos / Inicialice la base de datos con información predeterminada" (`Settings.jsx`).
- 🗑️ Removidos los botones de migración por Streaming (`JSON Streaming (1 request)` y `ZIP de Anexos (Streaming)`) y sus handlers (`_streamedDownload`, `handleDownloadData`, `handleDownloadAttachments`) de `ContingencyAttachmentsExport.jsx`. Solo permanecen los métodos paginados (estables en producción).
- Título actualizado a "Contingencia · Migración Cotizaciones" (sin sufijo "Streaming").

**Acordeones colapsables** (estado inicial CERRADO):
- **Settings.jsx**: cada Sede (PYME / CORP) en *Configuración de Correos de Notificación* es ahora un botón desplegable independiente. Test IDs: `sede-toggle-PYME`, `sede-content-PYME`, idem CORP.
- **EmailTemplatesEditor.jsx**: las 5 categorías de plantillas (Personalizadas, Sede Pyme, Sede Corp, Proyecto, Generales/Sin sede) son acordeones independientes con contador en píldora y chevron rotativo. Test IDs: `tpl-section-toggle-custom`, `tpl-section-toggle-sede-PYME`, `tpl-section-toggle-sede-CORP`, `tpl-section-toggle-project`, `tpl-section-toggle-legacy`.

**Estética**: chevron `lucide-react`, gradientes existentes preservados (violet/fuchsia para Personalizadas, orange/teal para Proyecto, amber para Sin Sede), hover backgrounds aplicados.

**Verificación E2E (Playwright)**:
- DB block removido (`'Inicialice la base de datos' not in body.innerText`).
- 2 botones streaming `count = 0`, 2 botones paginados visibles.
- `sede-content-PYME` inicia oculto → click → visible.
- Los 5 toggles de plantillas presentes (count=1 cada uno), todos cerrados al cargar, abrir/cerrar independiente.



### Iteration 29: Variable `{Ticket_Nro}` para Notificaciones de Proyectos — Feb 2026

**Bug latente corregido + Mejora**: La cápsula `Ticket_Nro` (y otras PascalCase Spanish: `Nro_Proyecto`, `Tipo_Proyecto`, `Fecha_Asignacion`, `Rif_Cliente`) aparecía en el panel de variables del editor pero **no se sustituía** al enviar el correo porque el backend solo exponía las versiones snake_case (`ticket_number`, `project_number`, etc.). Quedaban como literal en el body — bug silencioso desde forks previos.

**Implementación**:
- `services/project_template_vars.py`: agregados aliases PascalCase Spanish en el dict consolidado:
  - `Ticket_Nro` ← `project.ticket_number` (se carga al desbloquear el proyecto vía `PUT /api/projects/{id}/ticket`).
  - `Nro_Ticket` (segundo alias por compatibilidad).
  - `Nro_Proyecto`, `Tipo_Proyecto`, `Rif_Cliente`, `Fecha_Asignacion`, `Fecha_Desbloqueo_Ticket` (formateadas como `dd/mm/yyyy`).
- `EmailTemplatesEditor.jsx` (Configuración > Notificaciones): añadido `Ticket_Nro` a `VARIABLE_CATEGORIES.Implementación` y a las tres `BASE_TEMPLATE_VARIABLES` de proyectos (`project_notify_client`, `project_notify_bank`, `project_notify_bank_client`) — con etiqueta explícita "se carga al desbloquear el proyecto".
- `TemplatesAdminDialog.jsx` (per-project): descripción actualizada para `Ticket_Nro`.
- `RichTextEditor.jsx`: demo values para `Ticket_Nro=56785`, `Nro_Proyecto`, `Tipo_Proyecto`, `Fecha_Asignacion`, `Fecha_Desbloqueo_Ticket` — el mini-preview hover ahora muestra el valor demo correcto.

**Test (`/app/backend/tests/test_iteration29_ticket_nro_variable.py`)**: 2/2 PASS — `{Ticket_Nro}` resuelve a `"55512"` cuando el proyecto está desbloqueado, y a `""` cuando aún no se ha asignado ticket (proyecto bloqueado). Aliases en español y snake_case ambos funcionan.



### Iteration 28: Ranking COMPLETO de Implementadores en Reporte de Carga PDF — Feb 2026

**Cambio**: El ranking visual ahora lista a **todos los implementadores** (no solo el top 3), ordenados por cajas asignadas. Las medallas oro/plata/bronce siguen aplicándose a las primeras 3 posiciones; las restantes (4°+) usan un disco gris pizarra (`#475569`) con texto blanco. Layout grid de 3 columnas que envuelve automáticamente.

**Implementación**: `/app/backend/routes/projects.py`
- Eliminada la cota `top3 = ranking_items[:3]`; ahora se itera sobre la lista completa.
- `medals = {0:#FFD700, 1:#C0C0C0, 2:#CD7F32}`, fallback `#475569` para resto.
- CSS `.ranking-grid` cambiado a `display:grid; grid-template-columns: repeat(3, 1fr); gap:8px;`.
- Título actualizado: *"Ranking de Carga — Implementadores por Cajas Asignadas"*.

**Verificación (curl + pdfplumber)**: PDF 46KB. Los 10 implementadores listados con sus métricas correctas, ordenados por cajas desc (Omar Jiménez 40 → Rafael González Respaldo 7). Excluye "Sin asignar" del ranking.



### Iteration 27: Mini Ranking visual Top 3 por Cajas en Reporte de Carga PDF — Feb 2026

**Cambio**: Al final del PDF "Reporte de Carga y Estatus" se agrega una tarjeta visual con los **3 implementadores con mayor carga real (cajas)**, no por proyectos. Resuelve un sesgo del dato: un implementador con pocos proyectos pero muchas cajas (configuraciones reales) puede estar más cargado que uno con muchos proyectos pequeños.

**Implementación**: `/app/backend/routes/projects.py`
- `ranking_items` = lista (impl, cajas, n_proyectos), excluye `"Sin asignar"`. Ordenado por `(-cajas, -proyectos, nombre)`.
- Top 3 → tarjetas oscuras (fondo `#0f172a`) con:
  - Medallas circulares: oro `#FFD700` (1ro), plata `#C0C0C0` (2do), bronce `#CD7F32` (3ro).
  - Barra de progreso azul-índigo proporcional al líder (líder = 100%).
  - Métricas: `N caja(s) · M proyecto(s)` con N resaltado en ámbar.
- Layout flex 3 columnas, `break-inside: avoid` para no partir entre páginas.

**Verificación (curl + pdfplumber)**: PDF 40KB. Ranking real extraído:
- 🥇 1ro: Omar Jiménez — 40 caja(s) · 6 proyecto(s)
- 🥈 2do: Yulimarys Rivas — 38 caja(s) · 7 proyecto(s) *(más proyectos pero menos cajas — el ordenamiento por cajas corrigió el sesgo)*
- 🥉 3ro: Bryan Claro — 16 caja(s) · 5 proyecto(s)



### Iteration 26: Total de Cajas por Implementador en Reporte de Carga PDF — Feb 2026

**Cambio**: La cabecera de cada grupo del PDF "Reporte de Carga y Estatus" ahora muestra en la misma línea `Nro de Proyectos X · Nro de Cajas Y`, y el subtítulo global suma todas las cajas (`Total: N proyecto(s) · M caja(s)`).

**Implementación**: `/app/backend/routes/projects.py` workload-pdf endpoint
- Nuevo dict `cajas_by_impl` sumando `cantidad_cajas` / `box_count` solo de proyectos VPOS/MPOS (mismo criterio que la columna "Cajas").
- `group-head` ahora renderiza `<span class="count">Nro de Proyectos {count} · Nro de Cajas {boxes}</span>`.
- Subtítulo global ahora suma `total_cajas = sum(cajas_by_impl.values())`.

**Verificación (curl + pdfplumber)**: Generado `GET /api/projects/reports/workload-pdf` → PDF de 36KB con todos los implementadores mostrando ambos contadores. Ejemplos extraídos del PDF real:
- Yulimarys Rivas — Nro de Proyectos 7 · Nro de Cajas 38
- Omar Jiménez — Nro de Proyectos 6 · Nro de Cajas 40
- Total global: 42 proyecto(s) · 197 caja(s) ✅



### Iteration 25: Mini-Preview de Variables (Tooltip Hover) — Feb 2026

**Objetivo**: Mostrar al pasar el mouse sobre cada variable del panel lateral un tooltip con (a) descripción funcional, (b) token literal y (c) **valor demo** que aparecerá en el correo — sin necesidad de abrir Vista Previa.

**Implementación**:
- `RichTextEditor.jsx`: nuevo helper exportado `getExampleValue(token, extra)` que consulta el mapa interno `DEFAULT_EXAMPLE_VALUES`.
- `TemplatesAdminDialog.jsx`:
  - Cada cápsula del diccionario ahora se envuelve en `<Tooltip>` (shadcn) con `delayDuration={150}`.
  - El `TooltipContent` (`side="left"`, fondo `slate-900`) muestra: header con descripción + token (azul `#blue-300`); body con etiqueta "✨ VISTA PREVIA" (ámbar) y el demo value resaltado.
  - Si no hay valor demo, se indica "Se mostrará el valor real al enviar el correo."
- Test IDs nuevos: `var-tooltip-{token}`, `var-demo-{token}`.

**Verificación E2E (Playwright)**:
- Hover en `{Nombre_Cliente}` → `var-tooltip-Nombre_Cliente` visible, `var-demo-Nombre_Cliente` contiene `"CLIENTE DEMO S.A."` ✅.
- Hover en `{Datos_Contacto}` → cápsula resalta y tooltip muestra `"María Pérez · +58 212 555-0100 · contacto@clientedemo.com"`.



### Iteration 24: Inserción de Variables en Posición del Cursor — Feb 2026

**Objetivo (P2 cerrado)**: Las variables del panel lateral en `TemplatesAdminDialog` ahora se insertan **exactamente donde está el cursor** dentro del editor TipTap, en lugar de hacer un append simple al final del HTML.

**Implementación**:
- `RichTextEditor.jsx`: convertido a `forwardRef` + `useImperativeHandle`, exponiendo:
  - `insertText(text)` → `editor.chain().focus().insertContent(text).run()` (inserción nativa de TipTap en la selección actual).
  - `focus()` → enfoca el editor.
  - `getHTML()` → devuelve HTML actual.
- `TemplatesAdminDialog.jsx`: `editorRef = useRef(null)` pasado al `<RichTextEditor ref={editorRef}>`. `insertVar(token)` ahora llama `editorRef.current.insertText('{token}')`. Fallback al append previo si el editor aún no está montado.

**Verificación E2E (Playwright)**:
- Login → `/projects/{id}` → modal "Plantillas" → escribir `"Estimado "` → click variable `Nombre_Cliente` → continuar tipeo `", su proyecto es importante."`.
- HTML final: `<p>Estimado {Nombre_Cliente}, su proyecto es importante.</p>` ✅ (variable inyectada exactamente en la posición del caret, no al final).
- Contador del editor sincronizado: `53/20000`.



### Iteration 23: Control de Exención de IVA en Cotizaciones — Feb 2026

**Objetivo**: Identificar tempranamente clientes con régimen fiscal exento de IVA y automatizar la supresión del impuesto en cálculos, PDFs y facturación posterior.

**UI/UX (Frontend)**:
- Selector binario **"¿Cliente exento de IVA?"** (Sí/No, **default NO**) en `QuoteWizardDialog.jsx`, posicionado al lado del bloque "Implementación Patrocinada" (separador vertical `border-l`). Color verde esmeralda al activarse, gris en estado normal.
- Al elegir "Sí" se muestra nota inmediata `IVA forzado a $0.00` (testid `iva-exempt-active-note`).
- Insignia **"Exento IVA"** en `QuotesTable.jsx` para identificar de un vistazo las cotizaciones bajo este régimen.

**Lógica de cálculo (Backend + Frontend)**:
- `iva_rate = 0` cuando `iva_exempt=True`, en lugar del 16% estándar. Aplica a:
  - PDF cotizaciones VPOS/MPOS/Equipos/Reparaciones (`services/pdf_generator.py` páginas Setup, Recurrente, Equipment PYME, Equipment CORP).
  - PDF Fast Track / Equipos / Reparaciones (`routes/quotes.py` `generate-equipment-pdf` + `regenerate-equipment-pdf`).
  - Modal `ApprovalBillingModal.jsx` (facturación) — fila `billing-iva-row` con label dinámico "IVA (Exento)".
  - Modal `RepairCompleteModal.jsx`.
- Etiquetas de IVA cambian a "IVA (Exento)" cuando aplica.

**Persistencia + Herencia**:
- Modelo Pydantic: `iva_exempt: Optional[bool] = False` en `QuoteCreate`, `Quote`, `Project` (`models.py`), `QuoteCreateWithPDF` y `QuoteUpdate` (`routes/quotes.py`), y `TemplateQuotePDFRequest` + `EquipmentQuotePDFRequest`.
- `routes/quote_transitions.py`: el campo se copia del quote al proyecto al "enviar a implementación" para que la facturación lo respete.
- Duplicate quote (`quote_actions.py`) preserva `iva_exempt` automáticamente vía `{**original_quote, ...}`.

**Verificación**:
- ✅ Backend curl: `PUT /api/quotes/{id} {"iva_exempt": true}` persiste correctamente, `GET /api/quotes` retorna el campo en cada documento.
- ✅ UI Playwright: wizard renderiza nuevo bloque, default=No, clic en "Sí" muestra nota, persistencia verificada en estado React.
- 🟡 Static review por agente: implementación consistente en todas las pantallas y modelos.

**Pendiente / próximo retest**: ejecutar suite Playwright completa (crear cotización exenta, ver insignia en grid, abrir ApprovalBillingModal, verificar fila "IVA (Exento)" con monto $0.00) + grep en bytes de PDF para validar etiquetas. El agente de testing se quedó sin contexto antes de poder hacerlo en Iter12.



### Iteration 22: Editor WYSIWYG en Plantillas (Clientes / Proyectos / Integradores) — Feb 2026

**Objetivo**: Evolucionar el motor de plantillas de texto plano a un editor de texto enriquecido (TipTap), garantizar almacenamiento holgado (>1000 chars) y proveer Vista Previa con sustitución de tokens.

**Componentes**:
- `/app/frontend/src/components/RichTextEditor.jsx` — Editor TipTap reutilizable (Bold, Italic, Underline, Strike, Color, Highlight, Align L/C/R/Justify, listas, link, Undo/Redo) con:
  - Contador de caracteres (visible texto plano vs `maxChars`).
  - Prop `hardLimit` (default true) — para plantillas largas usar `hardLimit={false}` con `maxChars=20000`.
  - Botón "Vista Previa" (`showPreview` prop) que abre modal con HTML renderizado y tokens sustituidos por valores demo (mapa interno + extensible por prop `exampleValues`).
  - `substituteTokens(html, extra)` exportado: reemplaza `{{var}}` y `{var}` con valores reales o `[var]` fallback.
- Pantallas migradas:
  - `pages/ClientTemplatesConfig.jsx` (Clientes — `/clients/communications`).
  - `pages/EntityTemplatesConfig.jsx` (Integradores y Nuevos Productos — `/integrators/communications`, `/new-products/communications`).
  - `components/projects/TemplatesAdminDialog.jsx` (Proyectos — modal "Plantillas" en `/projects/:id`).
- Backend: `EmailTemplate.body_html: str` (sin maxlen), MongoDB almacena strings hasta 16MB — sin cambios necesarios.

**Test IDs disponibles por instancia del editor** (prefix dinámico):
- `cli-tpl-editor-*` (Clientes), `entity-tpl-editor-INTEGRADORES-*`, `entity-tpl-editor-NUEVOS_PRODUCTOS-*`, `project-tpl-editor-*`.
- Sub-testids: `-bold|-italic|-underline|-strike|-bullet|-ordered|-align-left|-align-center|-align-right|-align-justify|-color|-highlight-toggle|-link|-preview-btn|-counter|-content|-preview-dialog|-preview-body`.

**Test reports**: `/app/test_reports/iteration_10.json`, `/app/test_reports/iteration_11.json`, `/app/backend/tests/test_iteration22_rich_text_templates.py`.

**Fixes complementarios**:
- `TemplatesAdminDialog.insertVar` y `EmailTemplatesEditor` (sidebar de variables): el `navigator.clipboard.writeText()` ahora maneja la rejection (`.then(ok, err)`) para no levantar el overlay rojo "Uncaught runtime error" en contextos sin permiso de clipboard.

**Dependencias añadidas (yarn)**: `@tiptap/extension-link@3.23`, `@tiptap/extension-highlight@3.23`, `@tiptap/extension-character-count@3.23` (no usado en final). Resto del stack tiptap alineado a 3.23.x.

**Pendientes / oportunidades**:
- Migrar también el Master `EmailTemplatesEditor.jsx` (plantillas legacy de Cotizaciones por sede) al WYSIWYG — requiere validación para que TipTap respete las tablas HTML inline-styled extensas de los correos transaccionales.
- Insertar variables en posición del cursor dentro de TipTap (hoy se hace append simple en TemplatesAdminDialog).



### Iteration 13: Estabilización "Validar Pago" + Pinpads + Precarga Impresora Fiscal (Feb 2026)

**3 fixes críticos**:

**A. "Validar Pago" — Bug WriteError MongoDB + acción bloqueada por email faltante**
(`quote_action_customization.py`)
- **Causa raíz (descubierta vía logs)**: cotizaciones legacy con `custom_actions_executed: null` rompían el `$set` anidado de MongoDB con `WriteError: Cannot create field 'pago_validado' in element {custom_actions_executed: null}`. Toda invocación a `dispatch_custom_action` retornaba 500 → frontend mostraba "Error ejecutando Validar Pago".
- **Causa raíz #2**: si `try_dispatch` retornaba False (sin destinatarios configurados o error SMTP), el endpoint lanzaba HTTPException 400 → frontend lo trataba como error → el flujo NO avanzaba aunque la acción ya estuviera lista para ejecutarse.
- **Fix**:
  1. Normalización defensiva: antes del `$set` anidado, si `custom_actions_executed` es null o no existe, lo inicializa como `{}`.
  2. `try_dispatch` envuelto en try/except: si falla, se loggea pero NO se retorna 4xx. El flujo avanza siempre.
  3. Respuesta incluye `email_sent: bool` para que el frontend sepa si se envió correo.
  4. Fallback de búsqueda extendido a 3 niveles: `config_key` exacto → `biz+action_id+sub=None` → `action_id+enabled=True` (cualquier biz). Útil cuando la acción está configurada bajo `implementacion_pyme` pero la cot es `implementacion_corp`.

**B. Modal "¿Requiere Pinpads?" RESTAURADO para TODOS los flujos** (`Quotes.jsx`)
- **Causa raíz**: la iteración 12 conectó `handleProjectTypeSelect` directamente a `goToFiscalPrinterPhase()` para flujos no-PYME, omitiendo `pinpad_question`. El modal de pinpads sólo se mostraba en PYME.
- **Fix**: `handleProjectTypeSelect` ahora SIEMPRE transiciona a `pinpad_question` (PYME, payment_gateway, pos_fast_track, vpos_mpos). El modal es indispensable para indexar seriales de hardware en cualquier proyecto.
- Después de pinpad → `goToFiscalPrinterPhase` (ya existente) → `handleFiscalPrinterContinue` decide flujo: PYME → `consolidated_data`, no-PYME → `advanceToMultistorePhase` (ask/inherited/collect).

**C. Modal Impresora Fiscal — Precarga garantizada** (`Quotes.jsx`)
- **Causa raíz**: el state `fiscalPrinterFromClient` arrastraba valores de wizard previos, y si el GET `/clients/{id}` retornaba antes del render del modal pero con valor vacío para un cliente sin dato, no diferenciaba entre "cliente sin dato" y "fetch pendiente".
- **Fix**: reset explícito de `fiscalPrinterFromClient` y `fiscalPrinterModel` a `''` ANTES del `try`, luego sólo se setean si el GET retorna un valor no vacío. Garantiza que el modal lea fresh el campo del cliente cada vez que se abre.

**Validación** (`/app/backend/tests/test_iteration13_validar_pago_pinpads_fiscal.py` — **4/4 PASS**):
- ✅ Cotización con `custom_actions_executed: null` → ejecuta sin error, persiste objeto.
- ✅ Acción sin destinatarios → ok=True, marca ejecución, NO lanza 400.
- ✅ `handleProjectTypeSelect` transiciona a `pinpad_question` ≥2 veces (PYME + no-PYME).
- ✅ `goToFiscalPrinterPhase` resetea states antes del try del fetch.
- ✅ E2E curl: `POST /quotes/{id}/custom-action/pago_validado` → `{ok:true, email_sent:true, label:"Validar Pago"}` y `custom_actions_executed.pago_validado` persistido en BD.



### Iteration 12: Reportes Admin + Filtro Predictivo + Reingeniería Modales Impl + Impresora Fiscal (Feb 2026)

**Objetivo**: 5 mejoras transversales — gestión admin embebida en Salidas Facturadas, buscador predictivo de clientes, contraste/Razón Social en Nota de Entrega, eliminación del modal de equipos y nuevo modal de Impresora Fiscal con propagación a la Ficha Técnica.

**A. Reporte Salidas Facturadas — Gestión Admin embebida** (`InvoicedExitsReport.jsx` + `inventory.py`):
- Botón "Admin: Gestión de Salidas" visible solo para `role === 'admin'` (vía `usePermission`).
- Nueva columna "Acciones" con botón "Gestionar" por fila (solo admin).
- Modal `admin-edit-exit-modal`: editar cualquier campo (item, tipo, cantidad, factura, cliente, seriales, costo, referencia, notas) o eliminar el registro completo. Reusa endpoints existentes `PUT/DELETE /inventory/movements/{id}` con audit log.
- Endpoint `get_invoiced_exits_report` ahora retorna `movement_id` y `serials` por fila para alimentar el modal.

**B. Buscador Predictivo de Clientes** (`QuoteFilters.jsx`):
- Nuevo componente `ClientSearchableSelect` (Popover + Input + lista filtrada) reemplaza el Select nativo.
- Búsqueda en tiempo real por substring (case-insensitive), de-duplicación por `legal_name`.
- `data-testid`: `filter-client`, `filter-client-search`, `filter-client-option-{id}`, `filter-client-option-all`.

**C. Nota de Entrega** (`hoja_ruta_pdf.py` + `quote_actions.py`):
- Estilo `s_cell_white` (texto blanco, fontSize 8, bold) para los encabezados de la sección 3 (Detalle de Bienes) → contraste 100% legible sobre el fondo azul.
- Mapeo "Razón Social": `deliver_quote` ahora prioriza `client.legal_name` sobre `fantasy_name` cuando arma `client_name` → la nota imprime el nombre jurídico real.

**D. Reingeniería Modales "Enviar a Implementación"** (`Quotes.jsx` + `QuoteModals.jsx` + `quote_actions.py` + `quote_transitions.py` + `implementation_pdf.py` + `clients.py`):
- **Eliminado** el modal "Equipos Entregados al Cliente" (fase `equipment` removida del JSX). Los equipos vinculados a la cotización se auto-seleccionan en background al elegir tipo de proyecto.
- **Mantenido** el modal "¿La implementación requiere Pinpads?" sin cambios.
- **Nuevo modal `fiscal_printer`**: aparece después de pinpad (flujo PYME) o después de project_type (flujo no-PYME). Lee `client.modelo_impresora_fiscal`:
  - Si tiene valor → muestra informativamente y avanza al confirmar.
  - Si vacío → exige al usuario ingresar el modelo (input obligatorio).
- Si el cliente no tenía el dato, se persiste vía `PATCH /clients/{id}` (nuevo endpoint con whitelist de campos seguros incluyendo `modelo_impresora_fiscal`).
- El valor capturado viaja en `SendToImplementationRequest.fiscal_printer_model` → se persiste en `quote.fiscal_printer_model` y `project.fiscal_printer_model`.
- **Ficha Técnica PDF** (`implementation_pdf.py`): nueva sección "Modelo de Impresora Fiscal" colocada **justo después** del banner "C. SERIALES DE LOS EQUIPOS" y **antes** del Resumen Comercial. Lee `quote.fiscal_printer_model` con fallback a `client.modelo_impresora_fiscal`.

**E. Testing** (`/app/backend/tests/test_iteration12_reports_filters_fiscal.py` — **10/10 PASS**):
- Reporte incluye `movement_id` y `serials`.
- PDF Nota de Entrega usa `s_cell_white` para contraste.
- `deliver_quote` mapea legal_name como Razón Social.
- Ficha Técnica imprime "Modelo de Impresora Fiscal" en posición correcta (entre Seriales y Resumen).
- `_create_project_from_quote` acepta y persiste `fiscal_printer_model`.
- Wizard tiene fase `fiscal_printer` y NO tiene `equipment-phase`.
- Filtro tiene `ClientSearchableSelect` con `filter-client-search`.
- Reporte tiene `admin-edit-exit-modal` con `isAdmin` gating y botón "report-admin-tools-btn".
- Modelo Client tiene `modelo_impresora_fiscal` Optional.
- Endpoint `PATCH /clients/{id}` validado via curl E2E: setea y refleja el campo correctamente.



### Iteration 10: Gestión Admin de Seriales VENDIDOS (Feb 2026)

**Objetivo**: Habilitar al Administrador a gestionar seriales que ya salieron físicamente del stock (estado "vendido" en la tab "Por Modelo" del modal de gestión). Antes estos seriales quedaban congelados — sin posibilidad de devolución, desasignación residual ni eliminación. Ahora se puede:

**A. Backend (`inventory.py`)** — 3 nuevos endpoints admin-only:
- `POST /admin/inventory/serials/sold/{serial}/return-to-stock`:
  - Body: `{warehouse_id?, reason}`. Si no se pasa `warehouse_id`, se infiere del último movimiento de salida.
  - Crea un `inventory_movements` tipo `entrada` con `is_admin_return=True` y referencia al movimiento original. **NO modifica la salida histórica** (trazabilidad preservada).
  - Libera blacklist si el serial estaba bloqueado.
  - 409 si el serial sigue con asignación activa (preasignado/asignado/asignado_temporal).
- `POST /admin/inventory/serials/sold/{serial}/unassign`:
  - Body: `{reason, mark_non_assignable: bool}`. Limpia cualquier asignación residual en `serial_assignments` (cualquier estado) y opcionalmente envía a blacklist. No toca los movimientos de inventario.
- `DELETE /admin/inventory/serials/sold/{serial}` con header `x-reason`:
  - Acción **destructiva**: barre el serial de TODOS los movimientos (entradas, salidas, transferencias). Si el movimiento contiene solo ese serial → borra el movimiento; si tiene varios → solo lo remueve y decrementa qty.
  - Limpia asignaciones residuales y blacklist asociada.
- Helper compartido `_find_sold_serial_movement(serial)` ubica el último `salida`/`transferencia_salida` que contenga el serial.
- Todas las acciones generan entrada en `bitacora` con `executed_by`, `executed_at` y contadores.

**B. Frontend (`AdminSerialManagementModal.jsx`)**:
- 3 nuevos sub-componentes: `SubReturnSold`, `SubUnassignSold`, `SubDeleteSold`.
- `SubReturnSold`: selector de almacén destino + motivo. Carga `/inventory/warehouses` al abrir el modal.
- `SubUnassignSold`: motivo + checkbox opcional "marcar como no asignable" (blacklist).
- `SubDeleteSold`: motivo + confirmación tipeada "ELIMINAR" (acción irreversible, paleta roja).
- En la tabla "Por Modelo" cuando `r.status === 'vendido'` ahora se renderizan **3 botones**: "Devolver al Stock" (verde), "Desasignar" (rosa), "Eliminar" (rojo). Antes la fila no tenía acciones.
- `data-testid`: `btn-bm-return-sold-{serial}`, `btn-bm-unassign-sold-{serial}`, `btn-bm-delete-sold-{serial}`.

**Validación E2E** (script con serial sintético `TEST-RGZ-VENDIDO-E2E`):
- ✅ `return-to-stock` → HTTP 200, crea movimiento `entrada` con `is_admin_return=True`, conserva la salida original.
- ✅ `delete-sold` → HTTP 200, `movements_deleted=2`, asignaciones residuales = 0.
- ✅ Validaciones: 400 sin reason, 404 si serial no existe, 409 si serial activo en asignación, 403 para no-admin (gating por `_require_admin_user`).



### Iteration 9: Estabilización Flujo MPOS + Filtros Validar Pago/Preasign + Mapeo de Variables (Feb 2026)

**Objetivo**: Resolver el feedback del usuario sobre MPOS Imple+POS — habilitar acciones desde el inicio, eliminar alerta falsa de ruptura, precargar seriales preasignados, normalizar variables dinámicas y agregar dos estados nuevos al filtro de cotizaciones.

**A. UI MPOS — Acciones siempre habilitadas (`QuotesTable.jsx`)**:
- "Configuración" y "Enviar a Implementación" ya no se renderizan deshabilitadas en MPOS por falta de preasignación/configuración. El usuario decide el orden; un badge informativo "Sin preasignación" sigue presente como ayuda visual pero NO bloquea el flujo.
- La única condición de bloqueo de "Enviar a Implementación" es `sent_to_implementation_at` (ya creado el proyecto).

**B. Backend — Eliminar falsa alerta "Ruptura del proceso regular" (`quote_actions.py`)**:
- `send_quote_to_implementation` ahora detecta `quote_category == 'fast_track'` (o `quote_type == 'FAST_TRACK'`) y considera VÁLIDOS los estados `Aprobada`, `Configurada`, `Facturada`, `Pagada`. La secuencia Configuración → Enviar a Implementación es flujo institucional, no excepción.
- Para todos los demás tipos (VPOS/PG/LINK) se preserva la regla legacy `is_irregular = current_status != "Pagada"`.

**C. Modal de Búsqueda de Seriales — Precarga de Preasignados**:
- Backend `quote_serials.py` (`GET /quotes/{id}/inventory-serials`): ahora consulta `serial_assignments` con `status=preasignado` para el `client_id`/RIF normalizado del cliente ANTES de la búsqueda histórica en `inventory_movements`. Resultado: los preasignados aparecen al tope con flag `from_preassign=True`.
- Frontend `Quotes.jsx`: al entrar a la fase `pinpad_selection`, consulta `/quotes/{id}/preassigned-serials`; si hay preasignación previa, auto-selecciona el modelo (`item_id`) y carga los seriales automáticamente.
- Frontend `QuoteModals.jsx`: cada serial preasignado se renderiza con badge índigo "PREASIGNADO" y fila resaltada en `bg-indigo-50/40`.

**D. Mapeo de Variables Dinámicas (`notification_engine.py`)**:
- `{client_name}` / `{Nombre_Cliente}` / `{nombre_cliente}` ahora resuelven SIEMPRE con `legal_name` (Razón Social) como prioridad y `fantasy_name` como fallback (antes era al revés, lo que producía nombres comerciales en correos institucionales).
- `{Datos_Contacto}` / `{Contacto_Principal}` ya estaba correctamente poblado desde `contacts[0].full_name` (sin cambios).
- PDF Ficha Técnica (`implementation_pdf.py`): el banner de la sección C ahora dice "SERIALES DE LOS EQUIPOS" (antes "MODELO Y SERIALES DE EQUIPOS"), alineado al requerimiento del usuario.

**E. Filtro de Estados — Validar Pago + Preasign (`QuoteFilters.jsx` + `QuotesTable.jsx`)**:
- 2 nuevas opciones en el dropdown "Estado": `Preasign (Seriales Reservados)` y `Validar Pago`.
- `getEffectiveStatus()` en `QuotesTable.jsx`: retorna `'Preasign'` cuando hay `preassigned_at` o `preassigned_serials[]` pero todavía no `configured_at`. Devuelve `'Validar Pago'` cuando `custom_actions_executed.pago_validado*` está marcado pero aún no hay `paid_at` (ya estaba).

**Testing**:
- `/app/backend/tests/test_iteration9_mpos_filters.py`: **6/6 PASSED**:
  - `client_name` con legal_name primero (con cliente real con ambos campos).
  - `inventory-serials` retorna preasignados con `from_preassign=True` al tope.
  - Banner PDF "SERIALES DE LOS EQUIPOS" presente, viejo banner removido.
  - Código fast_track regular flow contiene set de estados naturales.
  - Filtro UI incluye Validar Pago y Preasign.
  - getEffectiveStatus retorna 'Preasign'.


### Iteration 8: Inventario Admin + Filtros + Flujo MPOS + Filtro Creador (Feb 2026)

**A. Herramienta Admin de Seriales (POS/PINPAD)** — Solo rol `admin`:
- Backend (`/app/backend/routes/inventory.py:1599+`): 6 endpoints nuevos:
  - `GET /admin/inventory/serials/search?q=` — busca por serial parcial.
  - `POST /admin/inventory/serials/{id}/replace` — reemplaza serial por falla; bloquea el viejo en blacklist si no se devuelve al stock; rechaza si el nuevo está en blacklist.
  - `POST /admin/inventory/serials/{id}/reassign-client` — cambia cliente/cotización destino.
  - `POST /admin/inventory/serials/{id}/unassign` — desasigna + opcional `mark_non_assignable`.
  - `GET /admin/inventory/serials/blacklist` y `POST .../blacklist/{serial}/release`.
- Validación: `quote_serials.preassign_serials` ahora rechaza con HTTP 409 si algún serial está en blacklist.
- Frontend: `AdminSerialManagementModal.jsx` (nuevo) con pestañas Búsqueda y Blacklist; botón en Inventario visible solo si `currentUser.role==='admin'`.
- Auditoría: Todos los cambios quedan en colección `bitacora` con `executed_by`, `executed_at`, `old_*`, `new_*`.

**B. Optimización Filtros Cotizaciones**:
- B.1 — De-duplicación cliente: `QuoteFilters.jsx` agrupa clients por `legal_name` normalizado; el value del Select contiene todos los `client_id` separados por coma. `QuotesTable.jsx` filtra con `allowedIds.includes(quote.client_id)`.
- B.2 — Filtro Estado estricto: nuevo helper `getEffectiveStatus(q)` en `QuotesTable.jsx` calcula el estado real basado en timestamps (delivered_at > paid_at > invoiced_at > approved_at > sent_at). Resuelve el caso de 7 cotizaciones con `invoice_number` pero `quote_status='Aprobada'` (regularizaciones).
- B.3 — Renombrado: `'Implementación MPOS Integrada'` → `'Implementación MPOS (Imple + POS)'`.

**C. Reingeniería Flujo MPOS (fast_track)**:
- `_create_project_from_quote` (`quote_transitions.py:1`) acepta `keep_quote_active: bool`. Si True: en lugar de borrar la cotización, la actualiza con `quote_status='Enviada a Imple'`, `sent_to_implementation_at`, `project_id`, `project_number`.
- `send_quote_to_implementation` detecta `quote.quote_category=='fast_track'` y: (1) NO archiva al histórico, (2) pasa `keep_quote_active=True`. Cotización permanece activa en grilla.
- `deliver_quote` archiva al histórico como antes y NO recrea proyecto (ya existía).
- Frontend `QuotesTable.jsx`: para fast_track, "Enviar a Implementación" renderizado DESPUÉS de "Configuración" (no al final). Botón duplicado del final excluye fast_track.

**D. Reportes de Ventas — Filtro Creador**:
- Backend `sales_reports.py`: `_build_match` acepta `created_by`. Agregado el query param a 8 endpoints: funnel, aging, monthly, receivables, clients-ranking, repair-productivity, irregular-quotes, irregular-quotes/pdf, executive-summary.
- Frontend `SalesReports.jsx`: nuevo state `createdBy` + carga `/admin/users`; nuevo `Select` "CREADOR" en la grilla de filtros, combinable con segmento/categoría/fechas/año; propagado a las llamadas API.

**Testing**:
- `/app/backend/tests/test_iteration8_admin_serials_mpos_reports.py` (27 tests): **25 passed, 2 skipped** (skipped requieren datos de prueba específicos para casos integrales).
- Cobertura: gates de admin (403 para no-admin), validación de body (400), HTTP 404 ante IDs inexistentes, parámetro `created_by` aceptado en todos los reports, flujo MPOS legacy preservado.


### Bug Fix: Anexos del Histórico no Descargaban (FileResponse no importado) (Feb 2026) — P0

**Síntoma**: Los anexos del Histórico de Cotizaciones aparecían listados pero al hacer clic en "Descargar" fallaba silenciosamente (HTTP 500 sin mensaje visible al usuario).

**Causa raíz**: En el fix anterior de "FS local primero" en `/app/backend/routes/quote_history.py:454-477` reemplacé el `StreamingResponse` por `FileResponse` para el path local, pero **olvidé importar `FileResponse`** en los imports del archivo. Resultado: `NameError: name 'FileResponse' is not defined` al ejecutar el endpoint.

**Fix**: Una línea: `from fastapi.responses import StreamingResponse, FileResponse`.

**Validación E2E**:
- ✅ Anexo COT-2026-05-001-CORP (att_57e852967455) → HTTP 200, 620KB, 212ms.
- ✅ Anexo de un quote_id distinto → HTTP 200, 632KB, 205ms.

**Lección**: Cuando se refactoriza el cuerpo de una función y se agrega/cambia una clase usada (FileResponse vs StreamingResponse), siempre revisar los imports del archivo. Lint manual del archivo modificado evita este tipo de errores (Python no advierte hasta runtime).


### Optimización Velocidad Descarga Anexos (Feb 2026) — Bug fix

**Síntoma**: Descargas de anexos PDF lentas (1-2s c/u), peor en Producción que en Preview.

**Causa raíz**: El fix anterior priorizó Object Storage como fuente primaria de los endpoints `/quotes/{id}/attachments/{aid}/download` y `/quote-history/{id}/attachments/{aid}/download`. Eso agregaba latencia de red (~500-2000ms) en CADA descarga, incluso cuando el archivo estaba disponible localmente.

**Fix**: Invertir orden de fallback:
1. **FS local primero** → respuesta instantánea (~10ms `FileResponse` con streaming nativo).
2. **Object Storage como fallback** → solo si el archivo no existe localmente.

Esto mantiene la garantía de disponibilidad cross-deploy (archivos viejos siguen accesibles vía Object Storage) sin penalizar el caso común (archivo presente localmente).

**Validación E2E** (curl 5 descargas en Preview):
- Antes: ~1-2s por descarga.
- Después: **180-375ms** por descarga (~5-7x más rápido).

Aplicado a:
- `/app/backend/routes/attachments.py` → `download_quote_attachment`
- `/app/backend/routes/quote_history.py` → `download_history_attachment`


### Reporte Mayor de Activos: Histórico Colapsable + Deferred FIFO + Precargas (Feb 2026) — NUEVO

**Objetivo**: Conservar trazabilidad histórica de movimientos en el Reporte Mayor sin saturar la vista financiera y resolver casos con datos cronológicamente inconsistentes.

**Backend** (`/app/backend/routes/inventory.py` → `get_asset_ledger`):
1. **Histórico por item**: Cada item del response ahora incluye un array `history` con todos los movimientos (entradas/salidas/transferencias) con fecha, tipo, almacén, cantidad signada, costo y referencia.
2. **Precargas incluidas en FIFO**: Las `transferencia_entrada` en estado `precarga` (cuarentena técnica de transferencias) ahora se cuentan en el FIFO, alineadas con `stock_by_wh`. Físicamente ya están en el almacén destino.
3. **Deferred FIFO**: Si una salida ocurre cronológicamente antes que sus lotes (datos inconsistentes tras reconstrucciones de almacenes), se difiere y se aplica al final contra los lotes que aparezcan después. Resuelve casos como salida del 07/may sobre lotes regenerados el 20/may.

**Frontend** (`AssetLedgerReport.jsx`):
- Botón colapsable "Ver histórico de movimientos (N)" bajo cada subtotal de item.
- Tabla anidada con: Fecha+hora, Tipo (badge colorido por tipo), Almacén (badge LCH/TBP), Cantidad signada, Costo unit., Referencia (cliente+cotización o proveedor+factura).
- Helpers: `movementTypeLabel`, `movementTypeColor`, `warehouseBadge`, `formatDateTime`.
- Botón oculto en impresión (`print:hidden`) para no inflar el PDF.

**Validación E2E** (Bateria VX820 con datos reconstruidos):
- ✅ Total: 162 uds (LCH:0, TBP:162) — coincide con kardex.
- ✅ 3 lotes activos: 100→97 (entrada directa, salida FIFO aplicada) + 5 + 60 (transferencias precarga incluidas).
- ✅ 8 movimientos en histórico (entradas, salidas, transferencias).
- ✅ Auditoría 26 items: 0 inconsistencias header vs sum(lotes).


### Fix Crítico FIFO: Transferencias Inter-Almacén Forman Parte del Ciclo FIFO del Destino (Feb 2026) — P0

**Síntoma reportado** (caso Batería VX820):
- El Reporte Mayor de Activos mostraba 3 lotes: 5 LCH + 60 LCH + 100 TBP, cuando físicamente las 65 uds de LCH ya habían sido transferidas a TBP (kardex LCH = 0, kardex TBP = 162).
- Cuando se hacía una salida desde TBP, el FIFO descontaba del lote "entrada directa" (más reciente) en lugar del lote "transferencia recibida" (más antiguo). Resultado: lotes fantasma en LCH y FIFO incorrecto en TBP.

**Causa raíz**: El endpoint `GET /api/inventory/asset-ledger` en `/app/backend/routes/inventory.py` SOLO procesaba `entrada` y `salida`, ignorando `transferencia_entrada` y `transferencia_salida`. Esto generaba:
1. Lotes "fantasma" en el almacén origen tras una transferencia (no se descontaban).
2. Ningún lote nuevo en el almacén destino (no se procesaba `transferencia_entrada`).
3. Salidas FIFO desde el destino solo encontraban lotes de entrada directa (no transferidos).

**Fix aplicado**: Refactor del algoritmo FIFO segmentado del asset-ledger:
- Query ahora incluye los 4 tipos: `entrada` + `transferencia_entrada` (crean lotes) y `salida` + `transferencia_salida` (descuentan FIFO).
- Excluye `certification_status='precarga'` (lotes en cuarentena).
- Procesamiento cronológico estable: entradas antes que salidas del mismo timestamp para evitar saldos negativos transitorios.
- `transferencia_entrada` usa `created_at[:10]` como purchase_date (fecha de llegada física al almacén destino, alineado con el ciclo FIFO operativo de ese almacén).
- `transferencia_entrada` hereda el `unit_cost` del origen (ya existía en el código de transferencia, `services/inventory.transfer_between_warehouses`).

**Validación E2E con curl** (Bateria VX820 — `hwr_f48c4cce83ca`):
- ✅ Total 162 uds | LCH: 0 | TBP: 162 (alineado con kardex).
- ✅ 2 lotes vivos en TBP: 62 (transferencia 15/abr) + 100 (entrada directa 28/abr).
- ✅ FIFO correcto: la salida de 3 descontó del lote transferido más antiguo (65→62).
- ✅ Auditoría general de 26 items: 0 inconsistencias header vs sum(lotes) por almacén.


### Auto-Recuperación de Anexos a Object Storage (Feb 2026) — NUEVO

**Objetivo**: Garantizar que TODOS los anexos referenciados en `quotes.attachments` y `quote_history.attachments` estén replicados en el Object Storage persistente. Útil para entornos con filesystem efímero/read-only (Producción tras un deploy) y como salvaguarda contra anexos que solo viven localmente.

**Backend** (`/app/backend/routes/data_migration.py`):
- Endpoint `POST /api/admin/attachments/recover-to-storage` (solo Admin).
- **Paginado** (skip/limit, default 50) para evitar timeout del proxy K8s (60s).
- **Concurrencia controlada** con `asyncio.Semaphore(8)` + `asyncio.to_thread` para llamadas síncronas al Object Storage.
- Algoritmo: para cada anexo → ¿está en storage? sí → skip. ¿no? → ¿está en FS local? sí → subir. ¿no? → reportar como missing.
- Parámetros: `dry_run=true|false`, `skip=int`, `limit=int (max 200)`.
- Response: `{ total, processed_so_far, done, next_skip, scanned, already_in_storage, uploaded, missing_everywhere, errors, by_collection, missing_details, error_details }`.

**Frontend** (`QuotesBundleMigrationModal.jsx`):
- Nuevo panel "3. Auto-recuperación de anexos al Object Storage" en la tab Importar.
- Botones: **Auditar (Dry-Run)** (no sube nada, solo reporta) y **Ejecutar Recuperación** (sube los faltantes).
- Loop automático en frontend hasta `done=true` con barra de progreso visible.
- Resumen final con stats por colección y detalle de anexos sin archivo (primeros 50).

**Validación E2E**:
- ✅ Test paginado: skip=0,limit=50 → HTTP 200 en 22s, total=327, processed=50, done=false.
- ✅ Test final: skip=300,limit=50 → HTTP 200 en 10s, processed=327, done=true.
- ✅ Preview: 327/327 anexos ya están en Object Storage (0 missing, 0 errors).


### Bug Fix Crítico: Anexos de Cotizaciones Fallaban Aleatoriamente en Producción (Feb 2026) — P0

**Síntoma**: En el ambiente de Deploy/Producción algunas cotizaciones mostraban su PDF anexo correctamente, otras aparecían vacías de forma aleatoria. La descarga del ZIP completo funcionaba (los archivos sí existen en Object Storage), pero la visualización individual desde el modal "Anexos" fallaba intermitentemente.

**Causa raíz**: El endpoint `GET /api/quotes/{quote_id}/attachments/{attachment_id}/download` en `/app/backend/routes/attachments.py` SOLO leía del filesystem local (`UPLOADS_DIR`). En Producción el FS del pod es efímero/read-only, así que tras cada deploy:
- Los anexos subidos *después* del último deploy → en FS del pod → se ven ✅
- Los anexos subidos *antes* del último deploy → solo en Object Storage → 404 ❌

El endpoint análogo del histórico (`/quote-history/.../attachments/.../download`) ya tenía fallback correcto a Object Storage, por eso ese flujo funcionaba bien.

**Fix aplicado**: Replicar el patrón de fallback en `download_quote_attachment`:
1. Intentar `get_pdf_from_storage(rel)` primero (Object Storage es la fuente de verdad cross-deploy).
2. Si retorna `None`, fallback al FS local con `FileResponse`.
3. Si tampoco existe → 404.

**Validación E2E** (curl en Preview):
- ✅ Descarga con archivo presente en FS → HTTP 200, 1.3 MB
- ✅ Descarga simulando FS sin archivo (movido a /tmp) → HTTP 200, 1.3 MB **vía Object Storage**

**Próximo paso**: Usuario debe redesplegar a Producción para que el fix surta efecto allí. Con esto se elimina la inconsistencia aleatoria en el módulo de cotizaciones.


### Recuperación de Inventario tras Borrado por Error (Feb 2026) — NUEVO

**Contexto**: El usuario solicitó borrado total de Inventario (warehouses + hardware + movimientos) y al recrear los almacenes manualmente (con UUIDs nuevos), reimportó solo el JSON de `inventory-movements` exportado de Producción. Esto dejó 69 movimientos huérfanos (warehouse_id apuntando a almacenes inexistentes) y 26 items huérfanos (item_id sin entrada en `hardware`).

**Solución aplicada** (script ad-hoc `/tmp/inv_rebuild.py`):
1. **Remapeo de `warehouse_id`** en los 69 movimientos:
   - `whs_bea89b61` → `whs_bdd845f6` (Los Chaguaramos): 41 movs
   - `whs_f00b02f4` → `whs_40dfa046` (Torre Banco Plaza): 28 movs
2. **Reconstrucción del catálogo `hardware`** desde los movimientos (aggregate por `item_id` tomando `item_name`, `item_type`, `unit_cost` del movimiento más reciente). Se crearon 26 items con flag `reconstructed_from_movements: true`. Por defecto: `asset_type='Bien'`, `price_usd=price_bs_usd=unit_cost`, `description=''`.

**Resultado final**: 0 huérfanos, 26 hardware, 69 movimientos asociados correctamente a los 2 almacenes activos.

**Pendiente conocido (Backlog P2)**: Agregar módulo `warehouses` al sistema de migración (`/app/backend/routes/data_migration.py` → `MODULES`) para futuro export/import. Hoy `MODULES` incluye: banks, payment-methods, hardware, commercial-categories, users, inventory-movements, clients, quote-history, taller-equipos. Falta `warehouses`.


## Módulos Implementados

### Asignaciones Temporales — Soporte para Personas Externas (Feb 2026) — NUEVO

**Objetivo**: Permitir asignar ítems temporalmente no solo a personal interno (usuarios del sistema) sino también a personas externas (integradores, contratistas, técnicos de terceros), capturando empresa y contacto en el motivo.

**Backend** (`/app/backend/routes/inventory_temporary.py`):
- `POST /inventory/temporary-assignments` ahora acepta dos modos en el responsable:
  - **Interno**: `responsible_user_id` (existing). Toma nombre/email del documento `users`.
  - **Externo**: `is_external_responsible: true` + `responsible_external_name` (texto libre).
- Validación: si externo, exige `responsible_external_name`; si no, exige `responsible_user_id`.
- Nuevo campo en el documento `is_external_responsible: bool` + `responsible_user_id: null` cuando es externo.
- Validación del motivo: máximo **500 caracteres** (antes sin límite explícito).

**Frontend** (`Inventory.jsx`):
- Selector "Responsable" muestra como **primera opción destacada en ámbar**: "👤 Persona externa (integrador, contratista...)".
- Al elegirla, aparece bloque ámbar con input "Nombre del responsable externo" y tip recordatorio para incluir empresa/teléfono en el motivo.
- Textarea de Motivo ahora con **5 filas, maxLength 500** y **contador `(X/500)`** visible junto al label.
- Placeholder dinámico: si el responsable es externo sugiere formato `Empresa / Teléfono / Motivo`; si es interno mantiene el ejemplo original.
- En la tabla de Asignaciones Temporales, los responsables externos se muestran con badge **"EXTERNO"** ámbar y subtítulo "Ver motivo para contacto" (en lugar del email).

**Validación E2E con curl**:
- ✅ Asignación con `is_external_responsible:true` + `responsible_external_name:"Juan Pérez (Integradora Andina C.A.)"` + motivo extenso (empresa+teléfono+motivo) → status 200.
- ✅ Validación: sin nombre externo → 400.
- ✅ Tabla muestra el badge "EXTERNO" cuando aplica.

### Inventario — Módulo de Asignaciones Temporales (Feb 2026) — NUEVO

**Objetivo**: Controlar la salida transitoria de ítems del inventario (pruebas, demos, uso interno) con trazabilidad completa y devolución posterior.

**Backend** (`/app/backend/routes/inventory_temporary.py` — nuevo módulo, registrado en `server.py`):
- Nueva colección `temporary_assignments` con `{assignment_id, item_id, warehouse_id, quantity, serials[], responsible_user_id, responsible_name, responsible_email, assigned_date, reason, status: 'asignado'|'devuelto', created_at, exit_movement_id, return_movement_id, returned_at, returned_by, return_notes}`.
- Endpoints:
  - `POST /api/inventory/temporary-assignments`: valida stock, crea `salida_temporal` en `inventory_movements`, bloquea seriales en `serial_assignments` (status `asignado_temporal`).
  - `POST /api/inventory/temporary-assignments/{id}/return`: crea `entrada_temporal`, libera seriales, marca status `devuelto`.
  - `GET /api/inventory/temporary-assignments?status=asignado|devuelto|overdue|all`: lista con filtros + enriquecido con `days_out` e `is_overdue` (>15 días).
  - `GET /api/inventory/temporary-assignments/active-by-item`: mapa `{item_id: [activas]}` para resaltar items en UI.
- Lógica de stock: `salida_temporal` y `entrada_temporal` se cuentan en el `sign` de `get_warehouse_stock` (descuentan/reintegran) y los seriales `asignado_temporal` están en la lista de bloqueados (evita que aparezcan disponibles para cotizaciones).

**Frontend** (`/app/frontend/src/pages/Inventory.jsx`):
- Botón **"Asignación Temporal"** (naranja) junto a "Entrada".
- Tabs reformados: Stock | Movimientos | **Asignaciones Temp.** (badge naranja con contador de activas).
- Modal de creación con todos los campos (ítem, cantidad/seriales según tipo, responsable, fecha, motivo).
- Modal de devolución con notas opcionales.
- Tab "Asignaciones Temp." con tabla filtrable (Activas | ⚠ Vencidas +15d | Devueltas | Todas), botón Devolver en cada fila activa, indicador de días fuera con código de color (>7d ámbar, >15d rojo).
- Stock tab: items con asignaciones activas se resaltan en **bg-amber-50** con badge "X en uso" (rojo si vencida).
- Constantes `MOV_LABELS` extendidas con `salida_temporal` (ámbar) y `entrada_temporal` (teal) para que aparezcan correctamente en el Kardex.

**Validado E2E con curl**:
- ✅ Stock antes: 46 → crear asignación qty=2 → stock: 44.
- ✅ Asignación visible en lista con `days_out: 0`.
- ✅ Devolver → stock restaurado a 46, status `devuelto`, `return_movement_id` poblado.

### Cotizaciones — Endpoint y UI de Regularización Masiva (Admin) (Feb 2026) — NUEVO

**Objetivo**: Permitir al Administrador disparar la migración masiva de regularización **desde producción** tras el deploy (sin acceso a scripts manuales).

**Backend** (`/app/backend/routes/quote_actions.py`):
- `POST /api/admin/quotes/regularize-batch` (admin-only). Acepta `{ "dry_run": bool }`.
- Lógica: por cada cotización con `is_irregular: True`:
  1. Verifica criterio de cobertura (`current_status >= ACTION_RESULT_STATUS[exc.action]`). Si no cumple → reporta como "no regularizable".
  2. Hace backfill de `status_history` con timestamps reales (`approved_at`, `invoiced_at`, etc.) — autor `"Sistema (backfill)"`, action `"_backfill"`.
  3. Aplica `try_auto_regularize_quote()` y reporta resultado.
- Respuesta detallada: `total_irregular_before/after`, `backfilled_count`, `regularized_count`, `cannot_regularize_count` y arrays con detalles por cotización.

**Frontend** (`/app/frontend/src/pages/Quotes.jsx`):
- Nuevo botón **"Regularizar masivo"** en el widget de Cotizaciones Irregulares (solo visible para admin).
- Modal en dos fases:
  - **Previsualización (dry-run)**: ejecuta el endpoint con `dry_run: true`, muestra resumen + secciones colapsables ("Regularizables", "Backfill propuesto", "No regularizables") sin tocar BD.
  - **Aplicar**: requiere confirmación con `window.confirm` y luego ejecuta con `dry_run: false`. Refresca el conteo y la tabla.

**Validado E2E**:
- ✅ Admin: dry-run reporta 3 no regularizables (las 3 restantes legítimamente irregulares).
- ✅ No-admin: 403.
- ✅ Modal renderiza el resumen + sección expandible "No regularizables".

**Uso en producción**: Tras el deploy, el admin entra a Cotizaciones → ve el widget naranja → clic en "Regularizar masivo" → "Previsualizar" → revisa el plan → "Aplicar ahora".

### Ajustes Menores — UX Cotizaciones, Embudo, Auto-Regularización (Feb 2026) — NUEVO

**4 ajustes solicitados y aplicados:**

**1. Botón retorno en Configuración de Acciones de Cotizaciones**:
- En `ActionNotificationsConfig.jsx` se añadió un botón **"← Configuración"** en la parte superior, mismo patrón que `NotificationConfig.jsx` y `EmailFooterConfig.jsx`. Usa `useNavigate('/settings')`. `data-testid="anc-back-btn"`.

**2. Reporte Embudo de Ventas — Tooltip muestra cantidades, no montos**:
- Bug: el `formatter` del `Tooltip` en `SalesReports.jsx` comparaba contra `name === 'count'`, pero el `name` del Bar era literal `"# Cotizaciones"`, por lo que siempre caía al `else` y mostraba `[fmtUSD(val), 'Monto USD']`.
- Fix: simplificado a `formatter={(val) => [val, '# Cotizaciones']}` ya que la barra única solo grafica cantidad.

**3. Lista de clientes en menú de cotizaciones — orden alfabético**:
- En `Quotes.jsx` el setter `setClients(clientsRes.data)` ahora ordena alfabéticamente por `fantasy_name || legal_name` usando `localeCompare('es', { sensitivity: 'base' })` antes de setear. Esto afecta a todos los dropdowns y listas que consumen `clients` en la pantalla.

**4. Auto-regularización de cotizaciones irregulares (cuando stepper queda completo sin saltos)**:
- Nueva función `try_auto_regularize_quote(quote_id)` en `/app/backend/routes/quote_helpers.py`. Criterio: para cada `irregular_exception` activa, el `quote_status` actual debe estar `>=` al estado producido por su `action` (mapa `ACTION_RESULT_STATUS`) Y todos los estados intermedios (`STATUS_ORDER[1..idx]`) deben aparecer en `status_history` (sin saltos).
- Si se cumplen ambos criterios → desmarca `is_irregular`, persiste `regularized_at` + `regularized_auto: True` y agrega un marker en `irregular_exceptions` para auditoría.
- Hook integrado en `update_quote_status` (endpoint genérico `PUT /api/quotes/{id}/status`) que ahora también pushea a `status_history`. También se invoca después de cada push a `status_history` en las acciones específicas (`collect` legacy + motor dinámico).
- Validado E2E con script Python:
  - Stepper con salto (falta "Enviada" en history) → NO regulariza.
  - Después de completar el paso "Enviada" → SÍ regulariza, `is_irregular: False`, `regularized_auto: True`.
  - Idempotente (llamadas subsecuentes no re-procesan).

### Contacto Inicial — Fix Sede TBP + Reset SLA al Reabrir (Feb 2026) — NUEVO

**Problemas resueltos**:

**1. Sede inválida ("TBP") en contactos iniciales**:
- Bug: el campo `sede` se tomaba directamente de `current_user.sede`. Los admins corporativos tienen sede `"TBP"` (transversal de plataforma), lo que producía contactos con sede inválida.
- Fix: en `create_initial_contact` se introduce función helper `_valid_sede` que sólo acepta `PYME` o `CORP`. La sede se resuelve en este orden:
  1. Sede del usuario asignado (si es válida).
  2. Sede del usuario creador (si es válida).
  3. Fallback: `"PYME"`.
- Migración aplicada: 8 contactos existentes con `sede=TBP` fueron actualizados a `sede=PYME`.

**2. SLA al reabrir gestión arrancaba en rojo**:
- Bug: al reabrir, la `due_date` no se reseteaba y el indicador visual quedaba "vencido" reflejando la fecha de la gestión original.
- Fix: el endpoint `POST /reopen` ahora acepta `new_due_date` opcional. Si no se provee, calcula automáticamente **hoy + 5 días** (indicador verde — "En Tiempo"). El frontend muestra un campo `date` precargado con ese default y el usuario puede ajustarlo.
- Trazabilidad reforzada: la entrada de bitácora incluye la nueva fecha límite y, opcionalmente, el motivo.
- Campos `reopened_at`, `reopened_by`, `reopened_by_name` se persisten en el documento del contacto.

**Validado E2E**:
- ✅ Admin con sede TBP crea contacto → queda con `sede=PYME`.
- ✅ Reapertura sin fecha → default `hoy+5` (verde).
- ✅ Reapertura con fecha custom → respeta el valor enviado.

### Contacto Inicial — Homologación Dashboard + Cierre/Reapertura democratizados (Feb 2026) — NUEVO

**Objetivo**: Paridad funcional entre la pantalla maestra de Contacto Inicial y el Dashboard, y democratización de las acciones de cierre/reapertura (antes admin-only).

**Cambios Backend** (`/app/backend/routes/initial_contacts.py`):
- `POST /api/initial-contacts/{id}/close`: **removida la restricción `admin-only`**. Disponible para todos los usuarios autenticados con acceso al módulo. El cierre genera entrada automática en `initial_contact_logs` con `origin: "initial_contact_closure"`, timestamp, autor y motivo.
- `POST /api/initial-contacts/{id}/reopen`: **removida la restricción `admin-only`** + se agregó payload opcional `{reason}` + log automático con `origin: "initial_contact_reopen"`.

**Cambios Frontend — Dashboard** (`/app/frontend/src/pages/Dashboard.jsx`):
- Eliminados los botones **"Documentar"** (MessageSquare) y **"Ver Bitácora"** (Clock) de la tabla de compromisos.
- Eliminados los dialogs `dashDocOpen` (formulario simple) y `dashBitacoraOpen` (viewer de array legacy).
- Reemplazados por **un solo botón** (icono BookOpen) que abre el `BitacoraModal` unificado con `apiPrefix="initial-contacts"` (paridad total con la pantalla principal: alta de gestiones, fecha de seguimiento, persona contactada, marcar completado).
- Nuevos botones **Cerrar Gestión** (XCircle, azul) y **Reabrir Gestión** (RotateCcw, esmeralda) con AlertDialogs para confirmar y capturar motivo.
- Fila de contacto cerrado se renderiza con fondo `bg-blue-50 hover:bg-blue-100` para señalizar visualmente el estado.

**Cambios Frontend — InitialContacts** (`/app/frontend/src/pages/InitialContacts.jsx`):
- Botón **Cerrar Gestión** ya no está gateado por `isAdmin` — disponible para todos los usuarios.
- Nuevo botón **Reabrir Gestión** + AlertDialog con motivo opcional.
- Lógica condicional: si `c.status === 'closed'` se muestra Reabrir; si activo, Cerrar.

**Validación E2E con curl** (usuario `srubio@megasoft.com.ve` NO-admin):
- ✅ Cierre: status 200 + entrada en bitácora `[CIERRE DE GESTIÓN]`.
- ✅ Reapertura: status 200 + entrada en bitácora `[REAPERTURA DE GESTIÓN]`.
- ✅ Ambos logs muestran al autor real (Sergio Rubio) y origin distintivo.

### Proyectos — Tooltip de Nombre de Fantasía (Feb 2026) — NUEVO

**Objetivo**: Replicar la UX de Cotizaciones en la pantalla de Proyectos para ver rápidamente el Nombre de Fantasía del cliente al pasar el mouse sobre la Razón Social.

**Comportamiento**:
- En Cotizaciones se muestra el **Nombre de Fantasía** y al hover aparece la **Razón Social**.
- En Proyectos (espejo invertido): se muestra la **Razón Social** (campo principal del proyecto, `client_name`) y al hover aparece el **Nombre de Fantasía** en un tooltip oscuro.
- Si el cliente no tiene `fantasy_name` o coincide con `legal_name`, el texto se renderiza sin tooltip (sin subrayado punteado) para evitar ruido visual.

**Frontend** (`/app/frontend/src/pages/Projects.jsx`):
- Carga `/clients` en paralelo con `/projects` y `/projects/stats`, construye `clientMap = {client_id → {fantasy_name, legal_name}}`.
- Render del nombre del cliente con el componente `Tooltip` de shadcn (mismo patrón que `QuotesTable.jsx` línea 309-336):
  - Subrayado punteado + cursor `help` cuando hay fantasy distinto.
  - `TooltipContent` con fondo `slate-900` blanco y label "Nombre de Fantasía" + valor.
- `data-testid="project-client-<id>"` en el `<p>` del nombre para regression tests.

**Validado visualmente**: prueba con cliente "INVERSIONES PAGO AQUI 24/7, C.A." cuyo `fantasy_name` se setteó temporalmente a "Astrocel Tienda Centro" — el tooltip se renderizó correctamente. Datos restaurados tras la verificación.

### Inventario — Edición Manual de Movimientos (Admin-only) (Feb 2026) — NUEVO

**Objetivo**: Permitir al Administrador corregir cualquier campo de un movimiento de inventario durante el arranque del sistema o ante data legacy errónea, dejando registro completo en auditoría.

**Backend** (`/app/backend/routes/inventory.py`):
- `PUT /api/inventory/movements/{movement_id}` (admin-only): edición libre absoluta. Acepta cualquier campo del documento (excepto `movement_id`, `_id`, `created_at`, `created_by` que son protegidos). Computa el diff campo-a-campo y solo registra cambios reales (no escribe audit si no hay cambios).
- `GET /api/inventory/movements/{movement_id}/audit` (admin-only): retorna el historial ordenado descendente.
- Audit log persiste en colección `inventory_movement_audits` con: `audit_id, movement_id, edited_by, edited_by_name, edited_by_email, edited_at, changes: {field: {old, new}}, warehouse_id, item_id, item_name`.
- El documento del movimiento gana `updated_at`, `last_edited_by`, `last_edited_by_name`.

**Frontend** (`/app/frontend/src/pages/Inventory.jsx`):
- Botón **lápiz (azul)** junto al de eliminar en cada fila de la pestaña "Movimientos" (solo visible para admin).
- Modal con dos pestañas:
  - **Datos**: grid de 2 columnas con TODOS los campos editables (tipo, almacén, ítem, cantidad, costo, fecha, proveedor, factura, cliente, cotización, referencia, seriales, notas, estado certificación, transfer_id).
  - **Historial**: tabla por edición mostrando Campo | Antes (rojo) | Después (verde), agrupado por timestamp + autor.
- Banner ámbar de advertencia: *"Edición libre absoluta (uso de arranque/corrección)"*.
- Validación de números (quantity → int, unit_cost → float) y normalización de seriales (CSV → lista).

**Seguridad**:
- Ambos endpoints retornan **403** para no-admin (validado E2E con usuario `srubio@megasoft.com.ve`).
- Bugfix paralelo: el handler de eliminar movimientos llamaba a `fetchMovements(selectedWh)` (función inexistente); ahora usa `fetchStock()`.

### Seguridad — Auditoría de Perfiles y Orden de Usuarios (Feb 2026) — NUEVO

**Objetivo**: Acelerar la administración de Seguridad anclando al/los Administrador(es) al tope de la lista, ordenando el resto alfabéticamente y permitiendo auditar de un vistazo a qué usuarios está asignado cada perfil.

**Reglas / UX**:
- **Anclaje (Pinning)** en `AdminUsers.jsx`: usuarios con `role === 'admin'` aparecen siempre al tope; el resto en orden alfabético A-Z por nombre completo (`localeCompare` con `es`).
- **Auditoría de perfiles** en `AdminProfiles.jsx`: nuevo botón **"Ver usuarios" + badge con conteo** junto a Duplicar/Eliminar. Al hacer clic abre un modal con tabla de los usuarios asignados:
  - **Nombre completo** (con badge Admin si aplica y badge de cargo)
  - **Login (email)**
  - **Sede / Departamento**
  - **Estatus** (Activo/Inactivo con icono y color)
- **Filtro local** dentro del modal por nombre, login, sede o departamento.
- **Hipervínculo**: cada fila es clickable y navega a `/admin/users?user=<id>` (deep link con pre-selección automática vía `useSearchParams`).
- **Carga bajo demanda**: el endpoint solo se invoca al abrir el modal (lazy).
- Si el perfil no tiene usuarios asignados (`user_count === 0`), el botón se deshabilita con tooltip explicativo.

**Backend**:
- `GET /api/admin/profiles/{profile_id}/users` (admin-only) — devuelve `{profile_id, profile_name, total, users[]}` con campos mínimos: `user_id, email, first_name, last_name, cargo, sede, departamento, is_active, role`. Lista ordenada alfabéticamente.

**Archivos**:
- `/app/backend/routes/profiles.py` — nuevo endpoint `list_profile_users`.
- `/app/frontend/src/pages/AdminUsers.jsx` — sort con pinning admin + deep link `?user=`.
- `/app/frontend/src/pages/AdminProfiles.jsx` — botón + modal de auditoría + navegación.

### Unificación de Bitácora — Contacto Inicial → Cliente (Feb 2026) — NUEVO

**Objetivo**: Heredar trazabilidad completa al convertir un Contacto Inicial en Prospecto.

**Reglas**:
- Al ejecutar `POST /api/initial-contacts/{id}/convert`, el sistema copia íntegramente todas las entradas de `initial_contact_logs` a `client_logs`, asignándoles el nuevo `client_id`.
- Cada entrada heredada conserva: `detail`, `action`, `follow_up_date`, `contacted_person`, `is_completed`, `created_by`, `created_by_name`, `created_at`, `contact_date`.
- Se agregan campos de trazabilidad: `origin = "initial_contact"`, `origin_contact_id`, `origin_log_id`.
- Se inserta una entrada adicional de tipo "[CONVERSIÓN]" indicando cuántos logs fueron heredados.
- La respuesta del endpoint incluye `inherited_logs: <count>`.

**UI**:
- En el modal de Bitácora de Clientes (`/app/frontend/src/pages/Clients.jsx`), cada entrada con `origin === "initial_contact"` muestra un badge ámbar "Origen: Contacto Inicial" con tooltip explicativo.
- El modal unificado `BitacoraModal.jsx` ya respeta `originBadge` cuando se reutiliza desde otros módulos.

**Archivos**:
- `/app/backend/routes/initial_contacts.py` — función `convert_to_prospect` actualizada.
- `/app/frontend/src/pages/Clients.jsx` — badge de origen en sección de logs.
- `/app/frontend/src/pages/InitialContacts.jsx` — bugfix `fetchData()` y import `MessageSquare`.

### Regla de Negocio: TDD/TDC Liquidación en Divisas — Tarifas default editables (Feb 2026) — NUEVO

**Objetivo**: Cuando el usuario incluye en "Set Up – Puesta en Marcha" un item llamado "TDD/TDC Liquidación en Divisas" (con cantidad > 0), las tarifas mensuales de los recurrentes con `autoTariff` se cargan automáticamente a su techo como **defaults editables**:
- "Derecho de uso de plataforma MServer por PDV" → **$8** (ceiling autoTariff).
- "Procesamiento (HSM, Server, DC, etc.)" → **$6** (ceiling autoTariff).

**Reglas**:
- Aplica solo a tipos de cotización **VPOS, MPOS, MPOS Imple+POS** (no Payment Gateway ni Link de Pago).
- El usuario puede **editar manualmente** las tarifas; mientras la regla esté activa el sistema no las sobrescribe.
- Si el usuario **quita el concepto** del Setup (cantidad = 0 o lo elimina), las tarifas **vuelven al cálculo automático** dinámico (`calculateAutoTariff` por unidad).
- Detección case-insensitive sobre el nombre del item; soporta variantes `TDD/TDC` y `TDC/TDD`, con o sin acentos, y con/sin espacios al separador `/`.

**Implementación** (`/app/frontend/src/pages/Quotes.jsx`):
- `isTddTdcDivisasActive` (`useMemo`) detecta el estado de la regla.
- `useEffect` de transición con `useRef` (`prevTddTdcActiveRef`):
  - Activación → setea tarifas a `autoTariff.ceiling`.
  - Desactivación → recalcula con `calculateAutoTariff(additional_items, ...)`.
- El `useEffect` de reactividad por `additional_items` agrega guarda: `if (isTddTdcDivisasActive) return;` para preservar valores cuando la regla está activa.


### Motor Dinámico de Notificaciones — Fase 3 (Seeder + Auditoría) (Feb 2026)

**Objetivo**: Cerrar el ciclo del Motor Dinámico con dos capacidades operativas:
1. **Seeder legacy**: pre-cargar la matriz completa de configuraciones (57 combinaciones) con un click, dejando una base sensata para que el admin la afine.
2. **Auditoría**: ver el historial de despachos del motor con filtros (acción, tipo de negocio, cotización, rango de fechas).

**Backend** (`/app/backend/routes/action_notifications.py`):
- `POST /api/action-notifications/seed-legacy?overwrite=false` — admin-only. Itera todas las combinaciones permitidas en `ALLOWED_ACTIONS_BY_BIZ_SUB` (57 totales) y crea config con `auto_seeded=True`. Para acciones client-facing (`send_to_client`, `approve` de reparaciones, `repair_complete` de reparaciones) pre-llena fila `client_field` con la plantilla equivalente al envío legacy. Para el resto crea skeleton vacío. **Respeta configs existentes con recipients ya definidos** (no las pisa salvo `overwrite=true`). PDF al cliente solo se adjunta en `send_to_client` (regla "PDF de Cálculos JAMÁS al cliente").
- `GET /api/action-notifications/audit-log` — admin-only. Lee de `db.bitacora` los registros `action=notification_engine_dispatch` con filtros: `action_id`, `business_type`, `quote_number`, `date_from`, `date_to`, `limit`, `offset`. Retorna `{items, total, limit, offset}`.
- Bitácora del seeder se registra como `action_notifications_seed_legacy` con conteos.

**Frontend** (`/app/frontend/src/pages/ActionNotificationsConfig.jsx`):
- Botón **"Pre-cargar matriz legacy"** (violeta, icono Sparkles) en el header del panel admin con `AlertDialog` de confirmación que explica el comportamiento (no sobrescribe existentes).
- **Tabs** "Matriz de configuración" / "Auditoría de envíos".
- Componente `AuditLogTab`: tabla paginada con filtros (5 campos), columnas Fecha · Acción · Combinación · Cotización · Enviados · Saltados (badge ámbar con tooltip de motivos) · Ejecutado por. Botones Anterior/Siguiente con conteo total.

**Tests**:
- `tests/test_notification_engine_phase3.py` — 1 PASS. Valida: seeder respeta configs existentes (skip), client-facing combos llevan `client_field`, internas no lo llevan, audit-log retorna items con filtros (business_type, action_id, quote_number), RBAC 403 para non-admin.

**Validación E2E** (curl):
- POST `/seed-legacy` → `created=54, updated=0, skipped_existing=3, total_combinations=57`.
- GET `/audit-log?business_type=equipos` → filtra correctamente los registros con `config_key` que empieza por "equipos|".


### Motor Dinámico de Notificaciones — Fase 2 (Wiring) (Feb 2026)

**Objetivo**: Interceptar las acciones del flujo de cotizaciones con el motor dinámico para que, cuando el admin haya creado una configuración custom en `action_notification_configs`, los correos se envíen según la matriz configurada (destinatarios + plantillas + adjuntos PDF). Si NO hay config, se preserva 100% el motor "legacy" (cero regresión).

**Implementación**:
- Helper único `_engine_or_legacy(action_id, quote, current_user, custom_message, cc_emails, **pdf_ctx)` en `/app/backend/routes/quote_actions.py`.
- 8 acciones hookeadas: `approve`, `configure`, `repair_complete`, `send_to_client`, `send_to_implementation`, `invoice`, `collect`, `deliver`.
- Patrón: el helper se llama justo antes del bloque legacy de envío de emails. Si retorna `list[dict]` → engine despachó, se retorna respuesta inmediata. Si retorna `None` → ejecuta legacy intacto.
- PDFs precalculados upfront y pasados como `**ctx`: `quote_pdf_bytes`, `billing_pdf_bytes`, `implementation_pdf_bytes`, `invoice_pdf_bytes`, `delivery_note_pdf_bytes`.
- `notification_engine.py` extendido para aceptar 5 keys de PDFs (antes 3).
- **Guardia de email cliente**: si la config custom incluye fila `client_field` y la cotización no tiene email, retorna HTTP 400 con mensaje legible. Bloquea ejecución antes de mutar cualquier estado.

**Side-effects preservados**:
- El bloque de transición de seriales preasignados FT + descargo de inventario fue movido ARRIBA del hook del engine en `deliver` para que se ejecute siempre, con o sin notificación dinámica.
- Status update + push events + bitácora se ejecutan en ambas ramas (engine y legacy).

**Tests**:
- `tests/test_notification_engine_phase2.py` — 1/1 PASS. Cubre: mapping `_quote_to_biz_sub` (5 casos), fallback sin config, dispatch con config válida, validación cliente sin email, registro en bitácora, `has_config`.
- `tests/test_approve_multipart_flow.py` + `tests/test_repair_complete_admin_pdf.py` — 5/5 PASS (sin regresiones legacy).
- E2E curl: `send_to_client` con config dinámica → respuesta `engine_dispatched` + bitácora `sent=1`. Sin config → fallback legacy con SMTP real. Cliente sin email + config `client_field` → HTTP 400 con mensaje legible.


### Privacidad por Departamento + Filtros Granulares + Bug "Hasta" (May 2026) — NUEVO

**Sección 10 — Privacidad por Departamento (P0)**:
- Reglas de visibilidad de cotizaciones:
  - **Admin / Director** → ven TODAS (sin filtro).
  - **Administración (departamento)** → solo cotizaciones cuyo `client_segment` coincide con su `sede` (PYME, CORP o TBP). Permite que todo el equipo de Administración de una misma sede vea las cotizaciones para procesos de facturación, cobranza y auditoría.
  - **Gerente / Coordinador** → solo cotizaciones de usuarios de su departamento (comportamiento previo).
  - **Ejecutivo / Consulta / perfiles RBAC custom** → filtran por `created_by_user_id IN [usuarios del mismo `departamento` + propio user_id]`.
- Aplica en `GET /api/quotes` (lista filtrada) y `GET /api/quotes/{id}` (Administración bloquea con 403 si la sede no coincide; otros con 403 por privacidad de departamento).
- Implementación: `/app/backend/routes/quotes.py` líneas ~454-524 (lista) y endpoint `get_quote` líneas ~571-596 (con detección de departamento "Administración" normalizado con/sin tilde).
- **Pruebas** (Feb 2026):
  - `tests/test_quote_admin_director_visibility.py` — 3 passed: Admin Pyme ve solo PYME, Admin Corp ve solo CORP, Director ve todas las sedes; GET por ID respeta sede.
  - `tests/test_quote_department_privacy.py` — 1 passed: privacidad de Ejecutivo por departamento.

**Sección 11 — Categorías separadas en filtro**:
- Antes: 1 opción "Equipos, Accesorios y Reparaciones".
- Ahora 3 opciones independientes en `QUOTE_FILTER_CATEGORIES`:
  - `implementation` — Implementación (VPOS/MPOS/PG)
  - `equipment` — Equipos y Accesorios
  - `repair` — Reparaciones
- Filtra estrictamente por `quote.quote_category` (la lógica antigua era binaria equipment/!equipment).

**Sección 12 — Bug fix: Filtro "Fecha Hasta" inclusivo**:
- **Causa raíz**: `new Date(filterDateTo)` (ej. `'2026-01-15'`) se interpreta como UTC midnight; al hacer `setHours(23,59,59)` quedaba en `local 23:59`, pero `created_at` (UTC) podía exceder ese límite por el offset de zona horaria, excluyendo cotizaciones del mismo día.
- **Fix**: `new Date(filterDateTo + 'T23:59:59.999')` interpreta el límite en zona local de forma inclusiva. Mismo arreglo aplicado a "Desde" → `'T00:00:00'`.
- Archivo: `QuotesTable.jsx`.

**Pruebas**:
- `tests/test_quote_department_privacy.py` — 1 passed con 5 assertions: admin OK, creador OK, mismo dept OK, otro dept → 403 + lista de quotes excluye/incluye correctamente.
- Smoke test UI confirmó que las 3 categorías aparecen separadas.


### Implementación Patrocinada (May 2026) — NUEVO

**Sección 9 — Campo "Implementación Patrocinada" en el Cotizador**:
- Nuevos campos en `quotes` (y heredados a `projects`):
  - `sponsored_implementation: bool` (default `False`).
  - `sponsoring_bank_id: str | null` (FK a Maestro de Bancos).
  - `sponsoring_bank_name: str | null` (snapshot del nombre).
- UI: bloque en sección Datos Generales del wizard (`QuoteWizardDialog.jsx`):
  - Radio Sí/No (testids `sponsored-impl-yes` / `sponsored-impl-no`).
  - Dropdown condicional `sponsoring-bank-select` (oculto si No, obligatorio si Sí).
  - Cambiar Sí→No limpia automáticamente `sponsoring_bank_id` para evitar dato huérfano.
  - Validación bloquea `isHeaderComplete` si Sí está seleccionado pero no hay banco.
- Backend:
  - Modelos `QuoteCreate`, `Quote`, `QuoteCreateWithPDF`, `QuoteUpdate`, `Project` actualizados.
  - `_create_project_from_quote` ahora hereda los 3 campos al proyecto resultante.
  - Reglas de limpieza: cuando `sponsored_implementation=False`, los IDs/nombres se persisten como `None`.
- **Reportes**: pendientes de definición — solo dejamos los campos persistidos, sin filtros UI ni endpoints específicos por ahora.

**Pruebas**:
- `tests/test_iteration188_sponsored_implementation.py`: 4/5 pytest passed (creación con PDF, default False, PUT update, duplicate). El 5° caso (send-to-implementation) se valida manualmente con script E2E que confirma herencia correcta al proyecto.
- Tipos cubiertos: aplica a TODOS (VPOS, MPOS, GATEWAY, LINK, PYME, CORP).


### Consolidación Flujo Enviar a Implementación + Instrucciones Rich-Text (May 2026) — NUEVO

**Sección 6 — Simplificación del wizard**:
- **Eliminado**: paso manual "Tipo de Proyecto". Se infiere automáticamente desde `quote.quote_type` al abrir el wizard (`VPOS→vpos_mpos`, `MPOS/FAST_TRACK→pos_fast_track`, `GATEWAY/LINK→payment_gateway`).
- **Nueva secuencia unificada**:
  1. (Multitienda si aplica — prefijo intacto)
  2. **Paso 1 – Pinpad Question**: ¿Requiere pinpads? (opcional pinpad_selection si Sí)
  3. **Paso 2 – Modal Consolidado** (`consolidated_data`): fusiona Servidor + Grupo Económico + Nombre de Fantasía + Instrucciones.
  4. **Paso 3 – Confirmación Implementador** (informativo, nombre heredado o "Por asignar").
  5. Cierre → crea proyecto.
- **Se mantiene aparte** el modal de "Personalizar Comunicación" (email).

**Sección 7 — Editor Rich-Text con TipTap**:
- Nuevo componente `RichTextEditor.jsx` basado en TipTap (`@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-underline`, `@tiptap/extension-text-align`, `@tiptap/extension-text-style`, `@tiptap/extension-color`).
- Toolbar: **Negrita**, *Cursiva*, <u>Subrayado</u>, Lista con viñetas, Lista numerada, Alineación (izq/centro/der), Color de texto, Undo/Redo.
- Contador visual "N/500" con barra de progreso (cambia a naranja al superar 90%).
- Validación de 500 caracteres de **texto visible** (ignora tags HTML).
- Hard-cap: si intenta escribir más, dispara `undo()` automáticamente.

**Sección 8 — Persistencia + Ficha Técnica PDF**:
- Nuevo campo `implementation_instructions` (HTML string) en el modelo `SendToImplementationRequest` y en la colección `projects`.
- Backend `_validate_instructions_length` (en `quote_actions.py`):
  - Valida ≤500 chars visibles → HTTP 422 si excede.
  - **Sanitiza** `<script>`, `<iframe>`, `<object>`, `<embed>`, `<style>`, `<meta>`, `<link>`, handlers `on*=`, y `javascript:` (defensa en profundidad aunque TipTap ya emita HTML limpio).
- En re-envíos, si llega vacío el campo se borra del proyecto (no queda contenido stale).
- PDF `implementation_pdf.py`: nueva sección "INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR" con box amber al final de la Ficha Técnica. Convierte `<strong>→<b>`, `<em>→<i>`, `<li>→ • texto`, `<p>→texto<br/>`, y limpia tags desconocidos.

**Pruebas**:
- `tests/test_instructions_validation.py`: 9 passed (5 de longitud + 4 de sanitización XSS).
- `tests/test_iteration187_impl_instructions.py` (testing agent): 3/3 pytest passed incluyendo E2E de `POST /api/quotes/{id}/send-to-implementation` con `implementation_instructions` y persistencia en proyecto.
- Testing agent code-review confirmó estructura del frontend (testids, eliminación de project_type, nuevo phase consolidated_data).


### Recordatorios por Email de "Mis Alertas" (May 2026) — NUEVO

**Sección 5 — Job programado `job_implementer_alerts_due`**:
- Archivo: `backend/services/notification_scheduler.py`.
- Cron diario a las 08:15 America/Caracas (cuarto job del scheduler, tras los 3 existentes a :00/:05/:10).
- Para cada proyecto con `implementer_alerts[]` y `assigned_to_user_id`:
  - Recorre alertas activas (`completed=false`) con `deadline`.
  - Si `deadline == hoy` → email "vence hoy".
  - Si `deadline < hoy` → email "vencida hace N día(s)".
  - Si `deadline > hoy` → omitida.
- Email HTML con encabezado amber, detalle del proyecto, mensaje y fecha objetivo.
- Cool-down de 24h (`implementer_alerts.$.last_reminder_at`) evita spam por ejecución manual/reintentos.
- Además emite push in-app `implementer_alert_due` (nuevo evento registrado en `NOTIFICATION_EVENTS`).

**Pruebas**:
- `backend/tests/test_implementer_alert_reminder.py` (nuevo) valida: hoy/pasado envían email y marcan `last_reminder_at`; futuro omitido; cool-down de 24h efectivo.
- Pytest: 1 passed.


### Automatización de Asignación + "Mis Alertas" + Filtros Reporte (May 2026) — NUEVO

**Sección 2 — Modal 2 "Confirmación de Implementador" en Enviar a Implementación**:
- Nueva fase `confirm_implementer` en el wizard de `QuoteModals.jsx`, insertada entre `economic_data` y `pinpad_question`.
- Al abrirse consulta `GET /api/clients/{client_id}` y muestra:
  - Con implementador: "El implementador asignado para este cliente es: **[Nombre]**" + botón **Avanzar**.
  - Sin implementador: "Por asignar Implementador" + botón **Avanzar**.
- Botón **Atrás** regresa a `economic_data` para editar Grupo Económico / Nombre de Fantasía.
- Backend `_create_project_from_quote` (`/backend/routes/quote_transitions.py`):
  - Si `client.implementer_user_id` presente → setea `assigned_to_*`, `assigned_at`, `status='Asignado / En Proceso'`, `auto_assigned_from_client=True` y añade nota "Asignado automáticamente a [Nombre] desde la ficha del cliente".
  - Si no → mantiene `status='Pendiente por Asignar'` (comportamiento anterior).

**Sección 3 — "Mis Alertas" (autogestión del Implementador)**:
- Nuevo array embebido en proyecto: `implementer_alerts[]` con `{alert_id, message, deadline, created_by_*, created_at, completed, completed_at, completed_by_name}`.
- 4 endpoints REST:
  - `GET /api/projects/{id}/implementer-alerts` — implementador asignado + admin/coord/gerente (lectura para supervisión).
  - `POST /api/projects/{id}/implementer-alerts` — **solo** el implementador asignado.
  - `PUT /api/projects/{id}/implementer-alerts/{alert_id}/complete` — solo el implementador asignado.
  - `DELETE /api/projects/{id}/implementer-alerts/{alert_id}` — solo el implementador asignado.
- Helper `_is_assigned_implementer(user, project)` en `projects.py`.
- Frontend `ImplementerAlertsModal.jsx` (paleta **amber/orange** para diferenciar de los Compromisos rojos):
  - Icono `BellRing`, textos "Mis Alertas", "Fecha objetivo", "Cumplida".
  - `canManage` = implementador asignado; `readOnly` = admin/coord/gerente.
  - Vista readonly muestra banner "Supervisión: solo lectura."
- Botón "Mis Alertas" en header de `ProjectDetail.jsx`, visible para implementador asignado O admin/coord. Badge amber con contador de alertas activas.

**Sección 4 — Filtros dinámicos en Reporte de Carga PDF**:
- Backend `GET /api/projects/reports/workload-pdf` ahora acepta query params multi-select:
  - `assigned_to` (repetible) — Implementador Actual.
  - `original_implementer` (repetible) — Implementador Original (reasignados).
  - `status` (repetible) — Estatus del proyecto.
  - `quote_type` (repetible) — VPOS / MPOS / GATEWAY / LINK.
  - `client` — búsqueda parcial en razón social, fantasía o RIF.
- Cabecera del PDF lista los filtros aplicados como chips.
- Frontend `WorkloadReportFiltersModal.jsx`: modal con chips clicables multi-select + input de cliente + botones "Limpiar filtros" / "Cancelar" / "Generar PDF".
- Botón "Reporte Carga (PDF)" en `Projects.jsx` ahora abre el modal en lugar de descargar directo.

**Validación E2E**:
- Backend pytest `test_iteration186_impl_alerts_workload.py`: 7/7 pasados.
- Script ad-hoc `test_autoassign.py`: herencia de implementer desde ficha de cliente verificada en ambas ramas (con/sin implementador).
- Frontend: modal de filtros abre con los 5 grupos de filtros; modal Mis Alertas abre en readonly para admin; flujo Modal 2 insertado correctamente.


### Fix Crítico Sidebar + Auditoría RBAC Clientes (May 2026) — NUEVO

**Bug P0 resuelto — "Sidebar desaparece al inactivar Cotizaciones"**:
- Root cause: `ProtectedRoute.jsx` redirigía a `/quotes` como fallback cuando el módulo destino estaba inactivo. Si el usuario tenía `cotizaciones=none`, cualquier intento de navegar a una ruta restringida disparaba un **bucle infinito de redirección** (`/x` → `/quotes` → `/quotes` → …), lo que causaba "Maximum update depth exceeded" en React y desmontaba el Layout completo (incluido el Sidebar).
- Fix: fallback cambiado a `/dashboard` (ruta no presente en `ROUTE_MODULE_MAP`, siempre accesible para usuarios autenticados) → rompe el ciclo.
- Defensa en profundidad:
  - Nuevo `SidebarErrorBoundary.jsx` envuelve al `Sidebar`. Si algún `renderMenuItem` crashea, se muestra un menú mínimo seguro (Dashboard + Configuración + Cerrar Sesión) en lugar de página en blanco.
  - `Sidebar.jsx` ahora envuelve el filtrado de items/children en `try/catch` individuales: un item defectuoso se excluye en lugar de romper todo el menú.

**Auditoría RBAC en Clientes (P1)**:
- Frontend `Clients.jsx`:
  - `handleSubmit` y `handleDelete` validan `canEdit` antes de ejecutar (guard redundante al gating de UI).
  - Dropdown "Escanear RIF" ahora gateado con `canEdit` (solo roles con edición ven la acción que muta datos).
- Backend `clients.py` y `dashboard.py`:
  - `POST /clients`, `PUT /clients/{id}`, `DELETE /clients/{id}`, `POST /clients/{id}/update-from-rif`, `POST /clients/parse-rif`, `POST /clients/import` ahora usan `require_permission(authorization, "clientes", "edit")`.
  - Belt-and-suspenders: `server.py` ya tiene un middleware RBAC que bloquea `POST/PUT/PATCH/DELETE` para usuarios con `level=read`; la doble capa evita cualquier escape.

**Validación E2E**:
- Usuario prueba: `srubio@megasoft.com.ve` con `cotizaciones=none`, `clientes=read`.
- ✅ Navegar a `/quotes` redirige a `/dashboard` sin bucle, sidebar intacto.
- ✅ POST `/api/clients` → 403 (`"No tiene permisos de escritura en 'clientes'"`).
- ✅ PUT `/api/clients/fakeid` → 403. DELETE `/api/clients/fakeid` → 403. GET `/api/clients` → 200.
- ✅ UI Clientes sin botones "Nuevo Cliente", "Importar", "Cargar desde RIF Digital".



### Fase B — Reasignación Masiva + Compromisos Gerenciales (Feb 2026) — NUEVO

**Sección 3 — Reasignación Masiva de Proyectos**:
- Nuevo estatus `"En proceso/reasignado"` agregado a `PROJECT_STATUSES` (6to valor) con color púrpura e icono `UserCog` tanto en UI (`STATUS_CONFIG`) como en transiciones (`STATUS_TRANSITIONS`).
- Endpoint `POST /api/projects/bulk-reassign` (admin/coordinador/gerente). Body: `{from_user_id, to_user_id, project_ids}`. Por cada proyecto: valida que destino tenga cargo "Implementador", hace push a `reassignment_history[]` (from_*, to_*, reassigned_at, reassigned_by_name), actualiza `assigned_to_*`, setea `reassigned_from_name/user_id`, cambia status.
- Nuevo componente `BulkReassignModal.jsx`: wizard de 3 pasos (origen → checkboxes con "Seleccionar todos" → destino → confirmar). Botón "Reasignación Masiva" (púrpura) en header de `Projects.jsx`, visible solo para Coord/Gerente/Admin.

**Sección 4 — Compromisos Gerenciales**:
- Modelo `ProjectCommitment` embebido en `projects.commitments[]`: `commitment_id, message, deadline, created_by_*, created_at, completed, completed_at, completed_by_name`.
- 4 endpoints: `GET list`, `POST create` (solo Coord/Gerente/Admin), `PUT /{cid}/complete` (idem), `DELETE /{cid}` (idem).
- Nuevo componente `CommitmentModal.jsx`: formulario con textarea + date picker, sección "Activos" (badge amber/red con VENCIDO si deadline < hoy) + "Cumplidos" (strike-through verde). Prop `canManage` gates mutation buttons.
- **Alerta "inevitable de ignorar" (opción 2b elegida)**:
  - Grilla Proyectos: botón bandera (`Flag`) por fila. Roja con **animate-pulse** + badge numérico rojo cuando hay compromisos activos.
  - `ProjectDetail.jsx`: banner **sticky top-0 z-10 gradient-red** con `animate-pulse-slow` que resume los primeros 2 compromisos activos (creador, mensaje, deadline, marca VENCIDO). Botón "Ver / Gestionar" abre el modal.

**RBAC**:
- Helper `_is_coordinator_or_admin` en backend: `role=admin` o `cargo IN ('coordinador','gerente')`.
- Frontend `canManage = role===admin || cargo===coordinador || cargo===gerente`.
- Doble capa: middleware RBAC de módulo `proyectos` + gate de rol/cargo por endpoint.

**Validación E2E (curl)**:
- ✅ Create commitment (admin): role=Admin, deadline guardado.
- ✅ List / Complete / Delete: todos 200 OK.
- ✅ Bulk reassign: 1 proyecto Omar Jimenez → Jhonatan Rojas. `status='En proceso/reasignado'`, `reassigned_from_name='Omar Jimenez'`, `reassignment_history[0]` completo.
- ✅ RBAC: srubio (user) bloqueado en middleware; admin autorizado.
- ✅ Frontend smoke: 9 botones Compromiso en grilla; 1 con badge rojo "1" animado; Modal abre y crea compromisos; modal Reasignación Masiva abre; status "En proceso/reasignado" visible en detalle.

### Fase A — Gestión de Responsables + Reporte de Carga (Feb 2026)

**5 secciones entregadas** (quedan pendientes reasignación masiva + compromisos gerenciales para Fase B):

**Sección 5 — VPOS Stand Alone**: `Quotes.jsx` handler `handleIntegratorChange` ahora detecta `integrator_id === 'sin_integrador'` y auto-completa `integrator_app_name = 'Stand Alone'` (campo obligatorio).

**Sección 2B — Auto "Último Contacto"**: `routes/projects.py` al enviar una notificación (client/provider/sponsor) guarda `last_contact_at`, `last_contact_by`, `last_contact_target`. La grilla de Proyectos lo muestra bajo el implementador en verde esmeralda (`data-testid="last-contact-{project_id}"`).

**Sección 7 — "Enviar al Cliente" siempre disponible**: eliminado `disabled={quote.quote_status !== 'Borrador'}` en `QuotesTable.jsx`. El backend `/quotes/{id}/send-to-client` no tenía gating, confirmado con curl. Aplica a los 3 flujos (Implementaciones / Equipos y Accesorios / Reparaciones) porque todos usan la misma tabla.

**Sección 1 — Responsables de Implementación en Ficha Cliente**:
- Modelo `Client` / `ClientCreate` extendido con `coordinator_user_id`, `coordinator_name`, `implementer_user_id`, `implementer_name`.
- Nuevo endpoint `GET /api/auth/coordinadores` (filtra `cargo=Coordinador` + `departamento=Implementación`). `/auth/implementadores` ya existía.
- `Clients.jsx`: bloque "Responsables de Implementación" bajo "Capacidad Operativa" con 2 dropdowns. Fallback visual cuando no hay usuarios con esos cargos.
- **Plantilla Excel** (`clients.py` `/clients/template`): columnas Q "Coordinador" + R "Implementador" agregadas. Documentación en hoja "Instrucciones" actualizada.
- **Importador Excel** (`dashboard.py` `/dashboard/import/clients`): lookups `coordinador_lookup` + `implementador_lookup` con validación por nombre/email. Errores con sugerencia de nombres disponibles.

**Sección 2A — Reporte PDF de Carga por Implementador**: Nuevo `GET /api/projects/reports/workload-pdf`. WeasyPrint landscape A4. Agrupa proyectos por `assigned_to_name`. Columnas: Cliente · Tipo (badge color) · Cajas (solo VPOS/MPOS) · Estado · Implementador Original · Fecha Asignación · Último Contacto. Botón "Reporte Carga (PDF)" en la esquina superior de `Projects.jsx`.

**Validación E2E**:
- ✅ `/auth/coordinadores` → 1 resultado (Kevin Malaguera), `/auth/implementadores` → 7.
- ✅ Excel template: 27 columnas con Coordinador/Implementador en posiciones Q/R.
- ✅ Workload PDF: 200 OK, 21KB.
- ✅ `send-notification` actualiza `last_contact_at` con timestamp server + `last_contact_by` + `last_contact_target`.
- ✅ Frontend smoke: grilla Proyectos muestra botón PDF + columna último contacto; modal Cliente muestra bloque "Responsables de Implementación" con ambos dropdowns operativos.

### Reestructuración de Vistas + Badges de Tipo de Negocio (Feb 2026)

**Objetivo**: Identificación inmediata del tipo de negocio (VPOS / MPOS / Payment / Link de Pago) en grilla de Proyectos, Histórico y Reporte de Irregularidades. Limpiar UI eliminando 3 columnas redundantes para liberar espacio.

**Cambios aplicados**:

1. **Componente reutilizable** — `components/projects/ProjectTypeBadge.jsx`:
   - 4 tipos: VPOS (azul), MPOS (verde esmeralda), Payment/GATEWAY (púrpura), Link de Pago/LINK (slate).
   - Cada badge con icono Lucide propio. Fallback gracioso "—" para valores legacy desconocidos.
   - Tamaños `sm` (default) y `xs` para vistas compactas.

2. **`pages/Projects.jsx`** (grilla):
   - 🗑 Removidas: columnas "Proyecto/Ticket" (redundante), "Cliente" separada, "Prioridad".
   - ➕ Nueva columna "Tipo" en lugar de Prioridad.
   - Cliente ahora es la información principal de la primera columna; Ticket queda subordinado bajo el cliente cuando aplica.
   - Eliminada lógica muerta `PRIORITY_OPTIONS`/`PRIORITY_COLORS`/`handlePriorityChange` (la API backend `/projects/{id}/priority` se conserva por si se necesita en otra vista).

3. **`pages/HistoricalQuotes.jsx`**:
   - ➕ Columna "Tipo" entre "Nº Cotización" y "Cliente".
   - colSpan de filas vacías ajustado a 9.

4. **`pages/SalesReports.jsx`** (Reporte de Irregularidades):
   - ➕ Badge "Tipo" justo después del número de cotización.
   - PDF del reporte (`routes/sales_reports.py`) ahora incluye el badge de tipo con colores idénticos a la UI.

5. **`pages/ProjectDetail.jsx`** — bloque "Datos del Proyecto":
   - ➕ Campo "Cotización Origen" (readonly, fuente mono azul) con `data-testid='project-quote-number-ref'`. Compensa la eliminación del `quote_number` de la grilla.

6. **Backend** — `routes/sales_reports.py`:
   - `_collect_irregular_quotes` ahora propaga `quote_type` tanto desde `db.quotes` como desde `db.quote_history` (snapshot + top-level).
   - Items irregulares incluyen `quote_type` en el JSON; el PDF lo renderiza como badge con colores consistentes.

**Retrocompatibilidad**: Los proyectos e históricos existentes ya guardan `quote_type` (heredado de la cotización al crearse). Validado E2E con curl: 8/8 proyectos + 3/3 históricos + items irregulares retornan `quote_type` correcto. Cotizaciones legacy con valores fuera del set (ej. "Verifone") muestran `—` graciosamente sin romper la UI.

**Validación visual**: screenshots confirman 6 columnas en Proyectos con badges Payment púrpura y VPOS azul; Histórico con columna TIPO y los mismos badges.

### Migración de BD para Cotizaciones, Histórico y Proyectos (Feb 2026)

**Objetivo**: Permitir al Administrador exportar/importar Cotizaciones + Histórico + Proyectos derivados con sus anexos para respaldos, replicación entre ambientes (Preview ↔ Production) o restauración tras pruebas.

**Diseño** — extensión del módulo `routes/data_migration.py`:
- 2 archivos por export (elegido por el usuario): JSON de datos + ZIP de anexos.
- Upsert por `id` natural (no destructivo): `quote_id`, `history_id`, `project_id`.
- Acceso restringido: solo `role=admin` (HTTP 403 para otros).

**5 endpoints nuevos** (paths con prefijo `/admin/quotes-bundle-migration/` para evitar colisión con la ruta dinámica `/admin/migration/{module}`):
- `GET    /export-data`        → JSON `{collections: {quotes, quote_history, projects}}` con `counts` y metadata.
- `GET    /export-attachments` → ZIP con `manifest.json` + archivos en sus paths originales (`attachments/{quote_id}/...`, `attachments/history/...`). Lee desde Object Storage con fallback a filesystem.
- `POST   /import-preview`     → resumen por colección (a crear / a actualizar) sin modificar BD.
- `POST   /import-data`        → upsert masivo con bitácora; preserva `created_at` original.
- `POST   /import-attachments` → restaura archivos al Object Storage (dual-write con filesystem) usando los paths del ZIP.

**Frontend** — `components/quotes/QuotesBundleMigrationModal.jsx`:
- Botón "Migración BD" (icono Database, color índigo) en `pages/Quotes.jsx` visible solo para admin.
- Modal con 2 tabs: Exportar (descarga JSON + descarga ZIP) e Importar (preview + apply data + restore attachments).
- Tabla resumen de preview/resultado con conteos por colección.
- Banner de advertencia: "los registros existentes se actualizarán; los nuevos se crearán; no se elimina nada".

**Bitácora** — cada acción (export-data, export-attachments, import-data, import-attachments) registra una entrada en `db.bitacora` con email del ejecutor y conteos.

**Validación E2E** (curl):
- ✅ Export data: 5 quotes + 3 history + 8 projects → JSON 253KB.
- ✅ Export attachments: ZIP de 2.7MB con 5 archivos + manifest (29 missing detectados correctamente — archivos referenciados pero ya purgados del storage).
- ✅ Import preview: `to_create=0, to_update=16` (todos detectados correctamente).
- ✅ Import data: 16 actualizados, 0 errores.
- ✅ Import attachments: 5 restaurados, 1 omitido (el manifest.json, correcto).
- ✅ RBAC: 403 para usuario no-admin.

### Homologación de Matrices para Proyectos Payment Gateway (Feb 2026)

**Problema resuelto**: Al ejecutar "Enviar a Implementación" en cotizaciones tipo Payment Gateway, el proyecto resultante no recibía la `implementation_matrix` (la lógica original solo construía la matriz desde `services` con `item_type='additional'`, formato exclusivo de VPOS/MPOS). Esto causaba: (1) email de Notificación al Cliente sin tabla de productos, (2) imposibilidad de marcar avances en ProjectDetail (matriz vacía).

**Solución implementada** — `routes/quote_transitions.py` `_create_project_from_quote`:
- Detecta `quote_type=='GATEWAY'` y construye `implementation_matrix` desde `pg_setup_items`:
  - Agrupa por `banco × concepto`.
  - **Excluye** items conceptuales fijos (`banco='N/A'`, ej. "Persona Jurídica").
  - **Pre-pobla** las 4 fases estándar (`Recibido / Configurado / Testeado / En Producción`) con `{expected: 1, processed: 0, completed: false}` para que el implementador edite cantidades reales (default 1).
- Lista de `banks` del proyecto incluye los bancos únicos de `pg_setup_items`.

**Comportamiento idéntico a VPOS/MPOS** — heredado sin cambios:
- UI/UX (`SingleBankSection.jsx`): mismo grid Banco→Producto×Fases con MiniPie de avance.
- Cascade desde "Recibido" propaga `expected` a las 3 fases siguientes (vía `updateMatrixCascade` que dispara `PUT /api/projects/{id}/matrix/phase` por cada fase).
- Iconos de estatus (gris→verde) y captura de fecha-hora (`updated_at/completed_at`) al marcar avance.
- Gating: requiere `client_notified=true` y permisos de implementador asignado/supervisor/admin.

**Email de Notificación al Cliente**:
- `_build_matrix_html` (`services/project_template_vars.py`) usa la matriz poblada y aplica fallback `qty=1` cuando `services` está vacío (caso PG) → tabla "Banco / Producto / Cantidad" sin precios, mismo look que VPOS.

**Validación E2E** (curl):
- Cotización PG con `pg_setup_items` (Mercantil×TDC/TDD + Banesco×PagoMovil/C2P + N/A×Persona Jurídica) → al enviar a implementación, proyecto creado con matriz `{Mercantil:{TDC,TDD}, Banesco:{PagoMovil,C2P}}` (Persona Jurídica excluida).
- `POST /api/projects/{id}/preview-notification`: matrix_html con 4 filas, banco × producto × cantidad=1, sin precios.
- `PUT /api/projects/{id}/matrix/phase`: cascade expected=5 + completar Recibido = OK, fases siguientes preservan `processed=0` con `expected=5`.

### Gestión Documental en Histórico de Cotizaciones + Normalización de Irregularidades (Feb 2026)

**Problema resuelto**: Las cotizaciones del Histórico aparecían en el reporte de "Cotizaciones Irregulares" sin manera de subsanarlas (no había forma de cargar el documento faltante). Además, la última fase del flujo aparecía en rojo aunque la cotización ya hubiera completado su ciclo operativo.

**Solución implementada**:
- **Backend** — nuevos endpoints en `routes/quote_history.py` exclusivos para Administradores del Sistema:
  - `GET    /api/quote-history/{history_id}/attachments` — listar (Director o Admin).
  - `POST   /api/quote-history/{history_id}/attachments` — subir (multipart, validación 10MB, categorías). **SOLO admin.**
  - `DELETE /api/quote-history/{history_id}/attachments/{attachment_id}` — eliminar. **SOLO admin.**
  - `GET    /api/quote-history/{history_id}/attachments/{attachment_id}/download` — descargar (Director o Admin). Lee desde Object Storage con fallback a filesystem.
  - Storage path: `attachments/history/{quote_id}/...` (dual-write FS + Emergent Object Storage).
  - Marca `is_subsana=True` solo si la categoría está en el conjunto subsanador (excluye 'Otros').
- **Backend — Normalización en `sales_reports.py`**:
  - `SUBSANA_CATEGORY_MAP` mapea cada categoría de anexo histórico al timestamp del flujo que subsana: `Cotización→sent_to_client_at`, `Soporte de Aprobación`/`Orden de Compra→approved_at`, `Factura→invoiced_at`, `Pagos→paid_at`, `Nota de Entrega→delivered_at`.
  - `_detect_irregularities` y `_format_phase_timeline` ahora reciben el flag `_is_history` y la lista de `attachments`. Cuando una fase faltante tiene un anexo subsanador → la fase se marca `present=True, subsana=True` y la irregularidad desaparece.
  - **Última fase siempre verde** para cotizaciones del histórico (ya completaron su ciclo operativo).
  - La irregularidad "Pasó a Proyecto sin Aprobación previa" se subsana al subir 'Orden de Compra' o 'Soporte de Aprobación'.
  - Consistencia: `_format_phase_timeline` ahora usa `_is_to_project_trigger()` (igual que `_detect_irregularities`) para reconocer ambos formatos `'status_enviada_imple'` y `'Enviada a Imple'`.
- **`models.py`**: `ATTACHMENT_CATEGORIES` extendido con `'Nota de Entrega'`.
- **Frontend**:
  - Nuevo componente `components/HistoricalAnexosModal.jsx` (7 categorías con etiquetas que indican qué fase subsanan).
  - `pages/HistoricalQuotes.jsx`: botón "Anexos" (icono `FolderOpen` ámbar) visible **solo para admin** (`data-testid="qh-anexos-{history_id}"`).
  - `pages/SalesReports.jsx`: timeline del reporte de irregulares colorea las fases subsanadas en cyan (`bg-cyan-50`) con tooltip explicativo.
- **Validación**:
  - Backend: 11/11 pytest pasados (RBAC, upload, listado, descarga, delete, subsanación E2E, PDF render).
  - Frontend: smoke OK (botón visible para admin, modal abre con 7 categorías).
  - Curl manual: subir Orden de Compra subsana `approved_at`; subir OC + Factura + Pagos remueve la cotización del reporte de irregulares.

### Persistencia de PDFs entre Deploys vía Object Storage (Feb 2026)

**Problema resuelto**: Los PDFs (cotizaciones, adjuntos de emails, transferencias) vivían en `/app/backend/uploads/` (filesystem local). Cada deploy de Preview→Production sobrescribía el filesystem llevándose los PDFs de Producción.

**Solución implementada**:
- **Helper `services/pdf_storage.py`**:
  - `save_pdf_dual(path, bytes, name)` → escribe en disco (cache local) + sube a Emergent Object Storage.
  - `get_pdf_from_storage(filename)` → lee desde storage, devuelve `(bytes, content_type)` o None.
  - **Namespace por ambiente**: usa `APP_ENV` env var (preview / production) → key prefix `pdfs/{APP_ENV}/...`. Cada ambiente tiene su propio bucket lógico aislado.
- **Endpoint `/api/uploads/{file_path:path}`** (`server.py`):
  - Sustituye al `StaticFiles` mount.
  - **1° intenta Object Storage** (persistente entre deploys).
  - **2° fallback al filesystem** (legacy / archivos no migrados).
  - 404 si no existe en ninguno.
- **Dual-write aplicado en**:
  - `quotes.py` (5 sitios: PDFs principales de cotizaciones, equipo, regenerar).
  - `quote_actions.py` (2 sitios: Notas de Entrega, Reparación).
  - `inventory.py` (transferencias de almacén).
  - `attachments.py` (adjuntos de cotizaciones).
  - `client_communications.py`, `entity_communications.py`, `initial_contact_communications.py`, `projects.py` (adjuntos de emails ad-hoc).
- **Configuración**: `APP_ENV=preview` añadido a `/app/backend/.env`. En Producción debe configurarse `APP_ENV=production`.
- **Limpieza preview**: PDFs y adjuntos viejos eliminados (261MB → 2.9MB), preservando logo institucional, templates, bank_logos y documentos institucionales.
- **Validado E2E**: 
  - Subida vía `save_pdf_to_storage()` → 200 OK con APP_ENV=preview.
  - GET `/api/uploads/test_pdf_storage_xyz.pdf` → HTTP 200 desde Object Storage.
  - Fallback filesystem para archivos pre-existentes.



### Refinamientos UX y Bug Fixes (Feb 2026) — NUEVO

**1. Bug Fix — Banco con email duplicado del Cliente** (`routes/projects.py /suggested-contacts`):
- La deduplicación previa eliminaba contactos legítimos: si un contacto Principal de un Banco compartía email con un contacto del Cliente, solo quedaba uno.
- Fix: deduplicar por tupla `(email, source, bank_name)`. Ahora el mismo email puede aparecer como Cliente y como contacto de cada Banco.

**2. Labels compactos en panel de contactos**:
- Eliminado "Banco Banco" duplicado y posición.
- Cliente: `Rafael Gonzalez` (antes: `Cliente: Rafael Gonzalez`).
- Banco: `Manuel Suarez · Principal` (antes: `Banco Banco Mercantil (Manuel Suarez · Ejecutivo · Principal)`).

**3. Autocompletar "Sin Entidad Patrocinadora"** (`QuoteWizardDialog.jsx`):
- Al seleccionar "Sin Pinpad/POS" en el wizard, `sponsor_bank_id` se setea automáticamente en `'none'` (Sin Entidad Patrocinadora). Lógica simétrica que ya existía en backend para nullear sponsor_bank_name al guardar.



### Refinamiento de Notificaciones Secuenciales (Feb 2026) — NUEVO
**Backend** + **Frontend**:

**1. Bug Fix — Matriz Bancos×Productos lookup case-trim** (`services/project_template_vars.py`):
- El lookup `qty_lookup` aplicaba `.strip()` solo en la indexación pero no al consultarlo desde `implementation_matrix`. Productos con trailing space (ej: `'C@mbio - Pago Móvil '`) no matcheaban, alternando 10/1/10/1 en la columna Cantidad.
- Fix: aplicado `.strip().lower()` en ambos lados del lookup. Verificado E2E: las 7 filas de la matriz ahora muestran 10 (cantidad real).

**2. Refactor UX — Selección manual de destinatarios principales (TO)** (`ProjectDetail.jsx` + `routes/projects.py`):
- El campo "Destinatarios Principales (TO)" ya **NO se autopobla**; inicia vacío.
- Botones de cada contacto cambiados de **"+CC"** a **"+Agregar"** (al TO) y **"Agregar todos a CC"** → **"Agregar todos"**.
- Chips de TO con botón **×** para quitar individualmente.
- Backend: `SequentialNotifyRequest` y `PreviewNotificationRequest` aceptan nuevo campo `to_override: List[str]`. Si está presente, sustituye el TO auto-resuelto. Los emails de CC siguen yendo separados.
- Validación frontend: bloquea preview/envío sin TO manual.
- Validado E2E backend: `POST /preview-notification` con `to_override:["custom1@x.com","custom2@x.com"]` retorna esos como recipients; sin override mantiene comportamiento legacy.
- UI idéntica para Cliente y Banco (mismos componentes y data-testids con prefijo `client`/`bank`).



### Optimizaciones de Comunicación, Trazabilidad y Reportes (Feb 2026) — NUEVO
**Backend** + **Frontend**:

**1. Bancos multi-contacto (`models.py`, `routes/banks.py`, `Banks.jsx`)**:
- Nuevo modelo `BankContact` (contact_id, first_name, last_name, full_name, position, email, phone, contact_type ∈ {Principal, Técnico, Otro}).
- Bank y BankCreate aceptan array `contacts: List[BankContact]`.
- Helper `ensure_bank_contacts()` migra in-memory bancos legacy (contact_name/email/phone) → `contacts[0]` Principal sin persistir.
- POST/PUT `/api/banks` sincronizan `contact_name/email/phone` legacy con primer contacto Principal para retrocompat.
- UI: repeater dinámico con tipo (Principal/Técnico/Otro), Cargo, Email y Teléfono; botón "Agregar contacto" / eliminar.

**2. Selector de destinatarios en notificaciones de Proyectos (`ProjectDetail.jsx`, `routes/projects.py /suggested-contacts`)**:
- Endpoint `/projects/{id}/suggested-contacts` extendido con `bank_name`, `contact_type`, `name` por contacto (soporta multi-contactos del banco).
- UI: contactos agrupados por Cliente / Banco, filtrados según `notifTarget.type` (cliente|banco|bank_client|bank).
- Botón individual "+CC" por contacto y "Agregar todos a CC" — añade emails al campo `additionalRecipients` evitando duplicados (case-insensitive).

**3. Cantidad real en Matriz Bancos×Productos (`services/project_template_vars.py`)**:
- `_build_matrix_html(matrix, services)` ahora indexa `cantidad_cajas` por (banco, producto) desde `project.services` (item_type='additional').
- La columna Cantidad refleja la cotización original; fallback a 1 si no hay coincidencia.

**4. Reporte irregularidades extendido (`routes/sales_reports.py`)**:
- Nueva regla explícita: **"Pasó a Proyecto sin Aprobación previa"** (cuando `archived` + trigger Imple + `approved_at=None`).
- Helper `_is_to_project_trigger()` normaliza valores `'Enviada a Imple'`, `'status_enviada_imple'`, `'status_enviada_imple_recovered'`. Aplicado en 3 puntos del reporte.
- Validado E2E: 3 cotizaciones en histórico (COT-2026-04-026/028/029-PYME) ahora aparecen correctamente flageadas.

**6. Layout de correos — mensaje personalizado antes de la firma (`config.py`, `routes/quote_actions.py`)**:
- Helper `inject_custom_message(html, msg, user_name)` inserta el bloque del operador:
  1. Reemplaza marcador `{{Mensaje_Personalizado}}` si está presente en plantilla.
  2. Inserta antes de patrones de cierre: `Atentamente`, `Saludos cordiales`, `Cordialmente`, `Equipo Mega Soft/Nexus`, `Quedamos a su disposición`.
  3. Antes de `</body>` o append final como fallback.
- Helper `build_custom_message_block` construye el bloque azul con label "Mensaje de {user_name}".
- Aplicado a 5 call sites en `quote_actions.py` (FT config, RC, html_content, RW templates).
- Tests inline: marcador explícito ✅, antes de Atentamente ✅, marcador limpio si custom vacío ✅.



### Herencia de "Bancos/Entes" en Suscripción PDV/Banco (Feb 2026) — NUEVO
**Frontend** (`/app/frontend/src/components/quotes/constants.js`, `Quotes.jsx`, `QuoteWizardDialog.jsx`):
- Flag `inheritBancos: true` añadido al concepto base "Suscripción PDV/Banco" (item 1 de Setup).
- `initializeSetupConcepts` ahora copia `cantidad_bancos` del header al inicializar items con `inheritBancos`.
- `useEffect` de propagación extendido: además de propagar Cajas, ahora propaga Bancos solo a items con `inheritBancos: true` cuando el usuario cambia el campo Bancos/Entes del header.
- `mapService` (loadQuoteForEdit) preserva el flag al cargar cotizaciones existentes; helper `hasInheritBancos()` detecta por nombre.
- UI: campo Bancos del item se renderiza como **read-only** (azul) con tooltip `Heredado del campo Bancos/Entes del header (N)`. El usuario ya no puede desincronizar manualmente.
- Validado E2E con Playwright: header=5 → item=5; cambio header→8 → item se actualiza a 8 automáticamente.



### Manejo de Sesión Expirada — Interceptor 401 (Feb 2026) — NUEVO
**Frontend** (`/app/frontend/src/utils/api.js`):
- Interceptor de Axios mejorado: al recibir HTTP 401 en cualquier endpoint que no sea `/auth/(login|register|forgot|reset|verify)`, ejecuta `handleSessionExpired()`:
  - Limpia `session_token`, `user` y cualquier clave de localStorage que coincida con `/token|session|auth|user/i`.
  - Muestra toast amigable: "Su sesión ha expirado. Por favor inicie sesión nuevamente."
  - Redirige a `/login` con delay de 600ms para que el toast sea visible.
  - Flag `sessionExpiredHandled` evita toasts duplicados cuando varias requests fallan en paralelo.
  - No interfiere con el formulario de login (errores de credenciales se muestran inline).
- Función `handleSessionExpired` exportable para uso opcional desde llamadas `fetch` raw.
- Validado E2E con Playwright: token inválido → redirect automático a `/login` y localStorage limpiado.

### Selector de Integradores con Búsqueda en Wizard de Cotizaciones (Feb 2026) — NUEVO
**Frontend** (`/app/frontend/src/components/quotes/QuoteWizardDialog.jsx`):
- Input de búsqueda sticky dentro del SelectContent de integradores en `QuoteWizardDialog`.
- Filtra por `name` (case-insensitive, trim) en tiempo real, ordenado alfabéticamente con `localeCompare('es')`.
- Muestra "Sin coincidencias" si no hay matches y "No hay integradores para esta modalidad" si la lista filtrada base está vacía.
- Validado E2E con Playwright: 234 opciones sin filtro → 0 con búsqueda "payway" → 234 al limpiar.



### Bancos por Producto en Medios de Pago (Feb 2026) — NUEVO
**Backend** (`/app/backend/routes/services.py`):
- `GET /api/services/{service_id}/banks` → lista de bancos asociados al producto. Cruza por `products.service_id` y por `product_name` normalizado (lowercase + sin acentos + trim, espejo del frontend).
- `GET /api/services/report/banks-by-product/pdf` → PDF "Bancos por Producto" generado con WeasyPrint. Diseño elegante: portada con KPIs (productos con/sin bancos asociados, total de asociaciones), una sección por producto con tabla de bancos (nombre, código, componentes habilitados como chips VPOS/Gateway/mPOS/Link), footer con paginación.

**Frontend** (`/app/frontend/src/pages/MediosPago.jsx`):
- Botón "Bancos" en cada fila → modal con lista detallada (logo, nombre, código, componentes habilitados).
- Botón global "Bancos por Producto" en cabecera → descarga PDF.

### Migración de Datos Catálogos (Feb 2026) — NUEVO
**Backend** (`/app/backend/routes/data_migration.py`):
- 8 endpoints admin-only para Export/Preview/Apply de catálogos maestros entre ambientes (Preview ↔ Deploy).
- Módulos soportados: `banks`, `payment-methods` (services), `hardware`, `commercial-categories`.
- Formato JSON consistente: `{schema_version, module, collection, key, exported_at, exported_by, count, documents}`.
- Endpoints:
  - `GET  /api/admin/migration/{module}/export` → JSON descargable.
  - `POST /api/admin/migration/{module}/import-preview` → preview con `to_create_count`/`to_update_count`.
  - `POST /api/admin/migration/{module}/import-apply` → upsert idempotente por id natural; conserva `created_at` original; refresca `updated_at`.
- Validación: archivo del módulo correcto; clave natural requerida; duplicados internos detectados; bitácora en `bitacora`.
- 403 a no-admins; 400 a archivos inválidos / módulo equivocado.

**Frontend** (`/app/frontend/src/components/MigrationButtons.jsx`):
- Componente reusable con barra ámbar "Migración (Admin): Exportar / Importar".
- Solo visible si `user.role === 'admin'`.
- Diálogo de **vista previa con confirmación** antes de aplicar (cuántos crear/actualizar/inválidos).
- Integrado en: `Banks.jsx`, `MediosPago.jsx`, `Hardware.jsx`, `CommercialCategories.jsx`.
- Toast con resultado: `X creado(s), Y actualizado(s)`.

**Validado E2E** (curl): export 39 categorías, re-import idempotente (39 actualizados, 0 creados), 403 a no-admin, 400 a archivo de módulo distinto.

### Histórico de Cotizaciones + Autocomplete Universal (Feb 2026)

**Histórico de Cotizaciones** (`/app/backend/routes/quote_history.py`):
- Colección `quote_history` con snapshot inmutable al llegar a estado final.
- Triggers automáticos en `quote_actions.py`:
  - `implementation` → `"Enviada a Imple"` (crea proyecto + archiva)
  - `equipment`, `fast_track`, `repair` → `"Entregada"` (última acción)
- Cotización original obtiene `archived=True` y desaparece del listado `/api/quotes`.
- Endpoints: `GET /quote-history` (filtros: search, quote_category, invoice_number, from/to), `GET /{id}`, `GET /{id}/pdf` (dispatch por categoría: equipment/repair→regenerate_equipment_pdf + FileResponse; implementation/fast_track→generate_quote_pdf binary), `POST /migrate-legacy` (solo admin).
- **Permisología**: `role='admin'` OR `cargo='Director'`.
- Frontend: página `/historical-quotes` con filtros, tabla, detalle modal y descarga de PDF. Entrada en sidebar solo visible para admin/Director.
- Migración inicial: 5 cotizaciones legacy archivadas automáticamente.

**InternalEmailInput** (`/app/frontend/src/components/InternalEmailInput.jsx`):
- Componente reusable de autocomplete con usuarios internos MegaNexus.
- Integrado en:
  - `ProjectDetail.jsx` — ad-hoc email dialog + datalist CC en notificaciones secuenciales.
  - `QuoteModals.jsx` — campo CC en modal de personalización de comunicaciones.
  - `EntityEmailDialog.jsx` — ya incluido desde iteration 173.

**UI Cleanup**: Botón "Anexos" + modal eliminados de `Projects.jsx` (obsoletos tras Bitácora + Notificaciones).

**Tests** (iteration_174 + 175): Backend **10/12** (corregido con iteration_175 PDF dispatch → **7/7 + 1 skip**), Frontend 95% flujos verificados. Cotizaciones archivadas de equipment/repair/fast_track descargan PDF binario correctamente.

### Sistema Genérico de Comunicaciones (Feb 2026)
Replicación del sistema de Clientes a Integradores + Nuevos Productos, con arquitectura DRY.

**Backend** (`/app/backend/routes/entity_communications.py`):
- `GET /api/users/internal-emails` — autocomplete de usuarios activos de MegaNexus.
- `GET|POST|DELETE /api/entity-documents?context=X` — biblioteca de documentos por contexto (INTEGRADORES / NUEVOS_PRODUCTOS).
- `POST /api/integrators/{id}/send-email` — envío con permisos (admin / implementador asignado / gestor / supervisor). Registra entrada en `bitacora` con `entry_type='notification'`, `email_data`, y timestamp ISO con segundos.
- `POST /api/new-products/{id}/send-email` — idem, registra en `new_product_evolution`.
- `POST /api/integrators/{id}/preview-email` y `/new-products/{id}/preview-email` — resolución de variables `{{...}}`.

**Frontend**:
- Componente genérico `/app/frontend/src/components/EntityEmailDialog.jsx`: plantillas (sidebar), variables insertables, vista previa, adjuntos externos + internos, **autocomplete de usuarios internos** (ranking por nombre/email).
- Página genérica `/app/frontend/src/pages/EntityTemplatesConfig.jsx` + wrappers `IntegratorTemplatesConfig` y `NewProductTemplatesConfig`.
- Integradores (`/app/frontend/src/pages/Integrators.jsx`): botón **"Plantillas"** en header (`integrator-templates-btn`) + botón **sobre (Mail)** por fila (`notify-{integrator_id}`).
- Nuevos Productos (`/app/frontend/src/pages/NewProducts.jsx`): `np-templates-btn` + `np-notify-btn-{product_id}`.
- Rutas: `/integrators/communications` y `/new-products/communications`.

**Variables soportadas**:
- Integradores: `{{nombre_integrador}}, {{razon_social}}, {{rif}}, {{email}}, {{telefono}}, {{contacto}}, {{estado}}, {{aplicativo}}, {{fase}}`
- Nuevos Productos: `{{producto}}, {{categoria}}, {{estado}}, {{desarrollador}}, {{sqa}}, {{fecha_entrega}}, {{banco}}`

**Tests** (iteration_173): Backend 12/12 pytest PASSED, Frontend 100% flujos verificados.

### Proyectos — Homologación de Matriz (Feb 2026)

#### Eliminación de fase "Notificado"
- Backend `IMPLEMENTATION_PHASES` reducido a 4 fases: `Recibido, Configurado, Testeado, En Producción`.
- Frontend `PHASES` homologado.
- PUT `/api/projects/{id}/matrix/phase` rechaza `Notificado` (400).

#### Notificación Única (Cliente + Banco)
- Nuevo target `bank_client` en `/api/projects/{id}/send-notification` y `/preview-notification`.
- Usa plantilla `project_notify_bank_client` (seed).
- Botón `data-testid="notif-bank-client-btn"` visible solo en proyectos Single con UN banco (oculta automáticamente el botón genérico "Notificaciones").
- Registra la notificación en historiales `client` y `bank_{bank}` (cliente lleva flag `combined_with_bank`).
- Desbloquea `client_notified=True` automáticamente.

#### Botón "(T)" por fase
- En Single: `data-testid="fill-phase-{bank}-{product}-{phase}"` → iguala `processed=expected` en UNA fase específica.
- En Multitienda: `data-testid="store-fill-phase-{storeId}-{bank}-{product}-{phase}"`.
- Se oculta cuando la fase ya está completa.

#### Lógica de cascada en "Expected"
- Al modificar `expected` de la fase `Recibido`, se propaga a Configurado/Testeado/En Producción (preservando `processed` de cada fase).
- Replicado en Single (`updateMatrixCascade`) y Multitienda (`updateStoreMatrixCascade`).

#### Refactor preventivo
- Extraídos a `/app/frontend/src/components/projects/`:
  - `MiniPie.jsx`, `SingleBankSection.jsx`, `MultistoreBankSection.jsx`, `StoreBankSection.jsx`
- `ProjectDetail.jsx` redujo de 2284 → 2068 líneas.

### Proyectos — Optimizaciones previas (Abr 2026)

#### Permisos de Edición:
- Solo el implementador asignado y su supervisor directo pueden editar la matriz
- Admin siempre tiene acceso completo
- Resto del personal: solo lectura

#### Header "Detalle para Implementación":
- **Integrador**: Campo editable, default "Stand Alone" si vacío
- **Aplicativo**: Campo editable
- **Seriales (Implementación)**: Carga manual y por Excel (.csv/.xlsx), display en header

#### Matriz de Implementación con Cantidades:
- Reemplaza checkmarks binarios por campos numéricos: Esperado/Procesado
- **Gráfico de Pie** (MiniPie SVG) por cada fase mostrando % de avance
- Colores: verde (100%), azul (>=50%), amarillo (>0%), gris (0%)

#### Bitácora Automática:
- Registro automático al cambiar cantidades en la matriz (fase, valor, fecha/hora)
- Registro automático al cargar seriales

### Cotizaciones
- Precio Bs/USD en vez de Precio Efectivo (17 ocurrencias corregidas)
- Filtro PinPad sin restricción por clasificación
- Flujo Reparaciones con plantillas correctas

### Clientes
- Comunicaciones, Plantillas, Bitácora con hora precisa

## Estado de Pruebas (iteration_172)
- Backend: 6/6 pytest PASSED (`/app/backend/tests/test_iteration172_matrix_homolog.py`)
- Frontend: 5/5 UI checks PASSED
- Warning cosmético de hydration pre-existente (iteration_171) abierto pero no bloqueante.

## Enhancement: Actividad Reciente en Dashboard (Feb-2026, iter 180)
- Endpoint `GET /api/notifications/recent-activity?limit=N` — feed empresa-wide, admin/director-only.
- Dedup inteligente: agrupa copias por destinatario usando `(event_type, quote/project/title, timestamp@segundo)`.
- Componente `RecentActivityCard.jsx` en Dashboard (debajo de los stat cards): últimos 5 eventos con prioridad coloreada, categoría, time-ago, click navega al link. Auto-refresh cada 60s.
- Se oculta automáticamente si el endpoint devuelve 403 (usuario no-admin/no-director).
- **No expone datos privados** (se excluyen user_id, read_at, is_read del recipient original).

## P1 — Sistema de Notificaciones Push (Feb-2026, iter 179)

### Arquitectura
- **WebSocket real-time** en `/api/ws/notifications/{user_id}?token=X` con `ConnectionManager` que soporta múltiples tabs por usuario. Fallback automático a polling 30s tras 3 fallos de WS.
- **Colecciones**: `db.notifications` (1 doc por usuario × evento) + `db.notification_config` (config admin global).
- **APScheduler** corriendo 3 cron jobs a las 08:00/08:05/08:10 America/Caracas: taller >15 días, proyectos asignados sin iniciar, proyectos sin avance en 5 días.
- **Catálogo**: 16 eventos (13 instantáneos + 3 programados) en 7 categorías. Cada uno configurable por admin (activo + prioridad Alta/Media/Baja).

### Recipients rules
- Por rol: creator, creator_supervisor, assignee, admin_by_sede, implementation_manager, almacen, sales_by_sede, sales_and_directors.
- "Administración" filtrado por sede del contexto (TBP/PYME/CORP).
- **Admins (role=admin) siempre reciben TODAS las notificaciones activas** (regla explícita del usuario).

### Hooks en flujos existentes
- `quote_actions.py`: approve, send-to-client, invoice, collect, deliver, repair-complete.
- `quote_helpers.py`: mark_quote_irregular.
- `quote_transitions.py`: _create_project_from_quote.
- `projects.py`: asignar implementador, notify-bank, matrix phase completed.
- `new_products.py`: phase change.
- `initial_contacts.py`: create contact. (Endpoints viejos `/notifications` eliminados, se centralizó todo.)

### UI
- Campana (NotificationBell) en sidebar expandido/colapsado con badge rojo de unread + indicador verde de conexión WS.
- Dropdown 400px con items (barra color por prioridad, pill, categoría, time-ago), click marca leído y navega al link.
- Toasts coloreados (sonner): rojo/ámbar/slate según prioridad. Sin sonido.
- Página admin `/settings/notifications`: 16 eventos en 7 acordeones, toggle + 3 selectores de prioridad. Card de acceso en Settings.

### Testing
- **iter_179**: Backend 11/11 PASS, Frontend 100% PASS. Sin regresiones. WS del ingress preview no soporta upgrade pero polling fallback cubre — no afecta al usuario final.
- 2 tests de 403 (non-admin) skipped por falta de credenciales no-admin funcionales (minor).

## Categorías Comerciales Dinámicas + Fix Timestamp Reparada (Feb-2026, iter 178)

### Nuevo catálogo: Categoría Comercial
- Backend `/app/backend/routes/commercial_categories.py` con CRUD completo (admin-only escritura): `GET` (opcional `only_active=true`), `POST`, `PUT` (propaga rename a `db.clients.categoria_comercial`), `DELETE` (bloquea 409 si en uso), `POST /seed-from-existing-clients` (migración one-shot).
- Regex con `re.escape()` para evitar ReDoS / falsos matches en nombres con metacaracteres.
- Seed inicial: 32 categorías (Retail, Farmacia, Restaurante, etc.) + 1 migrada desde datos existentes.
- Frontend `/app/frontend/src/pages/CommercialCategories.jsx`: tabla con search, badge activa/inactiva toggeable, modal crear/editar, delete confirmable.
- Entry "Categoría Comercial" agregado al sidebar grupo Catálogos (icono Tag).
- **Clientes** (`Clients.jsx`): eliminada la lista hardcoded de 32 items; ahora carga categorías activas desde `/api/commercial-categories?only_active=true`. Fallback defensivo: si el cliente tiene un valor legacy/inactivo, se muestra en el Select con sufijo "(inactiva / legado)" para no perder el dato.

### Bug fix: Timestamp "Reparada"
- **RCA**: el modelo Pydantic `Quote` no incluía `repaired_at` ni `configured_at`; FastAPI usaba `response_model=List[Quote]` en `GET /api/quotes` y hacía *strip* de esos campos aunque estuvieran persistidos en MongoDB.
- **Fix** (`/app/backend/models.py` L599-L600): agregados `repaired_at: Optional[datetime]` y `configured_at: Optional[datetime]`.
- El `QuoteStatusStepper.jsx` ya estaba preparado para renderizar el tooltip; solo faltaba que el dato llegara al frontend.

**Testing**: iter_178 → 11/11 backend PASS + 100% frontend PASS. Tooltip "Reparada — 22 abr. 2026, 03:31 p. m." confirmado visualmente en COT-2026-04-030-PYME.

## Reorganización de Sidebar v3 (Feb-2026, iter 179)
Nueva jerarquía de navegación según propuesta del usuario:
- **Gestión Comercial** (grupo): Contacto Inicial · Clientes · Cotizaciones · Histórico de Cotizaciones (gate admin/Director).
- **Catálogos** (grupo): Bancos · Medios de Pago · Bienes y Servicios · Tasa de Cambio.
- **Gestión de Implementación** (grupo): Proyectos · Integradores.
- **Nuevos Productos** (standalone).
- **Gestión Administrativa** (grupo): Inventarios · **Reportes Contables** (sub-grupo anidado: Kardex · Mayor · Salidas Facturadas).
- **Gestión de Taller** (renombrado desde "Equipos en Reparación").
- **Gestión de Seguridad** (grupo admin-only): Creación de Usuarios · Permisos de Usuarios.
- **Configuración** se mantiene en el footer.

Arquitectura: `Sidebar.jsx` ahora soporta **sub-grupos anidados** vía renderer recursivo y flags `isGroup` / `isSubGroup`. El filtro RBAC recorre la jerarquía respetando `requiresHistoryAccess` (admin/Director) y `adminOnly` (solo admin).

## Nuevos Productos — Multi-select de Componentes (Feb-2026, iter 178)
- Campo `Componente` en el modal "Nuevo Producto" cambió de Select de 2 duplas (`VPOS/MPOS`, `PG/Link`) a **multi-select con 4 componentes individuales**: `VPOS`, `MPOS`, `Payment Gateway`, `Link de Pago`.
- Imposible duplicar gracias al toggle de checkbox; se exige al menos uno.
- El frontend envía al backend `component_type` como string CSV (`"VPOS, MPOS"`), manteniendo 100% compatibilidad con el modelo existente.
- Display en tabla y detalle no cambia (solo muestra el string persistido).

## Footer Global de Correos (Feb-2026, iter 177)

**Backend** (`/app/backend/routes/settings.py` + `/app/backend/services/email_service.py`):
- Colección `db.config` con `type: "email_footer"` (body_html, updated_at, updated_by).
- Endpoints:
  - `GET /api/config/email-footer` — devuelve footer actual (cualquier usuario autenticado).
  - `PUT /api/config/email-footer` — admin-only, persiste y **invalida caché** en el servicio de correo.
  - `POST /api/config/email-footer/preview` — resuelve variables y retorna HTML listo.
- Inyección automática en `send_email()`: caché en memoria 60s, variables soportadas `{{año_actual}}` / `{{razon_social}}`, wrapper con borde superior anexado antes de `</body>`. Se aplica a **todos** los envíos del ecosistema (cotizaciones, proyectos, integradores, nuevos productos, soporte).

**Frontend** (`/app/frontend/src/pages/EmailFooterConfig.jsx`, ruta `/settings/email-footer`):
- Editor contentEditable con toolbar (B/I/U, alineación izq/centro/der, insertar enlace).
- Botones de variables: `{{año_actual}}` y `{{razon_social}}`.
- Vista previa en tiempo real con marco institucional.
- Botones Limpiar/Guardar con confirmación. Non-admin solo lectura.
- Entrada en `Settings.jsx` → card "Gestión de Footer Global".

**Tests**: iteration_177 → Backend 7/7 PASS · Frontend 100% interacciones validadas. Sin bugs.

## Backlog
- **P2**: Módulo de Reportes de Ventas
- **P2**: Lógica "Completado" en Roadmap Bancos
- **P2**: Refactor monolitos frontend restantes (`Quotes.jsx` >3400 líneas, `ProjectDetail.jsx` >2200 líneas) — **backend ya refactorizado** (ver sección P2 Refactor Backend)
- **P3**: Resolver warnings React hydration (`<span>/<tr>/<tbody>` mal anidados) en matriz de implementación

## Contactos Iniciales — Acciones en Dashboard + Delete Admin + Campos Opcionales (Feb-2026, iter 180)

**Backend** (`/app/backend/routes/initial_contacts.py`):
- `InitialContactCreate`: `phone` y `email` ahora `Optional[str] = ""`. Permite crear con solo uno o ambos (frontend valida "al menos uno").
- `DELETE /api/initial-contacts/{contact_id}` — admin-only. 403 non-admin, 404 no existe, 409 si ya fue convertido, 200 success con `logger.info` para auditoría.

**Frontend**:
- `InitialContacts.jsx`: modal de creación sin asteriscos en Telefono/Email + hint "Indique al menos uno". Botón Trash2 visible solo para admin (`delete-btn-{id}`) con AlertDialog (`ic-delete-dialog`).
- `Dashboard.jsx`: tabla "Mis Compromisos" tiene ahora íconos completos por fila — Documentar, Reasignar, Transferir, Convertir, Bitácora, **Eliminar (admin)**. Modales `dash-transfer-dialog`, `dash-bitacora-dialog`, `dash-delete-dialog`. Transferir usa `target_user_id/comment` y filtra solo Gerentes activos (consistente con vista Contacto Inicial). Bitácora renderiza `b.timestamp` + `b.description`.

**Tests** (iteration_180): Backend 8/8 PASS, Frontend 8/8 UI flows PASS. Validados: create con solo phone / solo email / validación frontend si ambos vacíos, delete admin-only (403/404/409/200), transfer end-to-end, bitácora sin "Invalid Date".

## Rediseño Módulo de Seguridad y Perfiles de Acceso (Feb-2026, iter 181)

**Estructura jerárquica**: Nivel 1 (Grupos de menú con toggle Activo/Inactivo) → Nivel 2 (Submódulos con 3 estados: Inactivo/Consulta/Edición Total) → Funciones Especiales (checkboxes que rompen la restricción de Consulta).

**Backend** (`/app/backend/permissions_catalog.py` — fuente única de verdad):
- 7 grupos de menú: dashboard, gestion_comercial, catalogos, gestion_implementacion, nuevos_productos, gestion_administrativa, gestion_taller.
- 16 módulos con mapeo a grupo padre. Niveles: `none/read/edit` → UI labels `Inactivo/Consulta/Edición Total`.
- 7 flags especiales: `proyectos:create`, `cotizaciones:{impl_pyme, impl_corp, equipos, reparaciones}`, `inventarios:create_warehouse`, `integradores:create`.
- 4 acciones admin-only hardcoded: `integradores:bulk_delete`, `integradores:import`, `proyectos:delete`, `taller_equipos:delete`.
- Endpoints nuevos: `GET /api/admin/permission-catalog`, `PUT /api/admin/users/{id}/menu-groups`. Extendido `PUT /permissions` y `PUT /special-permissions` para validar contra catálogo.
- Auto-migración en login + /auth/me: usuarios legacy sin `menu_groups` reciben todos los 7 grupos en `True`.
- Enforcement admin-only: agregado a `POST /api/integrators/import` (gap pre-existente). Los 3 DELETE restantes ya validaban admin.

**Frontend**:
- `hooks/usePermission.js` extendido: `hasSpecial(flag)`, `isGroupActive(groupId)`, `MODULE_TO_GROUP`. `canView/canEdit/canCreate` respetan grupo padre activo.
- `components/Sidebar.jsx`: cada ítem con `groupId`; si el grupo está inactivo, todo el grupo desaparece del menú.
- `pages/AdminUsers.jsx` (REESCRITO): vista por usuario (panel izq con lista + panel der con detalle). Atributos Rol/Estado/Almacén/Supervisor en grid 4-col. Acordeón por grupo con toggle Activo/Inactivo (banner amarillo informativo si usuario es Admin). Cada módulo con radio Inactivo/Consulta/Edición Total + checkboxes de Funciones Especiales agrupados bajo su módulo. Al desactivar un grupo, módulos hijos se ven opacos + badge "Grupo inactivo" + pointer-events-none.
- Integradores: botón `Importar` ahora admin-only. `Nuevo Proyecto de Integración` respeta flag `proyectos:create` como override de Consulta.
- Inventario: botón `Nuevo Almacén` respeta flag `inventarios:create_warehouse` como override.
- Cotizaciones: los 4 flags de tipo de cotización ya estaban aplicados (iter previa).

**Tests** (iteration_181): Backend 12/12 PASS, Frontend 13/14 OK (1 bug visual de opacidad corregido por main agent). Validado: catálogo, persistencia menu_groups, filtrado de flags inválidos, auto-migración en login, admin enforcement en `/integrators/import`, sidebar cascada, banners admin-only.

## Conversión Contacto Inicial → Prospecto: precarga primer contacto (Feb-2026, iter 182)

`POST /api/initial-contacts/{id}/convert` ahora precarga el primer `ContactCRM` del cliente nuevo con los datos del Contacto Inicial:
- `full_name` = `contact_name` del IC.
- `phone` = `phone` del IC.
- `email` = `email` del IC.
- `role` = "Administrativo" (default).
- `contact_id` autogenerado.
Si el IC no tenía ni teléfono ni email ni nombre, no se precarga ningún contacto. El frontend `Clients.jsx` ya consume `contacts[]` así que el primer contacto aparece listo para edición sin cambios adicionales. Validado por curl con IC con ambos campos y con sólo teléfono.

## Quotes: eliminada opción "Descargar PDF" del menú de acciones (Feb-2026, iter 182b)

Se removió el `DropdownMenuItem` "Descargar PDF" del menú ⋯ en `/app/frontend/src/components/quotes/QuotesTable.jsx` porque descargaba una versión desactualizada de la cotización. La función `downloadPDF()` y la prop `onDownloadPDF` fueron eliminadas de `Quotes.jsx`. El **PDF oficial se obtiene ahora exclusivamente desde el botón "Anexos"** de cada fila. Validado por screenshot: dropdown empieza con "Modificar (Nueva Versión)" y ya no expone el item con versión errada.


## P2 Refactor Backend — `quote_actions.py` (Feb-2026, iter 176)
Desglose del monolito `/app/backend/routes/quote_actions.py` (3060 → 2089 líneas, -31%).
Nuevos módulos:
- `routes/quote_helpers.py` (128 líneas): caché de plantillas, `get_email_template`, modelos `QuoteStatusUpdate`/`EmailSendRequest`, constantes `REGULAR_FLOW`/`STATUS_ORDER`, helpers `get_status_index`, `is_regularization`, `check_irregular_flow`, `log_audit_exception`, `mark_quote_irregular`.
- `routes/quote_transitions.py` (263 líneas): `_create_project_from_quote` — creación de proyecto + notificación a gerente de implementación al enviar a imple.
- `routes/quote_taller.py` (262 líneas, router independiente): `/repair-supplies`, `/taller-equipos` (GET/filtros), `/taller-equipos/{id}/historial`, `/taller-equipos/export-excel`, `DELETE /taller-equipos/{id}`.
- `routes/quote_serials.py` (429 líneas, router independiente): `/quotes/{id}/pinpad-models`, `/quotes/{id}/inventory-serials`, `/quotes/{id}/equipment-for-implementation`, `/inventory/{warehouse_id}/available-serials/{item_id}`, `/quotes/{id}/preassigned-serials`, `POST /quotes/{id}/preassign-serials`.

Routers registrados en `server.py`. Tests: iteration_176 → 27/27 backend PASS. Sin regresiones, helpers validados con 422 IRREGULAR en approve de Borrador.

## Gestión Granular de Seriales por Concepto en Cotizaciones de Reparaciones (Feb-2026, iter 182d)

**Backend** (`/app/backend/routes/quotes.py`):
- `EquipmentPDFItem` añade campo `serials: List[str] = []` (N:N con el pool `repair_models`).
- `POST /api/quotes/generate-equipment-pdf` renderiza chips de seriales (fuente monospace 9.5px, itálica, fondo naranja claro, borde naranja) debajo del nombre de cada concepto que tenga `serials`. Total en paréntesis.

**Frontend** (`/app/frontend/src/components/SerialsSelectorModal.jsx` — NUEVO):
- Modal reutilizable con buscador, agrupación por modelo con sticky header, contador `X/Y` (amber/emerald/red según estado), checkboxes con hard-limit (el checkbox restante se deshabilita con badge "límite alcanzado" al alcanzar la cantidad permitida).
- Botón `Guardar selección` queda disabled hasta que la cantidad de seriales = `requiredQty` (cantidad del concepto).
- Pool viene del padre — permite N:N entre conceptos sin bloqueo cruzado.

**Frontend** (`/app/frontend/src/components/EquipmentQuoteWizard.jsx`):
- Cada fila de la tabla de conceptos (paso 3) agrega un botón ListChecks con contador visual `X/Y` — emerald si está completo, orange si falta.
- Si el usuario reduce la cantidad del concepto, los seriales asociados se recortan automáticamente vía `slice(0, newQty)`.
- `serialsPool` derivado con `useMemo` de `repairModels` — aplana `[{serial, model_name, model_id}]`.

**Tests** (iteration_182): Backend 6/6 PASS (pytest en `/app/backend/tests/test_equipment_pdf_serials.py`) + Frontend 9/9 flows PASS. Validado: N:N (serial compartido entre 2 conceptos), hard-limit, buscador, preservación al reabrir, recorte por cambio de cantidad, PDF con chips.

## PDF Equipos/Reparación: encabezado fijo en todas las páginas (Feb-2026, iter 182e)

Usuario reportó que la página 2 de la cotización quedaba con bloques sueltos (Términos + Total) sin identificación. Se refactorizó el template en `/app/backend/routes/quotes.py` (`generate_equipment_quote_pdf`) usando CSS `position: running(page-header)` + `@page { @top-left { content: element(page-header); } }` con `margin-top: 200px`:
- El bloque con `logo + número de cotización + fecha + vence + badge de tipo + PREPARADO PARA (cliente/RIF/dirección) + EMITIDO POR` se renderiza ahora en cada página de la cotización.
- El **Anexo de Seriales** (página siguiente) se mantiene SIN encabezado según requisito del usuario.
- Validado con PDF multi-página (14 items): pág 1 ✅ header · pág 2 ✅ header · pág 3 ✅ anexo sin header. Análisis automático de imagen confirmó encabezado completo en la pág 2 (logo Mega Soft, COTIZACIÓN #, fechas, PREPARADO PARA con cliente + RIF + dirección completa, EMITIDO POR).

## Maestro de Perfiles + Techo de Permisos / Ceiling Rule (Feb-2026, iter 183)

**Arquitectura**: El perfil es una plantilla reutilizable que funciona como **techo máximo** de los permisos de cada usuario que lo tenga asignado. En la ficha del usuario solo se pueden reducir permisos — nunca elevarlos por encima del perfil. Admin role queda exento del ceiling.

**Backend**:
- `/app/backend/permissions_catalog.py`: helpers `LEVEL_RANK`, `level_within_ceiling`, `enforce_permissions/groups/specials_ceiling`.
- `/app/backend/routes/profiles.py` (NUEVO): CRUD completo. `POST /api/admin/profiles`, `PUT`, `DELETE` (409 si hay users vinculados), `POST /{id}/duplicate`, `PUT /api/admin/users/{id}/profile` (asigna y copia baseline). Al editar un perfil a la baja, re-sincroniza automáticamente todos los usuarios vinculados.
- `/app/backend/seed_profiles.py` (NUEVO): 4 perfiles semilla idempotentes — Vendedor Pyme, Vendedor Corp, Gerente Operativo, Operador Taller. Ejecutado en `startup`.
- `/app/backend/routes/auth.py`: añadido ceiling enforcement 403 en los 3 endpoints (`/permissions`, `/menu-groups`, `/special-permissions`) con mensajes específicos. `/auth/me` y login incluyen `profile_id`.

**Frontend**:
- `/app/frontend/src/pages/AdminProfiles.jsx` (NUEVO): misma paridad visual con AdminUsers. Panel izq lista + panel der acordeón. Botones Crear / Duplicar / Eliminar (con AlertDialog bloqueado si hay users vinculados).
- `/app/frontend/src/pages/AdminUsers.jsx`: selector "Perfil asignado (techo de permisos)" por usuario. Handler `handleProfileChange` → PUT `/profile` y patcheo local. `GroupCard` ahora recibe `profilePerms/profileGroups/profileSpecials` y renderiza:
  - Badge "Techo del perfil" junto al grupo si el perfil lo tiene inactivo.
  - Badge `Max: Edición/Consulta/Inactivo` junto a cada módulo.
  - `RadioGroupItem.disabled={optionBlocked}` + opacity + tooltip *"Acceso restringido: el nivel máximo para este perfil es [X]"*.
  - Checkboxes de funciones especiales disabled + etiqueta "no en perfil" cuando el perfil no las tiene.
- Ruta `/admin/profiles` registrada en App.js y en Sidebar bajo "Gestión de Seguridad → Perfiles de Usuario".

**Tests** (iteration_183): Backend 17/17 pytest PASS en `/app/backend/tests/test_iteration183_profiles_ceiling.py`. Frontend flows críticos PASS: crear/duplicar/eliminar perfil, asignar a user, badges de techo visibles, toggles/radios/checkboxes bloqueados por perfil. Una sugerencia LOW/cosmética ya implementada (disabled HTML nativo en Radix RadioGroupItem).

## Integradores: campo "Implementador" en plantilla y flujo de importación (Feb-2026, iter 183b)

`/app/backend/routes/integrators.py`:
- **Plantilla** (`GET /api/integrators/import/template`): nueva columna **"Implementador"** entre "Gestor" y "Categoria", con hoja de instrucciones explicando que el valor debe ser EXACTO al usuario en BD (nombre completo o email) y que vacío queda por asignar.
- **Export** (`GET /api/integrators/export`): incluye columna Implementador para round-trip.
- **Import** (`POST /api/integrators/import`):
  - Nuevo mapping de columna `Implementador/implementer/implementador_asignado → implementador`.
  - Pre-carga `user_lookup {nombre_lower | email_lower → {user_id, display}}` para validación.
  - Si el valor coincide exactamente con un usuario activo (nombre completo o email) → `implementador=display` + `implementador_user_id=user_id`.
  - Si está vacío → queda `None` (por asignar, se setea luego vía UI o endpoint `assign-implementador`).
  - Si el nombre NO coincide → reporta error específico en `row_errors` pero el integrador se crea con `implementador=None` (por asignar), alineado al requisito del usuario.
- Validado por curl: 3 casos (válido/vacío/inválido) todos ejecutados correctamente.

## Integradores: campo "Nro de Ticket" (iter 183c)

- Modelo `Integrator` e `IntegratorCreate` extendidos con `ticket_number: Optional[str]`.
- **Plantilla import/export**: columna **"Nro de Ticket"** añadida entre Implementador y Categoría.
- **Import**: mapping acepta `Nro de Ticket / ticket / Ticket / Numero de Ticket / nro_de_ticket / nro_ticket`. Texto libre, sin validación.
- **Frontend Integrators.jsx**: campo editable junto a Correo de Contacto en el diálogo Crear/Editar (`data-testid=integrator-ticket-input`). `formData.ticket_number` incluido en `resetForm` y `openEdit`.
- Validado por curl: plantilla contiene la columna, import persiste valor `TKT-00999`, PUT /integrators/{id} actualiza a `TKT-UPDATED-001`.

## Integradores: Reestructura de BD - Plantilla oficial A-AE con 19 productos (iter 183d)

**Solicitud del usuario**: alinear plantilla de importación y BD de Integradores con el archivo `Estructura de BD Integradores.xlsx` entregado. Restricción: NO tocar `db.services` (para evitar afectar Medios de Pago).

**Backend** (`/app/backend/routes/integrators.py`):
- Constante hardcoded `INTEGRATOR_PRODUCTS` con los **19 productos oficiales** (M-AE) + `INTEGRATOR_PRODUCT_IDS` + name→id map case-insensitive. Totalmente desacoplado de `db.services`.
- Reemplazadas las 4 lecturas previas a `db.services.find(...)` por la constante hardcoded (no hay acoplamiento con Medios de Pago).
- **Plantilla** (`GET /import/template`) ahora renderiza 31 columnas A-AE exactas: A-L (Nombre, Tipo, Aplicativo, Modalidad de Integración, Estatus, Tipo de Integracion, Gestor Administrativo, Implementador, Nro Ticket, Categoría, Último contacto con el Cliente, Correo) + M-AE (TDD/TDC, TDC/TDD (excepto maestro), Verificación P2C, C2P, Cryptobuyer/Criptomoneda, Biopago, Cambio P2C, Verificación Pago Zelle, Credito Inmediato/Verificación Transferencia, Debito Inmediato, Cambio Credito Inmediato/Cambio Transferencia, Deposito/Verificación Depósito, Cambio Cards, Consulta Cards, Cambio de Pin, Banplus Pay, CASHEA, Xcapit, Crixto).
- **Export** (`GET /export/excel`) emite las mismas 31 columnas en el orden canónico.
- **Import** acepta los nuevos headers (incluye alias típicos: "Modalidad de Integración", "Gestor Administrativo" con/sin typo legado "Adminisitrativo", "Último contacto con el Cliente", etc.).
- **Migración one-shot** `migrate_integrator_certifications_if_needed()` ejecutada en startup: resetea `certifications` de TODOS los integradores existentes al nuevo schema (19 keys = N/A). Idempotente vía flag `_migrations/integrator_cert_reset_v1`.

**Validado por curl** (iter 183d):
- Template: 31 columnas exactas ✅
- Export: 31 columnas, misma forma que template ✅
- Import de CSV con 31 columnas: 1 creado, 0 errores, certs persistidas (Crixto=N/A, CASHEA=P, TDD/TDC=C, VerifP2C=N/A) ✅
- Todos los integradores pre-existentes migrados a certs N/A con 19 keys nuevas ✅

**NO tocado**: `db.services`, módulo de Medios de Pago, modelos, frontend de Integrators.jsx (la UI de certificaciones se adapta automáticamente porque lee `certifications` dinámicamente del integrador).


## Integradores: Vaciar BD con flujo de 2 pasos + cascada opcional (iter 184)

**Solicitud del usuario**: (1) Borrar todo lo que no tenga cotizaciones, (2) preguntar si desea forzar borrado cascada para los que sí tienen, (3) corregir latencia del input "BORRAR TODO".

**Backend** (`/app/backend/routes/integrators.py` — `DELETE /integrators/bulk/all`):
- Nuevo parámetro `force_cascade: bool = False`.
- Modo **seguro** (default): borra sólo integradores sin referencias en `quotes`/`projects`, y devuelve `protected: [{integrator_id, name, quotes_count, projects_count}]` para que el frontend presente el paso 2.
- Modo **cascade**: elimina también todas las cotizaciones y proyectos referenciados, y después borra todos los integradores. Registra en `integrators_bulk_deletions` con `mode`, `quotes_deleted`, `projects_deleted`.
- Solo admin.

**Frontend** (`/app/frontend/src/components/PurgeIntegratorsDialog.jsx` — NUEVO, `memo`izado):
- Extraído del monolito `Integrators.jsx` (~1700 líneas) → fix latencia del input (cada onChange ya no re-renderiza toda la tabla, sólo el diálogo).
- Paso 1: confirmar con `BORRAR TODO`. Llama a `/integrators/bulk/all`.
- Paso 2 (solo si la respuesta trae `protected.length > 0`): muestra lista con asociaciones, pide escribir `FORZAR CASCADA`, llama a `/integrators/bulk/all?force_cascade=true`. Alternativa: botón "Conservar y cerrar".

**Validado E2E con Playwright**: 3 integradores (Norkut, HL Sistemas, Corp XETUX) con 4 cotizaciones → Paso 1 ofreció cascada → Paso 2 eliminó 3 integradores + 4 cotizaciones + 0 proyectos → tabla vacía. Latencia de input imperceptible (~90 ms/char, incluye overhead de Playwright).


## Integradores: Stats reactivas + label visible en filtros (iter 184b)

**Solicitud del usuario**: (1) las tarjetas de totales (Total, Certificados, En Ejecución, Sin Implementador, Suspendidos) deben reflejar el filtrado activo; (2) en el trigger de cada Select debe verse siempre el nombre del campo.

**Frontend** (`/app/frontend/src/pages/Integrators.jsx`):
- Stats ahora se calculan sobre `filteredIntegrators` (backend `filterStatus`/`filterType` + client-side `filterIntType`/`filterModality`/`filterGestor`/`searchTerm`).
- Cada `SelectTrigger` rendea un `<span>` con el label (`TIPO INT.:`, `ESTATUS:`, `TIPO:`, `MODALIDAD:`, `GESTOR:`) en mayúsculas pequeñas seguido de `SelectValue`. Anchos ampliados para acomodar label + valor.

**Validado E2E**: sin filtros 267/234/0/42/32 → Estatus=Certificado 234/234/0/27/0 → +Modalidad=REST 116/116/0/15/0 → Limpiar 267.

## Integradores: Fix filtro Gestor (iter 184c)

**Bug**: el dropdown "Gestor" se poblaba desde `/auth/users` (todos los usuarios activos — mezcla de Gestores, Implementadores, Ejecutivos) con `full_name` canónico ("Rafael González" con tilde). Pero los integradores en BD guardan `gestor="Rafael Gonzalez"` (sin tilde) → el match `intg.gestor !== filterGestor` devolvía 0 de 121 para Rafael.

**Fix** (`Integrators.jsx`): el filtro ahora se popula con `Array.from(new Set(integrators.map(i => i.gestor))).sort()`. Sólo aparecen los 5 gestores reales con integradores asignados, y los valores coinciden exactamente con la BD (match 100%).

**Validado E2E**: `Gestor=Rafael Gonzalez` → Total: 121, Certificados: 107, Sin Implementador: 9, Suspendidos: 14.

## Notificaciones a Contactos Iniciales (iter 185)

**Solicitud del usuario**: agregar el botón "Enviar Notificación" (similar al de Clientes) en las acciones de Contacto Inicial, tanto en el Dashboard como en la pantalla principal.

**Backend** (`/app/backend/routes/initial_contact_communications.py` — NUEVO):
- `POST /api/initial-contacts/{contact_id}/send-email` (multipart: recipients JSON, subject, message, internal_doc_ids JSON, files[]). Envía por SMTP, registra en `initial_contacts.bitacora` con `action='notification'` y `email_data` (subject, recipients, attachments, sent_by, sent_at). Reutiliza biblioteca `client_documents` para adjuntos internos.
- `POST /api/initial-contacts/{contact_id}/preview-email` → resuelve variables `{{contacto}}`, `{{razon_social}}`, `{{email}}`, `{{telefono}}`, `{{referido_por}}`, `{{asignado_a}}`, `{{aspectos_interes}}`, `{{empresa}}`, `{{nombre}}`.
- Router registrado en `server.py`.

**Frontend**:
- `/app/frontend/src/components/InitialContactEmailDialog.jsx` (NUEVO): diálogo de 2 columnas con plantillas (fallback `context=CLIENTES` si no hay `INITIAL_CONTACTS`), variables contextuales, vista previa, adjuntos externos e internos.
- `InitialContacts.jsx` y `Dashboard.jsx`: ícono `Send` (indigo) entre "Convertir a Prospecto" y "Ver Bitácora". `data-testid=notify-btn-{id}` / `dash-notify-btn-{id}`.

**Validado E2E con curl + Playwright**: `POST send-email` → SMTP envía (email_log_id generado) → bitácora registra `notification` con detalle `[Email] <subject> → <recipients>`. Preview muestra correctamente "Hola Juan Pérez Test" / "Test Notif Corp".


## Modal de Seriales: Selección Masiva + "Sin Serial" (iter 186)

**Solicitud del usuario**: optimizar la ventana de selección de seriales en cotizaciones de Reparación con (1) botón "Seleccionar todos" sincronizado con `quantity` y (2) opción "Sin Serial" para conceptos administrativos/logísticos (Casillero, Envío, Seguros, etc.).

**Backend** (`/app/backend/routes/quotes.py`):
- `EquipmentPDFItem` model: nuevo flag `no_serial: bool = False`.
- `generate-equipment-pdf`: si `item.no_serial=True`, en lugar de la lista de chips se renderiza una etiqueta sutil `Sin serial · concepto administrativo/logístico`. Si `False`, comportamiento original (chips de seriales).

**Frontend** (`/app/frontend/src/components/SerialsSelectorModal.jsx`):
- Toolbar superior con:
  - Switch "Sin Serial — concepto administrativo/logístico" (deshabilita lista, búsqueda y permite guardar sin selección).
  - Botón "Seleccionar todos" que marca hasta `requiredQty` de los visibles (filtrados); si hay más visibles que la cantidad, muestra warning y respeta el límite.
  - Botón "Limpiar".
  - Contador `n / requiredQty` o `Sin serial`.
- `onSave(serials, noSerial)` para que el wizard persista ambos valores.
- `(EquipmentQuoteWizard.jsx)`: `saveItemSerials(serials, noSerial)` setea `item.no_serial`. `openSerialsModal` permite abrir aunque el pool esté vacío si el item ya está marcado `no_serial`. Etiqueta del botón cambia a "Sin serial" en verde cuando aplica.

**Validado por curl**: PDF generado con 3 ítems (1 con 2 seriales + 2 con `no_serial=true`) → "Limpieza General" muestra `Seriales (2): SN-1001 SN-1002`; "Casillero (logístico)" y "Servicio de Envío" muestran `Sin serial · concepto administrativo/logístico` sin chips. Lint frontend OK.



## Refactor Quotes.jsx — Fase 1 (iter 187)

**Solicitud del usuario**: ejecutar Fase 1 del refactor del monolito `Quotes.jsx` (3299 líneas) sin afectar funcionalidad.

**Extracciones**:
- `/app/frontend/src/hooks/useQuoteFilters.js` (NUEVO, 33 líneas): centraliza los 6 filtros rápidos + helper `clearFilters`.
- `/app/frontend/src/hooks/useQuoteRbac.js` (NUEVO, 38 líneas): calcula flags RBAC (impl_pyme/corp/equipos/reparaciones) y filtra `quotes` según permisos especiales.
- `/app/frontend/src/components/quotes/NewQuoteButtons.jsx` (NUEVO, 75 líneas): barra de 3 botones (Implementaciones con dropdown PYME/CORP, Equipos y Accesorios, Reparaciones), visibilidad por rbac.
- `/app/frontend/src/components/quotes/IrregularQuotesBanner.jsx` (NUEVO, 24 líneas): banner naranja con conteo de cotizaciones irregulares.

**Resultado**: `Quotes.jsx` 3299 → 3220 líneas (-79, -2.4%). Lint OK. E2E con Playwright: los 3 botones, dropdown PYME/CORP, banner irregular, filtros y tabla con 15 filas funcionan sin errores en consola.

**Hidratación**: warnings reportados los inyecta el script `emergent-main.js` de Visual Edits (Emergent), sólo activo en preview iframe. NO requiere fix en código de la app.

## Módulo Reportes de Ventas (iter 188)

**Solicitud del usuario**: implementar 3 reportes ejecutivos: Embudo de cotizaciones, Aging y Ventas mensuales.

**Backend** (`/app/backend/routes/sales_reports.py` — NUEVO):
- `GET /api/reports/sales/funnel?date_from&date_to&segment&category`: conteo y monto cumulativo por etapa (Enviada→Aprobada→Facturada→Pagada→Entregada) usando timestamps `sent_to_client_at`, `approved_at`, `invoiced_at`, `paid_at`, `delivered_at`. Calcula conversión Enviada→Pagada y Enviada→Entregada.
- `GET /api/reports/sales/aging?segment&category`: cotizaciones no finalizadas (no Entregada y no archivadas) con días en estado actual. Buckets 0-7, 8-15, 16-30, >30 días. Resuelve gestor desde `users.created_by_user_id`.
- `GET /api/reports/sales/monthly?year&category&segment`: arreglo de 12 meses con cotizado/facturado/cobrado por `created_at`/`invoiced_at`/`paid_at`.

**Frontend** (`/app/frontend/src/pages/SalesReports.jsx` — NUEVO, ruta `/reports/sales`):
- 3 Tabs (Embudo / Aging / Mensual) con filtros compartidos (segmento, categoría, fechas, año).
- Recharts: BarChart horizontal para embudo, ComposedChart (bars + line) para mensual.
- KPIs por reporte, tabla detalle, export CSV en Aging y Mensual.
- Nuevo link en `Sidebar.jsx` → "Reportes de Ventas" (ícono BarChart3) bajo "Gestión Comercial".

**Validado E2E**: backend con curl (Funnel 19 quotes, Aging 3 rows, Monthly Apr 2026 totales correctos). Frontend con Playwright: los 3 tabs cargan con sus visualizaciones, filtro Categoría=Reparaciones reduce Cotizado de $15.313,16 a $5.998,36 correctamente.



## Reportes de Ventas — Fase 2 (iter 189)

**Solicitud del usuario**: implementar los 5 reportes adicionales propuestos.

**Backend** (`routes/sales_reports.py`, +5 endpoints):
- `GET /reports/sales/receivables`: cuentas por cobrar con buckets 0-30/31-60/61-90/>90 y top deudores agregados.
- `GET /reports/sales/clients-ranking?year&top_n`: ranking por monto cotizado con tendencia trimestral (NUEVO si no hay datos previos).
- `GET /reports/sales/repair-productivity`: lead times Enviada→Reparada y Reparada→Entregada por implementador. SLA breach (>7 días).
- `GET /reports/sales/stock-vs-demand?months_back`: cruza `inventory_movements` con `equipment_items`. Calcula demanda mensual, cobertura, semáforo crítico/alerta/ok.
- `GET /reports/sales/leads-funnel`: conversión global de `initial_contacts.is_converted` y por `referred_by`.

**Frontend** (`SalesReports.jsx`, +5 tabs): TabsList ahora con flex-wrap. Recharts PieChart en Leads. Export CSV en cada vista. Cards con badges de status.

**Validado E2E**: curl + Playwright. Por Cobrar $9.303 / 2 facturas. Stock 9 críticos. Leads 83.33% conversión. Lint OK.


## Resumen Ejecutivo PDF (iter 190)

**Solicitud del usuario**: botón único que genera un PDF con resumen de los 8 reportes para envío a gerencia.

**Backend** (`routes/sales_reports.py`):
- `GET /reports/sales/executive-summary?year&segment&category&date_from&date_to`: ejecuta los 8 reportes internamente, ensambla HTML con KPIs + top 5 de cada uno y renderiza con WeasyPrint. Retorna `StreamingResponse application/pdf` con `Content-Disposition: attachment`. Layout 1 página A4 ~32 KB.

**Frontend** (`SalesReports.jsx`): botón "Resumen Ejecutivo PDF" (negro, FileText) junto a "Actualizar". Llama con filtros activos, descarga blob.

**Validado E2E**: curl + Playwright. PDF 31907 bytes con secciones Embudo/Aging/Mensual/Por Cobrar/Top Deudores/Top Clientes/Productividad/Stock/Leads.

## Refactor Fase 2 — ProjectDetail.jsx (iter 191)

**Solicitud del usuario**: ejecutar Fase 2 del refactor del monolito `ProjectDetail.jsx` (2278 líneas).

**Extracciones**:
- `/app/frontend/src/components/projects/projectConstants.js` (NUEVO, 20 líneas): `PHASES`, `STORE_PHASES`, `PHASE_COLORS`, `ALL_TOKENS` compartidos.
- `/app/frontend/src/components/projects/TemplateBodyEditor.jsx` (NUEVO, 108 líneas): editor con resaltado de tokens y autocompletado vía `{`. Aislado para evitar re-renders del monolito.
- `/app/frontend/src/components/projects/BatchUpdateModal.jsx` (NUEVO, 158 líneas): diálogo de Actualización Masiva (fase + banco + producto + tiendas + motivo). Recibe estado y handlers controlados por el padre.

**Resultado**: `ProjectDetail.jsx` 2278 → 2069 líneas (-209, -9.2%). Lint OK. Smoke test: detail carga con header, datos del proyecto, matriz de implementación, BatchUpdateModal abre con 5 tiendas y selects funcionales. 0 errores nuevos en consola.


## Refactor Fase 3 — ProjectDetail.jsx (iter 192)

**Solicitud del usuario**: completar el refactor de `ProjectDetail.jsx` extrayendo los 3 diálogos restantes.

**Extracciones**:
- `/app/frontend/src/components/projects/EmailDetailViewer.jsx` (NUEVO, 47 líneas): visualizador read-only del detalle de un correo enviado.
- `/app/frontend/src/components/projects/TemplatesAdminDialog.jsx` (NUEVO, 167 líneas): CRUD de plantillas con layout 3-cols (lista | form | diccionario de variables agrupadas por Cliente/Proyecto/Infraestructura/Hardware).
- `/app/frontend/src/components/projects/EmailPreviewDialog.jsx` (NUEVO, 142 líneas): editor final del correo antes de enviar (asunto + contentEditable HTML, insertar variables, paste imágenes).

**Resultado**: `ProjectDetail.jsx` 2069 → 1833 líneas (-236, total 2 fases -445/-19.5% del original). Lint OK. Smoke test: el TemplatesAdminDialog abre correctamente con plantillas existentes, formulario y panel de variables. Sin errores nuevos en consola.



## Acciones Dinámicas — Migración a `allowed_user_ids` (iter 193, Feb 2026)

**Solicitud del usuario**: en las Acciones Custom y Overrides del flujo de cotizaciones, reemplazar el input de "Cargos permitidos" (texto libre) por un **selector múltiple de Usuarios específicos**. También asegurar que las Custom Actions aparezcan en el catálogo del Motor de Notificaciones para poder asignarles plantillas.

**Backend** (pre-migrado en fork anterior):
- `ActionOverride` y `CustomAction` aceptan `allowed_user_ids: List[str]`.
- `dispatch_custom_action` valida con `allowed_user_ids` (admin siempre OK, user_id debe estar en lista).
- `/api/action-notifications/catalog` inyecta las custom actions en `allowed_actions_by_biz_sub` y `actions[]` para que se puedan configurar plantillas en la Matriz.

**Frontend** (completado en esta iteración):
- Nuevo componente `UserMultiSelect` en `ActionNotificationsConfig.jsx`: popover con búsqueda y checkboxes por usuario (label, cargo/departamento visible).
- `OverrideRow` y `CustomActionDialog` ahora usan `UserMultiSelect` y envían `allowed_user_ids` (no `required_cargos`).
- Tabla de Custom Actions muestra columna **"Usuarios"** con nombres resueltos (o "Todos" si vacío).
- `QuotesTable.jsx` filtra overrides y custom actions por `currentUserId` contra `allowed_user_ids` (con fallback legacy a `required_cargos` si está vacío).
- `Quotes.jsx` pasa `currentUserId={currentUser?.user_id}` a `QuotesTable`.

**Validado**: Testing agent iter1 — backend 7/7 pytest (persistencia, catalog, dispatch con 403 a no autorizados) y frontend 100% (UserMultiSelect con 24 usuarios, data-testids verificados, columna "Usuarios" renderizando correctamente).


## Bugfix — `position_after` de Custom Actions ahora respetado (Feb 2026)

**Reportado**: user capturó screenshot donde "Validar Pago" (custom action `valida_pago`, `position_after=collect`) siempre aparecía en una sección "PERSONALIZADAS" al final del dropdown, ignorando el anclaje.

**Fix** (`QuotesTable.jsx`):
- Nueva función `getCustomActionsByAnchor(quote)` que agrupa las custom actions por su `position_after` (o `__end__` si no se especifica).
- Nueva función `renderAnchoredCustomActions(quote, anchorId, byAnchor)` que emite los `DropdownMenuItem` de las custom actions ancladas a un legacy action_id.
- El render invoca `renderAnchoredCustomActions` inmediatamente después de cada acción legacy (`send_to_client`, `approve`, `repair_complete`, `invoice`, `collect`, `deliver`, `send_to_implementation`). Las actions sin ancla siguen apareciendo al final bajo el encabezado "Personalizadas".

**Verificado**: orden del menú PYME/VPOS → `Enviar al Cliente → Aprobación → Factura → Registrar Pago → **Validar Pago** → Enviar a Implementación → Eliminar`.


## Bugfix — Restaurar Anexos en producción (Feb 2026)

**Reportado**: en deploy, el respaldo (ZIP de ~68 MB) se generaba bien con "Contingencia · Migración Cotizaciones (Streaming)", pero al **importarlo** en el modal "Migración BD" → "Restaurar anexos", el toast mostraba "Error al restaurar anexos" sin mensaje específico.

**Root cause**: el endpoint legacy `POST /admin/quotes-bundle-migration/import-attachments` recibe el ZIP completo en una sola request (`await file.read()` lo carga en RAM). El ingress de Kubernetes (nginx) suele rechazar bodies > 1 MB con 413, y el frontend solo mostraba el genérico "Error al restaurar anexos".

**Fix** (mismo patrón que el download paginado de `ContingencyAttachmentsExport.jsx`):
- **Backend** (`/app/backend/routes/data_migration.py`): nuevo endpoint `POST /admin/quotes-bundle-migration/import-attachment` que recibe un solo archivo + `path` (form). Valida path traversal, descarta `manifest.json`, y guarda con `save_pdf_dual` (FS local + Object Storage). El endpoint legacy en bloque permanece como fallback.
- **Frontend** (`QuotesBundleMigrationModal.jsx`): `handleImportAttachments` ahora descomprime el ZIP **en el navegador** con JSZip y sube cada archivo individualmente (request pequeña <2 MB típicamente). Botón muestra progreso `Subiendo X/N · ruta...`.

**Verificado E2E**: ZIP creado con 2 archivos + manifest → endpoint reporta `restored=2 skipped=1 errors=[]`, archivos físicamente presentes en `UPLOADS_DIR`.


## Bugfix — PDF Cálculos Definitivos en MPOS Imple+POS (Fast Track) (Feb 2026)

**Reportado**: en cotizaciones MPOS (Imple + POS) — `quote_category="fast_track"` —, al ejecutar la acción **Aprobado**: (1) el PDF "Cálculos Definitivos" no se anexa al correo, y (2) el PDF debería mostrar **dos secciones** (Implementación y Pinpads) porque la cotización es mixta.

**Root cause**:
- En `quote_actions.py::approve_quote`, la generación del PDF estaba dentro de `if not is_fast_track and not is_repair:`, excluyendo fast_track.
- En `ApprovalBillingModal.jsx`, los `consolidated_items` para fast_track caían en la rama "Implementación" usando solo `services` (los Pinpads de `ft_equipment_items` quedaban fuera).
- En `billing_pdf.py`, la tabla no soportaba sub-headers de sección.

**Fix aplicado**:
- **`quote_actions.py`**: la generación del billing PDF ahora aplica para `not is_repair` (incluye fast_track). Para el flujo legacy fast_track se anexa al `extra_attachments` del `send_workflow_notification` junto con el PDF de la cotización.
- **`ApprovalBillingModal.jsx`**: para `quote_category === 'fast_track'`, el consolidado emite items con `section: 'Implementación'` (de `services` no recurrentes) **y** `section: 'Pinpads'` (de `ft_equipment_items`). El payload incluye `section` en cada item.
- **`billing_pdf.py`**: si algún item trae `section`, el render agrupa visualmente por sección con sub-headers (fondo `#dfe6ec`, span horizontal). Los índices de Subtotal/IVA/Total se recalculan dinámicamente con `last_body_idx = len(table_data) - 1` para no descuadrarse cuando hay sub-headers.

**Verificado**: PDF generado con dos secciones (Implementación + Pinpads), subtotal, IVA y total general correctos. Análisis con AI confirmó: "secciones bien diferenciadas, orden lógico (Implementación → Pinpads), subtotal/IVA/TOTAL presentes y correctos".


## Bugfix iter2 — Cálculos Definitivos: facturas separadas para MPOS Imple+POS (Feb 2026)

**Solicitud del usuario**: en cotizaciones MPOS Imple+POS, los costos de Implementación y de Equipo (Pinpads) NO deben mezclarse. Cada sección debe mostrar su propio IVA y Total como facturas independientes.

**Fix** (`backend/services/billing_pdf.py`):
- Refactor del render: helper interno `_build_invoice_table(items, subtotal_label)` que produce una mini-factura completa (header + items + Subtotal + IVA + TOTAL).
- Si los items vienen con campo `section`, se renderiza **una mini-factura por sección** (ej. "Factura 1: Implementación", "Factura 2: Pinpads"), cada una con su propio Subtotal/IVA/TOTAL calculados desde sus propios items. NO se emite total combinado.
- Se añade nota al pie aclarando que cada sección se factura por separado.
- El comportamiento legacy (sin secciones) se preserva exacto, usando los totales pre-calculados del frontend.

**Verificado E2E**: PDF de prueba con 2 secciones (Implementación: $600 sub / $96 IVA / $696 total; Pinpads: $2,100 sub / $336 IVA / $2,436 total) → AI analyzer confirmó valores exactos, separación independiente, ausencia de total combinado.


## Bugfix Trio — Flujo MPOS Imple+POS (Feb 2026)

Tres fallas reportadas: (1) "Marcar como Configurada" no aparece activa pese a config OK; (2) círculo de estado de Preasignación invisible; (3) correo de preasignación no se despacha pese a inventario OK.

**Causa raíz**:
1. El botón "Marcar como Configurada" en `QuotesTable.jsx` no aplicaba `getActionMeta()` → ignoraba overrides del catálogo de acciones (no respetaba `custom_label` ni `allowed_user_ids`).
2. El stepper `QuoteStatusStepper.fast_track` no tenía paso 'Preasignada' — la fase no era visible.
3. `quote_serials.preassign_serials` defaulteaba a `operaciones@sede.local` (dominio inexistente) cuando `emails_by_sede.<SEDE>.operations` faltaba, y el response no informaba si el correo había fallado: el toast de éxito ocultaba el problema.

**Fixes aplicados**:
- **`QuoteStatusStepper.jsx`**: agregado paso `Preasignada` entre `Aprobada` y `Configurada` en flow `fast_track` (`ts: 'preassigned_at'`). `getStepStates` ahora marca como completed cualquier step con timestamp aunque el `quote_status` no haya avanzado por él (caso típico de fases laterales).
- **`QuotesTable.jsx`**: la acción "Marcar como Configurada" ahora pasa por `getActionMeta(quote, 'configure', defaultLabel)` — respeta hidden/disabled/custom_label/allowed_user_ids del override. Mantiene la regla de `Requiere seriales` cuando no hay preasignación.
- **`quote_serials.py::preassign_serials`**:
  - Cadena de fallback robusta para destinatarios: `operations` sede → `admin` sede → email del **creador de la cotización** → email del **ejecutante**. Nunca cae a dominio inexistente.
  - Respuesta enriquecida: `email_sent: bool`, `email_error: str|null`, `email_recipients: list`. Logging explícito por cada decisión.
- **`PreassignSerialsModal.jsx`**: muestra toast secundario diferenciado (warning si `email_sent=false` con `email_error`, info con destinatarios cuando se envió).

**Verificado**: smoke screenshot confirmó stepper con 7 pasos (Enviada→Aprobada→Preasign.→Config.→Factura→Pagada→Entregada), botón "Marcar como Configurada" presente con indicador "Requiere seriales", y "Preasignación de Seriales" con bullet azul (pendiente). Lint OK en los 4 archivos.


## Bugfix follow-up — Causa real del Trio MPOS (Feb 2026)

Tras prueba en preview, los 3 puntos seguían fallando. Causa raíz adicional encontrada:

**1) `Quote` model no incluía `preassigned_serials`/`preassigned_at`** → como `GET /api/quotes` usa `response_model=List[Quote]`, Pydantic strippeaba los campos del response. El frontend recibía `preassigned_serials: undefined`, así que:
- El stepper no podía marcar `Preasignada` como completed.
- "Marcar como Configurada" calculaba `hasPreassigned=false` y quedaba disabled con "Requiere seriales".

**Fix `models.py`**: agregados al modelo `Quote`:
- `preassigned_serials: Optional[List[str]] = None`
- `preassigned_at: Optional[datetime] = None`
- `preassigned_warehouse_id: Optional[str] = None`

**2) Correo de Preasignación NO respetaba "Configuración de Notificaciones"** → el envío legacy hardcoded a Operaciones ignoraba completamente lo que el admin configurara en `/settings/action-notifications` para la acción `preassign_serials` (incluso cuando el admin asignó destinatario tipo Cliente).

**Fix `quote_serials.py::preassign_serials`**: ahora llama PRIMERO al motor dinámico `notification_engine.try_dispatch(action_id="preassign_serials", quote, current_user, extra_template_vars={Lista_Seriales, Modelo_Equipo, ...})`. Si el catálogo tiene config para esa combinación (biz/sub/action), el motor despacha respetando plantilla y destinatarios (Cliente, Usuarios, etc). Solo si NO hay config cae al fallback legacy a Operaciones (con la cadena de fallback robusta del fix anterior). El response incluye `dispatched_by: "engine"|"legacy"` para observabilidad.

**Verificado E2E**:
- `GET /api/quotes` ahora devuelve `preassigned_serials: [...]` y `preassigned_at: ...` (2 cotizaciones de prueba con datos reales).
- Stepper de COT-2026-05-054-PYME muestra `Preasignada` como **completed** (verde con check).
- Dropdown "Marcar como Configurada" ahora aparece **habilitada** con bullet siguiente-paso, sin "Requiere seriales".


## Bugfix Quad — MPOS Imple+POS + Motor + UX (Feb 2026)

Tras pruebas en preview, 4 fallas reportadas. **TODAS corregidas**:

**1) "Correo de Operaciones" en Configuración → Sede PYME no persistía**
Causa: `routes/settings.py` GET normalizaba `emails_by_sede` sin incluir `operations` — el valor sí se guardaba en BD, pero el siguiente GET retornaba `operations: ""` y la UI lo mostraba vacío (efecto "se borró al guardar").
Fix: agregada normalización de `operations` (con fallback a `operations_email` legacy del config plano para PYME).

**2) Acción Preasignación NO usaba "Configuración de Notificaciones"**
Causa raíz: `notification_engine._quote_to_biz_sub()` mapeaba SOLO `quote_category` ∈ {implementation, equipment, repair} a (biz, sub). Para cotizaciones MPOS Imple+POS — categoría `fast_track` — retornaba `(None, None)`, por lo que `try_dispatch` salía inmediatamente y el flujo caía SIEMPRE al legacy a Operaciones, ignorando la matriz del catálogo (donde están bajo "Implementaciones Pyme · MPOS Imple+POS").
Fix: agregado caso `fast_track` → `(implementacion_pyme|corp, mpos_imple_pos)` según `sede`. Validado: config con key `implementacion_pyme|mpos_imple_pos|preassign_serials` (2 destinatarios: user + cliente) ahora es encontrada.

**3) Modal "Personalizar Comunicación" no aparecía para Preasignación**
Causa: `PreassignSerialsModal` solo manejaba selección de seriales, no había UI para mensaje/CC. El backend tampoco recibía esos campos.
Fix: añadida sección **"Personalizar Comunicación"** en el modal con mensaje personalizado (300 chars) y chips de CC. Backend recibe `custom_message` y `cc_emails` y los pasa a `try_dispatch` para que el motor los aplique sobre la plantilla configurada.

**4) Stepper: ícono de Aprobada no se actualizaba al ejecutar Preasignación**
Causa: `getStepStates` marcaba el step `current` (donde está `quote_status`) como `'current'` (círculo bordeado con número), no como completed, aunque ya tuviera `approved_at`. Resultado visual: Enviada ✓ - Aprobada "2" - Preasign ✓ - …
Fix: regla simplificada — **si el step tiene su timestamp, es completed** (independiente del current_status). El estado `current` solo aplica si NO hay timestamp todavía.

**5) Modelo Quote no exponía preassigned fields**
(Fix previo, pero relevante al combo): agregados `preassigned_serials`, `preassigned_at`, `preassigned_warehouse_id` al modelo Pydantic para que el `response_model` no los strippee.

**Verificado E2E en preview**:
- GET `/api/config/settings` retorna `operations: "ragg1008@gmail.com"` ✅
- `_quote_to_biz_sub(quote fast_track PYME)` → `(implementacion_pyme, mpos_imple_pos)` ✅
- DB tiene config con esa key y 2 destinatarios → motor la encuentra ✅
- Stepper COT-054: 3 checks verdes (Enviada, Aprobada, Preasign) ✅
- Modal Preasignación muestra "Personalizar Comunicación" con textarea + chips CC ✅


## Mejoras de Sesión — Bloques 1-4 (Feb 2026)

**Bloque 1 (Motor de Notificaciones)**:
- 2A: CCs del modal viajan como Cc real del SMTP (no copia separada con body genérico).
- 2B: `_build_template_vars` ahora calcula universalmente `items_table`, `Modelo_Equipo`, `Cantidad`, `lista_modelos_seriales`, `lista_equipos_seriales`, `almacen_custodia`, `Direccion_Entrega`, `modelos_resumen`.
- 2C: Custom actions pasan por modal "Personalizar Comunicación"; backend persiste timestamp en `custom_actions_executed.{action_id}`.

**Bloque 2 (UI/Flujos)**:
- 3A: Stepper inyecta custom actions ejecutadas como pasos extra **violeta** (con anclaje por `position_after`). Verificado: "Validar Pago" aparece en COT-058 entre Pagada y Entregada.
- 3B: `resolveBizSub` ahora mapea `quote_category="fast_track"` → `(implementacion_pyme|corp, mpos_imple_pos)` igual que el backend, así los overrides se aplican en el dropdown.

**Bloque 3 (Nota de Entrega Reparaciones)**:
- Si la Nota de Entrega no se genera, **no se envía correo** (evita anexo incorrecto o vacío).
- `repair_deliver` ahora pasa por `_engine_or_legacy` con SOLO `delivery_note_pdf_bytes`.
- Fallback legacy adjunta exclusivamente `NotaEntrega_{correlativo}.pdf`.
- `RepairDeliveryDialog` muestra toast diferenciado según `email_sent`.

**Bloque 4 (UX Grilla)**:
- `QuotesTable.jsx`: scrollbar superior espejo del inferior. Ambos sincronizados con refs + `onScroll` + `requestAnimationFrame` (evita loop). El top scrollbar tiene 14px de alto. Recalcula ancho con `useEffect` cuando cambian quotes/filtros.


---

## 2026-05-14 — Producto "Link de Pago" (LINK_PAGO) [COMPLETE]
**Objetivo**: Nuevo tipo de cotización "Link de Pago", clon de Payment Gateway, con anexo PDF estático inyectado en página 5.

**Implementado**:
- `pdf_generator.py::_generate_link_pago` corregido: maneja BytesIO correctamente y retorna BytesIO consistente para encadenar `append_pg_static_pages`. Inserta `/app/backend/static/anexos/link_pago_anexo.pdf` (2 págs) en índice 4 → final: P1-4 PG dinámico, P5-6 anexo, P7 Términos, P8-10 anexo PG estático (10 págs totales).
- `generate_pg` usa flag `_link_pago_mode` para mostrar subtítulo "Payment Gateway - Link de Pagos".
- `quotes.py` línea 269: respeta `data.quote_type` (no hardcodea "GATEWAY") para preservar LINK_PAGO.
- Frontend: `isPaymentGateway` incluye LINK_PAGO; `handleSubmitPGQuote` envía `quote_type` real; `templateTypeMap` mapea LINK_PAGO → 'payment_gateway'; Wizard `onValueChange` trata LINK_PAGO como PG-like (auto-carga "Persona Jurídica").
- Carga de datos al editar (`setPgSetupItems`) ahora soporta GATEWAY y LINK_PAGO.

**Verificación**:
- Curl crea COT-2026-05-069-PYME tipo LINK_PAGO, genera PDF de 10 págs con anexo correctamente intercalado.
- Wizard UI muestra "Link de Pago" en dropdown y al seleccionarlo oculta Cajas/Bancos/Modelo.
- Testing agent: 6/6 PASS backend (pytest `/app/backend/tests/test_link_pago_flow.py`); frontend 100% (wizard + lista + regresión GATEWAY).

**Notas técnicas**:
- Anexo tiene 2 páginas → Términos termina en P7 (no P6 como decía plan original con anexo de 1 pág).
- Filtro `?quote_type=` en `/api/quotes` NO filtra server-side (frontend filtra en cliente). Minor, sin impacto en este feature.




---

## 2026-05-14 — Link de Pago en Motor Dinámico + Reporte de Embudo Acumulado [COMPLETE]

**1) Link de Pago en matrices de acción (Pyme + Corp)**
- `action_notifications.py`: agregado `{id:"link_pago"}` a `PRODUCT_SUBCATEGORIES`; agregadas entradas en `ALLOWED_ACTIONS_BY_BIZ_SUB` para `("implementacion_pyme","link_pago")` y `("implementacion_corp","link_pago")` con clon 1:1 de Payment Gateway (send_to_client, approve, invoice, collect, send_to_implementation).
- `notification_engine.py::_quote_to_biz_sub`: mapea `LINK_PAGO`/`LINK` quote_type → sub `link_pago`.
- UI auto-renderiza la pestaña "Link de Pago" en `/settings/action-notifications` (Matrix + Overrides + Custom Actions) sin cambios en el componente.

**2) Reporte de Embudo — acumulado histórico**
- `sales_reports.py::funnel_report` ahora retorna `delivered_breakdown` con 3 categorías:
  - **implementaciones**: cotizaciones implementation/fast_track con `delivered_at` OR `sent_to_implementation_at` OR `archived=True` (pasaron a Proyecto).
  - **equipos**: equipment con `delivered_at`.
  - **reparaciones**: repair con `delivered_at`.
- El stage "Entregada" en `stages` ahora refleja la SUMA de los 3 segmentos (antes solo contaba `delivered_at`, excluyendo implementaciones que pasaban a Proyecto).
- Las etapas previas (Enviada/Aprobada/Facturada/Pagada) ya son cumulativas por timestamp, sin cambios.

**3) Barra segmentada "Entregadas" (UI)**
- `SalesReports.jsx`: nueva tarjeta "Cierre por línea de negocio (Entregadas / Pasaron al Histórico)" con barra horizontal multi-color (azul=Imple, naranja=Equipos, rojo=Reparaciones) + tooltip nativo (count + monto) + 3 tarjetas-leyenda con totales.

**4) Herramienta admin de Refresco del Embudo**
- Backend: `POST /api/reports/sales/funnel/recalculate` admin-only. Backfilla timestamps faltantes desde `status_history` (mapea `to_status` → ts field) y desde `archived_at` cuando `archived_trigger=status_enviada_imple`. NO sobrescribe valores existentes. Bitácora registrada.
- Frontend: `Settings.jsx` muestra tarjeta `FunnelRecalculateCard` con botón "Ejecutar refresco", confirmación nativa, toast con resumen y registro del último resultado.

**Testing**: iteration_3.json — Backend 7/7 PASS, Frontend 9/9 PASS, sin issues críticos.




---

## 2026-05-15 — UX/Integración: Adjuntos + Deep-link Cliente + Resumen 360 + Import Excel [COMPLETE]

**1) Adjuntos manuales en modal "Personalizar Comunicación" (límite 10MB)**
- `quote_actions.py`: POST `/api/quotes/manual-attachments/upload` (multipart, ≤10MB, valida MIME/extensión, devuelve `attachment_id`). Helper `_resolve_manual_attachments(ids)` lee CSV de IDs, valida tamaño total y consume one-shot.
- `quote_actions.py::send_quote_to_client`: nuevo header `x-manual-attachment-ids` → propaga a `_engine_or_legacy(extra_attachments=...)`.
- `quote_action_customization.py::dispatch_custom_action`: igual integración.
- Frontend `QuoteModals.jsx`: nuevo subcomponente `EmailManualAttachments` con upload múltiple, validación 10MB cliente, lista de adjuntos con tamaño y remover.
- Frontend `Quotes.jsx`: state `emailManualAttachments`, `getEmailHeaders` inyecta header, `executeCustomAction` lo pasa también.

**2) Hipervínculo Cliente → Ficha**
- `QuotesTable.jsx`: celda "Cliente" envuelta en `<a href="/clients?open={id}" target="_blank">` con `data-testid="quote-client-link-{quote_id}"` y clases `text-blue-700 hover:text-blue-900 hover:underline`.
- `Clients.jsx`: `useEffect` reacciona a `searchParams.get('open')` y abre `openEditDialog(client)` automáticamente.

**3) Vista 360: pestaña "Resumen de Negocio" en ficha del cliente**
- `Clients.jsx`: nuevas tabs `Datos del Cliente` / `Resumen de Negocio` (state `clientDialogTab`), sólo visible en modo edición.
- `ClientBusinessSummary.jsx` (nuevo): carga `/quotes?client_id=X` + `/projects?client_id=X` en paralelo, muestra 3 KPIs (Cotizaciones Activas / Total / Proyectos) y dos tablas con scroll: cotizaciones activas (excluye Entregada/Completada/archivadas) y proyectos (TODOS — cualquier estado). Botón abrir en nueva pestaña para cotización; navegación in-app para proyecto.

**4) Import Excel en "Detalle de Tiendas"**
- `BranchDetailPanel.jsx`: nuevo botón **"Plantilla"** descarga un .xlsx con cabeceras `Nombre Tienda` | `Cantidad de Cajas` y 3 filas ejemplo. Botón "Excel" ahora **REEMPLAZA** las filas existentes (antes hacía append). Validación: filas con `qty` no numérico o ≤ 0 se ignoran y se reportan en toast.

**Testing**: iteration_4.json — Backend pytest 8/8 PASS, Frontend 100% (5/5 features UI validadas + 1 via code review). Cero regresiones.

**Mejora minor aplicada post-test**: `_resolve_manual_attachments` ahora borra sólo los IDs efectivamente consumidos (no los truncados por límite total).



---

## Iteración 43 — Text-Wrap + Tooltip en Inventario (Feb 2026)

**Requerimiento**: Corregir desbordamiento de texto en selección de ítems (Inventario) y mostrar la "Descripción Opcional" del bien/servicio vía Tooltip (hover) sin ocupar espacio en la grilla.

**Implementado** (`/app/frontend/src/pages/Inventory.jsx`):
- Import de `Tooltip, TooltipContent, TooltipProvider, TooltipTrigger`.
- **Entrada de Inventario** (Select de Bien/Servicio): se eliminó `truncate`; el nombre ahora usa `whitespace-normal break-words` (ajuste multi-línea). El `SelectTrigger` muestra el valor seleccionado en multi-línea. Cada `SelectItem` envuelve el nombre con `Tooltip` (delayDuration={0}, side="right") que muestra `hardware.description` sólo si no está vacía.
- **Salida** y **Transferencia**: el nombre del ítem mostrado (`selectedExitItem`/`selectedTransferItem`) se envuelve con el mismo patrón de Tooltip (side="bottom") y `whitespace-normal break-words`.

**Testing**: Verificado vía screenshot tool — multi-línea OK (ej. "PinPad Verifone P200 Engage..." en 3 líneas) y tooltip instantáneo OK (ej. "Dongles Mifi Produccion mf67" → "Accesorios varios"). Lint OK.

---

## Iteración 44 — Descripción Opcional transversal (Inventario + Cotizador) (Feb 2026)

**Requerimiento**: Disponibilidad de la "Descripción Opcional" en (1) Entrada de Inventario como campo visible de solo lectura, y (2) Cotizador de Equipos/Accesorios vía hover/tooltip.

**Implementado**:
- `Inventory.jsx` (Entrada de Inventario): caja de solo lectura `data-testid="entry-item-description"` debajo del selector, se popula con `selectedEntryItem.description` al elegir ítem. Control de nulos: oculta si vacía.
- `EquipmentQuoteWizard.jsx` (Paso 3 — Selección de Productos):
  - Lista de productos disponibles: nombre con Tooltip (delay 0, side right) mostrando `item.description`. `data-testid="equipment-item-name-{id}"`.
  - Tabla "Productos Seleccionados": nombre con Tooltip; descripción resuelta vía `hardware.find(...).description`. `data-testid="equipment-selected-name-{index}"`.
  - Control de nulos: sin descripción → sin tooltip ni caja vacía. No altera líneas ni montos.
  - Aplicado SOLO en cotizador de Equipos/Accesorios (no en wizard de servicios), por decisión del usuario.

**Testing**: Verificado vía screenshot tool — caja de descripción en Inventario OK ("Accesorios varios"); tooltip en Paso 3 del cotizador OK ("Accesorios varios" sobre "Dongles Mifi Produccion mf67"). Lint OK en ambos archivos.

---

## Hotfix — Overlay de error "ResizeObserver loop" en Cotización Equipos (Feb 2026)

**Síntoma**: Al abrir el wizard de Cotización de Equipos/Accesorios y desplegar el selector de cliente, aparecía el overlay rojo de desarrollo "Uncaught runtime errors: ResizeObserver loop completed with undelivered notifications" (error benigno del dev-server, no ocurre en producción).

**Causa**: El popper de Radix Select midiendo una lista larga de clientes dispara el loop benigno de ResizeObserver, que el overlay de webpack-dev-server captura como error.

**Fix** (`/app/frontend/src/index.js`): Listeners globales `error` y `unhandledrejection` que detectan mensajes "ResizeObserver loop", llaman `stopImmediatePropagation()`/`preventDefault()` y ocultan `#webpack-dev-server-client-overlay`. No afecta funcionalidad ni producción.

**Testing**: Verificado vía screenshot tool — al abrir el wizard y desplegar el selector de cliente ya no aparece overlay (overlay present: 0, sin texto "Uncaught"). Flujo de cotización operativo. Lint OK.

---

## Fix UI — Desbordamiento por nombre de archivo largo en modales de carga (Feb 2026)

**Síntoma**: En el modal "Subir Documento de Comunicación" (Plantillas/Documentos), un nombre de archivo largo hacía crecer el botón "Archivo" y desbordaba el modal horizontalmente.

**Causa**: El `<Button>` del archivo renderizaba `docFile.name` directo, sin ancho máximo ni truncado, expandiéndose con el contenido.

**Fix**:
- `ClientTemplatesConfig.jsx` y `EntityTemplatesConfig.jsx`: botón "Archivo" ahora `w-full justify-start max-w-full` con el nombre en `<span className="truncate min-w-0">` + atributo `title` para ver el nombre completo al hover. También se agregó `truncate` a la línea `{doc.filename} | {doc.category}` del listado de documentos.
- `MigrationButtons.jsx`: `<div>` del nombre de archivo con `break-words`.

**Testing**: Verificado vía screenshot tool con archivo de nombre extremadamente largo — modal contenido en viewport (right edge 1184px), botón a ancho completo con elipsis, sin desbordamiento. Lint OK en los 3 archivos.
