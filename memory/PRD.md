# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Arquitectura Backend (Refactorizado 2026-03-06)
```
backend/
├── server.py              → 77 líneas. Init FastAPI + montar routers.
├── config.py              → 179 líneas. DB, auth, PDF helpers, render_email_template.
├── models.py              → 536 líneas. Todos los modelos Pydantic.
├── routes/
│   ├── auth.py, clients.py, dashboard.py, banks.py, hardware.py,
│   ├── services.py, quotes.py, quote_actions.py, attachments.py,
│   ├── integrators.py, settings.py, seed_and_templates.py
├── services/
│   ├── pdf_generator.py   → 1079 líneas. DynamicQuotePDFGenerator.
│   └── email_service.py   → Servicio email unificado con fallback simulado.
└── uploads/
```

## Funcionalidades Implementadas

### Modulos Core
1. Autenticacion, Clientes, Bancos, Integradores, Hardware, Medios de Pago
2. Dashboard con stats, alertas, PDFs faltantes

### Sistema de Cotizaciones
- Tipos: VPOS/MPOS, Payment Gateway, Equipos
- Nomenclatura atomica, Anexos, Workflow de Estados completo
- Selector Multivariable de Productos (2026-03-05)

### Motor de Correos Simulados (2026-03-06)
- services/email_service.py: intenta Resend, si falla -> modo simulado en BD
- Todas las acciones (send-to-client, approve, invoice, collect, send-to-implementation) usan send_email()
- GET /api/email-logs: historial de correos
- Panel en Settings: tabla con estado, acción, destinatario, asunto, cotización, fecha
- render_email_template: soporta {key}, #{key}, {{key}}
- Flujo completo probado: Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Enviada a Imple

### Refactorizaciones (2026-03-06)
- Backend: server.py 7375 -> 77 líneas (16 módulos)
- Frontend: Quotes.jsx 4444 -> 4043 líneas (3 componentes extraídos)

## Pendientes
- P1: Verificación Email / Recuperación Contraseña
- P2: Módulo de Reportes
- P2: Seguir descomponiendo Quotes.jsx
