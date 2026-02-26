import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, UserIcon, Pencil, Trash2 } from "lucide-react";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  type User,
} from "../client";
import { useAuth } from "../auth";
import UserForm from "../components/UserForm";

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
  });

  const extractError = (err: unknown): string => {
    if (err && typeof err === "object" && "response" in err) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response;
      const detail = resp?.data?.detail;
      if (detail === "A user with this email already exists") return "Пользователь с таким email уже существует";
      if (detail) return detail;
    }
    return "Не удалось сохранить";
  };

  const createMut = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, ...rest }: { id: string } & Parameters<typeof updateUser>[1]) =>
      updateUser(id, rest),
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditingUser(null);
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const handleDelete = (user: User) => {
    if (user.id === currentUser?.id) return;
    if (confirm(`Удалить пользователя ${user.email}?`)) {
      deleteMut.mutate(user.id);
    }
  };

  const users = data?.data ?? [];
  const ONLINE_WINDOW_MS = 5 * 60_000;
  const isRecentlyOnline = (lastSeenAt: string | null): boolean => {
    if (!lastSeenAt) return false;
    return Date.now() - new Date(lastSeenAt).getTime() <= ONLINE_WINDOW_MS;
  };
  const formatLastSeen = (lastSeenAt: string | null): string => {
    if (!lastSeenAt) return "Никогда";
    return new Date(lastSeenAt).toLocaleString("ru-RU");
  };

  return (
    <div className="space-y-6">
      <div className="app-toolbar p-4 sm:p-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Управление пользователями</h1>
          <p className="text-sm text-slate-500 mt-1">Создание аккаунтов и назначение ролей</p>
        </div>
        <button
          onClick={() => { setEditingUser(null); setFormError(null); setShowForm(true); }}
          className="app-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm transition"
        >
          <Plus className="h-4 w-4" />
          Создать
        </button>
      </div>

      <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
        <div className="app-stat bg-gray-100 px-4 py-3">
          <div className="text-2xl font-bold text-gray-900">{users.length}</div>
          <div className="text-xs text-gray-500 mt-0.5">Всего</div>
        </div>
        <div className="app-stat bg-blue-50 px-4 py-3">
          <div className="text-2xl font-bold text-blue-700">{users.filter((u) => u.is_superuser).length}</div>
          <div className="text-xs text-gray-500 mt-0.5">Администраторы</div>
        </div>
        <div className="app-stat bg-emerald-50 px-4 py-3">
          <div className="text-2xl font-bold text-emerald-700">{users.filter((u) => u.is_active).length}</div>
          <div className="text-xs text-gray-500 mt-0.5">Активные</div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      ) : users.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg">Нет пользователей</p>
        </div>
      ) : (
        <div className="app-panel overflow-hidden app-compact-scroll">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Пользователь</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Роль</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">В сети</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Создан</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className={`flex items-center justify-center h-8 w-8 rounded-full ${u.is_superuser ? "bg-blue-100" : "bg-gray-100"}`}>
                        {u.is_superuser ? (
                          <Shield className="h-4 w-4 text-blue-600" />
                        ) : (
                          <UserIcon className="h-4 w-4 text-gray-500" />
                        )}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">{u.full_name || "—"}</div>
                        <div className="text-xs text-gray-500">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        u.is_superuser
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {u.is_superuser ? "Админ" : "Пользователь"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        u.is_active
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {u.is_active ? "Активен" : "Заблокирован"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {isRecentlyOnline(u.last_seen_at) ? (
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700">
                        Онлайн
                      </span>
                    ) : (
                      <span className="text-sm text-gray-500">{formatLastSeen(u.last_seen_at)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(u.created_at).toLocaleDateString("ru-RU")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => { setEditingUser(u); setFormError(null); setShowForm(true); }}
                        className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
                        title="Редактировать"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      {u.id !== currentUser?.id && (
                        <button
                          onClick={() => handleDelete(u)}
                          className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 transition"
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <UserForm
          user={editingUser}
          loading={createMut.isPending || updateMut.isPending}
          error={formError}
          onClose={() => { setShowForm(false); setEditingUser(null); setFormError(null); }}
          onSave={(formData) => {
            setFormError(null);
            if (editingUser) {
              updateMut.mutate({ id: editingUser.id, ...formData });
            } else {
              createMut.mutate({ ...formData, password: formData.password! });
            }
          }}
        />
      )}
    </div>
  );
}
