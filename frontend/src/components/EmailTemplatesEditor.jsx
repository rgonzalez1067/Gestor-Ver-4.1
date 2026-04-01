import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Mail, FileText, Warehouse, Settings2, Edit, RotateCcw, Eye, Save, X, AlertCircle, CheckCircle, MapPin } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Sedes disponibles
const SEDES = [
  { id: 'PYME', name: 'Pyme', shortName: 'Pyme' },
  { id: 'CORP', name: 'Corp', shortName: 'Corp' }
];

// Tipos base de plantillas (sin sede)
const BASE_TEMPLATE_TYPES = [
  {
    baseId: 'quote_sent',
    icon: Mail,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    title: 'Envío de Cotización a Cliente',
    description: 'Se envía al cliente cuando se genera una cotización'
  },
  {
    baseId: 'quote_approved',
    icon: CheckCircle,
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    title: 'Cotización Aprobada',
    description: 'Se envía cuando una cotización es aprobada'
  },
  {
    baseId: 'invoice',
    icon: FileText,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    title: 'Facturación y Control Contable',
    description: 'Se envía a Administración cuando se factura'
  },
  {
    baseId: 'warehouse',
    icon: Warehouse,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    title: 'Despacho de Equipos',
    description: 'Se envía a Almacén cuando equipos son pagados'
  },
  {
    baseId: 'implementation',
    icon: Settings2,
    color: 'text-cyan-600',
    bgColor: 'bg-cyan-50',
    borderColor: 'border-cyan-200',
    title: 'Envío a Implementación',
    description: 'Se envía a Implementación con detalles técnicos'
  },
  {
    baseId: 'payment_receipt',
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    title: 'Envío de Comprobante de Pago',
    description: 'Notifica a Ventas que el cliente pagó para enviar a Implementación'
  }
];

// Plantillas globales de Proyecto (no se dividen por sede)
const PROJECT_TEMPLATE_TYPES = [
  {
    templateId: 'project_notify_client',
    icon: Mail,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    title: 'Notificación de Proyecto — Cliente',
    description: 'Comunicaciones secuenciales al cliente durante implementación'
  },
  {
    templateId: 'project_notify_bank',
    icon: Mail,
    color: 'text-teal-600',
    bgColor: 'bg-teal-50',
    borderColor: 'border-teal-200',
    title: 'Notificación de Proyecto — Banco',
    description: 'Comunicaciones secuenciales a bancos durante implementación'
  }
];

// Generar configuración de plantillas por sede
const generateTemplateConfig = () => {
  const config = {};
  SEDES.forEach(sede => {
    BASE_TEMPLATE_TYPES.forEach(template => {
      const templateId = `${template.baseId}_${sede.id}`;
      config[templateId] = {
        ...template,
        title: `${template.title} (Sede ${sede.shortName})`,
        sede: sede.id,
        sedeName: sede.name
      };
    });
  });
  return config;
};

const TEMPLATE_CONFIG = generateTemplateConfig();

// Variables disponibles por tipo de plantilla (aplican a todas las sedes)
const BASE_TEMPLATE_VARIABLES = {
  quote_sent: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'company_name', label: 'Nombre de la Empresa' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  quote_approved: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'approved_date', label: 'Fecha de Aprobación' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  invoice: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'invoice_number', label: 'Número de Factura' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  warehouse: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'client_address', label: 'Dirección del Cliente' },
    { key: 'items_table', label: 'Tabla de Items' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  implementation: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_name', label: 'Nombre del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'services_table', label: 'Tabla de Servicios' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  payment_receipt: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_quote_sent: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'modelos_resumen', label: 'Resumen de Modelos' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_approved: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_complete_client: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'lista_modelos_seriales', label: 'Lista de Modelos y Seriales' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_delivery: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'tipo_nota_entrega', label: 'Tipo de Entrega (Parcial/Final)' },
    { key: 'nro_nota_entrega', label: 'Nro. Nota de Entrega' },
    { key: 'cantidad_entregada', label: 'Cantidad Entregada' },
    { key: 'estatus_entrega', label: 'Estatus de Entrega' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' }
  ],
  repair_collect_warehouse: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'lista_equipos_seriales', label: 'Lista de Equipos y Seriales' },
    { key: 'almacen_custodia', label: 'Almacén de Custodia' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  // === Plantillas de Notificaciones de Proyectos (Implementación) ===
  project_notify_client: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente (Razón Social)' },
    { key: 'Contacto_Principal', label: 'Contacto Principal del Cliente' },
    { key: 'Nombre_Sucursal', label: 'Nombre de Sucursal(es)' },
    { key: 'Cantidad_Cajas', label: 'Cantidad de Cajas (PDVs)' },
    { key: 'Integrador', label: 'Integrador Asignado' },
    { key: 'Aplicativo_Integracion', label: 'Aplicativo de Integración' },
    { key: 'Nombre_Implementador', label: 'Nombre del Implementador' },
    { key: 'Correo_Implementador', label: 'Correo del Implementador' },
    { key: 'Telefono_Implementador', label: 'Teléfono del Implementador' },
    { key: 'Matriz_Bancos_Productos', label: 'Tabla de Bancos y Productos (HTML)' },
    { key: 'project_number', label: 'Nro. de Proyecto' },
    { key: 'quote_number', label: 'Nro. de Cotización' },
    { key: 'ticket_number', label: 'Nro. de Ticket' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'notification_level', label: 'Nivel de Notificación' },
    { key: 'notification_subject', label: 'Asunto de Notificación' },
    { key: 'assigned_to', label: 'Asignado a' },
  ],
  project_notify_bank: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente (Razón Social)' },
    { key: 'Contacto_Principal', label: 'Contacto Principal del Cliente' },
    { key: 'Nombre_Sucursal', label: 'Nombre de Sucursal(es)' },
    { key: 'Cantidad_Cajas', label: 'Cantidad de Cajas (PDVs)' },
    { key: 'Integrador', label: 'Integrador Asignado' },
    { key: 'Aplicativo_Integracion', label: 'Aplicativo de Integración' },
    { key: 'Nombre_Implementador', label: 'Nombre del Implementador' },
    { key: 'Correo_Implementador', label: 'Correo del Implementador' },
    { key: 'Telefono_Implementador', label: 'Teléfono del Implementador' },
    { key: 'Matriz_Bancos_Productos', label: 'Tabla de Bancos y Productos (HTML)' },
    { key: 'bank_name', label: 'Nombre del Banco' },
    { key: 'bank_products', label: 'Productos del Banco' },
    { key: 'project_number', label: 'Nro. de Proyecto' },
    { key: 'quote_number', label: 'Nro. de Cotización' },
    { key: 'ticket_number', label: 'Nro. de Ticket' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_app_name', label: 'Aplicativo del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'notification_level', label: 'Nivel de Notificación' },
    { key: 'notification_subject', label: 'Asunto de Notificación' },
  ],
};

// Función para obtener variables de una plantilla específica
const getTemplateVariables = (templateId) => {
  if (!templateId) return [];
  // Extraer el tipo base del template_id (ej: quote_sent_TBP -> quote_sent)
  const baseType = templateId.replace(/_PYME$|_CORP$/, '');
  return BASE_TEMPLATE_VARIABLES[baseType] || [];
};

export const EmailTemplatesEditor = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [saving, setSaving] = useState(false);
  
  // Formulario de edición
  const [formData, setFormData] = useState({
    subject: '',
    body_html: ''
  });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await api.get('/email-templates');
      setTemplates(response.data);
    } catch (error) {
      console.error('Error fetching templates:', error);
      toast.error('Error al cargar plantillas');
    } finally {
      setLoading(false);
    }
  };

  const openEditDialog = (template) => {
    setEditingTemplate(template);
    setFormData({
      subject: template.subject || '',
      body_html: template.body_html || ''
    });
    setEditDialogOpen(true);
  };

  const handleSave = async () => {
    if (!editingTemplate) return;
    
    setSaving(true);
    try {
      await api.put(`/email-templates/${editingTemplate.template_id}`, {
        ...editingTemplate,
        subject: formData.subject,
        body_html: formData.body_html
      });
      
      toast.success('Plantilla guardada exitosamente');
      setEditDialogOpen(false);
      fetchTemplates();
    } catch (error) {
      console.error('Error saving template:', error);
      toast.error('Error al guardar plantilla');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (templateId) => {
    if (!window.confirm('¿Está seguro de restablecer esta plantilla a los valores predeterminados?')) return;
    
    try {
      await api.post(`/email-templates/reset/${templateId}`);
      toast.success('Plantilla restablecida');
      fetchTemplates();
      if (editDialogOpen && editingTemplate?.template_id === templateId) {
        // Recargar datos en el formulario
        const response = await api.get(`/email-templates/${templateId}`);
        setFormData({
          subject: response.data.subject,
          body_html: response.data.body_html
        });
      }
    } catch (error) {
      console.error('Error resetting template:', error);
      toast.error('Error al restablecer plantilla');
    }
  };

  const openPreview = () => {
    // Reemplazar variables con ejemplos
    let html = formData.body_html;
    const variables = getTemplateVariables(editingTemplate?.template_id) || [];
    
    const exampleValues = {
      quote_number: 'COT-2024-001',
      client_name: 'Empresa Ejemplo C.A.',
      client_rif: 'J-12345678-9',
      quote_type: 'VPOS',
      total_usd: '1,500.00',
      company_name: 'Gestor WFPI',
      invoice_number: 'FAC-001234',
      client_address: 'Av. Principal, Edificio Centro, Piso 3',
      integrator_name: 'Integrador Demo (App Demo)',
      pinpad_model: 'Verifone P400',
      approved_date: '24/02/2026',
      sede_name: 'Torre Banco Plaza',
      Nombre_Ejecutivo: 'Rafael González',
      Email_Ejecutivo: 'rgonzalez@megasoft.com.ve',
      // Variables de Proyecto
      Nombre_Cliente: 'MegaFarma, C.A.',
      Contacto_Principal: 'Pedro Pérez',
      Nombre_Sucursal: 'Norte, Sur, Este',
      Cantidad_Cajas: 'Norte: 5 | Sur: 2 | Este: 3 (Total: 10)',
      Integrador: 'A2 Softway C.A.',
      Aplicativo_Integracion: 'A2 Softway POS',
      Nombre_Implementador: 'Carlos Rodríguez',
      Correo_Implementador: 'crodriguez@meganexus.com',
      Telefono_Implementador: '+58 412 555-0123',
      Matriz_Bancos_Productos: '<table style="border-collapse:collapse;width:100%;font-size:13px;"><thead><tr style="background:#2c3e50;color:white;"><th style="padding:8px;border:1px solid #ddd;">Banco</th><th style="padding:8px;border:1px solid #ddd;">Producto / Servicio</th><th style="padding:8px;border:1px solid #ddd;text-align:center;">Cantidad</th></tr></thead><tbody><tr><td style="padding:8px;border:1px solid #ddd;">Banco Mercantil</td><td style="padding:8px;border:1px solid #ddd;">Tarjeta de Crédito/Débito</td><td style="padding:8px;border:1px solid #ddd;text-align:center;">1</td></tr><tr style="background:#f8f9fa;"><td style="padding:8px;border:1px solid #ddd;">Banesco</td><td style="padding:8px;border:1px solid #ddd;">C2P o Débito Inmediato</td><td style="padding:8px;border:1px solid #ddd;text-align:center;">1</td></tr></tbody></table>',
      project_number: 'PRY-2026-03-001-PRI',
      ticket_number: '56785',
      bank_name: 'Banco Mercantil',
      bank_products: 'Tarjeta de Crédito/Débito, C2P o Débito Inmediato',
      notification_level: 'Primera Comunicación',
      notification_subject: 'Notificación de Implementación',
      assigned_to: 'Carlos Rodríguez',
      items_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Producto</th><th style="padding:8px;border:1px solid #ddd">Cantidad</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Terminal POS</td><td style="padding:8px;border:1px solid #ddd;text-align:center">2</td></tr></table>',
      services_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Servicio</th><th style="padding:8px;border:1px solid #ddd">Categoría</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Setup Inicial</td><td style="padding:8px;border:1px solid #ddd;text-align:center">setup</td></tr></table>',
      nro_cotizacion: 'COT-2024-001',
      nombre_cliente: 'Empresa Ejemplo C.A.',
      contacto_cliente: 'Juan Pérez',
      modelos_resumen: 'Verifone P400 (x3), Verifone V240m (x2)',
      lista_modelos_seriales: '<p><strong>Verifone P400</strong>: SN001, SN002, SN003</p><p><strong>Verifone V240m</strong>: SN004, SN005</p>',
      tipo_nota_entrega: 'Entrega Final',
      nro_nota_entrega: 'NE-2026-0015',
      cantidad_entregada: '5',
      estatus_entrega: 'Finalizado',
      lista_equipos_seriales: '<p><strong>Verifone P400</strong> (3 uds): SN001, SN002, SN003</p><p><strong>Verifone V240m</strong> (2 uds): SN004, SN005</p>',
      almacen_custodia: 'Torre Banco Plaza'
    };
    
    for (const v of variables) {
      const placeholder = `{${v.key}}`;
      html = html.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), exampleValues[v.key] || v.label);
    }
    
    setPreviewHtml(html);
    setPreviewDialogOpen(true);
  };

  const insertVariable = (variable, targetField = 'body') => {
    const elementId = targetField === 'subject' ? 'template-subject' : 'template-body';
    const fieldKey = targetField === 'subject' ? 'subject' : 'body_html';
    const el = document.getElementById(elementId);
    if (el) {
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const text = formData[fieldKey];
      const before = text.substring(0, start);
      const after = text.substring(end);
      const newText = before + `{${variable}}` + after;
      setFormData(prev => ({ ...prev, [fieldKey]: newText }));
      // Restore cursor position after insert
      setTimeout(() => {
        el.focus();
        const newPos = start + variable.length + 2;
        el.setSelectionRange(newPos, newPos);
      }, 50);
    } else {
      setFormData(prev => ({ ...prev, [fieldKey]: prev[fieldKey] + `{${variable}}` }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin h-8 w-8 border-4 border-brand-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  // Agrupar plantillas por sede
  const templatesBySede = {};
  SEDES.forEach(sede => {
    templatesBySede[sede.id] = templates.filter(t => t.template_id?.endsWith(`_${sede.id}`));
  });
  
  // Plantillas legacy (sin sede)
  const legacyTemplates = templates.filter(t => !t.template_id?.endsWith('_PYME') && !t.template_id?.endsWith('_CORP') && !t.is_project_template && !PROJECT_TEMPLATE_TYPES.some(pt => pt.templateId === t.template_id));

  // Plantillas de proyecto (globales)
  const projectTemplates = templates.filter(t => t.is_project_template || PROJECT_TEMPLATE_TYPES.some(pt => pt.templateId === t.template_id));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-slate-600 mb-4">
        <AlertCircle size={16} />
        <span className="text-sm">Use <code className="bg-slate-100 px-1 rounded">{'{variable}'}</code> para insertar datos dinámicos en las plantillas.</span>
      </div>

      {/* Plantillas agrupadas por sede */}
      {SEDES.map((sede) => (
        <div key={sede.id} className="border border-slate-200 rounded-lg overflow-hidden">
          {/* Header de la Sede */}
          <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <MapPin size={18} className="text-slate-600" />
              <span className="font-semibold text-slate-800">Plantillas Sede {sede.name}</span>
            </div>
          </div>
          
          <div className="p-4 space-y-3">
            {templatesBySede[sede.id]?.length > 0 ? (
              templatesBySede[sede.id].map((template) => {
                const config = TEMPLATE_CONFIG[template.template_id] || {};
                const IconComponent = config.icon || Mail;
                
                return (
                  <div 
                    key={template.template_id}
                    className={`p-3 rounded-lg border ${config.borderColor || 'border-slate-200'} ${config.bgColor || 'bg-slate-50'}`}
                    data-testid={`email-template-${template.template_id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg bg-white ${config.color || 'text-slate-600'}`}>
                          <IconComponent size={20} />
                        </div>
                        <div>
                          <h3 className="font-medium text-slate-900 text-sm">{config.title || template.name}</h3>
                          <p className="text-xs text-slate-600 mt-0.5">{config.description || template.description}</p>
                          <div className="mt-1 text-xs text-slate-500">
                            <span className="font-medium">Asunto:</span> {template.subject?.substring(0, 40)}...
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(template)}
                          className="h-7 text-xs"
                          data-testid={`edit-template-${template.template_id}`}
                        >
                          <Edit size={12} className="mr-1" />
                          Editar
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReset(template.template_id)}
                          className="h-7 text-slate-500 hover:text-red-600"
                          data-testid={`reset-template-${template.template_id}`}
                        >
                          <RotateCcw size={12} />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">
                No hay plantillas configuradas para esta sede. Se crearán automáticamente.
              </p>
            )}
          </div>
        </div>
      ))}

      {/* ===== Sección: Plantillas de Proyecto (Implementación) ===== */}
      {projectTemplates.length > 0 && (
        <div className="border border-orange-200 rounded-lg overflow-hidden">
          <div className="bg-gradient-to-r from-orange-50 to-teal-50 px-4 py-3 border-b border-orange-200">
            <div className="flex items-center gap-2">
              <Settings2 size={18} className="text-orange-600" />
              <span className="font-semibold text-slate-800">Plantillas de Proyecto (Implementación)</span>
            </div>
            <p className="text-xs text-slate-600 mt-1">
              Plantillas para las comunicaciones secuenciales con clientes y bancos durante el proceso de implementación.
              Las variables se resuelven automáticamente desde los datos del proyecto.
            </p>
          </div>
          
          <div className="p-4 space-y-3">
            {projectTemplates.map((template) => {
              const ptConfig = PROJECT_TEMPLATE_TYPES.find(pt => pt.templateId === template.template_id) || {};
              const IconComponent = ptConfig.icon || Mail;
              
              return (
                <div 
                  key={template.template_id}
                  className={`p-3 rounded-lg border ${ptConfig.borderColor || 'border-slate-200'} ${ptConfig.bgColor || 'bg-slate-50'}`}
                  data-testid={`email-template-${template.template_id}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg bg-white ${ptConfig.color || 'text-slate-600'}`}>
                        <IconComponent size={20} />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-900 text-sm">{ptConfig.title || template.name}</h3>
                        <p className="text-xs text-slate-600 mt-0.5">{ptConfig.description || template.description}</p>
                        <div className="mt-1 text-xs text-slate-500">
                          <span className="font-medium">Asunto:</span> {template.subject?.substring(0, 50)}...
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditDialog(template)}
                        className="h-7 text-xs"
                        data-testid={`edit-template-${template.template_id}`}
                      >
                        <Edit size={12} className="mr-1" />
                        Editar
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleReset(template.template_id)}
                        className="h-7 text-slate-500 hover:text-red-600"
                      >
                        <RotateCcw size={12} />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Plantillas legacy (sin sede) - mostrar si existen */}
      {legacyTemplates.length > 0 && (
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <div className="bg-amber-50 px-4 py-3 border-b border-amber-200">
            <div className="flex items-center gap-2">
              <AlertCircle size={18} className="text-amber-600" />
              <span className="font-semibold text-amber-800">Plantillas Generales (Sin Sede)</span>
            </div>
            <p className="text-xs text-amber-700 mt-1">Estas plantillas se migrarán a plantillas por sede.</p>
          </div>
          
          <div className="p-4 space-y-3">
            {legacyTemplates.map((template) => {
              const config = TEMPLATE_CONFIG[template.template_id] || {};
              const IconComponent = config.icon || Mail;
              
              return (
                <div 
                  key={template.template_id}
                  className={`p-3 rounded-lg border ${config.borderColor || 'border-slate-200'} ${config.bgColor || 'bg-slate-50'}`}
                  data-testid={`email-template-${template.template_id}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg bg-white ${config.color || 'text-slate-600'}`}>
                        <IconComponent size={20} />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-900 text-sm">{config.title || template.name}</h3>
                        <p className="text-xs text-slate-600 mt-0.5">{config.description || template.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditDialog(template)}
                        className="h-7 text-xs"
                      >
                        <Edit size={12} className="mr-1" />
                        Editar
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Dialog de edición */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="text-brand-blue-600" size={20} />
              Editar Plantilla: {TEMPLATE_CONFIG[editingTemplate?.template_id]?.title || editingTemplate?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Asunto */}
            <div>
              <Label htmlFor="template-subject" className="font-semibold">
                Asunto del Correo
              </Label>
              <Input
                id="template-subject"
                value={formData.subject}
                onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
                placeholder="Asunto del correo..."
                className="mt-1"
                data-testid="template-subject-input"
              />
            </div>

            {/* Variables disponibles — Panel mejorado */}
            {getTemplateVariables(editingTemplate?.template_id).length > 0 && (
              <div className="border border-indigo-200 rounded-lg overflow-hidden">
                <div className="bg-indigo-50 px-3 py-2 border-b border-indigo-100 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <AlertCircle size={14} className="text-indigo-500" />
                    <span className="text-xs font-semibold text-indigo-700 uppercase">Panel de Variables ({getTemplateVariables(editingTemplate?.template_id).length})</span>
                  </div>
                  <span className="text-[10px] text-indigo-500">Click para insertar en el campo activo</span>
                </div>
                <div className="p-3 bg-white space-y-2.5">
                  <div>
                    <p className="text-[10px] font-medium text-slate-400 uppercase mb-1">Insertar en Asunto</p>
                    <div className="flex flex-wrap gap-1.5">
                      {getTemplateVariables(editingTemplate?.template_id).map((v) => (
                        <button
                          key={`subj-${v.key}`}
                          onClick={() => insertVariable(v.key, 'subject')}
                          className="px-2 py-0.5 text-[11px] bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 hover:border-blue-400 transition-colors text-blue-700 font-mono cursor-pointer"
                          title={`Insertar {${v.key}} en el asunto`}
                          data-testid={`var-subject-${v.key}`}
                        >
                          {`{${v.key}}`}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="border-t pt-2">
                    <p className="text-[10px] font-medium text-slate-400 uppercase mb-1">Insertar en Cuerpo</p>
                    <div className="flex flex-wrap gap-1.5">
                      {getTemplateVariables(editingTemplate?.template_id).map((v) => (
                        <button
                          key={`body-${v.key}`}
                          onClick={() => insertVariable(v.key, 'body')}
                          className="group px-2 py-1 text-xs bg-white border border-slate-200 rounded hover:bg-indigo-50 hover:border-indigo-400 transition-colors cursor-pointer"
                          title={`Insertar {${v.key}} en el cuerpo`}
                          data-testid={`var-body-${v.key}`}
                        >
                          <span className="font-mono text-indigo-600 text-[11px]">{`{${v.key}}`}</span>
                          <span className="ml-1.5 text-slate-400 group-hover:text-slate-600">{v.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Cuerpo del correo */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label htmlFor="template-body" className="font-semibold">
                  Cuerpo del Correo (HTML)
                </Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openPreview}
                  className="text-brand-blue-600"
                >
                  <Eye size={14} className="mr-1" />
                  Vista Previa
                </Button>
              </div>
              <Textarea
                id="template-body"
                value={formData.body_html}
                onChange={(e) => setFormData(prev => ({ ...prev, body_html: e.target.value }))}
                placeholder="Contenido HTML del correo..."
                rows={15}
                className="font-mono text-sm"
                data-testid="template-body-input"
              />
              <p className="text-xs text-slate-500 mt-1">
                Puede usar HTML para dar formato al correo. Las variables entre llaves serán reemplazadas automáticamente.
              </p>
            </div>
          </div>

          <DialogFooter className="flex justify-between">
            <Button
              variant="ghost"
              onClick={() => handleReset(editingTemplate?.template_id)}
              className="text-slate-500"
            >
              <RotateCcw size={14} className="mr-1" />
              Restablecer Predeterminado
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
                Cancelar
              </Button>
              <Button
                onClick={handleSave}
                disabled={saving}
                className="bg-brand-green-600 hover:bg-brand-green-700"
                data-testid="save-template-btn"
              >
                <Save size={14} className="mr-1" />
                {saving ? 'Guardando...' : 'Guardar Plantilla'}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de vista previa */}
      <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="text-brand-blue-600" size={20} />
              Vista Previa del Correo
            </DialogTitle>
          </DialogHeader>

          <div className="border rounded-lg p-4 bg-white max-h-[60vh] overflow-y-auto">
            <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
              <X size={14} className="mr-1" />
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmailTemplatesEditor;
