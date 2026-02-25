# PRD - Cotizador Merchant Server

## Descripción
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Módulos Core
1. **Autenticación**: Registro/Login con sesiones, roles (admin/user), sedes (TBP/LCH)
2. **Gestión de Clientes (CRM)**: Multi-sede, contactos, bitácora de eventos, importación Excel
3. **Bancos y Medios de Pago**: CRUD de bancos con productos/medios de pago asociados
4. **Integradores**: Gestión de integradores certificados
5. **Hardware (Bienes y Servicios)**: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. **Tipos de Cotización**:
   - **VPOS/MPOS (Cajas y Tablet)**: Fusión de VPOS + MPOS. Flujo completo con Setup, Recurrentes, Adicionales
   - **Payment Gateway**: NUEVO. Solo Cliente + Integrador. Matriz de Setup con medios de pago + Costos recurrentes automáticos
   - **Link de Pago**: DESACTIVADO temporalmente
   - **Equipos/Accesorios/Reparaciones**: Wizard independiente
7. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE con contadores atómicos por sede/mes
8. **Anexos**: Subida de documentos por cotización (Cotización, OC, Factura, Pagos, Otros)
9. **Workflow de Estados**: Validación de documentos para cambiar estado (Aprobado→Facturado→Pagado)
10. **Dashboard**: Alertas de seguimiento con semáforo de colores

### Reestructuración del Modelo de Cotizaciones (Feb 2026)
- Consolidación VPOS/MPOS en un solo tipo
- Nuevo flujo Payment Gateway con setup items dinámicos desde medios de pago
- Motor de costos recurrentes basado en tabla Excel (15 rangos x 11 productos)
- Desactivación de Link de Pago
- PDF generado con secciones PG (Setup + Recurrentes)

## Stack Técnico
- Backend: FastAPI, MongoDB, ReportLab (PDF), openpyxl, pandas
- Frontend: React, Shadcn/UI, Radix UI

## Pendientes P0-P2
- P0: Refactorización backend server.py (6300+ líneas)
- P1: Refactorización frontend (Quotes.jsx, Clients.jsx)
- P1: Verificación de Email / Recuperación de Contraseña (requiere Resend API Key)
- P2: Bug contadores Dashboard
- P2: Módulo de Reportes

## Arquitectura
```
/app/backend/server.py       # Monolito (URGENTE refactorizar)
/app/frontend/src/pages/     # Páginas principales
/app/frontend/src/components/ # Componentes reutilizables
```

## Test Reports
- iteration_47: Payment Gateway features (9/9 backend, frontend verified)
