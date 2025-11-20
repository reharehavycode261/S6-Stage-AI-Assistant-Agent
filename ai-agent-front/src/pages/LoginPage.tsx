import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/useAuthStore';
import { Button } from '@/components/common/Button';
import { LogIn, Mail, Lock, Eye, EyeOff, Sparkles } from 'lucide-react';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuthStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      await login({ email, password });
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Identifiants incorrects');
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF6F0] flex items-center justify-center p-6">
      {/* Container principal */}
      <div className="w-full max-w-7xl grid lg:grid-cols-2 gap-12 items-center">
        
        {/* Section gauche - Hero + Logos */}
        <div className="hidden lg:block space-y-8">
          {/* Hero */}
          <div className="space-y-4">
            <h1 className="leading-tight">
              <span className="block text-5xl font-extrabold text-[#3A2B7C] font-brand">
                Where AI meets
              </span>
              <span className="block text-5xl font-extrabold text-[#3A2B7C] font-brand">
                Strategy <span className="font-serif italic text-[#D96927]">Unlocking</span>
              </span>
              <span className="block text-5xl font-serif italic text-[#D96927]">
                Potential
              </span>
            </h1>
            <p className="text-base text-gray-700">
              AI Consulting and Custom Development for Enterprises and SMEs
            </p>
            <button className="px-5 py-2.5 rounded-full bg-[#5B2E91] text-white text-sm font-semibold shadow-sm hover:bg-[#4C257A] transition-colors">
              Explore all services
            </button>
          </div>
          {/* Logos bas de page */}
          <div className="pt-6">
            <p className="text-xs uppercase tracking-wide text-gray-500 mb-3">Trusted by</p>
            <div className="flex items-center gap-6 flex-wrap text-gray-500">
              <span className="font-semibold">Xero</span>
              <span className="font-semibold">Slalom</span>
              <span className="font-semibold">Lead Forensics</span>
              <span className="font-semibold">Company Advantage</span>
              <span className="font-semibold">Hootsuite</span>
            </div>
          </div>
        </div>

        {/* Section droite - Illustration + Formulaire */}
        <div className="w-full">
          {/* Illustration robot */}
          <div className="hidden md:block mb-6">
            <div className="relative rounded-3xl bg-white border border-gray-200 shadow-xl overflow-hidden">
              <div className="absolute -right-16 -top-16 w-64 h-64 bg-[#E86F2C]/10 rounded-full blur-3xl" />
              <div className="absolute -left-10 -bottom-10 w-72 h-72 bg-[#E86F2C]/10 rounded-full blur-3xl" />
              <img
                src="/image/Robot futuriste position assise sans texte.png"
                alt="AI Robot"
                className="relative z-10 w-full h-64 object-contain"
              />
            </div>
          </div>

          <div className="bg-white rounded-3xl p-8 lg:p-10 shadow-lg">
            {/* Header */}
            <div className="mb-8">
              <div className="inline-flex items-center justify-center w-14 h-14 bg-[#5B2E91] rounded-2xl mb-4 lg:hidden">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Bienvenue
              </h2>
              <p className="text-gray-600">
                Connectez-vous pour accéder à votre espace
              </p>
            </div>

            {/* Formulaire */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email */}
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-gray-700">
                  Adresse email
                </label>
                <div className="relative">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                    <Mail className="w-5 h-5" />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@vydata.com"
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-[#F6F2EA] border-2 border-transparent rounded-xl text-gray-900 placeholder-gray-400 focus:border-[#5B2E91] focus:bg-white transition-all outline-none"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-gray-700">
                  Mot de passe
                </label>
                <div className="relative">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                    <Lock className="w-5 h-5" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full pl-12 pr-12 py-3.5 bg-[#F6F2EA] border-2 border-transparent rounded-xl text-gray-900 placeholder-gray-400 focus:border-[#5B2E91] focus:bg-white transition-all outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {/* Remember & Forgot */}
              <div className="flex items-center justify-between text-sm pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded border-gray-300 text-[#5B2E91] focus:ring-[#5B2E91]"
                  />
                  <span className="text-gray-600">Se souvenir de moi</span>
                </label>
                <button
                  type="button"
                  className="text-[#5B2E91] hover:text-[#4C257A] font-medium transition-colors"
                >
                  Mot de passe oublié ?
                </button>
              </div>

              {/* Error */}
              {error && (
                <div className="p-4 bg-red-50 border-2 border-red-100 rounded-xl">
                  <p className="text-sm text-red-700 font-medium">{error}</p>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-4 bg-[#5B2E91] hover:bg-[#4C257A] text-white font-semibold rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Connexion en cours...
                  </span>
                ) : (
                  'Se connecter'
                )}
              </button>

              {/* Dev credentials */}
              {import.meta.env.DEV && (
                <div className="mt-6 p-4 bg-[#F5F3EF] rounded-xl border border-gray-200">
                  <p className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Lock className="w-3 h-3" />
                    Credentials de test
                  </p>
                  <div className="space-y-1 text-xs text-gray-600 font-mono">
                    <p>Email: <span className="text-[#5B2E91] font-semibold">admin@vydata.com</span></p>
                    <p>Password: <span className="text-[#5B2E91] font-semibold">Admin123!</span></p>
                  </div>
                </div>
              )}
            </form>

            {/* Footer */}
            <div className="mt-8 pt-6 border-t border-gray-100 text-center">
              <p className="text-sm text-gray-500">
                Propulsé par <span className="font-semibold text-[#5B2E91]">VyData AI</span>
              </p>
            </div>
          </div>

          {/* Mobile tagline */}
          <div className="lg:hidden mt-6 text-center">
            <p className="text-gray-600 text-sm">
              Automatisez vos workflows avec l'IA
            </p>
          </div>
        </div>
      </div>

      {/* Version */}
      <div className="absolute bottom-4 left-4 text-xs text-gray-400">
        v3.0.0
      </div>
    </div>
  );
}
