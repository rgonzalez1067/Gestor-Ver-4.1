# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft).

## Arquitectura
- **Backend**: FastAPI + MongoDB (motor async) - routes/, services/, models.py, config.py
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **OCR**: pytesseract + pdf2image | **PDF**: reportlab + PyPDF2
- **Email**: Resend (modo simulado) | **Imágenes**: Pillow (PIL)

## Funcionalidades Implementadas

### Core
- CRUD clientes, cotizaciones, medios de pago, bancos
- Generación de PDFs, OCR de RIF, Dashboard con KPIs
- Import/Export (Excel, CSV, PDF), Bitácora por cliente

### Módulo de Bancos — Visor 360°
- Lista horizontal: Logo (150x150), Info Fiscal, Chips, Contacto+Acciones
- Contadores `[X Activos | Y en Integración]`
- Upload de Logo: Drag & drop, resize 150x150px, hover Cambiar/Eliminar
- Toggles de Componentes: VPOS, MPOS, PG, Link clickeables por producto por banco
- Pantalla Detalle `/banks/:bankId`: Secciones VPOS/MPOS, PG/Link, Roadmap Integraciones
- Gestión de Integraciones: CRUD, flujo Negoc. → DESA → SQA → Imple. → PreProd → Completado

### Reporte Global de Integraciones (Implementado 2026-03-08)
- Ruta: `/banks/integrations/report`
- Endpoint: `GET /api/banks/integrations/report` (consolidado de todas las integraciones)
- Tabla: Banco, Producto, Componente, Fase (Estatus), Notas
- Cards de resumen por fase con semáforo (gris, azul, amarillo, verde)
- Filtro por fase (dropdown + click en cards)
- Ordenado por fase más avanzada primero (PreProd → SQA → DESA → Negoc.)
- Click en fila navega al detalle del banco
- Botón de acceso prominente en página de Bancos

### Módulo de Medios de Pago
- Campo "Tipo" obligatorio: Producto / Servicio

### Módulo de Proyectos
- Trigger desde cotizaciones, Matriz con items `additional`

### Dashboard KPI
- Proyectos Activos con desglose por estado

## Tareas Pendientes

### P1
- Verificación de Email y Recuperación de Contraseña
- Refactorización Frontend: Descomponer `Quotes.jsx`

### P2
- Módulo de Reportes
- Lógica de roles por módulo
- Al completar integración, sugerir crear ítem en Medios de Pago

## Credenciales de Prueba
- Email: rgonzalez@megasoft.com.ve / Contraseña: Avila*0226*02
