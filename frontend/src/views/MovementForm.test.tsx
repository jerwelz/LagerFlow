import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MovementForm } from "./Movements";

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MovementForm", () => {
  it("shows the insufficient-stock error and does not report a change", async () => {
    vi.stubGlobal(
      "fetch",
      respond(409, {
        error: { code: "INSUFFICIENT_STOCK", message: "x", details: { requested: 50, available: 10 } },
      }),
    );
    const onBooked = vi.fn();
    render(<MovementForm productId={1} onBooked={onBooked} />);

    await userEvent.click(screen.getByLabelText("Abgang (Entnahme)"));
    await userEvent.clear(screen.getByLabelText("Menge"));
    await userEvent.type(screen.getByLabelText("Menge"), "50");
    await userEvent.click(screen.getByRole("button", { name: "Buchung speichern" }));

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Nicht genügend Bestand: angefordert 50, verfügbar 10.",
    );
    expect(onBooked).not.toHaveBeenCalled();
  });

  it("books an incoming movement and reports the change", async () => {
    const fetchMock = respond(201, {
      id: 9, product_id: 1, movement_type: "IN", quantity: 12, reason: "Lieferung", created_at: "2026-01-01T00:00:00Z",
    });
    vi.stubGlobal("fetch", fetchMock);
    const onBooked = vi.fn();
    render(<MovementForm productId={1} onBooked={onBooked} />);

    await userEvent.clear(screen.getByLabelText("Menge"));
    await userEvent.type(screen.getByLabelText("Menge"), "12");
    await userEvent.type(screen.getByLabelText("Grund (optional)"), "Lieferung");
    await userEvent.click(screen.getByRole("button", { name: "Buchung speichern" }));

    expect((await screen.findByRole("status")).textContent).toBe("Zugang von 12 Einheiten gebucht.");
    expect(onBooked).toHaveBeenCalledOnce();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      movement_type: "IN",
      quantity: 12,
      reason: "Lieferung",
    });
  });
});
