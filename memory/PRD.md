# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Arquitectura Backend (Refactorizado 2026-03-06)
```
backend/
├── server.py              → 77 líneas. Init FastAPI + montar routers.
├── config.py              → 179 líneas. DB, auth helpers, PDF helpers.
├── models.py              → 536 líneas. Todos los modelos Pydantic.
├── routes/
│   ├── auth.py            → 566 líneas. Registro, login, admin users.
│   ├── clients.py         → 288 líneas. CRUD clientes, import, RIF.
│   ├── dashboard.py       → 506 líneas. Stats, alerts, missing PDFs.
│   ├── banks.py           → 260 líneas. CRUD bancos.
│   ├── hardware.py        → 390 líneas. CRUD hardware.
│   ├── services.py        → 373 líneas. CRUD servicios, tasa cambio.
│   ├── quotes.py          → 1221 líneas. CRUD cotizaciones, PDF generation.
│   ├── quote_actions.py   → 653 líneas. Workflow (approve, invoice, collect).
│   ├── attachments.py     → 323 líneas. Gestión anexos.
│   ├── integrators.py     → 423 líneas. CRUD integradores.
│   ├── settings.py        → 257 líneas. Configuración app.
│   └── seed_and_templates.py → 497 líneas. Seed bancos, email templates.
├── services/
│   └── pdf_generator.py   → 1079 líneas. DynamicQuotePDFGenerator.
└── uploads/
```

## Arquitectura Frontend (Refactorizado 2026-03-06)
```
frontend/src/
├── pages/
│   └── Quotes.jsx         → 4043 líneas. Orchestrator (reducido de 4444).
├── components/
│   ├── quotes/
│   │   ├── QuoteFilters.jsx    → 109 líneas. Filtros rápidos.
│   │   ├── QuotesTable.jsx     → 197 líneas. Tabla con acciones.
│   │   └── PdfPreviewModal.jsx → 43 líneas. Preview PDF.
│   ├── MultiProductSelector.jsx
│   ├── AnexosModal.jsx
│   ├── EquipmentQuoteWizard.jsx
│   └── WorkflowUploadModal.jsx
```

## Funcionalidades Implementadas

### Modulos Core
1. Autenticacion: Registro/Login, roles (admin/user), sedes (TBP/LCH)
2. Gestion de Clientes: Multi-sede, contactos, bitacora, importacion Excel, RIF Digital
3. Bancos y Medios de Pago: CRUD con productos, gateway_available flag
4. Integradores: Gestion, filtro por modalidad PG
5. Hardware: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. Tipos: VPOS/MPOS, Payment Gateway, Equipos
7. Nomenclatura: COT-AAAA-MM-NNN-SEDE atomica
8. Anexos y Workflow de Estados
9. Dashboard con alertas, stats y alertas de PDFs faltantes

### PDF y Previsualizacion
- PDF VPOS dinamico + paginas anexo estatico
- PDF PG 4 paginas: Portada, Matriz Configuracion, Recurrentes, T&C
- Regeneracion de PDFs faltantes (individual y batch)

### Selector Multivariable (2026-03-05)
- MultiProductSelector: dropdown con checkboxes, busqueda, "Seleccionar Todo"

### Dashboard Alertas PDFs Faltantes (2026-03-06)
- GET /api/dashboard/missing-pdfs: detecta cotizaciones sin PDF
- POST /api/quotes/{id}/regenerate-pdf: regenera PDF individual
- Widget en Dashboard con "Regenerar" y "Regenerar Todos"

### Refactorizacion Backend (2026-03-06)
- server.py 7375 -> 77 lineas. 16 archivos modulares.

### Refactorizacion Frontend (2026-03-06)
- Quotes.jsx 4444 -> 4043 lineas
- Extraidos: QuoteFilters, QuotesTable, PdfPreviewModal

## Pendientes
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Modulo de Reportes
- P2: Seguir descomponiendo Quotes.jsx (el dialog wizard es aun grande)
