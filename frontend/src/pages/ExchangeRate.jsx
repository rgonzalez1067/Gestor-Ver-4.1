import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { RefreshCw, TrendingUp } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const ExchangeRate = () => {
  const [currentRate, setCurrentRate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    fetchCurrentRate();
  }, []);

  const fetchCurrentRate = async () => {
    try {
      const response = await api.get('/exchange-rate/current');
      setCurrentRate(response.data);
    } catch (error) {
      console.error('Error fetching exchange rate:', error);
      toast.error('Error al cargar tasa de cambio');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async () => {
    setUpdating(true);
    try {
      const response = await api.post('/exchange-rate/update');
      setCurrentRate(response.data);
      toast.success('Tasa de cambio actualizada exitosamente');
    } catch (error) {
      console.error('Error updating exchange rate:', error);
      toast.error('Error al actualizar tasa de cambio');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando tasa de cambio...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="exchange-rate-page">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
              Tasa de Cambio
            </h1>
            <p className="text-slate-600">Gestione la tasa de cambio BCV para cotizaciones</p>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-8">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="p-4 bg-amber-100 rounded-lg">
                  <TrendingUp size={32} className="text-amber-700" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">
                    Tasa Actual BCV
                  </p>
                  {currentRate && (
                    <p className="text-5xl font-bold text-slate-900 font-manrope mt-1">
                      {currentRate.rate.toFixed(2)} Bs/$
                    </p>
                  )}
                </div>
              </div>
              
              <Button
                onClick={handleUpdate}
                disabled={updating}
                data-testid="update-rate-button"
                className="bg-sky-600 hover:bg-sky-700 text-white"
              >
                {updating ? (
                  <>
                    <RefreshCw size={20} className="mr-2 animate-spin" />
                    Actualizando...
                  </>
                ) : (
                  <>
                    <RefreshCw size={20} className="mr-2" />
                    Actualizar Tasa
                  </>
                )}
              </Button>
            </div>

            {currentRate && (
              <div className="border-t pt-6">
                <dl className="grid grid-cols-1 gap-4">
                  <div className="flex justify-between items-center">
                    <dt className="text-sm font-medium text-slate-600">Fuente</dt>
                    <dd className="text-sm font-semibold text-slate-900">{currentRate.source}</dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-sm font-medium text-slate-600">Última Actualización</dt>
                    <dd className="text-sm font-semibold text-slate-900">
                      {new Date(currentRate.date).toLocaleString('es-VE', {
                        dateStyle: 'long',
                        timeStyle: 'short'
                      })}
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            <div className="mt-8 p-4 bg-sky-50 rounded-lg border border-sky-200">
              <p className="text-sm text-sky-900">
                <strong>Nota:</strong> La tasa de cambio se actualiza desde la API del Banco Central de Venezuela (BCV).
                Esta tasa se aplica automáticamente a todas las nuevas cotizaciones.
              </p>
            </div>
          </div>

          <div className="mt-8 bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4">
              Conversión Rápida
            </h2>
            {currentRate && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                  <p className="text-sm text-slate-600 mb-2">1 USD equivale a:</p>
                  <p className="text-3xl font-bold text-slate-900 font-manrope">
                    {currentRate.rate.toFixed(2)} Bs
                  </p>
                </div>
                <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                  <p className="text-sm text-slate-600 mb-2">1 Bs equivale a:</p>
                  <p className="text-3xl font-bold text-slate-900 font-manrope">
                    ${(1 / currentRate.rate).toFixed(6)} USD
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ExchangeRate;
