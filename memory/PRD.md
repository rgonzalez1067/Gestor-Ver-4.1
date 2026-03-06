# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Funcionalidades clave: generación de PDFs, extracción de datos de RIF mediante OCR, correos de notificación por sede, selector de productos múltiple, gestión de clientes con bitácora, módulo de proyectos post-venta.

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

### Digitalización RIF (Completado)
- Parseo OCR (PDF/JPG/PNG) con fallback OCR automático para PDFs escaneados
- Actualización de cliente (RIF, razón social, dirección) con comparación de datos
- Archivo y descarga de documento RIF
- Parser con 3 estrategias de extracción + corrección de errores OCR

### Módulo de Proyectos (Completado - 2026-03-06)
- **Trigger automático**: Al cambiar cotización a "Enviada a Imple" → clonación inteligente a colección Proyectos
- **Datos heredados**: Cliente, RIF, Sede, Productos, Bancos, PDF de cotización
- **4 estados**: Pendiente por Asignar → Asignado/En Proceso → Detenido por Cliente/Banco → Finalizado/Producción
- **Asignación**: Gerente selecciona implementador + fecha estimada de entrega
- **Notificaciones**: Email automático al gerente de implementación (al crear proyecto) y al implementador (al asignarse)
- **Notas**: Sistema de notas con historial y notas automáticas por cambio de estado
- **Prioridad**: 4 niveles (Baja, Normal, Alta, Urgente)
- **Configuración**: Campo "Correo Gerente de Implementación" en pantalla de Settings
- **Frontend**: Tabla expandible con detalle de cotización, productos, bancos y notas

### Gestión de Usuarios
- Campos Cargo (13 opciones dropdown) y Departamento (6 opciones)
- Campos en ficha de cliente: Dirección de Sucursal, Categoría Comercial (30 categorías)
- Contactos fusionados: campo único "Nombre y Apellidos"

### Refactorización
- Backend refactorizado de monolito a arquitectura modular
- Frontend parcialmente refactorizado

## Tareas Pendientes

### P1 - Próximas
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend Fase 2: Descomponer `Quotes.jsx`

### P2 - Futuro
- Módulo de Reportes (ventas y cotizaciones)
- Lógica de roles en Proyectos (Ventas: solo lectura, Gerente Impl: asignar, Implementador: actualizar)

## Schema DB Relevante
- **projects**: `{ project_id, project_number, quote_id, quote_number, client_id, client_name, client_rif, client_sede, status, assigned_to_user_id, assigned_to_name, estimated_delivery_date, priority, notes[], services[], banks[], total_usd, created_at }`
- **clients**: `{ client_id, rif, legal_name, branch_address, categoria_comercial, contacts[{full_name, phone, email, role}] }`
- **simulated_emails**: `{ subject, to, body, status, quote_id, created_at }`

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
- BD volátil: registrar usuario al inicio de cada sesión
