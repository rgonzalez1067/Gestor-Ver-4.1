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
  { id: 'TBP', name: 'Torre Banco Plaza', shortName: 'TBP' },
  { id: 'LCH', name: 'Los Chaguaramos', shortName: 'LCH' }
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
    { key: 'sede_name', label: 'Nombre de la Sede' }
  ],
  quote_approved: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'approved_date', label: 'Fecha de Aprobación' },
    { key: 'sede_name', label: 'Nombre de la Sede' }
  ],
  invoice: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'invoice_number', label: 'Número de Factura' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' }
  ],
  warehouse: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'client_address', label: 'Dirección del Cliente' },
    { key: 'items_table', label: 'Tabla de Items' },
    { key: 'sede_name', label: 'Nombre de la Sede' }
  ],
  implementation: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_name', label: 'Nombre del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'services_table', label: 'Tabla de Servicios' },
    { key: 'sede_name', label: 'Nombre de la Sede' }
  ]
};

// Función para obtener variables de una plantilla específica
const getTemplateVariables = (templateId) => {
  // Extraer el tipo base del template_id (ej: quote_sent_TBP -> quote_sent)
  const baseType = templateId.replace(/_TBP$|_LCH$/, '');
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
    const variables = TEMPLATE_VARIABLES[editingTemplate?.template_id] || [];
    
    const exampleValues = {
      quote_number: 'COT-2024-001',
      client_name: 'Empresa Ejemplo C.A.',
      client_rif: 'J-12345678-9',
      quote_type: 'VPOS',
      total_usd: '1,500.00',
      company_name: 'Merchant Server',
      invoice_number: 'FAC-001234',
      client_address: 'Av. Principal, Edificio Centro, Piso 3',
      integrator_name: 'Integrador Demo (App Demo)',
      pinpad_model: 'Verifone P400',
      items_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Producto</th><th style="padding:8px;border:1px solid #ddd">Cantidad</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Terminal POS</td><td style="padding:8px;border:1px solid #ddd;text-align:center">2</td></tr></table>',
      services_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Servicio</th><th style="padding:8px;border:1px solid #ddd">Categoría</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Setup Inicial</td><td style="padding:8px;border:1px solid #ddd;text-align:center">setup</td></tr></table>'
    };
    
    for (const v of variables) {
      const placeholder = `{${v.key}}`;
      html = html.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), exampleValues[v.key] || v.label);
    }
    
    setPreviewHtml(html);
    setPreviewDialogOpen(true);
  };

  const insertVariable = (variable) => {
    const textarea = document.getElementById('template-body');
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = formData.body_html;
      const before = text.substring(0, start);
      const after = text.substring(end);
      const newText = before + `{${variable}}` + after;
      setFormData(prev => ({ ...prev, body_html: newText }));
    } else {
      setFormData(prev => ({ ...prev, body_html: prev.body_html + `{${variable}}` }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin h-8 w-8 border-4 border-brand-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-slate-600 mb-4">
        <AlertCircle size={16} />
        <span className="text-sm">Use <code className="bg-slate-100 px-1 rounded">{'{variable}'}</code> para insertar datos dinámicos en las plantillas.</span>
      </div>

      {/* Lista de plantillas */}
      <div className="grid gap-4">
        {templates.map((template) => {
          const config = TEMPLATE_CONFIG[template.template_id] || {};
          const IconComponent = config.icon || Mail;
          
          return (
            <div 
              key={template.template_id}
              className={`p-4 rounded-lg border ${config.borderColor || 'border-slate-200'} ${config.bgColor || 'bg-slate-50'}`}
              data-testid={`email-template-${template.template_id}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg bg-white ${config.color || 'text-slate-600'}`}>
                    <IconComponent size={24} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900">{config.title || template.name}</h3>
                    <p className="text-sm text-slate-600 mt-1">{config.description || template.description}</p>
                    <div className="mt-2 text-xs text-slate-500">
                      <span className="font-medium">Asunto:</span> {template.subject?.substring(0, 50)}...
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditDialog(template)}
                    data-testid={`edit-template-${template.template_id}`}
                  >
                    <Edit size={14} className="mr-1" />
                    Editar
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleReset(template.template_id)}
                    className="text-slate-500 hover:text-red-600"
                    data-testid={`reset-template-${template.template_id}`}
                  >
                    <RotateCcw size={14} />
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

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

            {/* Variables disponibles */}
            <div>
              <Label className="font-semibold mb-2 block">Variables Disponibles</Label>
              <div className="flex flex-wrap gap-2 p-3 bg-slate-50 rounded-lg border">
                {(TEMPLATE_VARIABLES[editingTemplate?.template_id] || []).map((v) => (
                  <button
                    key={v.key}
                    onClick={() => insertVariable(v.key)}
                    className="px-2 py-1 text-xs bg-white border border-slate-300 rounded hover:bg-slate-100 hover:border-brand-blue-500 transition-colors"
                    title={`Insertar {${v.key}}`}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>

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
