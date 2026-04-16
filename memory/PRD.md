# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

### Cotizaciones — Flujo de Reparaciones PYME (Actualizado Abr 2026)

#### Modales reorganizados:
- **Aprobación (repair)**: Modal simplificado — solo solicita Comprobante de Aprobación de la reparación. Sin calculadora, sin comprobante de pago.
- **Reparada**: Nuevo modal `RepairCompleteModal` con:
  - Calculadora fiscal con conceptos de la cotización (equipment_items)
  - Fecha de facturación + tasa BCV automática
  - Tabla Subtotal/IVA 16%/Total en USD y Bs.
  - Carga opcional de comprobante de pago/anticipo
  - Notifica a Administración con billing_data adjunto

#### Notificaciones automáticas:
- **Enviar al cliente** → `repair_quote_sent_PYME` → cliente
- **Aprobación** → `repair_approved_PYME` → cliente
- **Reparada** → `repair_complete_client_PYME` → cliente + Admin PYME
- **Factura/Proforma** → `repair_invoice_PYME` → Operaciones PYME
- **Cobranza** → `repair_collect_warehouse_PYME` → Almacén PYME
- **Marcar como entregada** → `repair_delivery_PYME` → cliente + modal de insumos/factura

#### Modal de Cierre de Orden (Marcar como entregada):
- Nro. factura obligatorio + selector de insumos consumidos
- Salidas automáticas en inventario TBP

### Clientes
- Comunicaciones, Plantillas, Bitácora con hora precisa

### Inventarios
- Kardex en Bs., Mayor de Activos PEPS, salidas por reparación

## Archivos Clave
- `/app/frontend/src/components/ApprovalBillingModal.jsx` — Simplificado para repair
- `/app/frontend/src/components/quotes/RepairCompleteModal.jsx` — NUEVO: calculadora+pago
- `/app/frontend/src/components/quotes/RepairDeliveryDialog.jsx` — Modal entrega con insumos
- `/app/backend/routes/quote_actions.py` — Flujo completo

## Backlog
- **P1**: Sistema de Notificaciones Push
- **P2**: Reportes de Ventas, Roadmap Bancos
- **P2**: Refactorización monolitos
