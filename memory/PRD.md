# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos — Últimas Actualizaciones (Abr 2026)

### Cotizaciones — Modificación de Equipos y Reparaciones
- **Dropdown con catálogo dinámico**: Al agregar item, muestra dropdown filtrado por categoría:
  - Equipos y Accesorios: POS, Pinpad, Base (Bienes)
  - Reparaciones: Mantenimiento
- **Precio auto-completado** al seleccionar del catálogo
- **IVA consistente**: Desglose Subtotal + IVA 16% + Total en edición (mismo que creación)
- **Nuevos valores se persisten**: Items editados se guardan correctamente en la nueva versión
- **Justificación obligatoria** (min 20 chars) para los 3 tipos
- **PDF regenerado** desde datos almacenados, registrado en Anexos
- **Bitácora** registrada en el cliente

### Archivos Clave
- `/app/frontend/src/components/EditEquipRepairDialog.jsx` — Edición Equipos/Reparaciones con dropdown catálogo
- `/app/frontend/src/components/JustificationModal.jsx` — Modal justificación
- `/app/backend/routes/quotes.py` — regenerate-equipment-pdf, regenerate-pdf, override_total_usd

## Backlog
- P1: Sistema de Notificaciones Push
- P2: Reportes de Ventas, Roadmap Bancos, Refactorización monolitos
