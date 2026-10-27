import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage } from "./api";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("builds the product query from the given filters", async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0, limit: 20, offset: 0 });

    await api.listProducts({ search: "  kabel ", limit: 20, offset: 40, includeInactive: true });

    expect(fetchMock.mock.calls[0][0]).toBe("/products?search=kabel&limit=20&offset=40&include_inactive=true");
  });

  it("sends movements as JSON POST", async () => {
    const fetchMock = mockFetch(201, { id: 1 });

    await api.recordMovement(7, { movement_type: "OUT", quantity: 3, reason: null });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/products/7/movements");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ movement_type: "OUT", quantity: 3, reason: null });
  });

  it("turns the standard error format into an ApiError", async () => {
    mockFetch(409, {
      error: { code: "INSUFFICIENT_STOCK", message: "Insufficient stock", details: { requested: 5, available: 2 } },
    });

    const error = await api.recordMovement(1, { movement_type: "OUT", quantity: 5, reason: null }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "INSUFFICIENT_STOCK", details: { requested: 5, available: 2 } });
  });

  it("handles error responses without a JSON body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad Gateway", { status: 502 })));

    const error = await api.summary().catch((e) => e);

    expect(error).toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await api.summary().catch((e) => e);

    expect(errorMessage(error)).toBe("Der Server ist nicht erreichbar. Bitte später erneut versuchen.");
  });
});

describe("errorMessage", () => {
  it("explains insufficient stock with the numbers", () => {
    const error = new ApiError(409, "INSUFFICIENT_STOCK", "x", { requested: 50, available: 10 });
    expect(errorMessage(error)).toBe("Nicht genügend Bestand: angefordert 50, verfügbar 10.");
  });

  it("names the invalid fields of a validation error in German", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "x", [
      { loc: ["body", "sku"], msg: "bad" },
      { loc: ["body", "min_stock"], msg: "bad" },
    ]);
    expect(errorMessage(error)).toBe("Ungültige Eingabe: Artikelnummer, Mindestbestand.");
  });

  it("maps demo protections and falls back to the API message", () => {
    expect(errorMessage(new ApiError(429, "RATE_LIMITED", "x"))).toContain("Zu viele Änderungen");
    expect(errorMessage(new ApiError(409, "DEMO_LIMIT_REACHED", "x"))).toContain("Limit der Demo");
    expect(errorMessage(new ApiError(500, "INTERNAL_ERROR", "Boom"))).toBe("Fehler 500: Boom");
    expect(errorMessage(new Error("?"))).toBe("Unerwarteter Fehler. Bitte erneut versuchen.");
  });
});
