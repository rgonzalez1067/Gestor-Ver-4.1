import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Upload, Trash2, Image, Database, FileText, Check, X, Download, Mail, Save, Building2, Warehouse, FileCode, Key, Eye, EyeOff, CheckCircle, AlertCircle, MapPin } from 'lucide-react';
import { EmailTemplatesEditor } from '../components/EmailTemplatesEditor';
import api from '../utils/api';
import { toast } from 'sonner';

// Sedes disponibles
const SEDES = [
  { id: 'TBP', name: 'Torre Banco Plaza', shortName: 'TBP' },
  { id: 'LCH', name: 'Los Chaguaramos', shortName: 'LCH' }
];

const TEMPLATE_TYPES = [
  { id: 'vpos_pyme', name: 'VPOS Pyme', description: 'Cotización para pequeñas y medianas empresas con VPOS' },
  { id: 'vpos_corporativo', name: 'VPOS Corporativo', description: 'Cotización para empresas corporativas con VPOS' },
  { id: 'payment_gateway', name: 'Payment Gateway', description: 'Cotización para pasarela de pagos (Ecommerce)' },
  { id: 'mpos', name: 'MPOS', description: 'Cotización para soluciones móviles (Tablet/Android)' },
  { id: 'dispositivos', name: 'Dispositivos', description: 'Cotización de dispositivos de pago' },
  { id: 'accesorios', name: 'Accesorios', description: 'Cotización de accesorios complementarios' }
];

// Tipos de plantillas de documentos por sede
const DOCUMENT_TEMPLATE_TYPES = [
  { id: 'despacho_equipos', name: 'Despacho de Equipos', area: 'Logística', color: 'emerald' },
  { id: 'cotizacion_aprobada', name: 'Cotización Aprobada', area: 'Ventas', color: 'blue' },
  { id: 'facturacion_control', name: 'Facturación y Control Contable', area: 'Administración', color: 'purple' }
];

export const Settings = () => {
  const [logoUrl, setLogoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [templates, setTemplates] = useState({});
  const [uploadingTemplate, setUploadingTemplate] = useState(null);
  
  // Correos por sede
  const [emailsBySede, setEmailsBySede] = useState({
    TBP: { admin: '', warehouse: '' },
    LCH: { admin: '', warehouse: '' }
  });
  const [implementationEmail, setImplementationEmail] = useState('');
  const [savingEmail, setSavingEmail] = useState(false);
  
  // Plantillas de documentos por sede
  const [documentTemplates, setDocumentTemplates] = useState({});
  
  // Resend API Key state
  const [resendApiKey, setResendApiKey] = useState('');
  const [resendApiKeyConfigured, setResendApiKeyConfigured] = useState(false);
  const [resendApiKeyMasked, setResendApiKeyMasked] = useState('');
  const [showResendKey, setShowResendKey] = useState(false);
  const [savingResendKey, setSavingResendKey] = useState(false);
  const fileInputRef = useRef(null);
  const templateInputRefs = useRef({});

  useEffect(() => {
    fetchLogo();
    fetchTemplates();
    fetchSettings();
    fetchDocumentTemplates();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await api.get('/config/settings');
      setImplementationEmail(response.data.implementation_email || '');
      
      // Cargar correos por sede
      setEmailsBySede({
        TBP: {
          admin: response.data.emails_by_sede?.TBP?.admin || response.data.admin_email || '',
          warehouse: response.data.emails_by_sede?.TBP?.warehouse || response.data.warehouse_email || ''
        },
        LCH: {
          admin: response.data.emails_by_sede?.LCH?.admin || '',
          warehouse: response.data.emails_by_sede?.LCH?.warehouse || ''
        }
      });
      
      setResendApiKeyConfigured(response.data.resend_api_key_configured || false);
      setResendApiKeyMasked(response.data.resend_api_key_masked || '');
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  };

  const fetchDocumentTemplates = async () => {
    try {
      const response = await api.get('/config/document-templates');
      setDocumentTemplates(response.data || {});
    } catch (error) {
      console.error('Error fetching document templates:', error);
    }
  };

  const handleSaveResendKey = async () => {
    if (!resendApiKey.trim()) {
      toast.error('Por favor ingrese una API Key válida');
      return;
    }
    
    setSavingResendKey(true);
    try {
      await api.put('/config/settings', { 
        implementation_email: implementationEmail || null,
        emails_by_sede: emailsBySede,
        resend_api_key: resendApiKey
      });
      setResendApiKeyConfigured(true);
      setResendApiKeyMasked(`${'*'.repeat(resendApiKey.length - 4)}${resendApiKey.slice(-4)}`);
      setResendApiKey(''); // Limpiar el campo
      setShowResendKey(false);
      toast.success('API Key de Resend configurada correctamente');
    } catch (error) {
      toast.error('Error al guardar la API Key');
    } finally {
      setSavingResendKey(false);
    }
  };

  const handleSaveEmails = async () => {
    setSavingEmail(true);
    try {
      await api.put('/config/settings', { 
        implementation_email: implementationEmail || null,
        emails_by_sede: emailsBySede
      });
      toast.success('Configuración de correos guardada');
    } catch (error) {
      toast.error('Error al guardar la configuración');
    } finally {
      setSavingEmail(false);
    }
  };

  // Actualizar email por sede
  const updateSedeEmail = (sedeId, type, value) => {
    setEmailsBySede(prev => ({
      ...prev,
      [sedeId]: {
        ...prev[sedeId],
        [type]: value
      }
    }));
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

          {/* Motor de Correos (Resend) Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <Key size={24} />
              Motor de Correos (Resend)
            </h2>
            <p className="text-slate-600 mb-6">
              Configure la API Key de Resend para habilitar el envío de correos automáticos del sistema.
              Puede obtener su API Key en <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-brand-blue-600 hover:underline">resend.com/api-keys</a>
            </p>

            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
              {/* Estado actual */}
              <div className="flex items-center gap-2 mb-4">
                {resendApiKeyConfigured ? (
                  <>
                    <CheckCircle size={20} className="text-green-600" />
                    <span className="text-green-700 font-medium">API Key configurada</span>
                    {resendApiKeyMasked && (
                      <span className="text-slate-500 text-sm ml-2">({resendApiKeyMasked})</span>
                    )}
                  </>
                ) : (
                  <>
                    <AlertCircle size={20} className="text-amber-500" />
                    <span className="text-amber-700 font-medium">API Key no configurada</span>
                    <span className="text-slate-500 text-sm ml-2">(Los correos se enviarán en modo simulado)</span>
                  </>
                )}
              </div>

              {/* Campo para nueva API Key */}
              <div className="space-y-3">
                <Label className="text-sm font-medium text-slate-700">
                  {resendApiKeyConfigured ? 'Actualizar API Key' : 'Configurar API Key'}
                </Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      type={showResendKey ? 'text' : 'password'}
                      value={resendApiKey}
                      onChange={(e) => setResendApiKey(e.target.value)}
                      placeholder="re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      className="bg-white pr-10"
                      data-testid="resend-api-key-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowResendKey(!showResendKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showResendKey ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <Button
                    onClick={handleSaveResendKey}
                    disabled={savingResendKey || !resendApiKey.trim()}
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                    data-testid="save-resend-key-button"
                  >
                    <Save size={16} className="mr-2" />
                    {savingResendKey ? 'Guardando...' : 'Guardar'}
                  </Button>
                </div>
                <p className="text-xs text-slate-500">
                  La API Key se almacena de forma segura y nunca se muestra completa después de guardarla.
                </p>
              </div>
            </div>
          </div>

          {/* Configuración de Correos Section - POR SEDE */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <Mail size={24} />
              Configuración de Correos de Notificación
            </h2>
            <p className="text-slate-600 mb-6">
              Configure los correos electrónicos para las notificaciones automáticas del sistema por sede.
              Cada sede recibirá sus propias alertas según el flujo de trabajo de las cotizaciones.
            </p>

            <div className="space-y-6">
              {/* Correos por Sede */}
              {SEDES.map((sede) => (
                <div key={sede.id} className="border border-slate-200 rounded-lg overflow-hidden">
                  {/* Header de la Sede */}
                  <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                    <div className="flex items-center gap-2">
                      <MapPin size={18} className="text-slate-600" />
                      <span className="font-semibold text-slate-800">Sede {sede.name} ({sede.shortName})</span>
                    </div>
                  </div>
                  
                  <div className="p-4 space-y-4">
                    {/* Email de Administración - Sede */}
                    <div className="p-3 bg-purple-50 rounded-lg border border-purple-200">
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 size={16} className="text-purple-600" />
                        <Label className="text-sm font-semibold text-purple-800">
                          Correo de Administración - Sede {sede.shortName}
                        </Label>
                      </div>
                      <p className="text-xs text-purple-700 mb-2">
                        Recibe notificaciones cuando una cotización es <strong>Aprobada</strong> o <strong>Facturada</strong>.
                      </p>
                      <Input
                        type="email"
                        value={emailsBySede[sede.id]?.admin || ''}
                        onChange={(e) => updateSedeEmail(sede.id, 'admin', e.target.value)}
                        placeholder={`administracion.${sede.id.toLowerCase()}@empresa.com`}
                        className="bg-white"
                        data-testid={`admin-email-${sede.id}`}
                      />
                    </div>

                    {/* Email de Almacén - Sede */}
                    <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                      <div className="flex items-center gap-2 mb-2">
                        <Warehouse size={16} className="text-amber-600" />
                        <Label className="text-sm font-semibold text-amber-800">
                          Correo de Almacén - Sede {sede.shortName}
                        </Label>
                      </div>
                      <p className="text-xs text-amber-700 mb-2">
                        Recibe notificaciones cuando una cotización de <strong>Equipos y Accesorios</strong> es marcada como <strong>Pagada</strong>.
                      </p>
                      <Input
                        type="email"
                        value={emailsBySede[sede.id]?.warehouse || ''}
                        onChange={(e) => updateSedeEmail(sede.id, 'warehouse', e.target.value)}
                        placeholder={`almacen.${sede.id.toLowerCase()}@empresa.com`}
                        className="bg-white"
                        data-testid={`warehouse-email-${sede.id}`}
                      />
                    </div>
                  </div>
                </div>
              ))}

              {/* Email de Implementación (General - no por sede) */}
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center gap-2 mb-3">
                  <Mail size={18} className="text-blue-600" />
                  <Label className="text-sm font-semibold text-blue-800">
                    Correo de Implementación (General)
                  </Label>
                </div>
                <p className="text-sm text-blue-700 mb-3">
                  Recibe notificaciones cuando una cotización de <strong>Implementación</strong> es <strong>Enviada a Implementación</strong>.
                  Incluye los detalles técnicos del proyecto.
                </p>
                <Input
                  type="email"
                  value={implementationEmail}
                  onChange={(e) => setImplementationEmail(e.target.value)}
                  placeholder="implementacion@empresa.com"
                  className="bg-white"
                  data-testid="implementation-email-input"
                />
              </div>

              {/* Botón Guardar */}
              <div className="flex justify-end pt-2">
                <Button
                  onClick={handleSaveEmails}
                  disabled={savingEmail}
                  className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  data-testid="save-emails-button"
                >
                  <Save size={16} className="mr-2" />
                  {savingEmail ? 'Guardando...' : 'Guardar Configuración de Correos'}
                </Button>
              </div>
            </div>
          </div>

          {/* Gestión de Plantillas de Documentos por Sede */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <FileText size={24} />
              Gestión de Plantillas de Documentos
            </h2>
            <p className="text-slate-600 mb-6">
              Cada sede tiene sus propias plantillas de documentos para mantener la identidad y control separado.
              Las plantillas base se duplican y personalizan para cada sede.
            </p>

            <div className="space-y-6">
              {SEDES.map((sede) => (
                <div key={sede.id} className="border border-slate-200 rounded-lg overflow-hidden">
                  {/* Header de la Sede */}
                  <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                    <div className="flex items-center gap-2">
                      <MapPin size={18} className="text-slate-600" />
                      <span className="font-semibold text-slate-800">Plantillas - Sede {sede.name} ({sede.shortName})</span>
                    </div>
                  </div>
                  
                  <div className="p-4">
                    <div className="grid gap-3">
                      {DOCUMENT_TEMPLATE_TYPES.map((docType) => {
                        const templateKey = `${docType.id}_${sede.id}`;
                        const templateData = documentTemplates[templateKey];
                        const colorClasses = {
                          emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
                          blue: 'bg-blue-50 border-blue-200 text-blue-700',
                          purple: 'bg-purple-50 border-purple-200 text-purple-700'
                        };
                        
                        return (
                          <div 
                            key={templateKey}
                            className={`p-3 rounded-lg border ${colorClasses[docType.color] || 'bg-slate-50 border-slate-200'}`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className={`w-8 h-8 rounded flex items-center justify-center ${templateData?.exists ? 'bg-green-100' : 'bg-white/50'}`}>
                                  {templateData?.exists ? (
                                    <Check size={16} className="text-green-600" />
                                  ) : (
                                    <FileText size={16} className="opacity-50" />
                                  )}
                                </div>
                                <div>
                                  <h4 className="font-medium text-sm">{docType.name} - Sede {sede.shortName}</h4>
                                  <p className="text-xs opacity-75">Área: {docType.area}</p>
                                </div>
                              </div>
                              <span className={`text-xs px-2 py-1 rounded ${templateData?.exists ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                {templateData?.exists ? 'Configurada' : 'Pendiente'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Nota informativa */}
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-700">
                  <strong>Nota:</strong> Al generar un despacho o cotización, el sistema seleccionará automáticamente 
                  la plantilla y correo de notificación correspondientes según la sede del usuario que realiza la acción.
                </p>
              </div>
            </div>
          </div>

          {/* Plantillas de Correo Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <FileCode size={24} />
              Plantillas de Correo Electrónico
            </h2>
            <p className="text-slate-600 mb-6">
              Personalice el contenido de los correos automáticos que envía el sistema en cada etapa del flujo de trabajo.
              Puede modificar el asunto y el cuerpo de cada correo usando variables dinámicas.
            </p>

            <EmailTemplatesEditor />
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
