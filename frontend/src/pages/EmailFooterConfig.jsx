import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDateTime, formatDate, formatTime } from '../utils/dateFormat';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import {
  ArrowLeft,
  Save,
  Trash2,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Link as LinkIcon,
  Calendar,
  Building2,
  Eye,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

const RAZON_SOCIAL = 'Mega Soft Computación, C.A.';
const CURRENT_YEAR = new Date().getFullYear();

const resolveVariables = (html) => {
  if (!html) return '';
  return html
    .replaceAll('{{año_actual}}', String(CURRENT_YEAR))
    .replaceAll('{{ano_actual}}', String(CURRENT_YEAR))
    .replaceAll('{{razon_social}}', RAZON_SOCIAL);
};

export const EmailFooterConfig = () => {
  const navigate = useNavigate();
  const { user: currentUser } = usePermission('configuracion');
  const isAdmin = currentUser?.role === 'admin';

  const editorRef = useRef(null);
  const [bodyHtml, setBodyHtml] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const [updatedBy, setUpdatedBy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadFooter = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/config/email-footer');
      setBodyHtml(data.body_html || '');
      setUpdatedAt(data.updated_at || null);
      setUpdatedBy(data.updated_by || null);
      if (editorRef.current) editorRef.current.innerHTML = data.body_html || '';
    } catch (e) {
      toast.error('No se pudo cargar el footer global');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadFooter(); }, [loadFooter]);

  const handleEditorInput = () => {
    setBodyHtml(editorRef.current?.innerHTML || '');
  };

  const execCmd = (cmd, value = null) => {
    // eslint-disable-next-line
    document.execCommand(cmd, false, value);
    editorRef.current?.focus();
    handleEditorInput();
  };

  const insertLink = () => {
    const url = window.prompt('URL del enlace (incluye https://):', 'https://');
    if (!url) return;
    execCmd('createLink', url);
  };

  const insertVariable = (variable) => {
    editorRef.current?.focus();
    // eslint-disable-next-line
    document.execCommand('insertText', false, variable);
    handleEditorInput();
  };

  const handleClear = () => {
    if (!window.confirm('¿Estás seguro de limpiar el contenido del footer? Esta acción vacía el editor pero aún debes guardar para aplicarla.')) return;
    if (editorRef.current) editorRef.current.innerHTML = '';
    setBodyHtml('');
    toast.info('Contenido limpiado. Recuerda guardar para aplicar.');
  };

  const handleSave = async () => {
    if (!isAdmin) {
      toast.error('Solo administradores pueden guardar el footer global');
      return;
    }
    if (!window.confirm('Este footer se aplicará automáticamente a TODOS los correos del sistema. ¿Confirmas guardar?')) return;
    setSaving(true);
    try {
      const { data } = await api.put('/config/email-footer', { body_html: bodyHtml });
      setUpdatedAt(data.updated_at);
      setUpdatedBy(data.updated_by);
      toast.success('Footer global actualizado correctamente');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al guardar el footer');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto p-6 lg:p-8">
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/settings')}
              data-testid="footer-back-btn"
            >
              <ArrowLeft size={18} className="mr-1" />
              Configuración
            </Button>
          </div>

          <div className="mb-6">
            <h1 className="text-3xl font-bold text-slate-900 font-manrope" data-testid="footer-page-title">
              Gestión de Footer Global
            </h1>
            <p className="text-slate-600 mt-1 text-sm">
              Define el pie de página institucional que se adjuntará automáticamente al final de todos
              los correos del sistema (Cotizaciones, Proyectos, Integradores, Nuevos Productos y Soporte).
            </p>
            {updatedAt && (
              <p className="text-xs text-slate-500 mt-2" data-testid="footer-last-updated">
                Última actualización:{' '}
                <span className="font-medium text-slate-700">
                  {formatDateTime(updatedAt)}
                </span>
                {updatedBy ? <> · por <span className="font-medium text-slate-700">{updatedBy}</span></> : null}
              </p>
            )}
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* LEFT: Editor */}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="footer-editor-panel">
              <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Editor</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Se incluirá automáticamente al final de cada correo enviado.
                </p>
              </div>

              {/* Toolbar */}
              <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 px-3 py-2 bg-white">
                <button type="button" onClick={() => execCmd('bold')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Negrita" data-testid="toolbar-bold">
                  <Bold size={16} />
                </button>
                <button type="button" onClick={() => execCmd('italic')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Cursiva" data-testid="toolbar-italic">
                  <Italic size={16} />
                </button>
                <button type="button" onClick={() => execCmd('underline')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Subrayado" data-testid="toolbar-underline">
                  <Underline size={16} />
                </button>
                <span className="w-px h-5 bg-slate-200 mx-1" />
                <button type="button" onClick={() => execCmd('justifyLeft')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Alinear a la izquierda" data-testid="toolbar-align-left">
                  <AlignLeft size={16} />
                </button>
                <button type="button" onClick={() => execCmd('justifyCenter')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Centrar" data-testid="toolbar-align-center">
                  <AlignCenter size={16} />
                </button>
                <button type="button" onClick={() => execCmd('justifyRight')} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Alinear a la derecha" data-testid="toolbar-align-right">
                  <AlignRight size={16} />
                </button>
                <span className="w-px h-5 bg-slate-200 mx-1" />
                <button type="button" onClick={insertLink} className="p-1.5 rounded hover:bg-slate-100 text-slate-700" title="Insertar enlace" data-testid="toolbar-link">
                  <LinkIcon size={16} />
                </button>
                <span className="w-px h-5 bg-slate-200 mx-1" />
                <button
                  type="button"
                  onClick={() => insertVariable('{{año_actual}}')}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded hover:bg-slate-100 text-slate-700 border border-slate-200"
                  title="Insertar año actual"
                  data-testid="toolbar-var-year"
                >
                  <Calendar size={12} /> {'{{año_actual}}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('{{razon_social}}')}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded hover:bg-slate-100 text-slate-700 border border-slate-200"
                  title="Insertar razón social"
                  data-testid="toolbar-var-company"
                >
                  <Building2 size={12} /> {'{{razon_social}}'}
                </button>
              </div>

              <div className="p-4">
                {loading ? (
                  <div className="h-[360px] flex items-center justify-center text-sm text-slate-400">
                    Cargando footer actual...
                  </div>
                ) : (
                  <div
                    ref={editorRef}
                    contentEditable
                    suppressContentEditableWarning
                    onInput={handleEditorInput}
                    onBlur={handleEditorInput}
                    className="min-h-[360px] max-h-[480px] overflow-y-auto border border-slate-300 rounded-md p-4 text-sm text-slate-800 leading-relaxed focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                    data-testid="footer-editor-area"
                    style={{ fontFamily: "Arial, Helvetica, sans-serif" }}
                  />
                )}
                <p className="text-xs text-slate-500 mt-3">
                  Variables soportadas: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{'{{año_actual}}'}</code>{' '}
                  <code className="bg-slate-100 px-1.5 py-0.5 rounded">{'{{razon_social}}'}</code>
                </p>

                <div className="flex items-center justify-between gap-3 mt-5 pt-4 border-t border-slate-100">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleClear}
                    disabled={loading || saving}
                    data-testid="footer-clear-btn"
                  >
                    <Trash2 size={14} className="mr-2" />
                    Limpiar contenido
                  </Button>
                  <Button
                    type="button"
                    onClick={handleSave}
                    disabled={loading || saving || !isAdmin}
                    className="bg-slate-900 hover:bg-slate-800 text-white"
                    data-testid="footer-save-btn"
                  >
                    <Save size={14} className="mr-2" />
                    {saving ? 'Guardando...' : 'Guardar configuración'}
                  </Button>
                </div>
                {!isAdmin && (
                  <p className="text-xs text-amber-600 mt-3" data-testid="footer-admin-warning">
                    Solo los administradores pueden modificar el footer global.
                  </p>
                )}
              </div>
            </div>

            {/* RIGHT: Preview */}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="footer-preview-panel">
              <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
                <Eye size={16} className="text-slate-500" />
                <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Vista Previa</h2>
              </div>
              <div className="p-6 bg-slate-100">
                {/* Email frame */}
                <div className="bg-white rounded-md shadow-sm border border-slate-200 overflow-hidden max-w-2xl mx-auto">
                  <div className="px-6 py-4 border-b border-slate-100 bg-slate-50">
                    <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Cuerpo del correo</div>
                    <div className="text-sm text-slate-500 italic">
                      [Aquí aparece el contenido específico de la notificación: aprobación, envío a
                      cliente, notificación de proyecto, etc.]
                    </div>
                  </div>
                  <div className="px-6 py-5">
                    <div
                      className="prose prose-sm max-w-none text-slate-700"
                      style={{
                        fontFamily: 'Arial, Helvetica, sans-serif',
                        fontSize: '12px',
                        lineHeight: 1.6,
                        color: '#475569',
                        borderTop: '1px solid #e2e8f0',
                        paddingTop: '16px',
                      }}
                      data-testid="footer-preview-html"
                      dangerouslySetInnerHTML={{ __html: resolveVariables(bodyHtml) || '<em style="color:#94a3b8">Sin contenido. Escribe en el editor para ver la vista previa.</em>' }}
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-500 text-center mt-4">
                  Así se verá el footer al final de cada correo enviado por el sistema.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default EmailFooterConfig;
