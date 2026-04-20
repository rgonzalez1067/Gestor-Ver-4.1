# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

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

## Backlog
- **P1**: Sistema de Notificaciones Push (campana + WebSockets)
- **P2**: Módulo de Reportes de Ventas
- **P2**: Lógica "Completado" en Roadmap Bancos
- **P2**: Refactor monolitos restantes (`Quotes.jsx` >3400 líneas, `quote_actions.py` >3000 líneas)
- **P3**: Resolver warnings React hydration (`<span>/<tr>/<tbody>` mal anidados) en matriz de implementación
