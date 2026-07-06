import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Upload, Trash2, Image, FileText, Check, X, Download, Mail, Save, Building2, Warehouse, FileCode, Key, Eye, EyeOff, CheckCircle, AlertCircle, MapPin, TrendingUp, RefreshCw, Clock, Settings2, ChevronRight, ShieldCheck, ChevronDown, Wifi, DatabaseBackup, PenLine, CalendarDays } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { EmailTemplatesEditor } from '../components/EmailTemplatesEditor';
import { ContingencyAttachmentsExport } from '../components/ContingencyAttachmentsExport';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

// Sedes disponibles
const SEDES = [
  { id: 'PYME', name: 'PYME', shortName: 'PYME' },
  { id: 'CORP', name: 'CORP', shortName: 'CORP' }
];

const TEMPLATE_TYPES = [
  { id: 'vpos_pyme', name: 'VPOS Pyme', description: 'Cotización para pequeñas y medianas empresas con VPOS' },
  { id: 'vpos_corporativo', name: 'VPOS Corporativo', description: 'Cotización para empresas corporativas con VPOS' },
  { id: 'payment_gateway', name: 'Payment Gateway', description: 'Cotización para pasarela de pagos (Ecommerce)' },
  { id: 'mpos', name: 'MPOS', description: 'Cotización para soluciones móviles (Tablet/Android)' },
  { id: 'dispositivos', name: 'Dispositivos', description: 'Cotización de dispositivos de pago' },
  { id: 'accesorios', name: 'Accesorios', description: 'Cotización de accesorios complementarios' }
];

export const Settings = () => {
  const { canEdit } = usePermission('configuracion');
  const navigate = useNavigate();
  const [logoUrl, setLogoUrl] = useState(null);
  const [notifLogoUrl, setNotifLogoUrl] = useState(null);
  const [appendingSignature, setAppendingSignature] = useState(false);
  const [notifUploading, setNotifUploading] = useState(false);
  const [notifDragOver, setNotifDragOver] = useState(false);  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [templates, setTemplates] = useState({});
  const [uploadingTemplate, setUploadingTemplate] = useState(null);
  
  // Correos por sede
  const [emailsBySede, setEmailsBySede] = useState({
    PYME: { admin: '', warehouse: '', sales: '', operations: '' },
    CORP: { admin: '', warehouse: '', sales: '' }
  });
  const [implementationEmail, setImplementationEmail] = useState('');
  const [implManagerEmail, setImplManagerEmail] = useState('');
  const [savingEmail, setSavingEmail] = useState(false);
  
  // Resend API Key state
  const [resendApiKey, setResendApiKey] = useState('');
  const [resendApiKeyConfigured, setResendApiKeyConfigured] = useState(false);
  const [resendApiKeyMasked, setResendApiKeyMasked] = useState('');
  const [showResendKey, setShowResendKey] = useState(false);
  const [savingResendKey, setSavingResendKey] = useState(false);
  const [emailLogs, setEmailLogs] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  // Collapsible state para secciones de Correos por Sede (PYME / CORP) — inicia colapsado
  const [openSedes, setOpenSedes] = useState({ PYME: false, CORP: false });
  const fileInputRef = useRef(null);
  const templateInputRefs = useRef({});
  const notifLogoInputRef = useRef(null);

  useEffect(() => {
    fetchLogo();
    fetchNotifLogo();
    fetchTemplates();
    fetchSettings();
    fetchEmailLogs();
  }, []);

  const fetchSettings = async () => {
    try {
      const [settingsRes] = await Promise.all([api.get('/config/settings')]);
      const response = settingsRes;
      setImplementationEmail(response.data.implementation_email || '');
      setImplManagerEmail(response.data.implementation_manager_email || '');
      
      // Cargar correos por sede
      setEmailsBySede({
        PYME: {
          admin: response.data.emails_by_sede?.PYME?.admin || response.data.admin_email || '',
          warehouse: response.data.emails_by_sede?.PYME?.warehouse || response.data.warehouse_email || '',
          sales: response.data.emails_by_sede?.PYME?.sales || '',
          operations: response.data.emails_by_sede?.PYME?.operations || response.data.operations_email || ''
        },
        CORP: {
          admin: response.data.emails_by_sede?.CORP?.admin || '',
          warehouse: response.data.emails_by_sede?.CORP?.warehouse || '',
          sales: response.data.emails_by_sede?.CORP?.sales || ''
        }
      });
      
      setResendApiKeyConfigured(response.data.resend_api_key_configured || false);
      setResendApiKeyMasked(response.data.resend_api_key_masked || '');
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  };

  const fetchEmailLogs = async () => {
    setLoadingLogs(true);
    try {
      const res = await api.get('/email-logs?limit=50');
      setEmailLogs(res.data.email_logs || []);
    } catch { /* silently fail */ }
    finally { setLoadingLogs(false); }
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
        implementation_manager_email: implManagerEmail || null,
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
        implementation_manager_email: implManagerEmail || null,
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

  // ── Logotipo para Pie de Notificaciones (Firma institucional) ──
  const fetchNotifLogo = async () => {
    try {
      const response = await api.get('/config/notification-logo', { responseType: 'blob' });
      setNotifLogoUrl(URL.createObjectURL(response.data));
    } catch (error) {
      if (error.response?.status !== 404) console.error('Error fetching notif logo:', error);
      setNotifLogoUrl(null);
    }
  };

  const uploadNotifLogo = async (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) { toast.error('Seleccione una imagen .png o .jpg'); return; }
    setNotifUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await api.post('/config/notification-logo', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Logotipo de notificaciones subido');
      fetchNotifLogo();
    } catch (error) {
      toast.error(`Error: ${error.response?.data?.detail || 'No se pudo subir'}`);
    } finally {
      setNotifUploading(false);
    }
  };

  const handleDeleteNotifLogo = async () => {
    if (!window.confirm('¿Eliminar el logotipo de notificaciones?')) return;
    try {
      await api.delete('/config/notification-logo');
      setNotifLogoUrl(null);
      toast.success('Logotipo de notificaciones eliminado');
    } catch (error) {
      toast.error('Error al eliminar');
    }
  };

  const handleAppendSignatureToTemplates = async () => {
    if (!window.confirm('Se agregará la variable {Firma_Notificacion_Global} al pie de TODAS las plantillas de correo que aún no la tengan. ¿Continuar?')) return;
    setAppendingSignature(true);
    try {
      const res = await api.post('/email-templates/append-signature');
      const { updated = 0, skipped = 0 } = res.data || {};
      toast.success(`Firma agregada a ${updated} plantilla(s). ${skipped} ya la tenían.`);
    } catch (error) {
      toast.error(`Error: ${error.response?.data?.detail || 'No se pudo homologar las plantillas'}`);
    } finally {
      setAppendingSignature(false);
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

          {/* Logotipo para Pie de Notificaciones (Firma institucional global) */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="notification-logo-section">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1 flex items-center gap-2">
              <Image size={24} className="text-emerald-600" />
              Logotipo para Pie de Notificaciones
            </h2>
            <p className="text-slate-600 mb-4">
              Logo exclusivo para la <strong>firma institucional</strong> de correos y notificaciones.
              Se combina con los datos del usuario en sesión en la variable global{' '}
              <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs text-emerald-700">{'{Firma_Notificacion_Global}'}</code>,
              disponible en todos los editores de plantillas.
            </p>

            <div className="flex items-start gap-8">
              <div className="flex-shrink-0">
                {notifLogoUrl ? (
                  <div className="relative">
                    <img
                      src={notifLogoUrl}
                      alt="Logotipo de notificaciones"
                      className="w-48 h-32 object-contain border border-slate-200 rounded-lg bg-slate-50 p-2"
                      data-testid="notification-logo-preview"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleDeleteNotifLogo}
                      className="absolute -top-2 -right-2 text-red-600 hover:text-red-700 hover:border-red-300 bg-white"
                      data-testid="delete-notification-logo-button"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                ) : (
                  <div className="w-48 h-32 border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center bg-slate-50">
                    <Image size={40} className="text-slate-400 mb-2" />
                    <p className="text-sm text-slate-500">Sin logo</p>
                  </div>
                )}
              </div>

              <div className="flex-1">
                <div
                  onDragOver={(e) => { e.preventDefault(); setNotifDragOver(true); }}
                  onDragLeave={() => setNotifDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setNotifDragOver(false); uploadNotifLogo(e.dataTransfer.files?.[0]); }}
                  onClick={() => notifLogoInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${notifDragOver ? 'border-emerald-500 bg-emerald-50' : 'border-slate-300 hover:bg-slate-50'}`}
                  data-testid="notification-logo-dropzone"
                >
                  <Upload size={28} className="mx-auto text-emerald-600 mb-2" />
                  <p className="text-sm font-medium text-slate-700">
                    {notifUploading ? 'Subiendo...' : 'Arrastra y suelta el logo aquí, o haz clic para seleccionar'}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">PNG o JPG, con soporte de fondo transparente</p>
                </div>
                <input
                  type="file"
                  ref={notifLogoInputRef}
                  onChange={(e) => uploadNotifLogo(e.target.files?.[0])}
                  accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                  className="hidden"
                  data-testid="notification-logo-file-input"
                />
              </div>
            </div>

            {/* Homologación: insertar la firma global en todas las plantillas */}
            <div className="mt-6 pt-5 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" data-testid="append-signature-row">
              <div className="flex items-start gap-2">
                <PenLine size={18} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800">Insertar firma en todas las plantillas</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Agrega <code className="bg-slate-100 px-1 py-0.5 rounded text-[11px] text-emerald-700">{'{Firma_Notificacion_Global}'}</code> al pie de las plantillas que aún no la tengan. Las que ya la incluyen se omiten.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleAppendSignatureToTemplates}
                disabled={appendingSignature}
                className="bg-emerald-600 hover:bg-emerald-700 text-white flex-shrink-0"
                data-testid="append-signature-button"
              >
                <PenLine size={16} className="mr-2" />
                {appendingSignature ? 'Aplicando...' : 'Homologar plantillas'}
              </Button>
            </div>
          </div>

          {/* Contingencia: Export Streaming de Anexos (Admin) */}
          <ContingencyAttachmentsExport />

          {/* Gestor de Anexos Corporativos (Tarifas Link de Pago / Tokenizador) */}
          <CorporateAnexosCard />

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

            <div className="space-y-3">
              {/* Correos por Sede — botones desplegables independientes */}
              {SEDES.map((sede) => {
                const isOpen = !!openSedes[sede.id];
                return (
                <div key={sede.id} className="border border-slate-200 rounded-lg overflow-hidden" data-testid={`sede-block-${sede.id}`}>
                  {/* Header colapsable */}
                  <button
                    type="button"
                    onClick={() => setOpenSedes((p) => ({ ...p, [sede.id]: !p[sede.id] }))}
                    aria-expanded={isOpen}
                    data-testid={`sede-toggle-${sede.id}`}
                    className="w-full flex items-center justify-between gap-2 bg-slate-100 hover:bg-slate-200 transition-colors px-4 py-3 border-b border-slate-200 text-left"
                  >
                    <div className="flex items-center gap-2">
                      <MapPin size={18} className="text-slate-600" />
                      <span className="font-semibold text-slate-800">Sede {sede.name} ({sede.shortName})</span>
                    </div>
                    <ChevronDown
                      size={18}
                      className={`text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    />
                  </button>

                  {isOpen && (
                  <div className="p-4 space-y-4" data-testid={`sede-content-${sede.id}`}>
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

                    {/* Email de Ventas - Sede */}
                    <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingUp size={16} className="text-green-600" />
                        <Label className="text-sm font-semibold text-green-800">
                          Correo de Ventas - Sede {sede.shortName}
                        </Label>
                      </div>
                      <p className="text-xs text-green-700 mb-2">
                        Recibe notificaciones cuando una cotización es <strong>Aprobada</strong> o <strong>Facturada</strong>. Para seguimiento comercial de la sede.
                      </p>
                      <Input
                        type="email"
                        value={emailsBySede[sede.id]?.sales || ''}
                        onChange={(e) => updateSedeEmail(sede.id, 'sales', e.target.value)}
                        placeholder={`ventas.${sede.id.toLowerCase()}@empresa.com`}
                        className="bg-white"
                        data-testid={`sales-email-${sede.id}`}
                      />
                    </div>

                    {/* Email de Operaciones - Solo Sede PYME */}
                    {sede.id === 'PYME' && (
                      <div className="p-3 bg-cyan-50 rounded-lg border border-cyan-200">
                        <div className="flex items-center gap-2 mb-2">
                          <Settings2 size={16} className="text-cyan-600" />
                          <Label className="text-sm font-semibold text-cyan-800">
                            Correo de Operaciones - Sede {sede.shortName}
                          </Label>
                        </div>
                        <p className="text-xs text-cyan-700 mb-2">
                          Recibe notificaciones de <strong>MPOS (Imple + POS)</strong> (configuración de equipos) y flujos operativos de la sede Pyme.
                        </p>
                        <Input
                          type="email"
                          value={emailsBySede[sede.id]?.operations || ''}
                          onChange={(e) => updateSedeEmail(sede.id, 'operations', e.target.value)}
                          placeholder="operaciones.pyme@empresa.com"
                          className="bg-white"
                          data-testid={`operations-email-${sede.id}`}
                        />
                      </div>
                    )}
                  </div>
                  )}
                </div>
                );
              })}

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

              {/* Correo Gerente de Implementación */}
              <div className="bg-purple-50 rounded-lg border border-purple-200 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Mail size={16} className="text-purple-600" />
                  <Label className="text-sm font-semibold text-purple-800">
                    Correo Gerente de Implementación
                  </Label>
                </div>
                <p className="text-sm text-purple-700 mb-3">
                  Recibe una alerta automática cada vez que una cotización pasa a ser un <strong>Proyecto</strong>.
                  El Gerente puede asignar implementadores desde el módulo de Proyectos.
                </p>
                <Input
                  type="email"
                  value={implManagerEmail}
                  onChange={(e) => setImplManagerEmail(e.target.value)}
                  placeholder="gerente.implementacion@empresa.com"
                  className="bg-white"
                  data-testid="impl-manager-email-input"
                />
              </div>

              {/* Botón Guardar */}
              <div className="flex justify-end pt-2">
                <Button
                  onClick={handleSaveEmails}
                  disabled={!canEdit || savingEmail}
                  className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  data-testid="save-emails-button"
                >
                  <Save size={16} className="mr-2" />
                  {savingEmail ? 'Guardando...' : 'Guardar Configuración de Correos'}
                </Button>
              </div>
            </div>
          </div>

          {/* Pie de Página Global Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="global-footer-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-slate-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText size={20} className="text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope">
                    Gestión de Footer Global
                  </h2>
                  <p className="text-sm text-slate-600 mt-1 max-w-2xl">
                    Define el pie de página institucional (cláusulas de confidencialidad,
                    responsabilidad ambiental, etc.) que se anexará automáticamente al final de
                    cada correo despachado por el ecosistema MegaNexus.
                  </p>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/email-footer')}
                variant="outline"
                className="flex-shrink-0"
                data-testid="open-email-footer-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Remitentes de Correo (Admin) — multi-sender por área */}
          {(() => {
            let isAdminUser = false;
            try {
              const u = JSON.parse(localStorage.getItem('user') || '{}');
              isAdminUser = u?.role === 'admin' || u?.is_admin === true;
            } catch { /* noop */ }
            if (!isAdminUser) return null;
            return (
            <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="email-senders-card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Mail size={20} className="text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900 font-manrope">
                      Remitentes de Correo
                    </h2>
                    <p className="text-sm text-slate-600 mt-1 max-w-2xl">
                      Administra varias direcciones remitentes del dominio institucional y asígnalas
                      automáticamente por área. Los correos de <strong>Proyectos</strong> e
                      <strong> Integradores</strong> saldrán desde la dirección que definas aquí.
                    </p>
                  </div>
                </div>
                <Button
                  onClick={() => navigate('/settings/email-senders')}
                  variant="outline"
                  className="flex-shrink-0"
                  data-testid="open-email-senders-btn"
                >
                  Configurar
                  <ChevronRight size={16} className="ml-1" />
                </Button>
              </div>
            </div>
            );
          })()}

          {/* Calendario Laboral — días festivos (días hábiles en SLAs/Proyectos) */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="work-calendar-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <CalendarDays size={20} className="text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope">
                    Calendario Laboral
                  </h2>
                  <p className="text-sm text-slate-600 mt-1 max-w-2xl">
                    Administra los <strong>días festivos</strong> no laborables. El seguimiento de
                    proyectos y los <strong>SLAs</strong> contarán solo días hábiles, descontando
                    automáticamente fines de semana y los feriados aquí registrados.
                  </p>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/work-calendar')}
                variant="outline"
                className="flex-shrink-0"
                data-testid="open-work-calendar-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Notificaciones Push Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="notifications-config-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Mail size={20} className="text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope">
                    Notificaciones Push
                  </h2>
                  <p className="text-sm text-slate-600 mt-1 max-w-2xl">
                    Activa o desactiva los 16 eventos del sistema que disparan notificaciones
                    push en tiempo real (campana + toast). Ajusta la prioridad (Alta / Media / Baja)
                    por cada uno.
                  </p>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/notifications')}
                variant="outline"
                className="flex-shrink-0"
                data-testid="open-notifications-config-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Configuración de Acciones de Cotizaciones (Fase 1 — Motor Dinámico) */}
          <div className="bg-white rounded-lg border-2 border-blue-200 p-6 mb-6" data-testid="action-notifications-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <ShieldCheck size={24} className="text-blue-600 flex-shrink-0" />
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                    Configuración de Acciones de Cotizaciones
                  </h2>
                  <p className="text-sm text-slate-600 max-w-2xl">
                    Define qué destinatarios reciben qué plantilla en cada acción del flujo
                    (Enviar al Cliente, Aprobar, Enviar a Implementación, etc.) por tipo de
                    negocio y sub-categoría de producto. Motor dinámico que reemplaza la
                    rigidez del código actual.
                  </p>
                  <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 mt-2 text-xs">
                    Motor activo · fallback seguro a la lógica legacy
                  </Badge>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/action-notifications')}
                variant="outline"
                className="flex-shrink-0 border-blue-300 text-blue-700 hover:bg-blue-50"
                data-testid="open-action-notifications-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Configuración de otras Acciones (desacople de correos hardcode) */}
          <div className="bg-white rounded-lg border-2 border-blue-200 p-6 mb-6" data-testid="other-actions-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Settings2 size={24} className="text-blue-600 flex-shrink-0" />
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                    Configuración de otras Acciones
                  </h2>
                  <p className="text-sm text-slate-600 max-w-2xl">
                    Parametriza los destinatarios internos, la plantilla y el canal de envío
                    (Correo o Centro de Mensajes) de las notificaciones automáticas de
                    Nuevos Productos (cambio de fase) y Proyectos de Integración (creación),
                    que antes estaban fijas en el código.
                  </p>
                  <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 mt-2 text-xs">
                    Motor dinámico · fallback seguro a la lógica legacy
                  </Badge>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/other-actions')}
                variant="outline"
                className="flex-shrink-0 border-blue-300 text-blue-700 hover:bg-blue-50"
                data-testid="open-other-actions-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Configuración de Tiempos y SLA de Proyectos (semáforo + motor de acciones) */}
          <div className="bg-white rounded-lg border-2 border-blue-200 p-6 mb-6" data-testid="project-sla-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Settings2 size={24} className="text-blue-600 flex-shrink-0" />
                <div>
                  <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                    Configuración de Tiempos y SLA de Proyectos
                  </h2>
                  <p className="text-sm text-slate-600 max-w-2xl">
                    Parametriza la matriz de días del semáforo (Verde → Amarillo → Rojo) por etapa del
                    proyecto y configura las acciones automáticas (correo o Centro de Mensajes) que se
                    disparan cuando un proyecto cambia su color de alerta de tiempo.
                  </p>
                  <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 mt-2 text-xs">
                    Semáforo configurable · 6 disparadores automáticos
                  </Badge>
                </div>
              </div>
              <Button
                onClick={() => navigate('/settings/project-sla')}
                variant="outline"
                className="flex-shrink-0 border-blue-300 text-blue-700 hover:bg-blue-50"
                data-testid="open-project-sla-btn"
              >
                Configurar
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>

          {/* Centro de Respaldos (Admin) — Exportación/Importación unificada */}
          {(() => {
            let isAdminUser = false;
            try {
              const u = JSON.parse(localStorage.getItem('user') || '{}');
              isAdminUser = u?.role === 'admin' || u?.is_admin === true;
            } catch { /* noop */ }
            if (!isAdminUser) return null;
            return (
            <div className="bg-white rounded-lg border-2 border-indigo-200 p-6 mb-6" data-testid="backup-center-card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <DatabaseBackup size={24} className="text-indigo-600 flex-shrink-0" />
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                      Centro de Respaldos
                    </h2>
                    <p className="text-sm text-slate-600 max-w-2xl">
                      Exporta (Backup) e importa (Restauración) de forma centralizada los datos maestros:
                      Clientes, Bancos, Medios de Pago, Bienes y Servicios, Categoría Comercial, Inventarios
                      (Movimientos, Almacenes, Asignación de Seriales y Auditoría), Equipos en Reparación,
                      Permisos de Usuarios e Integradores. Exportación masiva en ZIP y modo "Reemplazo total"
                      para dejar un entorno idéntico al respaldo.
                    </p>
                    <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 mt-2 text-xs">
                      12 entidades · JSON · upsert / réplica
                    </Badge>
                  </div>
                </div>
                <Button
                  onClick={() => navigate('/settings/backup-center')}
                  variant="outline"
                  className="flex-shrink-0 border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                  data-testid="open-backup-center-btn"
                >
                  Abrir
                  <ChevronRight size={16} className="ml-1" />
                </Button>
              </div>
            </div>
            );
          })()}

          {/* Iter57: Usuarios Conectados — admin-only */}
          {(() => {
            let isAdminUser = false;
            try {
              const u = JSON.parse(localStorage.getItem('user') || '{}');
              isAdminUser = u?.role === 'admin' || u?.is_admin === true;
            } catch { /* noop */ }
            if (!isAdminUser) return null;
            return (
            <div className="bg-white rounded-lg border-2 border-violet-200 p-6 mb-6" data-testid="connected-users-card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Wifi size={24} className="text-violet-600 flex-shrink-0" />
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                      Usuarios Conectados
                    </h2>
                    <p className="text-sm text-slate-600 max-w-2xl">
                      Visualiza en tiempo real qué usuarios tienen sesión activa
                      en el sistema, su departamento y el número de pestañas/conexiones
                      abiertas. Útil para auditoría operativa y soporte en vivo.
                    </p>
                    <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 mt-2 text-xs">
                      Auto-refresh cada 15s · en vivo
                    </Badge>
                  </div>
                </div>
                <Button
                  onClick={() => navigate('/settings/connected-users')}
                  variant="outline"
                  className="flex-shrink-0 border-violet-300 text-violet-700 hover:bg-violet-50"
                  data-testid="open-connected-users-btn"
                >
                  Ver conectados
                  <ChevronRight size={16} className="ml-1" />
                </Button>
              </div>
            </div>
            );
          })()}

          {/* Refresco del Reporte de Embudo (Admin) */}
          <FunnelRecalculateCard />

          {/* Plantillas de Correo Section */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4 flex items-center gap-2">
              <FileCode size={24} />
              Plantillas de Correo Electrónico
            </h2>
            <p className="text-slate-600 mb-6">
              Personalice el contenido de los correos automáticos que envía el sistema en cada etapa del flujo de trabajo.
              Cada sede tiene sus propias plantillas para mantener la identidad y control separado.
            </p>

            <EmailTemplatesEditor />
          </div>
        </div>

        {/* Historial de Correos */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-8" data-testid="email-logs-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <Mail size={20} className="text-indigo-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Historial de Correos</h2>
                <p className="text-sm text-slate-500">Correos enviados y simulados del sistema</p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={fetchEmailLogs} disabled={loadingLogs} data-testid="refresh-email-logs">
              <RefreshCw size={14} className={`mr-1 ${loadingLogs ? 'animate-spin' : ''}`} />
              Actualizar
            </Button>
          </div>

          {emailLogs.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <Mail size={32} className="mx-auto mb-2 opacity-50" />
              <p>No hay correos registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="email-logs-table">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Estado</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Acción</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Destinatario</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Asunto</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Cotización</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">Fecha</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {emailLogs.map((log) => {
                    const statusConfig = {
                      sent: { label: 'Enviado', color: 'bg-green-100 text-green-700' },
                      simulated: { label: 'Simulado', color: 'bg-amber-100 text-amber-700' },
                      error: { label: 'Error', color: 'bg-red-100 text-red-700' },
                    };
                    const st = statusConfig[log.status] || statusConfig.error;
                    const actionLabels = {
                      send_to_client: 'Enviar al Cliente',
                      approve_admin: 'Aprobar (Admin)',
                      approve_sales: 'Aprobar (Ventas)',
                      approve_no_config: 'Aprobar (Sin config)',
                      invoice_admin: 'Facturar (Admin)',
                      invoice_sales: 'Facturar (Ventas)',
                      invoice_no_config: 'Facturar (Sin config)',
                      collect_warehouse: 'Cobrar (Almacén)',
                      send_to_implementation: 'Enviar a Imple',
                    };

                    return (
                      <tr key={log.email_log_id} className="hover:bg-slate-50" data-testid={`email-log-${log.email_log_id}`}>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${st.color}`}>{st.label}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-700">{actionLabels[log.action] || log.action}</td>
                        <td className="px-4 py-3 text-slate-600 font-mono text-xs">{(log.to || []).join(', ')}</td>
                        <td className="px-4 py-3 text-slate-700 max-w-[200px] truncate">{log.subject}</td>
                        <td className="px-4 py-3 text-slate-600 font-mono text-xs">{log.quote_number || '-'}</td>
                        <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
                          <Clock size={12} className="inline mr-1" />
                          {new Date(log.created_at).toLocaleString('es-VE')}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Settings;

// ========================================================================
// FunnelRecalculateCard — Herramienta admin para refrescar timestamps del
// Reporte de Embudo a partir de status_history / archived_at.
// ========================================================================
function FunnelRecalculateCard() {
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const handleRun = async () => {
    if (!window.confirm('¿Refrescar la información del Reporte de Embudo? Este proceso recalcula timestamps históricos a partir del historial de estados. No sobrescribe datos existentes.')) return;
    setRunning(true);
    try {
      const { data } = await api.post('/reports/sales/funnel/recalculate');
      setLastResult(data);
      toast.success(`Refresco completado: ${data.updated}/${data.scanned} cotizaciones actualizadas (${data.fields_added} timestamps)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al ejecutar el refresco');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border-2 border-amber-200 p-6 mb-6" data-testid="funnel-recalculate-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <RefreshCw size={24} className="text-amber-600 flex-shrink-0" />
          <div>
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
              Refresco del Reporte de Embudo
            </h2>
            <p className="text-sm text-slate-600 max-w-2xl">
              Herramienta administrativa para reconstruir los timestamps históricos del
              Reporte de Embudo (Enviada / Aprobada / Facturada / Pagada / Entregada) a
              partir del historial de estados y archivado. Útil tras un deploy o
              corrección de fechas hacia atrás.
            </p>
            <Badge variant="secondary" className="bg-amber-100 text-amber-800 mt-2 text-xs">
              Solo Admin · No sobrescribe datos existentes
            </Badge>
            {lastResult && (
              <p className="text-xs text-slate-600 mt-2" data-testid="funnel-recalculate-last-result">
                Último refresco: <strong>{lastResult.scanned}</strong> cotizaciones revisadas,
                <strong> {lastResult.updated}</strong> actualizadas,
                <strong> {lastResult.fields_added}</strong> timestamps añadidos.
              </p>
            )}
          </div>
        </div>
        <Button
          onClick={handleRun}
          disabled={running}
          variant="outline"
          className="flex-shrink-0 border-amber-300 text-amber-700 hover:bg-amber-50"
          data-testid="funnel-recalculate-run-btn"
        >
          {running ? 'Procesando...' : 'Ejecutar refresco'}
          <RefreshCw size={16} className={`ml-2 ${running ? 'animate-spin' : ''}`} />
        </Button>
      </div>
    </div>
  );
}


// ========================================================================
// CorporateAnexosCard — Gestor para subir/actualizar los anexos de tarifas
// (Link de Pago / Tokenizador) que el motor de PDF intercala en cotizaciones.
// ========================================================================
function CorporateAnexosCard() {
  const [anexos, setAnexos] = useState([]);
  const [uploadingKey, setUploadingKey] = useState(null);
  const [open, setOpen] = useState(false);
  const [openCats, setOpenCats] = useState({});
  const [loaded, setLoaded] = useState(false);
  const inputRefs = useRef({});

  const loadAnexos = async () => {
    try {
      const res = await api.get('/config/anexos');
      setAnexos(res.data?.anexos || []);
      setLoaded(true);
    } catch {
      toast.error('No se pudieron cargar los anexos corporativos');
    }
  };

  // Carga diferida: solo se piden los anexos al abrir la sección (menos carga inicial)
  const toggleOpen = () => {
    const next = !open;
    setOpen(next);
    if (next && !loaded) loadAnexos();
  };

  const toggleCat = (cat) => setOpenCats((prev) => ({ ...prev, [cat]: !prev[cat] }));

  const uploadAnexo = async (key, fileList) => {
    const f = fileList?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      toast.error('El archivo debe ser un PDF');
      return;
    }
    setUploadingKey(key);
    const toastId = toast.loading('Subiendo anexo...');
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await api.post(`/config/anexos/${key}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.dismiss(toastId);
      toast.success(`Anexo actualizado (${res.data?.pages || '?'} página(s))`);
      await loadAnexos();
    } catch (e) {
      toast.dismiss(toastId);
      toast.error(e?.response?.data?.detail || 'Error al subir el anexo');
    } finally {
      setUploadingKey(null);
    }
  };

  const downloadAnexo = async (key, filename) => {
    try {
      const res = await api.get(`/config/anexos/${key}/download`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = filename || `${key}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo descargar el anexo');
    }
  };

  const fmtDate = (iso) => {
    if (!iso) return 'Nunca';
    try { return new Date(iso).toLocaleString('es-VE'); } catch { return iso; }
  };

  const grouped = Object.entries(anexos.reduce((acc, a) => { (acc[a.category] = acc[a.category] || []).push(a); return acc; }, {}));

  return (
    <div className="bg-white rounded-lg border border-slate-200 mb-6 overflow-hidden" data-testid="corporate-anexos-section">
      {/* Encabezado clicable (colapsable) */}
      <button
        type="button"
        onClick={toggleOpen}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 p-6 text-left hover:bg-slate-50 transition-colors"
        data-testid="corporate-anexos-toggle"
      >
        <div className="flex items-start gap-2 min-w-0">
          <FileText size={24} className="text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope flex items-center gap-2">
              Anexos Corporativos de Cotización
              {loaded && anexos.length > 0 && (
                <Badge className="bg-slate-100 text-slate-600 border-slate-200 font-normal">{anexos.length}</Badge>
              )}
            </h2>
            <p className="text-slate-600 text-sm mt-0.5">
              Actualiza los PDFs corporativos (tarifas, términos y condiciones) sin un nuevo despliegue. Solo PDF.
            </p>
          </div>
        </div>
        <ChevronDown size={22} className={`text-slate-400 flex-shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Cuerpo desplegable */}
      {open && (
        <div className="px-6 pb-6 border-t border-slate-100 pt-4" data-testid="corporate-anexos-body">
          {!loaded ? (
            <div className="flex items-center justify-center py-8 text-slate-400" data-testid="corporate-anexos-loading">
              <RefreshCw size={18} className="animate-spin mr-2" /> Cargando anexos...
            </div>
          ) : grouped.length === 0 ? (
            <p className="text-sm text-slate-400 py-4">No hay anexos configurados.</p>
          ) : (
            <div className="space-y-3">
              {grouped.map(([cat, items]) => {
                const catOpen = !!openCats[cat];
                const configured = items.filter((i) => i.exists).length;
                return (
                  <div key={cat} className="border border-slate-200 rounded-lg overflow-hidden">
                    {/* Encabezado de categoría (colapsable interno) */}
                    <button
                      type="button"
                      onClick={() => toggleCat(cat)}
                      aria-expanded={catOpen}
                      className="w-full flex items-center justify-between gap-2 px-4 py-2.5 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                      data-testid={`anexo-cat-toggle-${cat}`}
                    >
                      <span className="flex items-center gap-2 text-sm font-semibold text-slate-700 uppercase tracking-wide">
                        <ChevronRight size={16} className={`text-slate-400 transition-transform duration-200 ${catOpen ? 'rotate-90' : ''}`} />
                        {cat}
                      </span>
                      <Badge className="bg-white text-slate-500 border-slate-200 font-normal">{configured}/{items.length}</Badge>
                    </button>
                    {catOpen && (
                      <div className="p-3 space-y-3" data-testid={`anexo-cat-body-${cat}`}>
                        {items.map((a) => (
                          <div key={a.key} className="border border-slate-200 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" data-testid={`anexo-row-${a.key}`}>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-800 text-sm">{a.label}</span>
                                {a.exists ? (
                                  <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">{a.pages || '?'} pág.</Badge>
                                ) : (
                                  <Badge className="bg-red-100 text-red-700 border-red-200">Sin archivo</Badge>
                                )}
                              </div>
                              <p className="text-xs text-slate-500 mt-1">{a.description}</p>
                              <p className="text-xs text-slate-400 mt-1">
                                Última actualización: {fmtDate(a.updated_at)}{a.updated_by ? ` · por ${a.updated_by}` : ''}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              {a.exists && (
                                <Button size="sm" variant="outline" onClick={() => downloadAnexo(a.key, a.filename)} data-testid={`anexo-download-${a.key}`}>
                                  <Download size={16} className="mr-1.5" /> Descargar
                                </Button>
                              )}
                              <input
                                type="file"
                                ref={(el) => { inputRefs.current[a.key] = el; }}
                                onChange={(e) => uploadAnexo(a.key, e.target.files)}
                                accept=".pdf,application/pdf"
                                className="hidden"
                                data-testid={`anexo-file-input-${a.key}`}
                              />
                              <Button
                                size="sm"
                                onClick={() => inputRefs.current[a.key]?.click()}
                                disabled={uploadingKey === a.key}
                                className="bg-blue-600 hover:bg-blue-700 text-white"
                                data-testid={`anexo-upload-${a.key}`}
                              >
                                <Upload size={16} className="mr-1.5" />
                                {uploadingKey === a.key ? 'Subiendo...' : 'Reemplazar'}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
