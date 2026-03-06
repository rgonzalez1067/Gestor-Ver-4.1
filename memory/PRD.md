# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Funcionalidades clave: generación de PDFs, extracción de datos de RIF mediante OCR, correos de notificación por sede, selector de productos múltiple, gestión de clientes con bitácora.

## Arquitectura
- **Backend**: FastAPI + MongoDB (motor async) - Arquitectura modular (routes/, services/, models.py, config.py)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **OCR**: pytesseract + pdf2image (Tesseract con soporte español)
- **PDF**: reportlab + PyPDF2
- **Email**: Resend (modo simulado activo)

## Funcionalidades Implementadas

### Core
- CRUD de clientes con validación RIF+Sucursal
- CRUD de cotizaciones con asistente multi-paso
- Generación de PDFs complejos para cotizaciones
- Sistema de correos por sede (modo simulado)
- Dashboard con estadísticas y alertas
- Importación/exportación de clientes (Excel, CSV, PDF)
- Bitácora de seguimiento por cliente
- Selector multivariable de productos
- Alertas y regeneración de PDFs faltantes

- **Digitalización RIF**: Parseo OCR (PDF/JPG/PNG), actualización de cliente (RIF, razón social, **dirección**), archivo de documento, descarga

## Tareas Pendientes

### P0 - Ninguna

### P1 - Próximas
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend Fase 2: Descomponer asistente de Quotes.jsx en QuoteFormDialog, QuoteFormHeader, VPOSSection, PGSection

### P2 - Futuro
- Módulo de Reportes (ventas y cotizaciones)

## Schema DB Relevante
- **clients**: `{ client_id, rif, legal_name, fantasy_name, segment, address, sucursal, contacts[], rif_document_url?, rif_document_filename?, rif_updated_at?, rif_updated_by? }`
- **simulated_emails**: `{ subject, to, body, status, quote_id, created_at }`

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
- BD volátil: registrar usuario al inicio de cada sesión

## Notas
- Servicio de correo intencionalmente en modo simulado (logs en BD, visible en Configuración)
- Idioma de comunicación: Español
