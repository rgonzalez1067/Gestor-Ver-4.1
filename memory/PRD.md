# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Modulos Core
1. Autenticacion: Registro/Login, roles (admin/user), sedes (TBP/LCH)
2. Gestion de Clientes (CRM): Multi-sede, contactos, bitacora, importacion Excel, busqueda server-side
3. Bancos y Medios de Pago: CRUD con productos, gateway_available flag
4. Integradores: Gestion, filtro por modalidad PG
5. Hardware: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. Tipos: VPOS/MPOS, Payment Gateway, Link de Pago (desactivado)
7. Payment Gateway: Filtro integradores PG, validacion concepto-banco muchos-a-muchos, PDF 4 paginas
8. Nomenclatura: COT-AAAA-MM-NNN-SEDE atomica
9. Anexos y Workflow de Estados
10. Dashboard con alertas

### PDF y Previsualizacion
- Previsualizacion PDF: Modal con iframe, botones Descargar/Cerrar
- Botones agrupados: [Previsualizar PDF] | [Exportar PDF] | [Guardar Cotizacion]
- PDF PG 4 paginas: Portada, Matriz Configuracion, Recurrentes (centrada), T&C (clon VPOS)
- Limpieza observaciones: "Persona Juridica" muestra "Costo Base"
- PDF VPOS con template dinamico

### Persistencia y Edicion
- Race condition fix con refs prevCajasRef/prevBancosRef
- Metadata persistence: lockBancos, autoBancos, bancosOverride, totalOverride
- Concept matching exacto/mas-largo
- MongoDB Indexes en clients y quotes

### Correos de Notificacion por Sede (Nuevo - 2026-03-03)
- Correo de Ventas por sede: TBP y LCH tienen su propio campo de correo de ventas
- Backend: approve_quote y invoice_quote notifican al correo de ventas de la sede correspondiente
- Backend: collect_quote usa warehouse email per-sede
- Frontend: Settings.jsx muestra inputs de correo de ventas por sede (tema verde)
- Resend integrado para envio real de correos

## Pendientes
- P0: Refactorizacion backend server.py (6800+ lineas)
- P1: Refactorizacion frontend Quotes.jsx (4300+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes

## Test Reports
- iteration_51-56: Optimizaciones, busqueda, PDF fix, persistencia, PG module
- iteration_57: Sales email per sede (11/11 backend, 6/6 frontend - ALL PASSED)
