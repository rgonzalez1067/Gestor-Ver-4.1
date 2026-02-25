# PRD - Cotizador Merchant Server

## Descripción
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Módulos Core
1. **Autenticación**: Registro/Login con sesiones, roles (admin/user), sedes (TBP/LCH)
2. **Gestión de Clientes (CRM)**: Multi-sede, contactos, bitácora de eventos, importación Excel
3. **Bancos y Medios de Pago**: CRUD de bancos con productos/medios de pago asociados (campo `pg_setup_cost` para PG)
4. **Integradores**: Gestión de integradores certificados
5. **Hardware (Bienes y Servicios)**: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. **Tipos de Cotización**:
   - **VPOS/MPOS (Cajas y Tablet)**: Fusión de VPOS + MPOS. Flujo completo con Setup, Recurrentes, Adicionales
   - **Payment Gateway**: Flujo independiente:
     - Solo Cliente + Integrador (sin Modelo de Precios, Cajas, Bancos, Pinpad, Entidad)
     - "Persona Jurídica" cargada automáticamente como ítem fijo (costo desde `/api/pg-defaults`)
     - Filtro de dependencia cruzada: Banco → Concepto filtrado por productos del banco
     - Botón "Generar Tabla de Recurrentes": cuenta N medios de pago y muestra tabla COMPLETA (15 rangos)
     - PDF generado automáticamente con secciones Setup + Tabla Recurrentes
   - **Link de Pago**: DESACTIVADO temporalmente
   - **Equipos/Accesorios/Reparaciones**: Wizard independiente
7. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE con contadores atómicos por sede/mes
8. **Anexos**: Subida de documentos por cotización
9. **Workflow de Estados**: Validación de documentos para cambiar estado
10. **Dashboard**: Alertas de seguimiento con semáforo de colores

## Stack Técnico
- Backend: FastAPI, MongoDB, ReportLab (PDF), openpyxl, pandas
- Frontend: React, Shadcn/UI, Radix UI

## API Endpoints PG
- `GET /api/pg-defaults` - Config de Persona Jurídica (concepto + costo)
- `PUT /api/pg-defaults` - Actualizar costo Persona Jurídica (solo admin)
- `GET /api/pg-recurring-costs` - Tabla completa de costos recurrentes (15 rangos x 11 productos)

## Pendientes P0-P2
- P0: Refactorización backend server.py (6400+ líneas)
- P1: Refactorización frontend (Quotes.jsx, Clients.jsx)
- P1: Verificación de Email / Recuperación de Contraseña (requiere Resend API Key)
- P2: Bug contadores Dashboard
- P2: Módulo de Reportes

## Test Reports
- iteration_47: PG features originales (9/9 backend)
- iteration_48: PG flow corregido (7/7 backend, 100% frontend)
