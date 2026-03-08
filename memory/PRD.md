# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Funcionalidades clave: generación de PDFs, OCR de RIF, correos por sede, selector de productos, gestión de clientes, módulo de proyectos post-venta con matriz de implementación.

## Arquitectura
- **Backend**: FastAPI + MongoDB (motor async) - routes/, services/, models.py, config.py
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **OCR**: pytesseract + pdf2image
- **PDF**: reportlab + PyPDF2
- **Email**: Resend (modo simulado)
- **Imágenes**: Pillow (PIL) para resize de logos

## Funcionalidades Implementadas

### Core
- CRUD de clientes con validación RIF+Sucursal
- CRUD de cotizaciones con asistente multi-paso
- Generación de PDFs, alertas de PDFs faltantes
- Dashboard con KPIs, alertas y proyectos
- Import/Export (Excel, CSV, PDF)
- Bitácora por cliente, OCR de RIF

### Módulo de Bancos — Visor 360° (Implementado 2026-03-08)
- **Lista horizontal**: Logo, Info Fiscal, Chips Medios de Pago, Contacto+Acciones
- **Contadores**: `[X Activos | Y en Integración]` por banco
- **Upload de Logo**: Drag & drop, resize 100x100px
- **Info Fiscal**: RIF, Código Bancario
- **Contacto**: Nombre, Teléfono, Email
- **Pantalla Detalle** (`/banks/:bankId`):
  - Sección A: Medios de Pago Activos VPOS/MPOS
  - Sección B: Medios de Pago Activos PG/Link
  - Sección C: Roadmap de Integraciones en Curso
- **Gestión de Integraciones**:
  - CRUD completo (agregar, editar status, eliminar)
  - Flujo de estados: Negoc. → DESA → SQA → Imple. → PreProd → Completado
  - Pipeline visual con dots de progreso
  - Dropdown de servicio (tipo Producto) + componente (VPOS/MPOS o PG/Link)

### Módulo de Medios de Pago
- Campo "Tipo" obligatorio: Producto / Servicio
- Badges visuales (naranja/cyan)

### Módulo de Proyectos
- Trigger desde cotizaciones, Matriz con items `additional`
- Bitácora, estados, prioridades, asignación

### Dashboard KPI
- Proyectos Activos con desglose por estado

## Endpoints Clave
- `GET /api/banks/{id}/detail` - Detalle 360° del banco
- `POST /api/banks/{id}/integrations` - Nueva integración
- `PUT /api/banks/{id}/integrations/{int_id}` - Actualizar status
- `DELETE /api/banks/{id}/integrations/{int_id}` - Eliminar integración
- `POST /api/banks/upload-logo` - Upload de logo
- `GET /api/projects/stats` - KPIs de proyectos

## Tareas Pendientes

### P1 - Próximas
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend Fase 2: Descomponer `Quotes.jsx`

### P2 - Futuro
- Módulo de Reportes (ventas y cotizaciones)
- Lógica de roles por módulo
- Al marcar integración "Completado", sugerir crear ítem en tabla de Medios de Pago

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
- BD volátil: registrar usuario al inicio de cada sesión
