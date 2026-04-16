# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

### Sistema de Plantillas de Correo (CRÍTICO)
- **Helper `get_email_template()`**: Busca plantillas primero en MongoDB, luego en defaults del código (`generate_email_templates_by_sede()`)
- Esto resuelve el problema de que solo 25 plantillas estaban en la BD, mientras los defaults del código tienen ~50+
- Todas las plantillas de reparación tienen HTML profesional (1400-4695 chars con estilos)

### Cotizaciones — Flujo de Reparaciones PYME
| Acción | Plantilla | Destinatario |
|---|---|---|
| Enviar al cliente | `repair_quote_sent_PYME` | Cliente |
| Aprobación | `repair_approved_PYME` | Cliente (+ guarda Soporte de Aprobación) |
| Reparada | `repair_complete_client_PYME` | Cliente + Admin PYME |
| Factura/Proforma | `repair_invoice_PYME` | Operaciones PYME |
| Cobranza | `repair_collect_warehouse_PYME` | Almacén PYME |
| Marcar entregada | `repair_delivery_PYME` | Cliente (+ insumos TBP) |

### Clientes
- Comunicaciones, Plantillas (context=CLIENTES), Bitácora con hora precisa
- Variables: {{nombre}}, {{contacto}}, {{rif}}, etc. resueltas al seleccionar plantilla

### Inventarios
- Kardex en Bs., Mayor de Activos PEPS
- Salidas por reparación: Referencia = "Factura: XXX | Cotización: COT-XXXX"

## Archivos Clave
- `/app/backend/routes/quote_actions.py` — Helper get_email_template + flujo completo
- `/app/backend/routes/seed_and_templates.py` — Defaults de plantillas
- `/app/frontend/src/components/quotes/RepairCompleteModal.jsx` — Calculadora fiscal
- `/app/frontend/src/components/quotes/RepairDeliveryDialog.jsx` — Modal entrega + insumos

## Backlog
- **P1**: Sistema de Notificaciones Push
- **P2**: Reportes de Ventas, Roadmap Bancos
- **P2**: Refactorización monolitos
