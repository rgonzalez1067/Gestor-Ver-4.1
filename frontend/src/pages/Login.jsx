import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import api from '../utils/api';

export const Login = () => {
  const navigate = useNavigate();
  const [logoUrl, setLogoUrl] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('session_token');
    if (token) {
      navigate('/dashboard');
    }
    fetchLogo();
  }, [navigate]);

  const fetchLogo = async () => {
    try {
      const response = await api.get('/config/logo', { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      setLogoUrl(url);
    } catch (error) {
      // No logo configured, use default
    }
  };

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleGoogleSignup = () => {
    // Same as login - Google handles both login and signup
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen flex bg-white">
      <div className="hidden lg:flex lg:w-1/2 items-center justify-center bg-slate-50 p-12">
        <div className="text-center max-w-md">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt="Logo de la empresa"
              className="w-48 h-48 object-contain mx-auto mb-8"
              data-testid="login-company-logo"
            />
          ) : (
            <div className="w-48 h-48 mx-auto mb-8 bg-slate-200 rounded-lg flex items-center justify-center">
              <span className="text-4xl font-bold text-slate-400">MS</span>
            </div>
          )}
          <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Gestor</h1>
          <h2 className="text-2xl font-semibold text-slate-700 font-manrope mb-6">Work Flow de Procesos Integrales</h2>
          <p className="text-lg text-slate-600 leading-relaxed">
            Sistema integral de cotizaciones para plataformas de medios de pago.
            Gestione bancos, hardware y genere cotizaciones profesionales.
          </p>
        </div>
      </div>

      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          <div className="lg:hidden text-center mb-8">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo de la empresa"
                className="w-24 h-24 object-contain mx-auto mb-4"
              />
            ) : (
              <div className="w-24 h-24 mx-auto mb-4 bg-slate-200 rounded-lg flex items-center justify-center">
                <span className="text-2xl font-bold text-slate-400">MS</span>
              </div>
            )}
            <h1 className="text-2xl font-bold text-slate-900 font-manrope">Gestor - Work Flow de Procesos Integrales</h1>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-slate-900 font-manrope mb-2">
              Bienvenido
            </h2>
            <p className="text-slate-600">
              Accede o crea tu cuenta con Google
            </p>
          </div>

          <div className="space-y-4">
            <Button
              onClick={handleGoogleLogin}
              data-testid="google-login-button"
              className="w-full h-12 bg-slate-900 hover:bg-slate-800 text-white rounded-lg font-medium text-base"
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Iniciar Sesión con Google
            </Button>

            <Button
              onClick={handleGoogleSignup}
              data-testid="google-signup-button"
              variant="outline"
              className="w-full h-12 border-2 border-slate-300 hover:border-slate-400 text-slate-700 rounded-lg font-medium text-base"
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Crear Cuenta con Gmail
            </Button>

            <div className="text-center text-sm text-slate-500 mt-6">
              <p>Al continuar, aceptas nuestros</p>
              <p className="mt-1">
                <span className="text-sky-600 hover:underline cursor-pointer">Términos de Servicio</span>
                {' y '}
                <span className="text-sky-600 hover:underline cursor-pointer">Política de Privacidad</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;