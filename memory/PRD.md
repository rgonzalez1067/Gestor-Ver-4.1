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

### Optimizaciones Recientes (Feb 2026)
- **Buscador predictivo de clientes**: Combobox con filtro por nombre y RIF (sucursal eliminado)
- **Setup Item #4 editable**: Campo "Bancos o Entes" editable manualmente con auto-calculo preservado. Badge "Auto" (purpura) cuando auto-calculado, badge "Manual" (ambar) + icono candado cuando editado. Duplicable con mismas caracteristicas.
- **Descuentos independientes**: descuento_setup y descuento_recurrente separados
- **Filtro gateway_available**: Solo medios de pago habilitados para e-commerce
- **Precio Outsourcing automatico**: Costo del catalogo de servicios
- **Cliente en Produccion**: Seccion Si/No despues de costos recurrentes. Si "Si", permite agregar conceptos recurrentes adicionales del catalogo de servicios. Los items se suman al total recurrente.

## Pendientes
- P0: Refactorizacion backend server.py (6400+ lineas)
- P1: Refactorizacion frontend (Quotes.jsx 4000+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes

## Test Reports
- iteration_47-49: Payment Gateway (backend 100%, frontend verified)
- iteration_50: Optimizaciones previas (backend 11/11, frontend 100%)
- iteration_51: 3 optimizaciones finales (8/8 features verified, 100% frontend)
