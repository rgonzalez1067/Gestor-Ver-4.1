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

## Usuario Implementador (Jrojas)
- Email: Jrojas@megasoft.com.ve
- Password: Test1234!
- Role: user / Cargo: Implementador
- Nota: password reseteado por el agente (2026-06-07) al validar el fix RBAC de catálogos (Proyectos Directos). El hash previo estaba desactualizado.

## Admin de respaldo (parachute)
- Email: ragg1008@gmail.com
- Password: admin123
- Role: admin
- Name: Rafael González (Respaldo)

## Usuario NO-admin de pruebas (perfil Consulta + Cotizaciones inactivas)
- Email: srubio@megasoft.com.ve
- Password: Test1234!
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
