import api from "./client";

describe("client interceptors", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, "location", {
      value: { href: "http://localhost/" },
      writable: true,
      configurable: true,
    });
  });

  it("adds bearer token to outgoing request headers", async () => {
    localStorage.setItem("access_token", "abc-token");
    const handlers = (api.interceptors.request as any).handlers;
    const fulfilled = handlers[0].fulfilled as (config: any) => any;
    const config = fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBe("Bearer abc-token");
  });

  it("clears token on 401/403 responses", async () => {
    localStorage.setItem("access_token", "abc-token");
    const handlers = (api.interceptors.response as any).handlers;
    const rejected = handlers[0].rejected as (error: any) => Promise<never>;

    await expect(rejected({ response: { status: 401 } })).rejects.toBeTruthy();
    expect(localStorage.getItem("access_token")).toBeNull();
  });
});

