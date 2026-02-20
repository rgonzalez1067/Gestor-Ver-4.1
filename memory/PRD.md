# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago.

## Estado Actual: MVP Operativo ✅

---

## Diagnóstico de Problemas Reportados - 20 Febrero 2026

### Problema Reportado:
- "Aprobar" y "Cobrar" no actualizan el estado
- "Eliminar" no funciona
- Botones visibles pero sin acción

### Causa Raíz Identificada: **SESIÓN EXPIRADA**
Los tokens de sesión del usuario ya no existían en la base de datos, causando errores 401 silenciosos.

### Solución:
1. **Para el usuario**: Cerrar sesión y volver a iniciar sesión con Google
2. **Mejoras implementadas**: 
   - Mejor manejo de errores 401 en el frontend
   - Mensajes claros cuando la sesión expira
   - Modales de confirmación estandarizados

### Verificación:
- Backend: 14/14 tests PASSED ✅
- Endpoints POST /approve, POST /collect, DELETE funcionan correctamente
- Requiere sesión válida (Bearer token)

---

## Flujo de Estados (Completo)

```
Borrador → Enviada → Aprobada (email admin) → 
Facturada (PDF req.) → Pagada → Enviada a Imple (email implementación)
```

| Acción | Estado Requerido | Estado Resultante | Notificación |
|--------|------------------|-------------------|--------------|
| Enviar al Cliente | Borrador | Enviada | Email cliente |
| Aprobar | Enviada | Aprobada | Email admin |
| Facturar | Aprobada | Facturada | - |
| Cobrar | Facturada | Pagada | Email almacén (equipos) |
| Enviar a Imple | Pagada | Enviada a Imple | Email implementación |

---

## Modales de Confirmación Estandarizados

Todos los CRUDs ahora tienen el mensaje:
> "¿Está seguro de que desea eliminar este [Registro] de forma permanente?
> Esta acción no se puede deshacer."

Registros actualizados:
- Cotización
- Banco
- Cliente
- Dispositivo
- Integrador
- Medio de Pago

---

## Backlog

### P2 - Media Prioridad
- [ ] Contadores del Dashboard
- [ ] Refactorización del código

---

## Testing Status
- Backend: 100% (14/14 tests) ✅
- Test report: `/app/test_reports/iteration_26.json`

---
**Última actualización:** 20 Febrero 2026
**Estado:** MVP Operativo - Flujo de Estados Verificado ✅
