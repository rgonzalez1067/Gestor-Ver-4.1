# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

### Reportes Contables (Actualizado Abr 2026)
- **Kardex de Activos** — Costo Promedio Ponderado + exportar Excel
- **Mayor de Activos** — PEPS/FIFO en Bs. + exportar Excel (NUEVO)
- **Relación de Salidas Facturadas** — NUEVO: Salidas de inventario agrupadas por almacén, filtradas por rango de fechas, con Nro. de Factura, Cliente, Cotización, Operador + exportar Excel

### Cotizaciones — Entrega de Equipos
- **Nro. de Factura obligatorio** en DeliveryDialog para Equipos/MPOS/Fast Track
- La referencia del movimiento de inventario incluye: `Factura: XXX | Cotización: COT-XXXX`
- El nro. de factura se almacena en `delivery_invoice_number` de la cotización

### Flujo de Reparaciones PYME
- Plantillas correctas por acción (repair_quote_sent, repair_approved, etc.)
- Helper `get_email_template()` busca BD → defaults del código
- Sincronización automática de plantillas a MongoDB al iniciar

### Clientes
- Comunicaciones, Plantillas, Bitácora con hora precisa

## Archivos Clave
- `/app/frontend/src/pages/InvoicedExitsReport.jsx` — NUEVO reporte Salidas Facturadas
- `/app/backend/routes/inventory.py` — Endpoint invoiced-exits-report
- `/app/frontend/src/components/quotes/DeliveryDialog.jsx` — Campo invoiceNumber obligatorio
- `/app/frontend/src/pages/AssetLedgerReport.jsx` — Agregado export Excel

## Backlog
- **P1**: Sistema de Notificaciones Push
- **P2**: Reportes de Ventas, Roadmap Bancos
- **P2**: Refactorización monolitos
