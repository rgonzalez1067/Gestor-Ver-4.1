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
- **P1**: Sistema de Notificaciones Push (campana + WebSockets)
- **P2**: Módulo de Reportes de Ventas
- **P2**: Lógica "Completado" en Roadmap Bancos
- **P2**: Refactor monolitos frontend restantes (`Quotes.jsx` >3400 líneas, `ProjectDetail.jsx` >2200 líneas) — **backend ya refactorizado** (ver sección P2 Refactor Backend)
- **P3**: Resolver warnings React hydration (`<span>/<tr>/<tbody>` mal anidados) en matriz de implementación

## P2 Refactor Backend — `quote_actions.py` (Feb-2026, iter 176)
Desglose del monolito `/app/backend/routes/quote_actions.py` (3060 → 2089 líneas, -31%).
Nuevos módulos:
- `routes/quote_helpers.py` (128 líneas): caché de plantillas, `get_email_template`, modelos `QuoteStatusUpdate`/`EmailSendRequest`, constantes `REGULAR_FLOW`/`STATUS_ORDER`, helpers `get_status_index`, `is_regularization`, `check_irregular_flow`, `log_audit_exception`, `mark_quote_irregular`.
- `routes/quote_transitions.py` (263 líneas): `_create_project_from_quote` — creación de proyecto + notificación a gerente de implementación al enviar a imple.
- `routes/quote_taller.py` (262 líneas, router independiente): `/repair-supplies`, `/taller-equipos` (GET/filtros), `/taller-equipos/{id}/historial`, `/taller-equipos/export-excel`, `DELETE /taller-equipos/{id}`.
- `routes/quote_serials.py` (429 líneas, router independiente): `/quotes/{id}/pinpad-models`, `/quotes/{id}/inventory-serials`, `/quotes/{id}/equipment-for-implementation`, `/inventory/{warehouse_id}/available-serials/{item_id}`, `/quotes/{id}/preassigned-serials`, `POST /quotes/{id}/preassign-serials`.

Routers registrados en `server.py`. Tests: iteration_176 → 27/27 backend PASS. Sin regresiones, helpers validados con 422 IRREGULAR en approve de Borrador.
