# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

### Cotizaciones — Flujo de Reparaciones PYME (Actualizado Abr 2026)
- **Enviar al cliente**: Plantilla `repair_quote_sent_PYME` → correo del cliente
- **Aprobación**: Plantilla `repair_approved_PYME` → correo del cliente
- **Reparada**: Plantilla `repair_complete_client_PYME` → cliente + Admin PYME
- **Factura/Proforma**: Plantilla `repair_invoice_PYME` → Operaciones PYME
- **Cobranza**: Plantilla `repair_collect_warehouse_PYME` → Almacén PYME
- **Marcar como entregada**: Plantilla `repair_delivery_PYME` → cliente
  - **Modal de Cierre de Orden**: Nro. factura obligatorio + selector de insumos consumidos (Accesorios/Componentes)
  - Los insumos se descargan como salidas en inventario TBP automáticamente

### Clientes
- CRUD completo con bitácora (fecha+hora precisa HH:MM:SS)
- Comunicaciones: Plantillas, Documentos, Email con adjuntos y variables dinámicas

### Inventarios
- Kardex en Bolívares (Bs.)
- Mayor de Activos (PEPS/FIFO) desglosado LCH/TBP
- Salidas automáticas por reparación (insumos consumidos vinculados a factura)

### Plantillas de Correo
- Organizadas por Sede (PYME / CORP)
- `repair_invoice` — Facturación de Reparaciones (nueva, duplicada de invoice)
- Todas las plantillas de reparación: Envío, Aprobación, Reparada, Facturación, Despacho, Entrega

### Otros módulos
- Proyectos, Contactos Iniciales, Taller de Equipos, Bancos, Integradores, etc.

## Archivos Clave
- `/app/backend/routes/quote_actions.py` — Flujo reparaciones (invoice repair→operations, deliver→insumos TBP)
- `/app/frontend/src/components/quotes/RepairDeliveryDialog.jsx` — Modal entrega con factura+insumos
- `/app/backend/routes/seed_and_templates.py` — Plantilla repair_invoice
- `/app/frontend/src/components/EmailTemplatesEditor.jsx` — Config visual plantillas

## Backlog
- **P1**: Sistema de Notificaciones Push
- **P2**: Reportes de Ventas, Roadmap Bancos
- **P2**: Refactorización monolitos
