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
- Endpoint ejecutivos filtrado por departamento
- **Super Poder Admin**: Eliminación permanente de usuarios (`DELETE /api/admin/users/{user_id}`) con AlertDialog de confirmación, protección contra auto-eliminación (Abr 2026)

### Autenticación (P1 — Abr 2026)
- **Recuperación de Contraseña**:
  - `POST /api/auth/forgot-password` — genera token (1h expiración), envía email con enlace
  - `POST /api/auth/reset-password` — valida token, actualiza hash, invalida sesiones previas
  - Mensaje genérico (no revela si email existe)
  - Tokens de un solo uso almacenados en `password_reset_tokens`
- **Verificación de Email**:
  - Token enviado automáticamente al registrarse
  - `POST /api/auth/verify-email` — marca `is_verified=true`
  - `POST /api/auth/resend-verification` — reenvía email (requiere auth)
  - Tokens almacenados en `email_verification_tokens`
- **Frontend**:
  - Modo "Recuperar Contraseña" en Auth.jsx con formulario de email
  - `/reset-password?token=xxx` — formulario nueva contraseña + confirmación
  - `/verify-email?token=xxx` — verificación automática por token
- **Admin**:
  - `POST /admin/users/{id}/reset-password` — genera y envía enlace de reset

## Archivos Clave
- `/app/backend/routes/auth.py` — Auth completo (login, register, forgot, reset, verify)
- `/app/backend/routes/projects.py`
- `/app/backend/routes/quote_actions.py`
- `/app/backend/models.py`
- `/app/frontend/src/pages/Auth.jsx`
- `/app/frontend/src/pages/ResetPassword.jsx`
- `/app/frontend/src/pages/VerifyEmail.jsx`
- `/app/frontend/src/pages/Quotes.jsx`
- `/app/frontend/src/pages/UserManagement.jsx`
- `/app/frontend/src/pages/Inventory.jsx`
- `/app/frontend/src/App.js` — Rutas /reset-password y /verify-email

## Backlog

### P1 (Próximos)
- Refactorización de `Quotes.jsx` (5800+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+, `quote_actions.py` 2600+)
