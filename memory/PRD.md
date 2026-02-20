# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago.

## Estado Actual: MVP Operativo ✅

---

## CORRECCIÓN CRÍTICA - 20 Diciembre 2025

### Problema Reportado (P0 - CRÍTICO):
- Las acciones del menú dropdown (Aprobar, Cobrar, Eliminar, Enviar al Cliente, Facturar) no funcionaban al hacer clic
- El usuario reportaba que los botones eran visibles pero no ejecutaban ninguna acción

### Causa Raíz Identificada: **USO INCORRECTO DE EVENTO EN RADIX UI**
Los componentes `DropdownMenuItem` de Radix UI/Shadcn utilizan `onSelect` en lugar de `onClick` para manejar eventos de selección. El código usaba `onClick` que era ignorado silenciosamente.

### Solución Aplicada:
- Cambiados TODOS los `onClick` por `onSelect` en los `DropdownMenuItem` (líneas 1842-1932 de `Quotes.jsx`)
- Acciones corregidas: Modificar, Enviar al Cliente, Aprobar, Facturar, Cobrar, Entregar, Enviar a Implementación, Eliminar

### Verificación (iteration_27.json):
- ✅ Todas las 7 acciones del menú dropdown funcionando
- ✅ Descarga de PDF funcionando
- ✅ Flujo de estados completo verificado
- Backend: 100% ✅
- Frontend: 100% ✅

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
