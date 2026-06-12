"""
Genera el Manual Funcional / de Usuario de MegaNexus (Gestor) en formato Word (.docx).
Uso: python -m scripts.generate_user_manual
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

BRAND = RGBColor(0x0E, 0x5A, 0x8A)      # azul corporativo
ACCENT = RGBColor(0x0891B2 >> 16 & 0xFF, 0x0891B2 >> 8 & 0xFF, 0x0891B2 & 0xFF)  # cian
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0x88, 0x88, 0x88)

doc = Document()

# ---------- estilos base ----------
normal = doc.styles['Normal']
normal.font.name = 'Calibri'
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0x22, 0x22, 0x22)


def _shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def h1(text):
    p = doc.add_heading(level=1)
    run = p.add_run(text)
    run.font.color.rgb = BRAND
    run.font.size = Pt(18)
    run.bold = True
    return p


def h2(text):
    p = doc.add_heading(level=2)
    run = p.add_run(text)
    run.font.color.rgb = BRAND
    run.font.size = Pt(14)
    run.bold = True
    return p


def h3(text):
    p = doc.add_heading(level=3)
    run = p.add_run(text)
    run.font.color.rgb = ACCENT
    run.font.size = Pt(12)
    run.bold = True
    return p


def para(text, italic=False, color=None, size=11):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style='List Bullet')
        if isinstance(it, tuple):
            r = p.add_run(it[0]); r.bold = True
            p.add_run(': ' + it[1])
        else:
            p.add_run(it)


def steps(items):
    for it in items:
        doc.add_paragraph(it, style='List Number')


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = 'Light Grid Accent 1'
    hdr = t.rows[0].cells
    for i, htxt in enumerate(headers):
        hdr[i].text = ''
        rp = hdr[i].paragraphs[0].add_run(htxt)
        rp.bold = True
        rp.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        rp.font.size = Pt(10)
        _shade(hdr[i], '0E5A8A')
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''
            rr = cells[i].paragraphs[0].add_run(str(val))
            rr.font.size = Pt(10)
    doc.add_paragraph()
    return t


def callout(text, kind='info'):
    colors = {'info': 'E8F1F8', 'warn': 'FFF4E5', 'ok': 'E9F7EF'}
    labels = {'info': 'NOTA', 'warn': 'IMPORTANTE', 'ok': 'BUENA PRÁCTICA'}
    t = doc.add_table(rows=1, cols=1)
    cell = t.rows[0].cells[0]
    _shade(cell, colors.get(kind, 'E8F1F8'))
    p = cell.paragraphs[0]
    r = p.add_run(f"{labels.get(kind,'NOTA')}: ")
    r.bold = True
    p.add_run(text)
    doc.add_paragraph()


# ================= PORTADA =================
for _ in range(4):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('MegaNexus'); r.bold = True; r.font.size = Pt(40); r.font.color.rgb = BRAND
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Work Flow de Procesos Integrales'); r.font.size = Pt(14); r.font.color.rgb = LIGHT
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Manual Funcional / de Usuario'); r.bold = True; r.font.size = Pt(22); r.font.color.rgb = ACCENT
for _ in range(6):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Documento de uso interno · MegaSoft'); r.font.size = Pt(11); r.font.color.rgb = GREY
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Generado: ' + datetime.now().strftime('%d/%m/%Y')); r.font.size = Pt(10); r.font.color.rgb = LIGHT
doc.add_page_break()

# ================= CONTROL DE VERSIONES =================
h1('Control de versiones')
table(['Versión', 'Fecha', 'Descripción', 'Autor'],
      [['1.0', datetime.now().strftime('%d/%m/%Y'), 'Versión inicial del Manual Funcional / de Usuario', 'Equipo MegaNexus']])

# ================= ÍNDICE =================
h1('Contenido')
para('Este manual está organizado por módulos siguiendo la estructura del menú de la aplicación, '
     'más una sección de flujos de negocio de extremo a extremo y un glosario.', color=GREY)
bullets([
    '1. Introducción',
    '2. Acceso, roles y permisos (RBAC)',
    '3. Estructura del menú',
    '4. Gestión Comercial (Dashboard, Contacto Inicial, Clientes, Cotizaciones, Reportes, Histórico)',
    '5. Catálogos (Bancos, Medios de Pago, Bienes y Servicios, Categoría Comercial, Tasa de Cambio)',
    '6. Gestión de Implementación (Proyectos, Proyectos Directos, Integradores, Datos de Imple)',
    '7. Nuevos Productos',
    '8. Gestión Administrativa (Inventarios y Reportes Contables)',
    '9. Gestión de Taller',
    '10. Configuración',
    '11. Gestión de Seguridad',
    '12. Flujos de negocio clave',
    '13. Glosario',
    '14. Preguntas frecuentes',
])
doc.add_page_break()

# ================= 1. INTRODUCCIÓN =================
h1('1. Introducción')
para('MegaNexus (también identificado como "Gestor") es la plataforma integral de MegaSoft para administrar '
     'el ciclo comercial y de implementación de soluciones de pago: desde el primer contacto con el cliente, '
     'la elaboración de cotizaciones, hasta la ejecución y seguimiento de los proyectos de implementación.')
h3('¿Para quién es este manual?')
bullets([
    ('Ejecutivos de Ventas', 'gestión de clientes, contactos y cotizaciones.'),
    ('Coordinadores e Implementadores', 'gestión de proyectos, fichas técnicas y datos de implementación.'),
    ('Administradores', 'catálogos, usuarios, perfiles y configuración del sistema.'),
])
h3('Conceptos generales de navegación')
bullets([
    ('Menú lateral', 'agrupa las opciones por área. Se puede contraer/expandir y fijar.'),
    ('Permisos', 'cada usuario solo ve los módulos habilitados para su perfil.'),
    ('Buscadores', 'la mayoría de listados permite buscar por nombre, RIF u otros campos clave.'),
    ('Guardado', 'los formularios validan los datos antes de guardar y muestran confirmaciones (toasts).'),
])

# ================= 2. RBAC =================
h1('2. Acceso, roles y permisos (RBAC)')
h3('Inicio de sesión')
steps([
    'Ingrese a la dirección de la aplicación.',
    'Escriba su correo y contraseña, y presione "Ingresar".',
    'Al autenticarse, verá el Dashboard y el menú con los módulos habilitados para su perfil.',
])
h3('Perfiles y niveles de acceso')
para('El acceso se controla por módulo mediante tres niveles:')
table(['Nivel', 'Significado'],
      [['Inactivo', 'El módulo no aparece en el menú del usuario.'],
       ['Consulta', 'El usuario puede ver/leer, pero no modificar.'],
       ['Edición Total', 'El usuario puede crear, editar y eliminar según el módulo.']])
para('Los perfiles (ej. Vendedor Pyme, Vendedor Corp, Gerente Operativo, Coordinador de Administración, '
     'Gerencia de Implementación, Analista de Operaciones, Operador Taller) agrupan estos permisos y se '
     'asignan a cada usuario. El administrador puede activar o desactivar módulos por perfil desde '
     'Gestión de Seguridad → Perfiles de Usuario.')
callout('El usuario administrador tiene acceso total a todos los módulos, independientemente del perfil.', 'info')

# ================= 3. MENÚ =================
h1('3. Estructura del menú')
table(['Grupo', 'Opciones'],
      [['Dashboard', 'Panel de indicadores'],
       ['Gestión Comercial', 'Contacto Inicial · Clientes · Cotizaciones · Reportes de Ventas · Reportes por Patrocinador · Histórico de Cotizaciones'],
       ['Catálogos', 'Bancos · Medios de Pago · Bienes y Servicios · Categoría Comercial · Tasa de Cambio'],
       ['Gestión de Implementación', 'Proyectos · Proyectos Directos · Integradores · Datos de Imple'],
       ['Nuevos Productos', 'Gestión de nuevos productos'],
       ['Gestión Administrativa', 'Inventarios · Reportes Contables (Kardex, Mayor de Activos, Salidas Facturadas)'],
       ['Gestión de Taller', 'Gestión de equipos en taller'],
       ['Gestión de Seguridad', 'Creación de Usuarios · Permisos de Usuarios · Perfiles de Usuario (solo administradores)']])
doc.add_page_break()

# ================= 4. GESTIÓN COMERCIAL =================
h1('4. Gestión Comercial')

h2('4.1 Dashboard')
para('Pantalla de inicio con una visión general de la operación (indicadores y accesos rápidos). '
     'Es el punto de partida tras iniciar sesión.')

h2('4.2 Contacto Inicial')
para('Registra el primer acercamiento con un prospecto antes de convertirlo en cliente formal: '
     'permite capturar el origen del contacto y los datos básicos para su seguimiento comercial.')

h2('4.3 Clientes')
para('Repositorio central de clientes. Un cliente se identifica de forma única por la combinación '
     'RIF + Sucursal, por lo que un mismo RIF puede tener varias sucursales como registros independientes.')
h3('Crear / editar un cliente')
steps([
    'Ingrese a Clientes y presione "Nuevo Cliente".',
    'Puede cargar el RIF (PDF/imagen) para extraer automáticamente RIF, razón social y dirección fiscal.',
    'Complete los datos comerciales: nombre de fantasía, segmento, condición, categoría comercial, referidor.',
    'Asigne responsables: Ejecutivo Propietario, Coordinador, Implementador e Integrador/Aplicativo.',
    'Agregue contactos (nombre, cargo, correo, teléfono) y guarde.',
])
h3('Campos clave')
bullets([
    ('RIF + Sucursal', 'clave única del cliente.'),
    ('Ejecutivo Propietario', 'dueño comercial del cliente.'),
    ('Tipo de Servicio (Componentes)', 'VPOS, MPOS, Payment Gateway, Link de Pago.'),
    ('Integrador / Aplicativo', 'socio tecnológico y su aplicación asociada.'),
    ('Coordinador / Implementador', 'responsables del proceso de implementación.'),
])
callout('Para correcciones rápidas de datos de implementación en clientes con varias sucursales, '
        'use el módulo "Datos de Imple" (ver sección 6.4), que replica los cambios a todas las sucursales del mismo RIF.', 'info')

h2('4.4 Cotizaciones')
para('Módulo para elaborar las propuestas comerciales. Soporta distintos tipos de solución y el modelo '
     'multitienda (varias sucursales en una misma cotización).')
h3('Tipos de cotización')
bullets([
    ('VPOS / MPOS', 'soluciones de punto de venta físico/móvil.'),
    ('Payment Gateway (Pasarela)', 'cobros en línea; usa conceptos de "Set Up de Pasarela".'),
    ('Link de Pago', 'cobro mediante enlace.'),
])
h3('Secciones financieras')
bullets([
    ('Set Up – Puesta en Marcha (Inversión Inicial)', 'costos de implementación únicos.'),
    ('Costos Recurrentes – Básicos', 'cargos mensuales del servicio.'),
    ('Costos Recurrentes – Otros / Adicionales', 'cargos mensuales complementarios.'),
])
h3('Sincronización automática de "Número de Cajas"')
para('Al cambiar el número de cajas de un ítem en la sección Set Up, el sistema propaga automáticamente '
     'ese valor al ítem equivalente (mismo producto/ID) de Costos Recurrentes – Básicos y recalcula '
     'subtotales, totales e impuestos. El flujo es unidireccional (de Set Up hacia Recurrentes).')
h3('Plantillas y variables')
bullets([
    'Las cotizaciones y proyectos comparten el mismo catálogo de variables (ej. datos del cliente, montos, fechas).',
    'Los editores incluyen buscador de variables e inserción en la posición del cursor.',
    'La Vista Previa permite revisar asunto y cuerpo antes de enviar; el cuerpo se conserva al editar el asunto.',
])
h3('Enviar al Cliente')
steps([
    'Genere la cotización y verifique la Vista Previa.',
    'Use la acción de envío para enviar la Ficha/Propuesta al cliente por correo.',
    'La cotización queda registrada con su estado (ej. Enviada) y su PDF asociado.',
])

h2('4.5 Reportes de Ventas')
para('Consolidado de la actividad comercial para análisis y seguimiento de la gestión de ventas.')

h2('4.6 Reportes por Patrocinador')
para('Reportes orientados a patrocinadores (bancos u otros), con la información de su cartera asociada.')

h2('4.7 Histórico de Cotizaciones')
para('Archivo de cotizaciones para consulta. El acceso a este módulo depende del permiso correspondiente '
     'en la matriz de seguridad (además del acceso histórico para perfiles Director/Administrador).')
doc.add_page_break()

# ================= 5. CATÁLOGOS =================
h1('5. Catálogos')
para('Los catálogos alimentan las listas y precios usados por Cotizaciones y Proyectos. Mantenerlos '
     'actualizados garantiza propuestas correctas.')
h2('5.1 Bancos')
para('Registro de bancos/patrocinadores, sus contactos y la información comercial asociada (roadmap, integraciones).')
h2('5.2 Medios de Pago')
para('Catálogo de medios de pago disponibles para asociar a las soluciones cotizadas.')
h2('5.3 Bienes y Servicios')
para('Catálogo de hardware, software y servicios con sus precios (Set Up y recurrentes) que se utilizan al cotizar.')
h2('5.4 Categoría Comercial')
para('Clasificación comercial de clientes para segmentación y reportes.')
h2('5.5 Tasa de Cambio')
para('Tasa utilizada para los cálculos financieros expresados en distintas monedas.')
doc.add_page_break()

# ================= 6. IMPLEMENTACIÓN =================
h1('6. Gestión de Implementación')

h2('6.1 Proyectos')
para('Un proyecto representa la ejecución de una implementación para un cliente. Se origina desde una '
     'cotización aprobada o como Proyecto Directo.')
h3('Ciclo de vida del proyecto')
table(['Estado', 'Descripción'],
      [['Por asignar', 'Proyecto creado, pendiente de asignar implementador.'],
       ['Asignado', 'Se asignó un implementador responsable.'],
       ['En Gestión', 'Implementación en curso.'],
       ['Suspendido', 'Temporalmente detenido.'],
       ['Implementado parcial', 'Implementación parcial (algunas sucursales/puntos).'],
       ['Culminado', 'Proyecto finalizado.']])
para('El estado puede usarse como variable en plantillas mediante la etiqueta {Estado_Proyecto}.')
h3('Bitácora')
para('Cada proyecto mantiene una bitácora de eventos y comunicaciones (incluye los correos enviados y sus copias).')
h3('Ficha Técnica de Implementación')
bullets([
    'La Ficha Técnica que se almacena en el proyecto contiene el Resumen Ejecutivo con los bancos y productos seleccionados, distribución logística (sucursales) y datos de configuración.',
    'Esta ficha debe ser equivalente a la que se envía al cliente, tomando como fuente de verdad los datos del propio proyecto.',
])
h3('Notificaciones por correo')
bullets([
    ('Notificaciones a Clientes/Bancos', 'envíos formales con plantillas; incluyen destinatarios principales (Para) y copias (CC) mediante un selector de tokens.'),
    ('Otras Notificaciones (Ad-hoc)', 'envíos puntuales con el mismo selector de destinatarios y copias.'),
    ('Grupos de Correo (CC)', 'permite guardar y reutilizar grupos de destinatarios en copia, compartidos entre los modales de notificación.'),
    ('Filtro estratégico', 'al agregar destinatarios internos, el buscador prioriza usuarios estratégicos.'),
])

h2('6.2 Proyectos Directos')
para('Permite crear un proyecto sin partir de una cotización previa, capturando directamente las sucursales, '
     'bancos y productos (matriz de implementación). Genera igualmente su Ficha Técnica.')

h2('6.3 Integradores')
para('Catálogo de integradores (socios tecnológicos) y sus aplicativos. Se asocian a clientes y proyectos, '
     'e incluyen seguimiento de su gestión e integraciones.')

h2('6.4 Datos de Imple')
para('Opción de corrección rápida y focalizada de los datos de implementación de un cliente, con '
     'replicación automática a todas sus sucursales.')
h3('¿Qué campos permite editar?')
para('Exclusivamente cinco (5) campos:')
bullets([
    ('Componentes', 'tipo de servicio (VPOS, MPOS, Payment Gateway, Link de Pago).'),
    ('Integrador', 'socio tecnológico.'),
    ('Aplicación', 'aplicativo del integrador (se autocompleta al elegir el integrador).'),
    ('Implementador', 'responsable de la implementación.'),
    ('Coordinador', 'coordinador asignado.'),
])
callout('Por diseño, esta vista NO incluye el campo "Ejecutivo Propietario", para evitar cambios '
        'accidentales del dueño comercial del cliente.', 'warn')
h3('Precarga del Coordinador')
para('Al abrir el formulario, el campo Coordinador se precarga con el usuario que tiene el perfil '
     '"Coordinación de Administración". Si esa persona cambia, la precarga se actualiza automáticamente.')
h3('Actualización multisucursal (cascada)')
steps([
    'Ingrese a Datos de Imple y busque el cliente por nombre, RIF o implementador.',
    'Presione "Editar" en la fila deseada.',
    'Modifique los campos necesarios (el sistema indica cuántas sucursales se actualizarán).',
    'Presione "Guardar y replicar".',
])
callout('Al guardar, los 5 campos se aplican a TODAS las sucursales que comparten el mismo RIF, en una sola '
        'operación. Ejemplo: si el cliente tiene 4 sucursales y cambia el Integrador, las 4 quedan actualizadas.', 'ok')
doc.add_page_break()

# ================= 7. NUEVOS PRODUCTOS =================
h1('7. Nuevos Productos')
para('Espacio para la gestión de nuevos productos del portafolio, con su documentación y seguimiento.')

# ================= 8. ADMINISTRATIVA =================
h1('8. Gestión Administrativa')
h2('8.1 Inventarios')
para('Control de activos e inventario de equipos.')
h2('8.2 Reportes Contables')
bullets([
    ('Kardex de Activos', 'movimientos de entrada/salida de activos.'),
    ('Mayor de Activos', 'saldos y resumen contable de activos.'),
    ('Salidas Facturadas', 'control de salidas con facturación asociada.'),
])

# ================= 9. TALLER =================
h1('9. Gestión de Taller')
para('Gestión de equipos que ingresan a taller: recepción, diagnóstico, reparación y entrega.')

# ================= 10. CONFIGURACIÓN =================
h1('10. Configuración')
para('Centraliza ajustes del sistema relacionados con comunicaciones y notificaciones:')
bullets([
    ('Plantillas de correo', 'creación y edición de plantillas para clientes, integradores y nuevos productos.'),
    ('Pie de página / Remitentes', 'configuración del footer y de las direcciones remitentes por área.'),
    ('Notificaciones y Otras Acciones', 'configuración del motor de notificaciones y acciones automáticas.'),
])

# ================= 11. SEGURIDAD =================
h1('11. Gestión de Seguridad')
para('Disponible para administradores:')
bullets([
    ('Creación de Usuarios', 'alta de usuarios con su cargo, departamento y datos.'),
    ('Permisos de Usuarios', 'asignación de niveles por módulo a cada usuario.'),
    ('Perfiles de Usuario', 'definición de perfiles reutilizables y activación/desactivación de módulos por perfil.'),
])
doc.add_page_break()

# ================= 12. FLUJOS DE NEGOCIO =================
h1('12. Flujos de negocio clave')

h2('12.1 De la cotización al proyecto')
steps([
    'Registrar/seleccionar el cliente (Clientes o Contacto Inicial).',
    'Elaborar la Cotización (tipo de solución, sucursales, Set Up y Costos Recurrentes).',
    'Revisar la Vista Previa y Enviar al Cliente.',
    'Al aprobarse, convertir la cotización en Proyecto (o crear un Proyecto Directo).',
    'Asignar Implementador y dar seguimiento por el ciclo de vida (Por asignar → … → Culminado).',
])

h2('12.2 Envío de Ficha Técnica al implementador')
steps([
    'Desde el Proyecto, generar/descargar la Ficha Técnica de Implementación.',
    'Verificar que el Resumen Ejecutivo incluya bancos y productos seleccionados y la distribución por sucursales.',
    'Enviar las notificaciones correspondientes (con destinatarios y copias/CC según el caso).',
])

h2('12.3 Corrección rápida de datos de implementación (multisucursal)')
steps([
    'Ingresar a Datos de Imple y buscar el cliente.',
    'Editar Componentes, Integrador, Aplicación, Implementador y/o Coordinador.',
    'Guardar: los cambios se replican a todas las sucursales del mismo RIF.',
])

# ================= 13. GLOSARIO =================
h1('13. Glosario')
table(['Término', 'Definición'],
      [['RIF', 'Registro de Información Fiscal; junto con la Sucursal forma la clave única del cliente.'],
       ['Sucursal', 'Punto/sede del cliente. Un mismo RIF puede tener varias sucursales.'],
       ['Set Up', 'Inversión inicial / puesta en marcha de la solución.'],
       ['Costos Recurrentes', 'Cargos mensuales del servicio (básicos y otros).'],
       ['VPOS / MPOS', 'Punto de venta virtual / móvil.'],
       ['Payment Gateway', 'Pasarela de pago para cobros en línea.'],
       ['Ficha Técnica', 'Documento de implementación con el resumen ejecutivo y la configuración del proyecto.'],
       ['Grupo CC', 'Conjunto reutilizable de destinatarios en copia para correos.'],
       ['Componentes', 'En Datos de Imple, corresponde al Tipo de Servicio del cliente.'],
       ['RBAC', 'Control de acceso basado en roles/perfiles.']])

# ================= 14. FAQ =================
h1('14. Preguntas frecuentes')
h3('No veo un módulo en el menú')
para('Su perfil podría no tener permiso sobre ese módulo. Solicite al administrador habilitarlo desde '
     'Gestión de Seguridad → Perfiles/Permisos.')
h3('Cambié las cajas en Set Up y no se reflejó en Recurrentes')
para('La sincronización aplica al ítem equivalente (mismo producto) y es unidireccional (Set Up → Recurrentes). '
     'Verifique que el ítem exista en ambas secciones.')
h3('La Ficha Técnica salía sin el Resumen Ejecutivo')
para('La Ficha del proyecto toma los datos del propio proyecto (bancos y productos). Vuelva a descargar la '
     'ficha desde el detalle del proyecto para obtener la versión completa.')
h3('Edité un dato en Datos de Imple, ¿afecta a todas las sucursales?')
para('Sí. Por diseño, los 5 campos se replican a todas las sucursales con el mismo RIF en una sola operación.')

# ---------- guardar ----------
out_dir = '/app/docs'
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'Manual_Usuario_MegaNexus.docx')
doc.save(out_path)
print('OK ->', out_path)
