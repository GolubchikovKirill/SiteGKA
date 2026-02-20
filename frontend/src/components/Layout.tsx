import type { ReactNode } from "react";
import { useAuth } from "../auth";
import { LogOut, Server } from "lucide-react";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <Server className="h-6 w-6 text-blue-600" />
            <span className="text-lg font-semibold text-gray-900">InfraScope</span>
            <span className="text-sm text-gray-400 hidden sm:inline">IT Monitoring</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              {user?.full_name || user?.email}
            </span>
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition"
            >
              <LogOut className="h-4 w-4" />
              Выход
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
