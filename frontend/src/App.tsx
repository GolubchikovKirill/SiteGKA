import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth";
import { pollAllMediaPlayers, pollAllPrinters, pollAllSwitches } from "./client";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import MediaPlayersPage from "./pages/MediaPlayersPage";
import SwitchesPage from "./pages/SwitchesPage";
import UsersPage from "./pages/Users";

const GLOBAL_AUTO_REFRESH_MS = 15 * 60_000;

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!user) return;
    const timer = setInterval(() => {
      Promise.allSettled([
        pollAllPrinters("laser"),
        pollAllPrinters("label"),
        pollAllMediaPlayers(),
        pollAllSwitches(),
      ]).finally(() => {
        queryClient.invalidateQueries({ queryKey: ["printers"] });
        queryClient.invalidateQueries({ queryKey: ["media-players"] });
        queryClient.invalidateQueries({ queryKey: ["switches"] });
      });
    }, GLOBAL_AUTO_REFRESH_MS);
    return () => clearInterval(timer);
  }, [queryClient, user]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user?.is_superuser) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/media-players" element={<MediaPlayersPage />} />
                <Route path="/switches" element={<SwitchesPage />} />
                <Route
                  path="/users"
                  element={
                    <AdminRoute>
                      <UsersPage />
                    </AdminRoute>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
