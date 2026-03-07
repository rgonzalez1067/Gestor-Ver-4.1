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
- Dashboard con estadísticas, alertas y KPI de proyectos
- Importación/exportación de clientes (Excel, CSV, PDF)
- Bitácora de seguimiento por cliente
- Digitalización RIF (OCR PDF/JPG/PNG, 3 estrategias de extracción)

### Módulo de Proyectos (Completado)
- **Trigger**: Cotización "Enviada a Imple" → crea Proyecto, elimina cotización
- **Nomenclatura**: PRY-YYYY-MM-NNN-SEDE (ej: PRY-2026-03-001-PRI)
- **4 estados**: Pendiente por Asignar → Asignado/En Proceso → Detenido → Finalizado
- **Prioridad**: Alta, Media, Normal
- **Asignación**: Selección de implementador + fecha estimada + notificación por email
- **Anexos**: Herencia automática de archivos de la cotización al proyecto
- **Matriz de Implementación (CORREGIDA 2026-03-07)**: Construida EXCLUSIVAMENTE desde items `additional` (medios de pago seleccionados por banco). NO incluye defaults recurrentes (Derecho de uso MServer, Comunicación Backend, Procesamiento).
- **Bitácora de Seguimiento**: Entradas con fecha de ejecución y observaciones
- **Endpoint de migración**: POST /api/projects/migrate-matrix para reconstruir matrices existentes

### Dashboard KPI de Proyectos (Completado 2026-03-07)
- Card "Proyectos Activos" con desglose por estado (Por Asignar, En Proceso, Detenidos, Finalizados)
- Clickeable para navegar a /projects
- Consume endpoint `/api/projects/stats`

## Lógica de Negocio Clave

### Tipos de items en una cotización:
| item_type | Descripción | En Matriz? |
|-----------|-------------|------------|
| setup | Costos de configuración fijos | NO |
| recurring_basic (default) | Derechos de uso MServer | NO |
| recurring_basic (auto-linked) | Recurrentes vinculados | NO |
| recurring_other | Comunicación/Procesamiento | NO |
| **additional** | **Medios de pago por banco** | **SÍ** |

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
