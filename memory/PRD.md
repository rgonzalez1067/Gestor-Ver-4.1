# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Cotizaciones
- RBAC con `special_permissions`
- Flujo de excepción para pasos saltados
- Fast Track completo con Prerregistro de Seriales
- Badge de Iniciales del Creador
- PDF con Header/Footer Persistente (ReportLab overlay)
- Buscador Dinámico de Clientes (server-side)
- **Total USD = Solo Inversión Inicial**: Columna y almacenamiento muestra Setup + Equipos, excluyendo recurrentes. Etiqueta "Excl. Recurrentes" (Abr 2026)
- **PDF Versionado al Modificar**: Al duplicar, `attachments` y `quote_pdf_url` se limpian. Nuevo PDF se genera automáticamente vía `POST /quotes/{id}/regenerate-pdf` y se registra en Anexos (Abr 2026)
- **Backend: total_usd solo Setup+Equipment**: `create-with-pdf` calcula total_usd excluyendo recurring items (Abr 2026)

### Clientes
- Bitácora de gestiones por cliente (Fix endpoint `/logs` — Abr 2026)
- Importación desde Excel/CSV

### Integradores
- Importación masiva con matriz de 20 productos de certificación
- Fix parseo datetime de Excel y mapping `Categoria` sin tilde (Abr 2026)

### Medios de Pago (Servicios)
- Modelo `Service` con campos opcionales: category, tipo_corp, order, is_active
- Acceso defensivo para `created_at` en todos los endpoints

### Autenticación
- SHA256 con salt (NO bcrypt)
- Recuperación y Reset de Contraseña
- Verificación de Email

### Gestión de Usuarios, Bancos, Inventario, Proyectos, Pipeline
- (Ver PRD anterior para detalles completos)

## Archivos Clave
- `/app/backend/routes/quotes.py` — Creación, update, regenerate-pdf, PDF generation
- `/app/backend/routes/quote_actions.py` — Duplicate, status flow, email
- `/app/frontend/src/pages/Quotes.jsx` — Cotizaciones (handleSaveEditedQuote con PDF auto)
- `/app/frontend/src/components/quotes/QuotesTable.jsx` — Display Total USD (setup-only)
- `/app/frontend/src/pages/Clients.jsx` — Clientes y bitácora
- `/app/backend/routes/integrators.py` — Integradores con importación
- `/app/backend/routes/services.py` — Medios de Pago
- `/app/backend/routes/banks.py` — Bancos

## Backlog

### P1 (Próximos)
- Sistema de Notificaciones Push (campana con contador) + alertas en tiempo real

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
