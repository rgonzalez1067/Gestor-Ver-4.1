import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileText, Users, Building2, TrendingUp, CreditCard, Package } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const Dashboard = () => {
  const [stats, setStats] = useState({
    totalQuotes: 0,
    totalClients: 0,
    totalBanks: 0,
    totalMediosPago: 0,
    totalHardware: 0,
    exchangeRate: 0
  });
  const [recentQuotes, setRecentQuotes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [quotesRes, clientsRes, banksRes, servicesRes, hardwareRes, rateRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/services'),
        api.get('/hardware'),
        api.get('/exchange-rate/current')
      ]);

      // Contar registros correctamente
      const quotesCount = Array.isArray(quotesRes.data) ? quotesRes.data.length : 0;
      const clientsCount = Array.isArray(clientsRes.data) ? clientsRes.data.length : 0;
      const banksCount = Array.isArray(banksRes.data) ? banksRes.data.length : 0;
      const servicesCount = Array.isArray(servicesRes.data) ? servicesRes.data.length : 0;
      const hardwareCount = Array.isArray(hardwareRes.data) ? hardwareRes.data.length : 0;

      setStats({
        totalQuotes: quotesCount,
        totalClients: clientsCount,
        totalBanks: banksCount,
        totalMediosPago: servicesCount,
        totalHardware: hardwareCount,
        exchangeRate: rateRes.data?.rate || 0
      });

      setRecentQuotes(Array.isArray(quotesRes.data) ? quotesRes.data.slice(0, 5) : []);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      toast.error('Error al cargar datos del dashboard');
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: 'Cotizaciones',
      value: stats.totalQuotes,
      icon: FileText,
      color: 'bg-sky-100 text-sky-700'
    },
    {
      title: 'Clientes',
      value: stats.totalClients,
      icon: Users,
      color: 'bg-emerald-100 text-emerald-700'
    },
    {
      title: 'Bancos',
      value: stats.totalBanks,
      icon: Building2,
      color: 'bg-purple-100 text-purple-700'
    },
    {
      title: 'Medios de Pago',
      value: stats.totalMediosPago,
      icon: CreditCard,
      color: 'bg-rose-100 text-rose-700'
    },
    {
      title: 'Hardware',
      value: stats.totalHardware,
      icon: Package,
      color: 'bg-orange-100 text-orange-700'
    },
    {
      title: 'Tasa BCV',
      value: stats.exchangeRate ? `${stats.exchangeRate.toFixed(2)} Bs/$` : '-',
      icon: TrendingUp,
      color: 'bg-amber-100 text-amber-700'
    }
  ];

  const chartData = [
    { name: 'Ene', cotizaciones: 12 },
    { name: 'Feb', cotizaciones: 19 },
    { name: 'Mar', cotizaciones: 15 },
    { name: 'Abr', cotizaciones: 22 },
    { name: 'May', cotizaciones: 18 },
    { name: 'Jun', cotizaciones: 25 }
  ];

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando dashboard...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="dashboard">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
              Dashboard
            </h1>
            <p className="text-slate-600">Vista general del sistema</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 mb-8">
            {statCards.map((stat, index) => {
              const Icon = stat.icon;
              return (
                <div
                  key={index}
                  data-testid={`stat-${stat.title.toLowerCase()}`}
                  className="bg-white rounded-lg border border-slate-200 p-6 card-hover"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className={`p-3 rounded-lg ${stat.color}`}>
                      <Icon size={24} />
                    </div>
                  </div>
                  <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-1">
                    {stat.title}
                  </h3>
                  <p className="text-3xl font-bold text-slate-900 font-manrope">
                    {stat.value}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4">
                Cotizaciones por Mes
              </h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="cotizaciones" fill="#0284c7" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4">
                Últimas Cotizaciones
              </h2>
              <div className="space-y-3">
                {recentQuotes.length > 0 ? (
                  recentQuotes.map((quote) => (
                    <div
                      key={quote.quote_id}
                      className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-sky-200 transition-colors"
                    >
                      <div>
                        <p className="font-medium text-slate-900">{quote.quote_number}</p>
                        <p className="text-sm text-slate-500">
                          {new Date(quote.created_at).toLocaleDateString('es-VE')}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-slate-900">
                          ${quote.total_usd.toFixed(2)}
                        </p>
                        <p className="text-sm text-slate-500">
                          {quote.total_bs.toFixed(2)} Bs
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-center text-slate-500 py-8">
                    No hay cotizaciones recientes
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;