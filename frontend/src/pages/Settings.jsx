import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Upload, Trash2, Image, Database, FileText, Check, X, Download, Mail, Save, Building2, Warehouse } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const TEMPLATE_TYPES = [
  { id: 'vpos_pyme', name: 'VPOS Pyme', description: 'Cotización para pequeñas y medianas empresas con VPOS' },
  { id: 'vpos_corporativo', name: 'VPOS Corporativo', description: 'Cotización para empresas corporativas con VPOS' },
  { id: 'payment_gateway', name: 'Payment Gateway', description: 'Cotización para pasarela de pagos (Ecommerce)' },
  { id: 'mpos', name: 'MPOS', description: 'Cotización para soluciones móviles (Tablet/Android)' },
  { id: 'dispositivos', name: 'Dispositivos', description: 'Cotización de dispositivos de pago' },
  { id: 'accesorios', name: 'Accesorios', description: 'Cotización de accesorios complementarios' }
];

export const Settings = () => {
  const [logoUrl, setLogoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [templates, setTemplates] = useState({});
  const [uploadingTemplate, setUploadingTemplate] = useState(null);
  const [implementationEmail, setImplementationEmail] = useState('');
  const [savingEmail, setSavingEmail] = useState(false);
  const fileInputRef = useRef(null);
  const templateInputRefs = useRef({});

  useEffect(() => {
    fetchLogo();
    fetchTemplates();
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await api.get('/config/settings');
      setImplementationEmail(response.data.implementation_email || '');
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  };

  const handleSaveImplementationEmail = async () => {
    if (!implementationEmail) {
      toast.error('Ingrese un email válido');
      return;
    }
    
    setSavingEmail(true);
    try {
      await api.put('/config/settings', { implementation_email: implementationEmail });
      toast.success('Email de implementación guardado');
    } catch (error) {
      toast.error('Error al guardar el email');
    } finally {
      setSavingEmail(false);
    }
  };

  const fetchLogo = async () => {
    try {
      const response = await api.get('/config/logo', { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      setLogoUrl(url);
    } catch (error) {
      if (error.response?.status !== 404) {
        console.error('Error fetching logo:', error);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await api.get('/config/templates');
      setTemplates(response.data);
    } catch (error) {
      console.error('Error fetching templates:', error);
    }
  };

  const handleTemplateUpload = async (templateType, event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      toast.error('Por favor seleccione un archivo PDF');
      return;
    }

    setUploadingTemplate(templateType);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post(`/config/templates/${templateType}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Plantilla subida exitosamente');
      fetchTemplates();
    } catch (error) {
      console.error('Error uploading template:', error);
      toast.error('Error al subir la plantilla');
    } finally {
      setUploadingTemplate(null);
      // Reset the input
      if (templateInputRefs.current[templateType]) {
        templateInputRefs.current[templateType].value = '';
      }
    }
  };

  const handleTemplateDelete = async (templateType) => {
    if (!window.confirm('¿Está seguro de eliminar esta plantilla?')) return;

    try {
      await api.delete(`/config/templates/${templateType}`);
      toast.success('Plantilla eliminada exitosamente');
      fetchTemplates();
    } catch (error) {
      console.error('Error deleting template:', error);
      toast.error('Error al eliminar la plantilla');
    }
  };

  const handleTemplateDownload = async (templateType, templateName) => {
    try {
      const response = await api.get(`/config/templates/${templateType}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `plantilla_${templateType}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error al descargar la plantilla');
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      toast.error('Por favor seleccione un archivo de imagen');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post('/config/logo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Logo subido exitosamente');
      fetchLogo();
    } catch (error) {
      console.error('Error uploading logo:', error);
      toast.error('Error al subir el logo');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteLogo = async () => {
    if (!window.confirm('¿Está seguro de eliminar el logo?')) return;

    try {
      await api.delete('/config/logo');
      setLogoUrl(null);
      toast.success('Logo eliminado exitosamente');
    } catch (error) {
      console.error('Error deleting logo:', error);
      toast.error('Error al eliminar el logo');
    }
  };

  const handleSeedBanks = async () => {
    if (!window.confirm('¿Desea poblar la base de datos con bancos de Venezuela, EE.UU. y Fintechs?')) return;

    setSeeding(true);
    try {
      const response = await api.post('/banks/seed');
      toast.success(response.data.message);
    } catch (error) {
      console.error('Error seeding banks:', error);
      toast.error('Error al poblar la base de datos');
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando configuración...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="settings-page">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
              Configuración
            </h1>
            <p className="text-slate-600">Personalice la aplicación según sus necesidades</p>
          </div>

          {/* Logo Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <Image size={24} />
              Logo de la Empresa
            </h2>
            <p className="text-slate-600 mb-6">
              Suba el logo de su empresa para personalizar las cotizaciones y documentos.
            </p>

            <div className="flex items-start gap-8">
              <div className="flex-shrink-0">
                {logoUrl ? (
                  <div className="relative">
                    <img
                      src={logoUrl}
                      alt="Logo de la empresa"
                      className="w-48 h-48 object-contain border border-slate-200 rounded-lg bg-slate-50 p-2"
                      data-testid="company-logo"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleDeleteLogo}
                      className="absolute -top-2 -right-2 text-red-600 hover:text-red-700 hover:border-red-300 bg-white"
                      data-testid="delete-logo-button"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                ) : (
                  <div className="w-48 h-48 border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center bg-slate-50">
                    <Image size={48} className="text-slate-400 mb-2" />
                    <p className="text-sm text-slate-500">Sin logo</p>
                  </div>
                )}
              </div>

              <div className="flex-1">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  accept="image/*"
                  className="hidden"
                  data-testid="logo-file-input"
                />
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  data-testid="upload-logo-button"
                >
                  <Upload size={20} className="mr-2" />
                  {uploading ? 'Subiendo...' : 'Subir Logo'}
                </Button>
                <p className="text-sm text-slate-500 mt-3">
                  Formatos soportados: PNG, JPG, JPEG, GIF, SVG
                </p>
                <p className="text-sm text-slate-500">
                  Tamaño recomendado: 200x200 píxeles o mayor
                </p>
              </div>
            </div>
          </div>

          {/* Database Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <Database size={24} />
              Base de Datos
            </h2>
            <p className="text-slate-600 mb-6">
              Inicialice la base de datos con información predeterminada.
            </p>

            <div className="space-y-4">
              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                <h3 className="font-medium text-slate-900 mb-2">Poblar Bancos</h3>
                <p className="text-sm text-slate-600 mb-4">
                  Agrega automáticamente los principales bancos de Venezuela, bancos de Estados Unidos 
                  (Bank of America, Banesco USA, Wells Fargo, Citi Bank, US Bank, Chase, Amerant) 
                  y Fintechs (Cashea, Lysto, Crixto).
                </p>
                <Button
                  onClick={handleSeedBanks}
                  disabled={seeding}
                  variant="outline"
                  data-testid="seed-banks-button"
                >
                  <Database size={16} className="mr-2" />
                  {seeding ? 'Poblando...' : 'Poblar Bancos'}
                </Button>
              </div>
            </div>
          </div>

          {/* Email de Implementación Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <Mail size={24} />
              Email de Implementación
            </h2>
            <p className="text-slate-600 mb-6">
              Configure el correo electrónico del equipo de implementación. Las cotizaciones aprobadas 
              serán enviadas a este email cuando se utilice la acción "Enviar a Implementación".
            </p>

            <div className="flex items-end gap-4 max-w-md">
              <div className="flex-1">
                <Label htmlFor="implementation-email" className="text-sm font-medium text-slate-700 mb-2 block">
                  Email del equipo
                </Label>
                <Input
                  id="implementation-email"
                  type="email"
                  value={implementationEmail}
                  onChange={(e) => setImplementationEmail(e.target.value)}
                  placeholder="implementacion@empresa.com"
                  className="w-full"
                  data-testid="implementation-email-input"
                />
              </div>
              <Button
                onClick={handleSaveImplementationEmail}
                disabled={savingEmail}
                className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
                data-testid="save-email-button"
              >
                <Save size={16} className="mr-2" />
                {savingEmail ? 'Guardando...' : 'Guardar'}
              </Button>
            </div>
            {implementationEmail && (
              <p className="text-sm text-green-600 mt-2 flex items-center gap-1">
                <Check size={14} />
                Email configurado correctamente
              </p>
            )}
          </div>

          {/* Templates Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <FileText size={24} />
              Plantillas de Cotización (PDF)
            </h2>
            <p className="text-slate-600 mb-6">
              Cargue los modelos de cotización en formato PDF para cada tipo de producto/servicio.
              Estas plantillas se utilizarán como referencia para las cotizaciones generadas.
            </p>

            <div className="grid gap-4">
              {TEMPLATE_TYPES.map((template) => {
                const templateStatus = templates[template.id];
                const isUploading = uploadingTemplate === template.id;
                
                return (
                  <div 
                    key={template.id} 
                    className={`p-4 rounded-lg border ${templateStatus?.exists ? 'bg-green-50 border-green-200' : 'bg-slate-50 border-slate-200'}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${templateStatus?.exists ? 'bg-green-100' : 'bg-slate-200'}`}>
                          {templateStatus?.exists ? (
                            <Check size={20} className="text-green-600" />
                          ) : (
                            <X size={20} className="text-slate-400" />
                          )}
                        </div>
                        <div>
                          <h3 className="font-medium text-slate-900">{template.name}</h3>
                          <p className="text-sm text-slate-500">{template.description}</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <input
                          type="file"
                          ref={(el) => templateInputRefs.current[template.id] = el}
                          onChange={(e) => handleTemplateUpload(template.id, e)}
                          accept="application/pdf"
                          className="hidden"
                          data-testid={`template-input-${template.id}`}
                        />
                        
                        {templateStatus?.exists && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleTemplateDownload(template.id, template.name)}
                              className="text-brand-blue-600 hover:text-brand-blue-700"
                              data-testid={`download-template-${template.id}`}
                            >
                              <Download size={16} className="mr-1" />
                              Ver
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleTemplateDelete(template.id)}
                              className="text-red-600 hover:text-red-700 hover:border-red-300"
                              data-testid={`delete-template-${template.id}`}
                            >
                              <Trash2 size={16} />
                            </Button>
                          </>
                        )}
                        
                        <Button
                          size="sm"
                          onClick={() => templateInputRefs.current[template.id]?.click()}
                          disabled={isUploading}
                          className={templateStatus?.exists 
                            ? 'bg-slate-600 hover:bg-slate-700 text-white' 
                            : 'bg-brand-green-600 hover:bg-brand-green-700 text-white'
                          }
                          data-testid={`upload-template-${template.id}`}
                        >
                          <Upload size={16} className="mr-1" />
                          {isUploading ? 'Subiendo...' : (templateStatus?.exists ? 'Reemplazar' : 'Subir PDF')}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            
            <p className="text-sm text-slate-500 mt-4">
              <strong>Nota:</strong> Solo se aceptan archivos en formato PDF. El tamaño máximo recomendado es 10MB.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Settings;
