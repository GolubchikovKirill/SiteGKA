import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";
import { LogOut, Server, Printer, Users, Monitor, Network, Moon, Sun } from "lucide-react";
import { readThemeMode, setThemeMode, type ThemeMode } from "../theme";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => readThemeMode());

  const navItems = [
    { to: "/", label: "Принтеры", icon: Printer, visible: true },
    { to: "/media-players", label: "Медиаплееры", icon: Monitor, visible: true },
    { to: "/switches", label: "Свитчи", icon: Network, visible: true },
    { to: "/users", label: "Пользователи", icon: Users, visible: isSuperuser },
  ];

  const handleToggleTheme = () => {
    const next: ThemeMode = themeMode === "light" ? "dark" : "light";
    setThemeMode(next);
    setThemeModeState(next);
  };

  return (
    <div className="min-h-screen flex flex-col app-shell">
      <header className="app-header sticky top-0 z-30 border-b backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 p-2 shadow-md">
                <Server className="h-5 w-5 text-white" />
              </div>
              <div>
                <span className="text-lg font-semibold text-slate-900">InfraScope</span>
                <span className="ml-2 text-xs text-slate-500 hidden sm:inline">IT Monitoring</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleToggleTheme}
                className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm transition app-btn-secondary"
                title={themeMode === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
              >
                {themeMode === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
                {themeMode === "light" ? "Dark" : "Light"}
              </button>
              <span className="text-sm text-slate-600 max-w-56 truncate">
                {user?.full_name || user?.email}
              </span>
              <button
                onClick={logout}
                className="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm transition app-btn-secondary"
              >
                <LogOut className="h-4 w-4" />
                Выход
              </button>
            </div>
          </div>

          {/* Navigation tabs */}
          <nav className="-mb-px flex gap-2 pb-2 overflow-x-auto">
            {navItems
              .filter((item) => item.visible)
              .map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end
                  className={({ isActive }) =>
                    `inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition whitespace-nowrap ${
                      isActive
                        ? "border-blue-200 bg-blue-50 text-blue-700 app-nav-active"
                        : "border-transparent text-slate-500 hover:border-slate-200 hover:bg-white hover:text-slate-700 app-nav-idle"
                    }`
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
