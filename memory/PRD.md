# PRD - Cotizador Merchant Server

## Descripción
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Módulos Core
1. **Autenticación**: Registro/Login con sesiones, roles (admin/user), sedes (TBP/LCH)
2. **Gestión de Clientes (CRM)**: Multi-sede, contactos, bitácora de eventos, importación Excel
3. **Bancos y Medios de Pago**: CRUD con productos, gateway_available flag, pg_setup_cost
4. **Integradores**: Gestión de integradores certificados
5. **Hardware**: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. **Tipos**: VPOS/MPOS (fusionado), Payment Gateway (nuevo), Link de Pago (desactivado)
7. **Payment Gateway**: Persona Jurídica fija + filtro Banco→gateway_available + precio outsourcing automático + tabla recurrentes completa
8. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE atómica
9. **Anexos** y **Workflow de Estados**
10. **Dashboard** con alertas de seguimiento

### Optimizaciones Recientes (Feb 2026)
- **Buscador predictivo de clientes**: Combobox con filtro multicriterio (nombre, RIF, sucursal)
- **Setup Item #4 editable**: Total de "Config MP/Banco en MServer por PDV" editable con indicador visual (candado abierto)
- **Descuentos independientes**: descuento_setup y descuento_recurrente separados, cada uno aplica solo a su sección
- **Filtro gateway_available**: Solo medios de pago habilitados para e-commerce en cada banco
- **Precio Outsourcing automático**: Al agregar medio de pago en PG, el costo viene del catálogo de servicios

## Pendientes
- P0: Refactorización backend server.py (6400+ líneas)
- P1: Refactorización frontend (Quotes.jsx 3800+ líneas)
- P1: Verificación Email / Recuperación Contraseña (Resend API)
- P2: Bug contadores Dashboard
- P2: Módulo de Reportes

## Test Reports
- iteration_47-49: Payment Gateway (backend 100%, frontend verified)
- iteration_50: 3 optimizaciones (backend 11/11, frontend 100%)
