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
- **Vinculación Logística en "Enviar a Implementación"**
- **Flujo Transaccional Seguro (Fix P0 — Feb 2026)**
- **Flujo Extendido PYME (Feb 2026)**
- **Motor de Reemplazo de Variables ROBUSTO** (19 variables dinámicas)
- **Editor de Envío Final**: Editable con soporte de imágenes (Object Storage)
- **VTIDs por Sucursal**
- **Notificaciones Secuenciales**
- **Asignación Simplificada** + Candado de Seguridad

### Cotizaciones
- RBAC con `special_permissions`
- Flujo de excepción para pasos saltados
- Fast Track completo con Prerregistro de Seriales

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
- Endpoint ejecutivos filtrado por departamento (Ventas Pyme/Corporativas)

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/routes/quote_actions.py`
- `/app/backend/routes/auth.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/object_storage.py`
- `/app/backend/services/implementation_pdf.py`
- `/app/backend/models.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Quotes.jsx`
- `/app/frontend/src/pages/UserManagement.jsx`
- `/app/frontend/src/pages/Inventory.jsx`

## Historial Reciente
- **Abr 2026**: Actualización de Cargos y Departamentos:
  - Cargos simplificados de 13 a 9 opciones genéricas
  - 3 departamentos nuevos: Desarrollo, Aseguramiento de Calidad, Operaciones
  - 12 usuarios activos con cargos reasignados
  - Endpoint `/api/auth/ejecutivos` migrado a filtro por departamento
  - 9 usuarios eliminados (TEST, duplicados, obsoletos)

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5800+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
