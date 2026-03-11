import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, vi } from "vitest";

const api = vi.hoisted(() => ({
  exportBoardingPass: vi.fn(),
}));

vi.mock("../client", () => ({
  exportBoardingPass: api.exportBoardingPass,
}));

import BoardingPassPanel from "./BoardingPassPanel";

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BoardingPassPanel />
    </QueryClientProvider>,
  );
}

describe("BoardingPassPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    api.exportBoardingPass.mockReset();
  });

  it("prefills simple route mode with defaults", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-11T12:00:00Z"));

    renderPanel();

    expect(screen.getByDisplayValue("SVO")).toBeInTheDocument();
    expect(screen.getByDisplayValue("LED")).toBeInTheDocument();
    expect(screen.getByText("Шаблон по умолчанию: John Doe, BA1234, место 35A, сегодняшняя дата.")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("submits only route fields and auto-fills the rest", async () => {
    api.exportBoardingPass.mockResolvedValue(new Blob(["png-content"], { type: "image/png" }));
    const createUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    const revokeUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-11T12:00:00Z"));

    renderPanel();

    fireEvent.change(screen.getByDisplayValue("Aztec"), { target: { value: "pdf417" } });
    fireEvent.change(screen.getByDisplayValue("SVO"), { target: { value: " zrh1 " } });
    fireEvent.change(screen.getByDisplayValue("LED"), { target: { value: " sfo " } });
    fireEvent.click(screen.getByRole("button", { name: "Сформировать PNG" }));

    await waitFor(() => {
      expect(api.exportBoardingPass).toHaveBeenCalled();
      expect(api.exportBoardingPass.mock.calls[0]?.[0]).toEqual({
        format: "pdf417",
        first_name: "JOHN",
        last_name: "DOE",
        booking_ref: "XYZ123",
        from_code: "ZRH",
        to_code: "SFO",
        flight_operator: "BA",
        flight_number: "1234",
        flight_date: "2026-03-11",
        day_in_year: "070",
        travel_class: "Y",
        seat: "35A",
        boarding_index: "0001",
      });
    });
    expect(await screen.findByText("Файл boarding pass сформирован и скачан.")).toBeInTheDocument();

    createUrl.mockRestore();
    revokeUrl.mockRestore();
    clickSpy.mockRestore();
    vi.useRealTimers();
  });

  it("uses raw payload when it is provided", async () => {
    api.exportBoardingPass.mockResolvedValue(new Blob(["png-content"], { type: "image/png" }));
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderPanel();

    fireEvent.click(screen.getByText("Расширенный режим"));
    fireEvent.change(screen.getByPlaceholderText("M1DOE/JOHN XYZ123 SVOLEDBA1234..."), {
      target: { value: " M1RAW " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сформировать PNG" }));

    await waitFor(() => {
      expect(api.exportBoardingPass.mock.calls[0]?.[0]).toMatchObject({
        format: "aztec",
        raw_data: "M1RAW",
      });
    });
  });

  it("shows backend validation errors", async () => {
    api.exportBoardingPass.mockRejectedValue({
      response: {
        data: {
          detail: "last_name is required",
        },
      },
    });

    renderPanel();
    fireEvent.change(screen.getByDisplayValue("SVO"), { target: { value: "DME" } });
    fireEvent.change(screen.getByDisplayValue("LED"), { target: { value: "AER" } });
    fireEvent.click(screen.getByRole("button", { name: "Сформировать PNG" }));

    expect(await screen.findByText("last_name is required")).toBeInTheDocument();
  });
});
