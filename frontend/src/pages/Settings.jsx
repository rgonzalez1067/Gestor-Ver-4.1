import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Upload, Trash2, Image, Database } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const Settings = () => {
  const [logoUrl, setLogoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchLogo();
  }, []);

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
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
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
                  className="bg-sky-600 hover:bg-sky-700 text-white"
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
          <div className="bg-white rounded-lg border border-slate-200 p-6">
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
        </div>
      </main>
    </div>
  );
};

export default Settings;
