# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

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

