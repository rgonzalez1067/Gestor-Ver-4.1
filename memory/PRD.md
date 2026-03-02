# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Modulos Core
1. **Autenticacion**: Registro/Login con sesiones, roles (admin/user), sedes (TBP/LCH)
2. **Gestion de Clientes (CRM)**: Multi-sede, contactos, bitacora, importacion Excel
3. **Bancos y Medios de Pago**: CRUD con productos, gateway_available flag
4. **Integradores**: Gestion de integradores, filtro por modalidad PG
5. **Hardware**: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. **Tipos**: VPOS/MPOS, Payment Gateway, Link de Pago (desactivado)
7. **Payment Gateway**: 
   - Filtro integradores por modalidad (PG Universal / PG No universal) + "Sin integrador"
   - Validacion concepto-banco muchos-a-muchos (mismo concepto, diferentes bancos)
   - PDF 4 paginas: Portada PG, Matriz de Configuracion, Recurrentes, T&C
8. **Nomenclatura**: COT-AAAA-MM-NNN-SEDE atomica
9. **Anexos** y **Workflow de Estados**
10. **Dashboard** con alertas

### Persistencia y Edicion
- Race condition fix: useEffect propagacion con refs prevCajasRef/prevBancosRef
- Metadata persistence: lockBancos, autoBancos, bancosOverride, totalOverride en QuoteItem
- Concept matching: Matching exacto/mas-largo evita colisiones
- MongoDB Indexes: clients y quotes

## Pendientes
- P0: Refactorizacion backend server.py (6800+ lineas)
- P1: Refactorizacion frontend Quotes.jsx (4200+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes

## Test Reports
- iteration_51: 3 optimizaciones (8/8)
- iteration_52: Busqueda server-side + PDF fix (9/9)
- iteration_53: Edicion persistencia modelos (7/7)
- iteration_54: Race condition fix (7/7 + 2/2)
- iteration_55: Payment Gateway module (11/11 backend + 4/4 frontend)
