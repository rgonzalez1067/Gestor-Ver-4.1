# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

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

## P2 Refactor Backend — `quote_actions.py` (Feb-2026, iter 176)
Desglose del monolito `/app/backend/routes/quote_actions.py` (3060 → 2089 líneas, -31%).
Nuevos módulos:
- `routes/quote_helpers.py` (128 líneas): caché de plantillas, `get_email_template`, modelos `QuoteStatusUpdate`/`EmailSendRequest`, constantes `REGULAR_FLOW`/`STATUS_ORDER`, helpers `get_status_index`, `is_regularization`, `check_irregular_flow`, `log_audit_exception`, `mark_quote_irregular`.
- `routes/quote_transitions.py` (263 líneas): `_create_project_from_quote` — creación de proyecto + notificación a gerente de implementación al enviar a imple.
- `routes/quote_taller.py` (262 líneas, router independiente): `/repair-supplies`, `/taller-equipos` (GET/filtros), `/taller-equipos/{id}/historial`, `/taller-equipos/export-excel`, `DELETE /taller-equipos/{id}`.
- `routes/quote_serials.py` (429 líneas, router independiente): `/quotes/{id}/pinpad-models`, `/quotes/{id}/inventory-serials`, `/quotes/{id}/equipment-for-implementation`, `/inventory/{warehouse_id}/available-serials/{item_id}`, `/quotes/{id}/preassigned-serials`, `POST /quotes/{id}/preassign-serials`.

Routers registrados en `server.py`. Tests: iteration_176 → 27/27 backend PASS. Sin regresiones, helpers validados con 422 IRREGULAR en approve de Borrador.
