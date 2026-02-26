import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { ReactNode } from "react";

vi.mock("./components/Layout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("./pages/Dashboard", () => ({ default: () => <div>DashboardPage</div> }));
vi.mock("./pages/MediaPlayersPage", () => ({ default: () => <div>MediaPlayersPage</div> }));
vi.mock("./pages/SwitchesPage", () => ({ default: () => <div>SwitchesPage</div> }));
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

describe("App routes", () => {
  it("redirects unauthenticated user to login", async () => {
    authState.user = null;
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("LoginPage")).toBeInTheDocument();
  });

  it("shows dashboard for authenticated user", async () => {
    authState.user = { is_superuser: true };
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("DashboardPage")).toBeInTheDocument();
  });
});

