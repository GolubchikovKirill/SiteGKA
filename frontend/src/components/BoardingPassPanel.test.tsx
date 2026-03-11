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

  it("submits normalized payload and downloads blob", async () => {
    api.exportBoardingPass.mockResolvedValue(new Blob(["png-content"], { type: "image/png" }));
    const createUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    const revokeUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderPanel();

    fireEvent.change(screen.getByDisplayValue("Aztec"), { target: { value: "pdf417" } });
    fireEvent.change(screen.getByPlaceholderText("IVAN"), { target: { value: " ivan " } });
    fireEvent.change(screen.getByPlaceholderText("IVANOV"), { target: { value: " ivanov " } });
    fireEvent.change(screen.getByPlaceholderText("EBR123"), { target: { value: " ebr123 " } });
    fireEvent.change(screen.getByPlaceholderText("SVO"), { target: { value: " svo " } });
    fireEvent.change(screen.getByPlaceholderText("LED"), { target: { value: " led " } });
    fireEvent.change(screen.getByPlaceholderText("SU"), { target: { value: " su " } });
    fireEvent.change(screen.getByPlaceholderText("1234"), { target: { value: " 1234 " } });
    fireEvent.change(screen.getByLabelText("Дата рейса"), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByPlaceholderText("032"), { target: { value: " 032 " } });
    fireEvent.change(screen.getByPlaceholderText("Y"), { target: { value: " y " } });
    fireEvent.change(screen.getByPlaceholderText("12A"), { target: { value: " 12a " } });
    fireEvent.change(screen.getByPlaceholderText("001"), { target: { value: " 7 " } });
    fireEvent.click(screen.getByRole("button", { name: "Сформировать и скачать PNG" }));

    await waitFor(() => {
      expect(api.exportBoardingPass).toHaveBeenCalled();
      expect(api.exportBoardingPass.mock.calls[0]?.[0]).toEqual({
        format: "pdf417",
        first_name: "ivan",
        last_name: "ivanov",
        booking_ref: "ebr123",
        from_code: "svo",
        to_code: "led",
        flight_operator: "su",
        flight_number: "1234",
        flight_date: "2026-02-01",
        day_in_year: "032",
        travel_class: "y",
        seat: "12a",
        boarding_index: "7",
        raw_data: undefined,
      });
    });
    expect(await screen.findByText("Файл boarding pass сформирован и скачан.")).toBeInTheDocument();

    createUrl.mockRestore();
    revokeUrl.mockRestore();
    clickSpy.mockRestore();
  });

  it("uses raw payload when it is provided", async () => {
    api.exportBoardingPass.mockResolvedValue(new Blob(["png-content"], { type: "image/png" }));
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderPanel();

    fireEvent.change(screen.getByPlaceholderText("M1IVANOV/IVAN EBR123 SVOLED..."), {
      target: { value: " M1RAW " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сформировать и скачать PNG" }));

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
    fireEvent.click(screen.getByRole("button", { name: "Сформировать и скачать PNG" }));

    expect(await screen.findByText("last_name is required")).toBeInTheDocument();
  });
});
