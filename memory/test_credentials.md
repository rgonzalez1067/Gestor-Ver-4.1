## QA — Aislamiento por segmento en Histórico de Cotizaciones (Jun 2026)
Password para todos: Test1234! (reseteado por el agente con config.hash_password → campo `password_hash`)
- gteran@megasoft.com.ve  → sede PYME, Coordinador, quote_history=edit. Ve SOLO histórico de sede PYME (105 registros).
- ablanco@megasoft.com.ve → sede CORP, Coordinador, quote_history=read (otorgado por el agente para QA). Ve SOLO histórico de sede CORP (5 registros).
- acastro@megasoft.com.ve → sede CORP, cargo Director. EXCEPCIÓN: ve TODO (128, Corp+Pyme+TBP).
- Admin (rgonzalez@megasoft.com.ve / admin123): ve TODO (128).
Regla: usuarios no-admin/no-Director solo ven registros del Histórico cuya `sede` (sede del USUARIO creador) coincida con la suya.

## QA — Cotizaciones de Reparación / seriales (Jun 2026)
- kherrera@megasoft.com.ve / Test1234!  → Analista PYME, role=user (NO admin), special_permissions: proyectos:create, cotizaciones:equipos, cotizaciones:reparaciones. Usado para la prueba cruzada RBAC de paridad de seriales.
- Cotización reparación de prueba con seriales: quo_fb10e377bbf3 (COT-2026-05-022-PYME).

# Test Credentials

## Usuario de Operaciones (Reparaciones + Equipos)
- Email: ragg1008@hotmail.com
- Password: Test1234!
- Role: user
- Departamento: Operaciones
- Cargo: Coordinador
- Special permissions: cotizaciones:equipos, cotizaciones:reparaciones
- Nota: válido para probar el fix Iter36 (acciones libres en repair/equipos, restricción solo en fast_track MPOS).

## Admin principal
- Email: rgonzalez@megasoft.com.ve
- Password: admin123
- Role: admin
- Name: Rafael González
- Nota (2026-06): password re-restablecido a `admin123` con config.hash_password en PREVIEW (se había cambiado a otra clave). Verificado login OK vía API.

## Usuario Implementador (Jrojas)
- Email: jrojas@megasoft.com.ve  (⚠️ el email está en MINÚSCULAS en BD; el login usa match exacto)
- Password: Test1234!
- Role: user / Cargo: Implementador
- Permisos: `condiciones_banco_mediopago='read'` (SOLO CONSULTA) → útil para validar gobernanza RBAC del nuevo módulo Condiciones Banco/Medio de Pago.
- Nota: password re-reseteado (2026-07-14) con config.hash_password al validar el módulo Condiciones Banco/Medio de Pago.

## Usuario Corporativo (antes "parachute") — AHORA role=user
- Email: ragg1008@gmail.com
- Password: admin123
- Role: user (⚠️ fue degradado de admin a user)
- Name: Rafael González (Respaldo)
- departamento: Ventas Corporativas · cotizaciones=edit
- Nota: es el usuario que reportó el bug del modal "Equipos de Infraestructura".
  Sirve para probar flujos de Corporativo NO-admin (no tiene el módulo
  config_otras_acciones → 403 en /api/other-actions/*).

## Usuario NO-admin de pruebas (perfil Consulta + Cotizaciones inactivas)
- Email: srubio@megasoft.com.ve
- Password: Test1234!   ⚠️ DESINCRONIZADO (jun 2026): el login devuelve "Credenciales inválidas".
  Para pruebas de 403/no-admin usar en su lugar: Jrojas@megasoft.com.ve / Test1234! (role=user).
- Role: user
- user_id: usr_3e9641ea80e3
- Name: Sergio Rubio
- Permisos:
  - cotizaciones: none  (módulo inactivo — escenario de prueba del bug Sidebar)
  - clientes: read      (solo consulta — escenario de prueba RBAC)
  - initial_contacts, reportes_ventas, quote_history, bancos, medios_pago,
    dispositivos, commercial_categories, exchange_rate, proyectos,
    integradores, nuevos_productos, inventarios, reportes_contables,
    taller_equipos, configuracion: read

## Usuario Implementador para pruebas de "Mis Alertas"
- Email: Jrojas@megasoft.com.ve
- Password: Test1234!
- Role: user
- user_id: user_a8e3874291c8
- Name: Jhonatan Rojas
- cargo: Implementador
- Permisos: proyectos=edit
- Nota: tiene al menos un proyecto asignado (prj_bba45a09cd00) para probar
  los endpoints `/api/projects/{id}/implementer-alerts`.


## Ventas Corporativas — pruebas de Visibilidad Colectiva (Jun 2026)
- Vendedor A: mmartin@megasoft.com.ve / Test1234! (user_a9f878a5c38a, Ejecutivo, Ventas Corporativas, proyectos=read)
- Vendedor B: mposligua@megasoft.com.ve / Test1234! (user_60c7d104d330, Ejecutivo, Ventas Corporativas, proyectos=read)
- Nota: passwords reseteados por el agente para QA. Ambos deben ver TODOS los proyectos del equipo Ventas Corporativas (37 proyectos, 3 creadores distintos). Equipo completo: esilva, ragg1008@gmail.com, mmartin, corporativos, mposligua.

## Implementador para pruebas de Aislamiento de Visibilidad (Jun 2026)
- Email: agonzalez@megasoft.com.ve
- Password: Test1234!
- Role: user
- user_id: user_5ea91fd44449
- Name: Axel González
- cargo: Implementador · departamento: Implementación
- Nota: tiene EXACTAMENTE 3 proyectos asignados. Sirve para validar la regla P0
  de visibilidad: la grilla GET /projects devuelve solo sus 3 proyectos, y
  GET /projects/{id} de un proyecto ajeno/huérfano responde 403. Password
  reseteado por el agente para QA.

## Usuario Ejecutivo agodoy — pruebas de Actions Override Equipos (Jul 2026)
- Email: agodoy@megasoft.com.ve
- Password: Test1234!  (reseteado por el agente para QA con config.hash_password)
- Role: user / Cargo: Ejecutivo / Departamento: Ventas Pyme / Sede: PYME
- user_id: user_54999f93a974 (fue RECREADO; su user_id viejo user_a8e3874291c8 quedó obsoleto en overrides)
- special_permissions: cotizaciones:impl_pyme, cotizaciones:equipos, proyectos:create, integradores:create
- Nota: sirve para validar el fix de "Actions Override" (autorización por correo estable, no por user_id volátil).

## QA Usuarios — Cobro Recurrente ($) en Proyectos (creados 2026-06, desechables)
Password para todos: Test1234!
- qa_corp@megasoft.com.ve  → departamento "Ventas Corporativas" (cargo Gerente), permisos proyectos=edit. Puede alternar $ en proyectos CORP; bloqueado en PYME.
- qa_pyme@megasoft.com.ve  → departamento "Ventas Pyme" (cargo Ejecutivo), permisos proyectos=read. Puede alternar $ en proyectos PYME; bloqueado en CORP.
- qa_impl@megasoft.com.ve  → departamento "Implementación" (cargo Implementador), proyectos=edit. Ve el $ como indicador de solo lectura (deshabilitado).
Admin (toggle cualquiera): rgonzalez@megasoft.com.ve / admin123
Proyectos de referencia: CORP=prj_ad1bb4bd314e, PYME=prj_826643491b64
