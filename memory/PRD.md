# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Sistema full-stack para gestión completa de cotizaciones con múltiples módulos CRUD, generación de PDF, sistema multi-sede, y gestión de usuarios.

## Stack Tecnológico
- **Backend:** FastAPI + MongoDB (Motor async)
- **Frontend:** React + Shadcn/UI + Tailwind CSS
- **PDF:** reportlab + PyPDF2
- **Auth:** JWT sessions con hash de contraseñas

## Módulos Implementados

### Completados
- [x] Autenticación JWT (login/registro con sedes)
- [x] CRUD completo (Clientes, Bancos, Bienes/Servicios, Integradores, Medios Pago, Hardware)
- [x] Gestión de Cotizaciones con ciclo de vida completo
- [x] Generador de PDF dinámico con reportlab
- [x] Importación/Exportación Excel (todos los módulos)
- [x] Sistema Multi-Sede (TBP/LCH)
- [x] Gestión de Usuarios Pro
- [x] Módulo Anexos con 5 categorías
- [x] Flujo de Estados Basado en Evidencias (25/Feb/2026)
- [x] Módulo Clientes & CRM Evolucionado (25/Feb/2026)
  - Multi-sede (RIF+Sucursal), Contactos dinámicos con roles, Bitácora, Dashboard Alertas
- [x] Importación de Clientes mejorada (25/Feb/2026)
  - Plantilla Excel descargable (3 hojas: Plantilla, Instrucciones, Valores Válidos)
  - Validación RIF+Sucursal, soporte contactos CRM, resultados detallados por fila

## Pendiente / Backlog

### P1 - Alta Prioridad
- [ ] Bug: Contadores del Dashboard (parcialmente resuelto)
- [ ] Verificar funcionalidad "Guardar con PDF" end-to-end
- [ ] Verificación de email al registrarse (requiere API Key Resend)
- [ ] Recuperación de contraseña (requiere API Key Resend)
- [ ] **Refactorización backend/server.py** (CRÍTICO - 6000+ líneas)

### P2 - Media Prioridad
- [ ] Refactorización frontend (Settings.jsx, Users.jsx, Quotes.jsx)
- [ ] Módulo de Reportes avanzados

## Credenciales de Prueba
- Email: test_anexos@test.com / Password: Test1234! (admin)

## Test Reports
- iteration_42: Anexos module (15/15)
- iteration_43: Workflow state transitions (14/14)
- iteration_44: CRM evolution (11/11)
- iteration_45: Client import (13/13)
