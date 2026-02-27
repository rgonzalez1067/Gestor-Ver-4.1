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
7. **Payment Gateway**: Persona Juridica fija + filtro Banco->gateway_available + precio outsourcing automatico + tabla recurrentes completa
8. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE atomica
9. **Anexos** y **Workflow de Estados**
10. **Dashboard** con alertas de seguimiento

### Optimizaciones (Feb 2026)
- **Buscador predictivo server-side**: Combobox con busqueda en BD via GET /api/clients/search?q=texto (regex). Debounce 300ms, sin limite de registros, soporte 5000+ clientes.
- **Setup Item #4 editable**: Campo "Bancos o Entes" editable manualmente con auto-calculo preservado. Badge "Auto"/"Manual" + icono candado.
- **Descuentos independientes**: descuento_setup y descuento_recurrente separados
- **Cliente en Produccion**: Seccion Si/No para agregar conceptos recurrentes adicionales del catalogo
- **PDF corregido**: Variable 'descuento' (NameError) -> 'monto_desc_setup'. Production items incluidos en PDF. Campos extra en modelos Pydantic.

## Pendientes
- P0: Refactorizacion backend server.py (6500+ lineas)
- P1: Refactorizacion frontend (Quotes.jsx 4000+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes

## Test Reports
- iteration_51: 3 optimizaciones (8/8 frontend, 100%)
- iteration_52: Busqueda server-side + PDF fix (9/9 backend, code review verified)
