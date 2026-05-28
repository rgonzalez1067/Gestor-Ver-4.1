import { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../utils/api';
import { showInboxWelcomeToast } from '../utils/inboxWelcome';

export const AuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      try {
        const hash = location.hash;
        const params = new URLSearchParams(hash.replace('#', ''));
        const sessionId = params.get('session_id');

        if (!sessionId) {
          navigate('/login');
          return;
        }

        const response = await api.post('/auth/session', null, {
          headers: { 'X-Session-ID': sessionId }
        });

        const { session_token, user } = response.data;
        localStorage.setItem('session_token', session_token);
        localStorage.setItem('user', JSON.stringify(user));

        // Iter44: aviso destacado si tiene mensajes sin leer en el Centro de Mensajes.
        showInboxWelcomeToast({ firstName: user?.first_name });

        navigate('/dashboard', { state: { user }, replace: true });
      } catch (error) {
        console.error('Authentication failed:', error);
        navigate('/login');
      }
    };

    processSession();
  }, [navigate, location]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-600 mx-auto"></div>
        <p className="mt-4 text-slate-600">Autenticando...</p>
      </div>
    </div>
  );
};

export default AuthCallback;