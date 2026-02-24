import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Eye, EyeOff, User, Mail, Lock, CreditCard, Loader2, Building2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Sedes disponibles
const SEDES = [
  { value: 'TBP', label: 'Torre Banco Plaza (TBP)' },
  { value: 'LCH', label: 'Los Chaguaramos (LCH)' }
];

export const Auth = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState('login'); // 'login' o 'register'
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  // Form data
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    cedula: '',
    email: '',
    password: '',
    sede: 'TBP'  // Sede por defecto
  });
  
  // Errors
  const [errors, setErrors] = useState({});
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Limpiar error al escribir
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };
  
  const validateForm = () => {
    const newErrors = {};
    
    if (mode === 'register') {
      // Nombre: solo letras
      if (!formData.firstName.trim()) {
        newErrors.firstName = 'El nombre es requerido';
      } else if (!/^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$/.test(formData.firstName)) {
        newErrors.firstName = 'Solo se permiten letras';
      }
      
      // Apellido: solo letras
      if (!formData.lastName.trim()) {
        newErrors.lastName = 'El apellido es requerido';
      } else if (!/^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$/.test(formData.lastName)) {
        newErrors.lastName = 'Solo se permiten letras';
      }
      
      // Cédula: solo números, mínimo 6 caracteres
      if (!formData.cedula.trim()) {
        newErrors.cedula = 'La cédula es requerida';
      } else if (!/^\d{6,15}$/.test(formData.cedula)) {
        newErrors.cedula = 'Ingrese un número de cédula válido (6-15 dígitos)';
      }
    }
    
    // Email
    if (!formData.email.trim()) {
      newErrors.email = 'El correo es requerido';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Ingrese un correo válido';
    }
    
    // Contraseña
    if (!formData.password) {
      newErrors.password = 'La contraseña es requerida';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Mínimo 8 caracteres';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setLoading(true);
    
    try {
      if (mode === 'login') {
        // Login
        const response = await api.post('/auth/login', {
          email: formData.email,
          password: formData.password
        });
        
        localStorage.setItem('session_token', response.data.session_token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        
        toast.success(`Bienvenido, ${response.data.user.first_name || response.data.user.name}`);
        navigate('/quotes');
        
      } else {
        // Registro
        const response = await api.post('/auth/register', {
          first_name: formData.firstName,
          last_name: formData.lastName,
          cedula: formData.cedula,
          email: formData.email,
          password: formData.password
        });
        
        localStorage.setItem('session_token', response.data.session_token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        
        toast.success('Cuenta creada exitosamente');
        navigate('/quotes');
      }
    } catch (error) {
      console.error('Auth error:', error);
      const message = error.response?.data?.detail || 'Error de autenticación';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };
  
  const switchMode = (newMode) => {
    setMode(newMode);
    setErrors({});
  };
  
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
      {/* Overlay sutil para mejor legibilidad */}
      <div className="absolute inset-0 bg-black/30"></div>
      
      <div className="w-full max-w-md relative z-10">
        {/* Card con fondo semitransparente */}
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-8">
          {/* Logo y Título dentro del card */}
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-slate-800">Cotizador</h1>
            <p className="text-slate-600 mt-1">Merchant Server</p>
          </div>
          
          {/* Mode Selector */}
          <div className="flex mb-8 bg-slate-100 rounded-lg p-1">
            <button
              type="button"
              onClick={() => switchMode('login')}
              className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all ${
                mode === 'login'
                  ? 'bg-white shadow-sm text-slate-900'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              data-testid="login-tab"
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={() => switchMode('register')}
              className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all ${
                mode === 'register'
                  ? 'bg-white shadow-sm text-slate-900'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              data-testid="register-tab"
            >
              Registrarse
            </button>
          </div>
          
          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <>
                {/* Nombre */}
                <div className="space-y-1.5">
                  <Label htmlFor="firstName" className="text-sm font-medium text-slate-700">
                    Nombre
                  </Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      id="firstName"
                      name="firstName"
                      type="text"
                      placeholder="Ingrese su nombre"
                      value={formData.firstName}
                      onChange={handleChange}
                      className={`pl-10 ${errors.firstName ? 'border-red-500' : ''}`}
                      data-testid="register-firstname"
                    />
                  </div>
                  {errors.firstName && (
                    <p className="text-xs text-red-500">{errors.firstName}</p>
                  )}
                </div>
                
                {/* Apellido */}
                <div className="space-y-1.5">
                  <Label htmlFor="lastName" className="text-sm font-medium text-slate-700">
                    Apellido
                  </Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      id="lastName"
                      name="lastName"
                      type="text"
                      placeholder="Ingrese su apellido"
                      value={formData.lastName}
                      onChange={handleChange}
                      className={`pl-10 ${errors.lastName ? 'border-red-500' : ''}`}
                      data-testid="register-lastname"
                    />
                  </div>
                  {errors.lastName && (
                    <p className="text-xs text-red-500">{errors.lastName}</p>
                  )}
                </div>
                
                {/* Cédula */}
                <div className="space-y-1.5">
                  <Label htmlFor="cedula" className="text-sm font-medium text-slate-700">
                    Cédula de Identidad
                  </Label>
                  <div className="relative">
                    <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      id="cedula"
                      name="cedula"
                      type="text"
                      placeholder="Ej: 12345678"
                      value={formData.cedula}
                      onChange={handleChange}
                      className={`pl-10 ${errors.cedula ? 'border-red-500' : ''}`}
                      data-testid="register-cedula"
                    />
                  </div>
                  {errors.cedula && (
                    <p className="text-xs text-red-500">{errors.cedula}</p>
                  )}
                </div>
              </>
            )}
            
            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-medium text-slate-700">
                Correo Electrónico
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="correo@ejemplo.com"
                  value={formData.email}
                  onChange={handleChange}
                  className={`pl-10 ${errors.email ? 'border-red-500' : ''}`}
                  data-testid="auth-email"
                />
              </div>
              {errors.email && (
                <p className="text-xs text-red-500">{errors.email}</p>
              )}
            </div>
            
            {/* Contraseña */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium text-slate-700">
                Contraseña
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'}
                  value={formData.password}
                  onChange={handleChange}
                  className={`pl-10 pr-10 ${errors.password ? 'border-red-500' : ''}`}
                  data-testid="auth-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  data-testid="toggle-password"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-red-500">{errors.password}</p>
              )}
            </div>
            
            {/* Forgot Password Link (solo en login) */}
            {mode === 'login' && (
              <div className="text-right">
                <button
                  type="button"
                  onClick={() => toast.info('Próximamente: Recuperación de contraseña')}
                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                  data-testid="forgot-password-link"
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
            )}
            
            {/* Submit Button */}
            <Button
              type="submit"
              className="w-full bg-slate-800 hover:bg-slate-900 text-white py-2.5 mt-6"
              disabled={loading}
              data-testid="auth-submit"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {mode === 'login' ? 'Ingresando...' : 'Registrando...'}
                </>
              ) : (
                mode === 'login' ? 'Ingresar' : 'Crear Cuenta'
              )}
            </Button>
          </form>
          
          {/* Info text */}
          <p className="text-center text-xs text-slate-500 mt-6">
            Al continuar, aceptas nuestros{' '}
            <a href="#" className="text-blue-600 hover:underline">Términos de Servicio</a>
            {' '}y{' '}
            <a href="#" className="text-blue-600 hover:underline">Política de Privacidad</a>
          </p>
        </div>
        
        {/* Footer */}
        <p className="text-center text-xs text-white/80 mt-6 drop-shadow-lg">
          Sistema integral de cotizaciones para plataformas de medios de pago
        </p>
      </div>
    </div>
  );
};

export default Auth;
