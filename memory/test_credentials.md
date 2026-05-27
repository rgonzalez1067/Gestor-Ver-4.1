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
