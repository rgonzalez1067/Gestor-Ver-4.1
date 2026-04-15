# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- Vinculación Logística en "Enviar a Implementación"
- Flujo Transaccional Seguro (Fix P0 — Feb 2026)
- Flujo Extendido PYME (Feb 2026)
- Motor de Reemplazo de Variables ROBUSTO (19 variables dinámicas)
- Editor de Envío Final con soporte de imágenes (Object Storage)
- VTIDs por Sucursal, Notificaciones Secuenciales
- Asignación Simplificada + Candado de Seguridad

### Cotizaciones
- RBAC con `special_permissions`
- Flujo de excepción para pasos saltados
- Fast Track completo con Prerregistro de Seriales
- **Badge de Iniciales del Creador**: Muestra iniciales del usuario que generó la cotización junto al segmento, con tooltip del nombre completo (Abr 2026)
- **PDF con Header/Footer Persistente**: Encabezado con logo, número de cotización y fecha; pie con "Documento Confidencial - Propiedad de Mega Soft Computación C.A." y "Página X" (Abr 2026)
- **Buscador Dinámico de Clientes**: Búsqueda server-side por RIF y razón social (Abr 2026)
- **Total USD = Solo Inversión Inicial**: Columna muestra Setup + Equipos, excluyendo recurrentes (Abr 2026)
- **PDF Versionado al Modificar**: Al duplicar/editar cotización, el pdf_url se limpia para evitar referencia al PDF original (Abr 2026)

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

### Inventario
- FIFO basado en Fecha de Adquisición
- Costo Ponderado
- Estados de Hardware: Disponible → Preasignado → Asignado

### Gestión de Usuarios
- Cargos simplificados: Director, Gerente, Coordinador, Analista, Asistente, Tecnico, Desarrollador, Implementador, Ejecutivo
- Departamentos: Desarrollo, Aseguramiento de Calidad, Implementación, Infraestructura, Operaciones, Dirección, Ventas Pyme, Ventas Corporativas, Administración
- **Super Poder Admin**: Eliminación permanente de usuarios (Abr 2026)

### Autenticación (P1 — Abr 2026)
- Recuperación y Reset de Contraseña
- Verificación de Email
- Hash SHA256 con salt (NO bcrypt)

### Clientes
- Bitácora de gestiones por cliente (Abr 2026 — Fix endpoint `/logs`)
- Importación desde Excel/CSV

### Integradores
- Importación masiva con matriz de 20 productos de certificación
- Campos Categoria y Ultimo Contacto (Fix parseo datetime de Excel — Abr 2026)
- Mapping case-insensitive para columnas sin acentos (Abr 2026)

### Medios de Pago (Servicios)
- Modelo `Service` con campos opcionales: category, tipo_corp, order, is_active (Fix Abr 2026)
- Acceso defensivo para `created_at` en todos los endpoints (Fix Abr 2026)

## Archivos Clave
- `/app/backend/routes/auth.py` — Auth completo
- `/app/backend/routes/quote_actions.py` — Lógica de cotizaciones
- `/app/backend/routes/clients.py` — Clientes y bitácora
- `/app/backend/routes/integrators.py` — Integradores con importación
- `/app/backend/routes/services.py` — Medios de Pago
- `/app/backend/routes/banks.py` — Bancos
- `/app/frontend/src/pages/Quotes.jsx` — Cotizaciones
- `/app/frontend/src/components/quotes/QuotesTable.jsx` — Tabla de cotizaciones
- `/app/frontend/src/pages/Clients.jsx` — Clientes

## Backlog

### P1 (Próximos)
- Sistema de Notificaciones Push (campana con contador) + alertas en tiempo real

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
