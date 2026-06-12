"""
Genera el Manual Funcional / de Usuario de MegaNexus (Gestor) en Word (.docx),
con capturas de pantalla reales y detalle ampliado del módulo de Proyectos.
Uso: python -m scripts.generate_user_manual
Requiere capturas previas en /app/docs/screenshots (ver scripts/capture_screenshots.py).
Salida: /app/docs/Manual_Usuario_MegaNexus.docx
"""
import os
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BRAND = RGBColor(0x0E, 0x5A, 0x8A)
ACCENT = RGBColor(0x08, 0x91, 0xB2)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0x88, 0x88, 0x88)
SHOTS = '/app/docs/screenshots'

doc = Document()
normal = doc.styles['Normal']
normal.font.name = 'Calibri'
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0x22, 0x22, 0x22)


def _shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def h1(text):
    p = doc.add_heading(level=1); r = p.add_run(text)
    r.font.color.rgb = BRAND; r.font.size = Pt(18); r.bold = True; return p


def h2(text):
    p = doc.add_heading(level=2); r = p.add_run(text)
    r.font.color.rgb = BRAND; r.font.size = Pt(14); r.bold = True; return p


def h3(text):
    p = doc.add_heading(level=3); r = p.add_run(text)
    r.font.color.rgb = ACCENT; r.font.size = Pt(12); r.bold = True; return p


def para(text, italic=False, color=None, size=11):
    p = doc.add_paragraph(); r = p.add_run(text)
    r.italic = italic; r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style='List Bullet')
        if isinstance(it, tuple):
            r = p.add_run(it[0]); r.bold = True; p.add_run(': ' + it[1])
        else:
            p.add_run(it)


def steps(items):
    for it in items:
        doc.add_paragraph(it, style='List Number')


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = 'Light Grid Accent 1'
    hdr = t.rows[0].cells
    for i, htxt in enumerate(headers):
        hdr[i].text = ''; rp = hdr[i].paragraphs[0].add_run(htxt)
        rp.bold = True; rp.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); rp.font.size = Pt(10)
        _shade(hdr[i], '0E5A8A')
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''; rr = cells[i].paragraphs[0].add_run(str(val)); rr.font.size = Pt(10)
    doc.add_paragraph(); return t


def callout(text, kind='info'):
    colors = {'info': 'E8F1F8', 'warn': 'FFF4E5', 'ok': 'E9F7EF'}
    labels = {'info': 'NOTA', 'warn': 'IMPORTANTE', 'ok': 'BUENA PRÁCTICA'}
    t = doc.add_table(rows=1, cols=1); cell = t.rows[0].cells[0]
    _shade(cell, colors.get(kind, 'E8F1F8'))
    p = cell.paragraphs[0]; r = p.add_run(f"{labels.get(kind,'NOTA')}: "); r.bold = True
    p.add_run(text); doc.add_paragraph()


_fig_n = {'n': 0}


def figure(filename, caption, width=6.3):
    path = os.path.join(SHOTS, filename)
    if not os.path.exists(path):
        para(f'[Captura pendiente: {filename}]', italic=True, color=LIGHT); return
    _fig_n['n'] += 1
    doc.add_picture(path, width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(f'Figura {_fig_n["n"]}. {caption}')
    r.italic = True; r.font.size = Pt(9); r.font.color.rgb = LIGHT


# ================= PORTADA =================
for _ in range(4): doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('MegaNexus'); r.bold = True; r.font.size = Pt(40); r.font.color.rgb = BRAND
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Work Flow de Procesos Integrales'); r.font.size = Pt(14); r.font.color.rgb = LIGHT
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Manual Funcional / de Usuario'); r.bold = True; r.font.size = Pt(22); r.font.color.rgb = ACCENT
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Edición ilustrada — énfasis en el módulo de Proyectos'); r.font.size = Pt(12); r.font.color.rgb = GREY
for _ in range(5): doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Documento de uso interno · MegaSoft'); r.font.size = Pt(11); r.font.color.rgb = GREY
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Generado: ' + datetime.now().strftime('%d/%m/%Y')); r.font.size = Pt(10); r.font.color.rgb = LIGHT
doc.add_page_break()

# ================= CONTROL DE VERSIONES =================
h1('Control de versiones')
table(['Versión', 'Fecha', 'Descripción', 'Autor'],
      [['1.0', datetime.now().strftime('%d/%m/%Y'), 'Versión inicial', 'Equipo MegaNexus'],
       ['2.0', datetime.now().strftime('%d/%m/%Y'), 'Edición ilustrada con capturas y detalle ampliado de Proyectos', 'Equipo MegaNexus']])

h1('Contenido')
bullets([
    '1. Introducción', '2. Acceso, roles y permisos (RBAC)', '3. Estructura del menú',
    '4. Gestión Comercial', '5. Catálogos',
    '6. Gestión de Implementación — PROYECTOS (detallado), Proyectos Directos, Integradores, Datos de Imple',
    '7. Nuevos Productos', '8. Gestión Administrativa', '9. Gestión de Taller',
    '10. Configuración', '11. Gestión de Seguridad', '12. Flujos de negocio', '13. Glosario', '14. Preguntas frecuentes',
])
doc.add_page_break()

# ================= 1. INTRODUCCIÓN =================
h1('1. Introducción')
para('MegaNexus ("Gestor") es la plataforma integral de MegaSoft para administrar el ciclo comercial y de '
     'implementación de soluciones de pago: desde el primer contacto, la cotización, hasta la ejecución y '
     'seguimiento de los proyectos. Este manual hace énfasis en el módulo de Proyectos, el más usado por los '
     'Implementadores y donde se concentran las operaciones sensibles: actualizaciones individuales y masivas, '
     'creación de plantillas y envío de notificaciones.')
h3('¿Para quién es este manual?')
bullets([
    ('Ejecutivos de Ventas', 'clientes, contactos y cotizaciones.'),
    ('Coordinadores e Implementadores', 'proyectos, fichas técnicas, datos de implementación y notificaciones.'),
    ('Administradores', 'catálogos, usuarios, perfiles y configuración.'),
])

# ================= 2. RBAC =================
h1('2. Acceso, roles y permisos (RBAC)')
h3('Inicio de sesión')
steps(['Ingrese a la dirección de la aplicación.',
       'Escriba su correo y contraseña, y presione "Ingresar".',
       'Verá el Dashboard y el menú con los módulos habilitados para su perfil.'])
h3('Niveles de acceso por módulo')
table(['Nivel', 'Significado'],
      [['Inactivo', 'El módulo no aparece en el menú.'],
       ['Consulta', 'Puede ver/leer, no modificar.'],
       ['Edición Total', 'Puede crear, editar y eliminar según el módulo.']])
para('Los perfiles agrupan estos permisos y se asignan a cada usuario desde Gestión de Seguridad → Perfiles. '
     'El administrador tiene acceso total.')

# ================= 3. MENÚ =================
h1('3. Estructura del menú')
table(['Grupo', 'Opciones'],
      [['Dashboard', 'Panel de indicadores'],
       ['Gestión Comercial', 'Contacto Inicial · Clientes · Cotizaciones · Reportes de Ventas · Reportes por Patrocinador · Histórico'],
       ['Catálogos', 'Bancos · Medios de Pago · Bienes y Servicios · Categoría Comercial · Tasa de Cambio'],
       ['Gestión de Implementación', 'Proyectos · Proyectos Directos · Integradores · Datos de Imple'],
       ['Nuevos Productos', 'Gestión de nuevos productos'],
       ['Gestión Administrativa', 'Inventarios · Reportes Contables'],
       ['Gestión de Taller', 'Gestión de equipos'],
       ['Gestión de Seguridad', 'Usuarios · Permisos · Perfiles (solo administradores)']])
doc.add_page_break()

# ================= 4. COMERCIAL =================
h1('4. Gestión Comercial')
h2('4.1 Dashboard')
para('Pantalla de inicio con indicadores y accesos rápidos.')
h2('4.2 Contacto Inicial')
para('Registra el primer acercamiento con un prospecto: origen del contacto y datos básicos para seguimiento.')
h2('4.3 Clientes')
para('Repositorio central de clientes. La clave única es RIF + Sucursal, por lo que un mismo RIF puede tener '
     'varias sucursales como registros independientes.')
h3('Crear / editar un cliente')
steps(['Ingrese a Clientes y presione "Nuevo Cliente".',
       'Opcional: cargue el RIF (PDF/imagen) para autocompletar RIF, razón social y dirección.',
       'Complete datos comerciales y responsables (Ejecutivo, Coordinador, Implementador, Integrador/Aplicativo).',
       'Agregue contactos y guarde.'])
callout('Para correcciones rápidas de datos de implementación en clientes con varias sucursales, use el módulo '
        '"Datos de Imple" (sección 6.8), que replica los cambios a todas las sucursales del mismo RIF.', 'info')
h2('4.4 Cotizaciones')
para('Elaboración de propuestas. Soporta VPOS, MPOS, Payment Gateway y Link de Pago, y el modelo multitienda. '
     'Secciones financieras: Set Up (inversión inicial), Costos Recurrentes Básicos y Otros.')
bullets([
    ('Sincronización de cajas', 'al cambiar el "Número de Cajas" en Set Up, se propaga al ítem equivalente de Costos Recurrentes Básicos y se recalculan totales (flujo unidireccional).'),
    ('Plantillas y variables', 'catálogo común con cotizaciones/proyectos, buscador e inserción en el cursor.'),
    ('Enviar al Cliente', 'genera y envía la propuesta/ficha por correo; queda registrada con su estado y PDF.'),
])
h2('4.5–4.7 Reportes y Histórico')
bullets([('Reportes de Ventas', 'consolidado de la gestión comercial.'),
         ('Reportes por Patrocinador', 'información por banco/patrocinador.'),
         ('Histórico de Cotizaciones', 'archivo de cotizaciones para consulta (según permiso).')])
doc.add_page_break()

# ================= 5. CATÁLOGOS =================
h1('5. Catálogos')
para('Alimentan listas y precios de Cotizaciones y Proyectos.')
bullets([('Bancos', 'patrocinadores, contactos e integraciones.'),
         ('Medios de Pago', 'medios disponibles para asociar a las soluciones.'),
         ('Bienes y Servicios', 'hardware/software/servicios con precios (Set Up y recurrentes).'),
         ('Categoría Comercial', 'clasificación de clientes.'),
         ('Tasa de Cambio', 'tasa para cálculos financieros.')])
doc.add_page_break()

# ================= 6. IMPLEMENTACIÓN (DETALLADO) =================
h1('6. Gestión de Implementación')
para('Esta es el área central para Coordinadores e Implementadores. Se documenta en detalle el módulo de '
     'Proyectos por ser el más sensible.', color=GREY)

# ---- 6.1 Lista de Proyectos ----
h2('6.1 Proyectos — Lista y búsqueda')
para('Al ingresar a Proyectos verá el listado con su estado, tipo, patrocinador e implementador asignado. '
     'Las insignias identifican proyectos Directos, Multitienda o Irregulares.')
figure('01_projects_list.png', 'Listado de Proyectos con filtros (estado, tipo, patrocinador) y buscador.')
h3('Búsqueda y filtros')
bullets([
    ('Buscador', 'por número de proyecto, cliente, etc.'),
    ('Filtro por Estado', 'Por asignar, Asignado, En Gestión, Suspendido, Implementado parcial, Culminado.'),
    ('Filtro por Tipo', 'según el tipo de solución/origen.'),
    ('Filtro por Patrocinador', 'banco asociado.'),
])
para('Acciones disponibles desde la lista: PDF de carga de trabajo, gestión de Plantillas y Actualización Masiva '
     'de asignación.')

# ---- 6.2 Actualización masiva (reasignación) desde la lista ----
h2('6.2 Actualización Masiva de asignación (reasignación)')
para('Permite reasignar varios proyectos a un implementador en una sola operación, evitando editar uno por uno.')
steps([
    'En la lista de Proyectos, presione "Actualización Masiva" / botón de reasignación.',
    'Seleccione el implementador destino.',
    'Indique la fecha y un comentario que justifique la reasignación.',
    'Confirme. Los proyectos seleccionados quedan reasignados.',
])
figure('02_bulk_reassign_dialog.png', 'Diálogo de Actualización Masiva: reasignación de implementador.')
callout('La reasignación masiva afecta a todos los proyectos seleccionados. Verifique el implementador y la '
        'fecha antes de confirmar.', 'warn')

# ---- 6.3 Detalle del proyecto ----
h2('6.3 Detalle del Proyecto')
para('Al abrir un proyecto verá su información general, el estado actual, los datos del cliente y la bitácora. '
     'Desde aquí se realizan las operaciones del día a día del Implementador.')
figure('04_project_detail_overview.png', 'Vista general del detalle del Proyecto.')
h3('Ciclo de vida y cambio de estado (actualización individual)')
table(['Estado', 'Descripción'],
      [['Por asignar', 'Creado, pendiente de implementador.'],
       ['Asignado', 'Implementador asignado.'],
       ['En Gestión', 'Implementación en curso.'],
       ['Suspendido', 'Temporalmente detenido.'],
       ['Implementado parcial', 'Parcial (algunas sucursales).'],
       ['Culminado', 'Finalizado.']])
steps([
    'En el detalle, abra el control de Estado del proyecto.',
    'Seleccione el nuevo estado, indique fecha y comentario.',
    'Confirme. El cambio queda registrado en la bitácora y disponible como variable {Estado_Proyecto}.',
])
h3('Bitácora')
para('Registra eventos y comunicaciones del proyecto (incluye correos enviados y sus copias). Puede agregar '
     'entradas manuales con fecha y descripción.')

# ---- 6.4 Multitienda individual ----
h2('6.4 Multitienda — Actualización individual de sucursales')
para('En proyectos multitienda, cada sucursal se gestiona en la sección Multitienda: puede ajustar el número '
     'de cajas y los datos por sucursal de forma individual.')
figure('05_multistore_individual.png', 'Sección Multitienda: edición individual por sucursal.')
callout('La edición individual aplica solo a la sucursal seleccionada. Para aplicar el mismo cambio a varias '
        'sucursales del proyecto a la vez, use la Actualización Masiva (sección 6.5).', 'info')

# ---- 6.5 Batch update multitienda ----
h2('6.5 Actualización Masiva (Batch) multitienda')
para('Permite aplicar un mismo cambio (fase, banco, productos) a varias sucursales del proyecto simultáneamente.')
steps([
    'En el detalle de un proyecto multitienda, presione "Actualización Masiva".',
    'Seleccione las sucursales (o "Seleccionar todas").',
    'Elija la fase y/o el banco, y marque los productos a actualizar.',
    'Indique el motivo y confirme.',
])
figure('06_batch_update_dialog.png', 'Diálogo de Actualización Masiva (Batch) por sucursales.')

# ---- 6.6 Creación de plantillas ----
h2('6.6 Creación de Plantillas de correo')
para('Las plantillas estandarizan los correos de Proyectos. Se gestionan desde "Gestionar Plantillas" '
     '(disponible en la lista y en el detalle).')
figure('07_templates_dialog.png', 'Modal de gestión de Plantillas: lista (izquierda), formulario (centro) y variables (derecha).')
h3('Crear o editar una plantilla')
steps([
    'Abra "Gestionar Plantillas".',
    'Presione "+ Nueva" para crear, o haga clic en una plantilla de la lista para editarla.',
    'Defina el Nombre, el Asunto y el Cuerpo del mensaje.',
    'Inserte variables desde el panel derecho (use el buscador y haga clic para insertarlas en el cursor).',
    'Guarde. La plantilla queda disponible en el selector de notificaciones.',
])
para('Sugerencias de uso: al pasar el cursor sobre el nombre de una plantilla se muestra el nombre completo; '
     'las acciones Editar/Eliminar aparecen al situar el mouse sobre cada tarjeta.')
figure('08_template_edit_form.png', 'Edición de una plantilla: nombre, asunto, cuerpo y panel de variables.')
callout('Las variables (ej. datos del cliente, montos, {Estado_Proyecto}) se reemplazan automáticamente al '
        'enviar el correo. Use el buscador de variables para encontrarlas rápido.', 'ok')

# ---- 6.7 Notificaciones ----
h2('6.7 Envío de Notificaciones')
para('Desde el detalle del proyecto se envían las notificaciones por correo. Hay dos modalidades: '
     'Notificaciones a Clientes/Bancos (formales, con plantilla y secuencia de envíos) y Otras Notificaciones '
     '(envíos puntuales/ad-hoc).')
h3('6.7.1 Notificaciones a Clientes / Bancos')
figure('09_notifications_dialog.png', 'Modal de Notificaciones: contactos, destinatarios TO/CC, grupos CC, plantilla y editor.')
steps([
    'Abra "Notificaciones" en el detalle del proyecto y elija el destino (Cliente / Banco / Cliente y Banco).',
    'En "Destinatarios del Proyecto" marque los contactos a incluir.',
    'Revise los Destinatarios Principales (TO): puede agregar/corregir correos o buscar usuarios internos.',
    'Agregue Destinatarios Adicionales (CC) y, si lo desea, aplique un Grupo de Correo guardado.',
    'Seleccione la Plantilla; el asunto y el cuerpo se cargan automáticamente.',
    'Adjunte archivos, imágenes o la matriz si corresponde.',
    'Use Vista Previa para revisar el resultado final y luego Enviar.',
])
bullets([
    ('Destinatarios TO/CC con tokens', 'el selector permite usuarios internos (con filtro estratégico) y correos externos.'),
    ('Grupos de Correo (CC)', 'guarde y reutilice grupos de copia; son compartidos con Otras Notificaciones.'),
    ('Historial de envíos', 'muestra los envíos previos y el próximo envío sugerido de la secuencia.'),
])
callout('Verifique siempre los destinatarios TO antes de enviar. Los correos prellenados del cliente pueden '
        'corregirse en el mismo modal.', 'warn')

h3('6.7.2 Otras Notificaciones (Ad-hoc)')
para('Para envíos puntuales que no forman parte de la secuencia formal. Incluye el mismo selector de '
     'destinatarios (TO/CC) con tokens, Grupos de Correo, plantillas, adjuntos y vista previa.')
figure('10_adhoc_dialog.png', 'Modal de Otras Notificaciones (Ad-hoc) con destinatarios TO/CC y grupos.')
steps([
    'Abra "Otras Notificaciones" en el detalle del proyecto.',
    'Seleccione contactos y/o agregue destinatarios TO y CC (puede aplicar un Grupo de Correo).',
    'Elija una plantilla o redacte el asunto y el mensaje; adjunte archivos si es necesario.',
    'Revise con Vista Previa y envíe.',
])

# ---- 6.8 Ficha Técnica ----
h2('6.8 Ficha Técnica de Implementación')
bullets([
    'Contiene el Resumen Ejecutivo con bancos y productos seleccionados, distribución por sucursales y datos de configuración.',
    'Toma como fuente de verdad los datos del propio proyecto, por lo que es equivalente a la ficha enviada al cliente.',
    'Se puede descargar desde el detalle del proyecto.',
])

# ---- 6.9 Proyectos Directos / Integradores / Datos de Imple ----
h2('6.9 Proyectos Directos')
para('Crea un proyecto sin cotización previa, capturando directamente sucursales, bancos y productos. Genera '
     'igualmente su Ficha Técnica.')
h2('6.10 Integradores')
para('Catálogo de integradores (socios tecnológicos) y sus aplicativos, asociados a clientes y proyectos.')
h2('6.11 Datos de Imple')
para('Corrección rápida de 5 campos del cliente con replicación a todas las sucursales del mismo RIF.')
bullets([('Componentes', 'tipo de servicio (VPOS/MPOS/Payment Gateway/Link de Pago).'),
         ('Integrador', 'socio tecnológico.'), ('Aplicación', 'aplicativo (autocompletado).'),
         ('Implementador', 'responsable.'), ('Coordinador', 'precargado con el perfil "Coordinación de Administración".')])
callout('NO incluye "Ejecutivo Propietario" por diseño. Al guardar, los 5 campos se replican a TODAS las '
        'sucursales del mismo RIF en una sola operación.', 'ok')
doc.add_page_break()

# ================= 7–11 =================
h1('7. Nuevos Productos')
para('Gestión de nuevos productos del portafolio, con documentación y seguimiento.')
h1('8. Gestión Administrativa')
bullets([('Inventarios', 'control de activos e inventario de equipos.'),
         ('Kardex de Activos', 'movimientos de activos.'),
         ('Mayor de Activos', 'saldos y resumen contable.'),
         ('Salidas Facturadas', 'salidas con facturación asociada.')])
h1('9. Gestión de Taller')
para('Recepción, diagnóstico, reparación y entrega de equipos en taller.')
h1('10. Configuración')
bullets([('Plantillas de correo', 'clientes, integradores y nuevos productos.'),
         ('Pie de página / Remitentes', 'footer y direcciones remitentes por área.'),
         ('Notificaciones y Otras Acciones', 'motor de notificaciones y acciones automáticas.')])
h1('11. Gestión de Seguridad')
bullets([('Creación de Usuarios', 'alta de usuarios.'),
         ('Permisos de Usuarios', 'niveles por módulo por usuario.'),
         ('Perfiles de Usuario', 'perfiles reutilizables y activación de módulos por perfil.')])
doc.add_page_break()

# ================= 12. FLUJOS =================
h1('12. Flujos de negocio clave')
h2('12.1 De la cotización al proyecto')
steps(['Registrar/seleccionar el cliente.', 'Elaborar la Cotización.', 'Revisar Vista Previa y Enviar al Cliente.',
       'Convertir en Proyecto (o crear Proyecto Directo).', 'Asignar Implementador y dar seguimiento por estado.'])
h2('12.2 Operación del Implementador en un Proyecto')
steps(['Abrir el proyecto y revisar estado y bitácora.',
       'Actualizar estado o datos por sucursal (individual) o usar Actualización Masiva.',
       'Verificar/descargar la Ficha Técnica.',
       'Enviar Notificaciones (Cliente/Banco u Otras) usando plantillas y grupos de CC.'])
h2('12.3 Corrección rápida multisucursal (Datos de Imple)')
steps(['Buscar el cliente en Datos de Imple.', 'Editar los 5 campos.', 'Guardar: se replica a todas las sucursales del mismo RIF.'])

# ================= 13. GLOSARIO =================
h1('13. Glosario')
table(['Término', 'Definición'],
      [['RIF + Sucursal', 'Clave única del cliente.'],
       ['Set Up', 'Inversión inicial / puesta en marcha.'],
       ['Costos Recurrentes', 'Cargos mensuales (básicos y otros).'],
       ['VPOS / MPOS', 'Punto de venta virtual / móvil.'],
       ['Payment Gateway', 'Pasarela de pago para cobros en línea.'],
       ['Ficha Técnica', 'Documento de implementación con resumen ejecutivo y configuración.'],
       ['Grupo CC', 'Conjunto reutilizable de destinatarios en copia.'],
       ['Actualización Masiva', 'Cambio aplicado a varios proyectos/sucursales en una sola operación.'],
       ['Componentes', 'En Datos de Imple, corresponde al Tipo de Servicio.']])

# ================= 14. FAQ =================
h1('14. Preguntas frecuentes')
h3('No veo un módulo en el menú')
para('Su perfil podría no tener permiso. Solicite al administrador habilitarlo en Gestión de Seguridad.')
h3('¿La Actualización Masiva afecta a todo?')
para('Solo a los proyectos/sucursales que usted selecciona en el diálogo. Revise la selección antes de confirmar.')
h3('¿Las notificaciones envían copia (CC)?')
para('Sí. Puede agregar correos en CC manualmente o aplicar un Grupo de Correo guardado.')
h3('La Ficha Técnica salía sin Resumen Ejecutivo')
para('La ficha toma los datos del propio proyecto; vuelva a descargarla desde el detalle para obtener la versión completa.')
h3('¿Datos de Imple afecta todas las sucursales?')
para('Sí, por diseño replica los 5 campos a todas las sucursales con el mismo RIF.')

# ---------- guardar ----------
out_dir = '/app/docs'; os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'Manual_Usuario_MegaNexus.docx')
doc.save(out_path)
print('OK ->', out_path, '| figuras:', _fig_n['n'])
