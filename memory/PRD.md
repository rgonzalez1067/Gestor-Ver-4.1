# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Modulos Core
1. **Autenticacion**: Registro/Login con sesiones, roles (admin/user), sedes (TBP/LCH)
2. **Gestion de Clientes (CRM)**: Multi-sede, contactos, bitacora de eventos, importacion Excel
3. **Bancos y Medios de Pago**: CRUD con productos, gateway_available flag, pg_setup_cost
4. **Integradores**: Gestion de integradores certificados
5. **Hardware**: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. **Tipos**: VPOS/MPOS (fusionado), Payment Gateway (nuevo), Link de Pago (desactivado)
7. **Payment Gateway**: Persona Juridica fija + filtro Banco->gateway_available + precio outsourcing automatico
8. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE atomica
9. **Anexos** y **Workflow de Estados**
10. **Dashboard** con alertas de seguimiento

### Optimizaciones (Feb-Mar 2026)
- **Buscador server-side**: GET /api/clients/search?q=texto (regex MongoDB, debounce 300ms)
- **Setup Item #4 editable**: Bancos editable con auto-calculo + Badge "Auto"/"Manual"
- **Descuentos independientes**: descuento_setup y descuento_recurrente persistentes en BD
- **Cliente en Produccion**: Seccion Si/No + items recurrentes adicionales persistentes
- **Concept matching fix**: Matching exacto/mas-largo evita colisiones substring(0,20)
- **MongoDB Indexes**: clients (fantasy_name, legal_name, rif, client_id), quotes (quote_id, client_id)
- **PDF fix**: Variable 'descuento' NameError corregida + production items en PDF

### Correccion Critica: Persistencia en Edicion (Mar 2026)
- **Race condition fix**: useEffect de propagacion de header sobrescribia valores al cambiar isLoadingEdit. Corregido con refs (prevCajasRef/prevBancosRef) que detectan cambios reales del usuario.
- **autoBancos guard**: Guard isLoadingEdit en useEffect de auto-calculo
- **Metadata persistence**: lockBancos, autoBancos, bancosOverride, totalOverride, isAutoLinked guardados en QuoteItem (backend) y restaurados al editar
- **Regla de Oro**: "Si el dato existe en el registro de la cotizacion, tiene prioridad absoluta sobre parametros globales"

## Pendientes
- P0: Refactorizacion backend server.py (6500+ lineas)
- P1: Refactorizacion frontend Quotes.jsx (4100+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes

## Test Reports
- iteration_51: 3 optimizaciones (8/8 frontend, 100%)
- iteration_52: Busqueda server-side + PDF fix (9/9 backend OK)
- iteration_53: Edicion persistencia modelos (7/7 backend OK)
- iteration_54: Race condition fix (7/7 backend + 2/2 frontend OK)
