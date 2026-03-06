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

### Digitalización RIF (Completado - 2026-03-06)
- **Parseo de RIF**: Extracción OCR de datos desde PDF, JPG, PNG (`POST /api/clients/parse-rif`)
- **Actualización de cliente desde RIF**: Escanea documento, actualiza datos y archiva archivo (`POST /api/clients/{id}/update-from-rif`)
- **Descarga de RIF archivado**: Permite descargar el documento RIF del expediente digital (`GET /api/clients/{id}/rif-document`)
- **Frontend**: Botón de escaneo RIF por cliente en tabla, diálogo de actualización con comparación de datos, botón de descarga para clientes con RIF archivado
- **Testing**: 100% backend (16/16 tests) y frontend verificados

### Refactorización
- Backend refactorizado de monolito a arquitectura modular (routes/, services/)
- Frontend parcialmente refactorizado (QuoteFilters, QuotesTable, MultiProductSelector extraídos)

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
