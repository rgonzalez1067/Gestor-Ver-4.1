# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Cotizaciones
- Total USD = Total Setup Neto + Equipment (usa `totalNetoSetup` del wizard como fuente de verdad)
- PDF versionado al modificar: `regenerate-pdf` reconstruye desde datos almacenados
- Bitácora de Clientes fix (`/logs`)

### Reportes Contables (Nuevo — Abr 2026)
- **Kardex de Activos**: Reporte CPP existente (`/inventory/accounting-report`)
- **Mayor de Activos**: Nuevo reporte PEPS/FIFO (`/inventory/asset-ledger`)
  - Solo costos de entradas al Almacén Principal (LCH)
  - Transferencias NO son salidas reales
  - Salidas (ventas) se descuentan del lote más antiguo (FIFO)
  - Solo muestra lotes con saldo > 0
  - Columnas: Fecha Compra, Proveedor, Referencia, Cant. Comprada, Saldo Disponible, Costo Unitario, Valor del Lote
  - Totales por item y Gran Total Contable
- **Sidebar**: Menú agrupado "Reportes Contables" con ambos reportes

### Medios de Pago (Servicios)
- Modelo `Service` con campos opcionales
- Restauración desde CSV del usuario (30 productos + 14 servicios recurrentes)

### Integradores
- Fix importación: Categoria sin tilde, datetime de Excel
- Reimportación completa desde archivo del usuario

## Archivos Clave
- `/app/backend/routes/inventory.py` — Inventario + endpoint PEPS (`asset-ledger`)
- `/app/frontend/src/pages/AssetLedgerReport.jsx` — Mayor de Activos (NUEVO)
- `/app/frontend/src/pages/InventoryAccountingReport.jsx` — Kardex de Activos
- `/app/frontend/src/components/Sidebar.jsx` — Menú con Reportes Contables
- `/app/backend/routes/quotes.py` — Creación, regenerate-pdf, total_usd override
- `/app/frontend/src/pages/Quotes.jsx` — handleSaveEditedQuote con totalNetoSetup
- `/app/frontend/src/components/quotes/QuotesTable.jsx` — Display total_usd directo

## Backlog

### P1 (Próximos)
- Sistema de Notificaciones Push (campana con contador) + alertas en tiempo real

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
