# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Cotizaciones — Modificación Universal
- **Implementaciones**: Wizard completo con justificación obligatoria (min 20 chars), nueva versión vía `duplicate`, PDF regenerado automáticamente, bitácora en cliente
- **Equipos y Accesorios** (NUEVO Abr 2026): Diálogo dedicado `EditEquipRepairDialog` con items editables (add/remove/edit qty/price), justificación obligatoria, nueva versión + PDF + bitácora
- **Reparaciones** (FIX Abr 2026): Eliminada llamada incorrecta a función de Implementaciones. Ahora usa `EditEquipRepairDialog` con campos específicos (serial, descripción de falla, modelos)
- **JustificationModal**: Componente reutilizable para los 3 tipos de cotización
- Total USD = Total Setup Neto + Equipment (fuente de verdad: wizard)

### Reportes Contables
- **Kardex de Activos**: Reporte CPP existente
- **Mayor de Activos**: Reporte PEPS/FIFO — costos centralizados LCH, solo lotes con saldo > 0

### Medios de Pago, Integradores, Clientes, Inventario, Bancos, Proyectos
- (Ver sesiones anteriores para detalles)

## Archivos Clave (Abr 2026)
- `/app/frontend/src/components/EditEquipRepairDialog.jsx` — Edición Equipos/Reparaciones (NUEVO)
- `/app/frontend/src/components/JustificationModal.jsx` — Modal justificación (NUEVO)
- `/app/frontend/src/pages/AssetLedgerReport.jsx` — Mayor de Activos PEPS (NUEVO)
- `/app/backend/routes/quotes.py` — regenerate-pdf, regenerate-equipment-pdf, override_total_usd
- `/app/frontend/src/pages/Quotes.jsx` — handleEditQuote tripartito, handleSaveEditedQuote con bitácora

## Backlog

### P1 (Próximos)
- Sistema de Notificaciones Push (campana con contador) + alertas en tiempo real

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
