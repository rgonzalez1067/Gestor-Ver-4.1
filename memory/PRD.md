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
- CRUD de clientes con validación RIF+Sucursal, Dirección Sucursal, Categoría Comercial
- CRUD de cotizaciones con asistente multi-paso, selector multivariable de productos
- Generación de PDFs, alertas de PDFs faltantes
- Sistema de correos por sede (modo simulado)
- Dashboard con estadísticas, alertas y KPI de proyectos
- Importación/exportación de clientes (Excel, CSV, PDF)
- Bitácora de seguimiento por cliente
- Digitalización RIF (OCR PDF/JPG/PNG)

### Módulo de Bancos (Rediseñado 2026-03-07)
- Layout horizontal: Logo, Info Fiscal (RIF, Código), Chips Medios de Pago, Contacto+Acciones
- Upload de Logo: Drag & drop, auto-resize 100x100px
- Contacto Institucional: Nombre, Teléfono, Email

### Módulo de Medios de Pago (Actualizado 2026-03-07)
- **Campo "Tipo" (Producto/Servicio)**: Categorización obligatoria
  - Producto: Tangible, requiere despacho (Pinpads, Cables)
  - Servicio: Intangible (Mantenimiento, Licencia, Instalación)
- Badge visual en tabla (naranja=Producto, cyan=Servicio)
- Selector visual en formulario con iconos y descripción

### Módulo de Proyectos
- Trigger: Cotización "Enviada a Imple" → crea Proyecto
- Matriz de Implementación: Items `additional` (medios de pago por banco)
- Bitácora, 4 estados, prioridades, asignación

### Dashboard KPI
- Card "Proyectos Activos" con desglose por estado

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
