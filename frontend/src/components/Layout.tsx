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
    <div className="min-h-screen app-shell md:flex">
      <aside className="app-sidebar hidden md:flex md:w-72 md:flex-col md:sticky md:top-0 md:h-screen md:border-r">
        <div className="px-5 py-5 border-b border-inherit">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-gradient-to-br from-red-700 to-rose-600 p-2 shadow-md">
              <Server className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="text-lg font-semibold text-slate-900">InfraScope</div>
              <div className="text-xs text-slate-500">Control Center</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems
            .filter((item) => item.visible)
            .map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end
                className={({ isActive }) =>
                  `inline-flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${
                    isActive
                      ? "app-nav-active"
                      : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:bg-white/60 hover:text-slate-700"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
        </nav>

        <div className="p-4 border-t border-inherit space-y-2">
          <button
            onClick={handleToggleTheme}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm transition app-btn-secondary"
            title={themeMode === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
          >
            {themeMode === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            {themeMode === "light" ? "Тёмная тема" : "Светлая тема"}
          </button>
          <div className="text-xs text-slate-500 truncate px-1">{user?.full_name || user?.email}</div>
          <button
            onClick={logout}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm transition app-btn-secondary"
          >
            <LogOut className="h-4 w-4" />
            Выход
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="app-header md:hidden sticky top-0 z-30 border-b backdrop-blur-xl">
          <div className="px-3 py-3 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-gradient-to-br from-red-700 to-rose-600 p-1.5 shadow-sm">
                  <Server className="h-4 w-4 text-white" />
                </div>
                <span className="font-semibold text-slate-900">InfraScope</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleToggleTheme}
                  className="inline-flex items-center rounded-lg border px-2 py-1.5 text-xs app-btn-secondary"
                >
                  {themeMode === "light" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                </button>
                <button
                  onClick={logout}
                  className="inline-flex items-center rounded-lg border px-2 py-1.5 text-xs app-btn-secondary"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <nav className="flex gap-2 overflow-x-auto pb-1">
              {navItems
                .filter((item) => item.visible)
                .map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end
                    className={({ isActive }) =>
                      `inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium whitespace-nowrap ${
                        isActive
                          ? "app-nav-active"
                          : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:bg-white/70"
                      }`
                    }
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </NavLink>
                ))}
            </nav>
          </div>
        </header>

        <main className="w-full mx-auto px-3 sm:px-5 lg:px-8 py-5 sm:py-7">
          {children}
        </main>
      </div>
    </div>
  );
}
