import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { ReactNode } from "react";

vi.mock("./components/Layout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("./pages/Dashboard", () => ({ default: () => <div>DashboardPage</div> }));
vi.mock("./pages/MediaPlayersPage", () => ({ default: () => <div>MediaPlayersPage</div> }));
vi.mock("./pages/SwitchesPage", () => ({ default: () => <div>SwitchesPage</div> }));
vi.mock("./pages/ServiceFlowMapPage", () => ({ default: () => <div>ServiceFlowMapPage</div> }));
vi.mock("./pages/Users", () => ({ default: () => <div>UsersPage</div> }));
vi.mock("./pages/Login", () => ({ default: () => <div>LoginPage</div> }));

const authState = {
  user: null as null | { is_superuser: boolean },
  isLoading: false,
};
vi.mock("./auth", () => ({
  useAuth: () => authState,
}));

import App from "./App";

function renderWithProviders(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App routes", () => {
  it("redirects unauthenticated user to login", async () => {
    authState.user = null;
    renderWithProviders("/");
    expect(await screen.findByText("LoginPage")).toBeInTheDocument();
  });

  it("shows dashboard for authenticated user", async () => {
    authState.user = { is_superuser: true };
    renderWithProviders("/");
    expect(await screen.findByText("DashboardPage")).toBeInTheDocument();
  });

  it("shows service flow page for authenticated user", async () => {
    authState.user = { is_superuser: true };
    renderWithProviders("/service-flow-map");
    expect(await screen.findByText("ServiceFlowMapPage")).toBeInTheDocument();
  });
});

