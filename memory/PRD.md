# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Funcionalidades clave: generación de PDFs, extracción de datos de RIF mediante OCR, correos de notificación por sede, selector de productos múltiple, gestión de clientes con bitácora, módulo de proyectos post-venta con matriz de implementación.

## Arquitectura
- **Backend**: FastAPI + MongoDB (motor async) - Arquitectura modular (routes/, services/, models.py, config.py)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **OCR**: pytesseract + pdf2image
- **PDF**: reportlab + PyPDF2
- **Email**: Resend (modo simulado activo)
- **Imágenes**: Pillow (PIL) para resize de logos

## Funcionalidades Implementadas

### Core
- CRUD de clientes con validación RIF+Sucursal, campos Dirección Sucursal, Categoría Comercial
- CRUD de cotizaciones con asistente multi-paso, selector multivariable de productos
- Generación de PDFs complejos, alertas de PDFs faltantes
- Sistema de correos por sede (modo simulado)
- Dashboard con estadísticas, alertas y KPI de proyectos
- Importación/exportación de clientes (Excel, CSV, PDF)
- Bitácora de seguimiento por cliente
- Digitalización RIF (OCR PDF/JPG/PNG, 3 estrategias de extracción)

### Módulo de Bancos (Rediseñado 2026-03-07)
- **Layout horizontal**: Filas con 4 bloques (Logo, Info Fiscal, Chips Medios de Pago, Contacto+Acciones)
- **Upload de Logo**: Drag & drop + click, auto-resize a 100x100px (PIL), almacenamiento local
- **Información Fiscal**: Campos RIF y Código Bancario
- **Contacto Institucional**: Nombre, Teléfono, Email
- **Chips de Medios de Pago**: Badges visuales de servicios activos por banco
- **CRUD completo**: Crear, editar, eliminar con validación de integridad referencial
- **Import/Export**: CSV/Excel/PDF

### Módulo de Proyectos (Completado)
- Trigger: Cotización "Enviada a Imple" → crea Proyecto
- Matriz de Implementación: Construida desde items `additional` (medios de pago por banco)
- Bitácora de Seguimiento, 4 estados, prioridades, asignación

### Dashboard KPI de Proyectos (Completado 2026-03-07)
- Card "Proyectos Activos" con desglose por estado

## Lógica de Negocio Clave

### Tipos de items en una cotización:
| item_type | Descripción | En Matriz? |
|-----------|-------------|------------|
| setup | Costos de configuración fijos | NO |
| recurring_basic (default) | Derechos de uso MServer | NO |
| recurring_basic (auto-linked) | Recurrentes vinculados | NO |
| recurring_other | Comunicación/Procesamiento | NO |
| **additional** | **Medios de pago por banco** | **SÍ** |

## Endpoints Clave
- `POST /api/banks/upload-logo` - Upload de logo con resize
- `POST /api/projects/migrate-matrix` - Migración de matrices
- `GET /api/projects/stats` - KPIs de proyectos
- `POST /api/quotes/{id}/send-to-implementation` - Trigger de proyectos

## Tareas Pendientes

### P1 - Próximas
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend Fase 2: Descomponer `Quotes.jsx`

### P2 - Futuro
- Módulo de Reportes (ventas y cotizaciones)
- Lógica de roles por módulo

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
- BD volátil: registrar usuario al inicio de cada sesión
