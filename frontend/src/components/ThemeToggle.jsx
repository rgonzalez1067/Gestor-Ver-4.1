import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';

// Botón día/noche. Usa next-themes (persiste en localStorage y respeta el SO).
export const ThemeToggle = ({ collapsed = false }) => {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && (resolvedTheme === 'dark' || theme === 'dark');
  const toggle = () => setTheme(isDark ? 'light' : 'dark');
  const label = isDark ? 'Modo claro' : 'Modo oscuro';

  const icons = (
    <span className="relative inline-flex h-5 w-5 items-center justify-center">
      <Sun size={20} className="absolute rotate-0 scale-100 transition-transform duration-500 dark:-rotate-90 dark:scale-0" />
      <Moon size={20} className="absolute rotate-90 scale-0 transition-transform duration-500 dark:rotate-0 dark:scale-100" />
    </span>
  );

  if (collapsed) {
    return (
      <button
        onClick={toggle}
        data-testid="theme-toggle-button"
        aria-label={label}
        className="flex items-center justify-center w-full py-2.5 mb-2 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-slate-800 dark:hover:text-indigo-300 rounded-lg transition-colors"
      >
        {icons}
      </button>
    );
  }

  return (
    <button
      onClick={toggle}
      data-testid="theme-toggle-button"
      aria-label={label}
      className="flex items-center gap-3 px-4 py-2.5 mx-3 mb-2 rounded-lg w-[calc(100%-1.5rem)] text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-indigo-300 transition-colors"
    >
      {icons}
      <span className="font-medium text-sm">{label}</span>
    </button>
  );
};
