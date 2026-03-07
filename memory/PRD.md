# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Funcionalidades clave: generación de PDFs, extracción de datos de RIF mediante OCR, correos de notificación por sede, selector de productos múltiple, gestión de clientes con bitácora, módulo de proyectos post-venta con matriz de implementación.

## Arquitectura
- **Backend**: FastAPI + MongoDB (motor async) - Arquitectura modular (routes/, services/, models.py, config.py)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **OCR**: pytesseract + pdf2image
- **PDF**: reportlab + PyPDF2
- **Email**: Resend (modo simulado activo)

## Funcionalidades Implementadas

### Core
- CRUD de clientes con validación RIF+Sucursal, campos Dirección Sucursal, Categoría Comercial
- CRUD de cotizaciones con asistente multi-paso, selector multivariable de productos
- Generación de PDFs complejos, alertas de PDFs faltantes
- Sistema de correos por sede (modo simulado)
- Dashboard con estadísticas y alertas
- Importación/exportación de clientes (Excel, CSV, PDF)
- Bitácora de seguimiento por cliente
- Digitalización RIF (OCR PDF/JPG/PNG, 3 estrategias de extracción)

### Módulo de Proyectos (Completado - 2026-03-07)
- **Trigger**: Cotización "Enviada a Imple" → crea Proyecto, elimina cotización
- **Nomenclatura**: PRY-YYYY-MM-NNN-SEDE (ej: PRY-2026-03-001-PRI)
- **4 estados**: Pendiente por Asignar → Asignado/En Proceso → Detenido → Finalizado
- **Prioridad**: Alta, Media, Normal (dropdown inline en tabla)
- **Asignación**: Selección de implementador + fecha estimada + notificación por email
- **Anexos**: Herencia automática de archivos de la cotización al proyecto
- **Matriz de Implementación**: Bancos × Productos × 5 fases (Notificado, Recibido, Configurado, Testeado, En Producción) con checkboxes interactivos
- **Bitácora de Seguimiento**: Entradas con fecha de ejecución y observaciones
- **Configuración**: Campo "Correo Gerente de Implementación" en Settings
- **Detalle**: Pantalla separada `/projects/:id` con cabecera técnica (Pinpad, Banco Patrocinador)

## Tareas Pendientes

### P1 - Próximas
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend Fase 2: Descomponer `Quotes.jsx`
- Lógica de roles por módulo (Ventas solo lectura, Gerente asigna, Implementador actualiza)

### P2 - Futuro
- Módulo de Reportes (ventas y cotizaciones)

## Schema DB
- **projects**: `{ project_id, project_number, quote_id, client_id, client_name, client_rif, client_sede, status, priority, assigned_to_*, implementation_matrix: {bank: {product: {phase: {completed, updated_at}}}}, attachments[], bitacora[], notes[], services[], banks[], pinpad_model, sponsor_bank_name }`
- **clients**: `{ client_id, rif, legal_name, branch_address, categoria_comercial, contacts[{full_name}] }`

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
- BD volátil: registrar usuario al inicio de cada sesión
