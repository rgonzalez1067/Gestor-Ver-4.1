import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export default function VerifyEmail() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState('loading'); // loading | success | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Token de verificación no proporcionado.');
      return;
    }

    const verify = async () => {
      try {
        const response = await api.post('/auth/verify-email', { token });
        setStatus('success');
        setMessage(response.data.message);
        toast.success(response.data.message);

        // Update stored user if logged in
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
          const user = JSON.parse(storedUser);
          user.is_verified = true;
          localStorage.setItem('user', JSON.stringify(user));
        }
      } catch (err) {
        setStatus('error');
        const detail = err.response?.data?.detail;
        const msg = typeof detail === 'string' ? detail : 'Error al verificar el correo.';
        setMessage(msg);
        toast.error(msg);
      }
    };

    verify();
  }, [token]);

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative bg-black"
      style={{
        backgroundImage: 'url(/fondo-megasoft.jpg)',
        backgroundSize: 'contain',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat'
      }}
    >
      <div className="absolute inset-0 bg-black/30" />

      <div className="w-full max-w-md relative z-10">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-8">
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-slate-800">Gestor</h1>
            <p className="text-slate-600 mt-1">Verificación de Correo</p>
          </div>

          <div className="text-center space-y-4">
            {status === 'loading' && (
              <div data-testid="verify-loading">
                <Loader2 className="h-16 w-16 text-blue-500 mx-auto animate-spin" />
                <h2 className="text-xl font-semibold text-slate-800 mt-4">Verificando...</h2>
                <p className="text-slate-600">Estamos verificando tu correo electrónico.</p>
              </div>
            )}

            {status === 'success' && (
              <div data-testid="verify-success">
                <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
                <h2 className="text-xl font-semibold text-slate-800 mt-4">Correo Verificado</h2>
                <p className="text-slate-600">{message}</p>
                <Button
                  onClick={() => navigate('/login')}
                  className="w-full bg-slate-800 hover:bg-slate-900 text-white mt-4"
                  data-testid="verify-go-login-btn"
                >
                  Ir a Iniciar Sesión
                </Button>
              </div>
            )}

            {status === 'error' && (
              <div data-testid="verify-error">
                <XCircle className="h-16 w-16 text-red-500 mx-auto" />
                <h2 className="text-xl font-semibold text-slate-800 mt-4">Error de Verificación</h2>
                <p className="text-slate-600">{message}</p>
                <Button
                  onClick={() => navigate('/login')}
                  className="w-full bg-slate-800 hover:bg-slate-900 text-white mt-4"
                  data-testid="verify-go-login-btn"
                >
                  Ir a Iniciar Sesión
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
