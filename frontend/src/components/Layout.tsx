import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import {
  ChevronDown,
  ChevronRight,
  LogOut,
  Shield,
  Server,
  Printer,
  Users,
  Monitor,
  Laptop,
  Network,
  Moon,
  Sun,
  ScrollText,
  Settings2,
  UserIcon,
  Wallet,
  Radar,
  Cable,
} from "lucide-react";
import { readThemeMode, setThemeMode, type ThemeMode } from "../theme";
import { motion, AnimatePresence } from "framer-motion";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isSuperuser = user?.is_superuser ?? false;
  const displayName = user?.full_name?.trim() || user?.email || "Пользователь";
  const isOnline = Boolean(user);
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "U";
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => readThemeMode());
  const [isSidebarVisible, setSidebarVisible] = useState<boolean>(() => {
    try {
      return localStorage.getItem("infrascope_sidebar_hidden") !== "1";
    } catch {
      return true;
    }
  });

  const [isEquipmentOpen, setEquipmentOpen] = useState(true);
  const equipmentItems = [
    { to: "/", label: "Принтеры", icon: Printer, visible: true },
    { to: "/media-players", label: "Медиаплееры", icon: Monitor, visible: true },
    { to: "/switches", label: "Сетевое оборудование", icon: Network, visible: true },
    { to: "/cash-registers", label: "Кассы", icon: Wallet, visible: true },
    { to: "/computers", label: "Компьютеры", icon: Laptop, visible: true },
    { to: "/network-search", label: "Поиск в сети", icon: Radar, visible: true },
  ];
  const baseItems = [
    { to: "/onec", label: "1C", icon: Cable, visible: true },
    { to: "/settings", label: "Настройки", icon: Settings2, visible: true },
    { to: "/logs", label: "Логи", icon: ScrollText, visible: true },
    { to: "/users", label: "Пользователи", icon: Users, visible: isSuperuser },
  ];
  const equipmentVisibleItems = equipmentItems.filter((item) => item.visible);
  const equipmentIsActive = equipmentVisibleItems.some((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to),
  );

  const handleToggleTheme = () => {
    const next: ThemeMode = themeMode === "light" ? "dark" : "light";
    setThemeMode(next);
    setThemeModeState(next);
  };

  const handleToggleSidebar = () => {
    setSidebarVisible((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("infrascope_sidebar_hidden", next ? "0" : "1");
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen app-shell md:flex">
      <aside className={`${isSidebarVisible ? "hidden md:flex" : "hidden"} app-sidebar md:w-72 md:flex-col md:sticky md:top-0 md:h-screen md:border-r`}>
        <div className="px-5 py-5 border-b border-[var(--app-panel-border)]">
          <div className="flex items-center gap-3 justify-between">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleToggleSidebar}
                className="app-logo-btn app-logo-live rounded-xl bg-linear-to-br from-red-700 to-rose-600 p-2 shadow-md"
                title="Свернуть/развернуть меню"
              >
                <Server className="h-5 w-5 text-white" />
              </button>
              <div>
                <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">InfraScope</div>
                <div className="text-xs text-slate-500">Control Center</div>
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          <button
            type="button"
            onClick={() => setEquipmentOpen((prev) => !prev)}
            className={`inline-flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${
              equipmentIsActive ? "app-nav-active" : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:text-slate-700"
            }`}
          >
            <span className="inline-flex items-center gap-3">
              <Server className="h-4 w-4 shrink-0" />
              Оборудование
            </span>
            {isEquipmentOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
          {isEquipmentOpen &&
            equipmentVisibleItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end
                className={({ isActive }) =>
                  `inline-flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 pl-8 text-sm font-medium transition ${
                    isActive
                      ? "app-nav-active"
                      : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:text-slate-700"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          {baseItems
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
                      : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:bg-white/60 hover:text-slate-700 dark:hover:bg-slate-800/60 dark:hover:text-slate-200"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
        </nav>

        <div className="p-4 border-t border-[var(--app-panel-border)] space-y-2.5">
          <div className="app-user-card rounded-xl px-3 py-2.5">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-rose-600 to-red-700 text-xs font-semibold text-white shadow-sm">
                {initials}
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100 inline-flex items-center gap-1.5">
                  <span>{displayName}</span>
                  {isSuperuser ? (
                    <span title="Администратор"><Shield className="h-3.5 w-3.5 text-rose-600" /></span>
                  ) : (
                    <span title="Пользователь"><UserIcon className="h-3.5 w-3.5 text-slate-500" /></span>
                  )}
                </div>
                <div className="truncate text-xs text-slate-500">{user?.email || "—"}</div>
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="app-badge-neutral inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium">
                Пользователь
              </span>
              <span className={`inline-flex items-center gap-1 text-[11px] ${isOnline ? "text-emerald-600" : "text-slate-500"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${isOnline ? "bg-emerald-500" : "bg-slate-400"}`} />
                {isOnline ? "Онлайн" : "Оффлайн"}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleToggleTheme}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs transition app-btn-secondary"
              title={themeMode === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
            >
              {themeMode === "light" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={logout}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs transition app-btn-secondary"
              title="Выйти из аккаунта"
            >
              <LogOut className="h-3.5 w-3.5" />
              Выход
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col h-screen overflow-hidden relative">
        <AnimatePresence>
          {!isSidebarVisible && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="hidden md:flex px-3 sm:px-5 lg:px-8 pt-3 absolute z-10"
            >
              <button
                type="button"
                onClick={handleToggleSidebar}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs app-btn-secondary app-logo-live backdrop-blur-md bg-white/70 dark:bg-slate-900/70"
                title="Развернуть меню"
              >
                <Server className="h-4 w-4" />
                InfraScope
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <header className="app-header md:hidden sticky top-0 z-30 border-b backdrop-blur-xl">
          <div className="px-3 py-3 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-linear-to-br from-red-700 to-rose-600 p-1.5 shadow-sm">
                  <Server className="h-4 w-4 text-white" />
                </div>
                <span className="font-semibold text-slate-900 dark:text-slate-100">InfraScope</span>
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
              <button
                type="button"
                onClick={() => setEquipmentOpen((prev) => !prev)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium whitespace-nowrap ${
                  equipmentIsActive ? "app-nav-active" : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200"
                }`}
              >
                <Server className="h-3.5 w-3.5" />
                Оборудование
                {isEquipmentOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              </button>
              {baseItems
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
                          : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200 hover:bg-white/70 dark:hover:bg-slate-800/70"
                      }`
                    }
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </NavLink>
                ))}
            </nav>
            {isEquipmentOpen && (
              <nav className="flex gap-2 overflow-x-auto pb-1">
                {equipmentVisibleItems.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end
                    className={({ isActive }) =>
                      `inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium whitespace-nowrap ${
                        isActive
                          ? "app-nav-active"
                          : "app-nav-idle border-transparent text-slate-500 hover:border-slate-200"
                      }`
                    }
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </NavLink>
                ))}
              </nav>
            )}
          </div>
        </header>

        <main className="flex-1 mx-auto w-full px-1 sm:px-3 lg:px-4 xl:px-5 py-5 sm:py-7 app-compact-scroll overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
