import { devices, expect, test, type Page } from "@playwright/test";

// One end-to-end walk through the dashboard against the real API (local demo server or BASE_URL).
// Each run uses its own SKU, so it also works on the shared public demo.
const sku = `E2E-${Date.now()}`;

async function openTab(page: Page, name: string) {
  await page.getByRole("tab", { name }).click();
}

// Fail on console errors or uncaught exceptions in every test (tests in this file run serially).
// The browser also logs the 409/422 responses the tests provoke on purpose; those are expected.
const expectedHttpError = /status of (409|422) /;
let problems: string[] = [];

test.beforeEach(({ page }) => {
  problems = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !expectedHttpError.test(message.text())) problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

test("overview shows demo data, KPIs, activity and links", async ({ page, request }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "LagerFlow" })).toBeVisible();
  await expect(page.getByText("Demo-Modus")).toBeVisible();
  await expect(page.getByText("fiktiven Daten")).toBeVisible();
  await expect(page.getByTestId("kpi-Aktive Artikel")).not.toHaveText("–");
  await expect(page.getByRole("region", { name: "Kennzahlen" })).toBeVisible();
  await expect(page.locator("li", { hasText: "Wareneingang" }).first()).toBeVisible();
  await expect(page.getByText("Unter Mindestbestand").first()).toBeVisible();

  await expect(page.getByRole("link", { name: "API-Dokumentation" })).toHaveAttribute("href", "/docs");
  const docs = await request.get("/docs");
  expect(docs.status()).toBe(200);
  const csv = await request.get("/reports/inventory.csv");
  expect(csv.status()).toBe(200);
  expect(csv.headers()["content-type"]).toContain("text/csv");
});

test("product search, create, movements, insufficient stock, edit and deactivate", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "Artikel");

  // Search
  await page.getByLabel("Artikel suchen").fill("Sechskant");
  const table = page.getByRole("table", { name: "Artikelliste" });
  await expect(table.getByText("Sechskantschraube M6x30, verzinkt, 100 Stück")).toBeVisible();
  await expect(table.getByText("Packband")).toHaveCount(0);
  await page.getByLabel("Artikel suchen").fill("");

  // Validation error from the API is shown in German
  await page.getByRole("button", { name: "Neuer Artikel" }).click();
  const dialog = page.getByRole("dialog", { name: "Neuer Artikel" });
  await dialog.getByLabel("Artikelnummer (SKU)").fill("ungültig #1");
  await dialog.getByLabel("Bezeichnung").fill("Testartikel");
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Ungültige Eingabe: Artikelnummer.");

  // Create
  await dialog.getByLabel("Artikelnummer (SKU)").fill(sku);
  await dialog.getByLabel("Mindestbestand").fill("5");
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(`Artikel „Testartikel“ wurde angelegt.`)).toBeVisible();
  await expect(page.getByTestId("detail-stock")).toHaveText("0");

  // Incoming stock
  await page.getByRole("button", { name: "Buchen", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Buchungen" })).toHaveAttribute("aria-selected", "true");
  await page.getByLabel("Menge").fill("10");
  await page.getByLabel("Grund (optional)").fill("E2E Wareneingang");
  await page.getByRole("button", { name: "Buchung speichern" }).click();
  await expect(page.getByText("Zugang von 10 Einheiten gebucht.")).toBeVisible();
  await expect(page.getByTestId("current-stock")).toHaveText("10");
  const history = page.getByRole("table", { name: "Buchungshistorie" });
  await expect(history.getByRole("row", { name: /E2E Wareneingang/ })).toContainText("+10");

  // Outgoing stock larger than available: rejected, stock unchanged
  await page.getByText("Abgang (Entnahme)").click();
  await page.getByLabel("Menge").fill("50");
  await page.getByRole("button", { name: "Buchung speichern" }).click();
  await expect(page.getByRole("alert")).toHaveText("Nicht genügend Bestand: angefordert 50, verfügbar 10.");
  await expect(page.getByTestId("current-stock")).toHaveText("10");

  // Valid outgoing stock
  await page.getByLabel("Menge").fill("3");
  await page.getByRole("button", { name: "Buchung speichern" }).click();
  await expect(page.getByText("Abgang von 3 Einheiten gebucht.")).toBeVisible();
  await expect(page.getByTestId("current-stock")).toHaveText("7");
  await expect(history.getByRole("row")).toHaveCount(3); // header + 2 movements
  await expect(history.getByRole("row").nth(1)).toContainText("−3");

  // Edit (no stock field in the form)
  await openTab(page, "Artikel");
  await page.getByLabel("Artikel suchen").fill(sku);
  await page.getByRole("table", { name: "Artikelliste" }).getByRole("button", { name: "Testartikel" }).click();
  await expect(page.getByTestId("detail-stock")).toHaveText("7");
  await page.getByRole("button", { name: "Bearbeiten" }).click();
  const editDialog = page.getByRole("dialog", { name: "Artikel bearbeiten" });
  await expect(editDialog.getByLabel("Bestand", { exact: true })).toHaveCount(0);
  await editDialog.getByLabel("Bezeichnung").fill("Testartikel geändert");
  await editDialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText(`Artikel „Testartikel geändert“ wurde gespeichert.`)).toBeVisible();

  // Deactivate
  await page.getByRole("button", { name: "Deaktivieren" }).click();
  await page.getByRole("button", { name: "Wirklich deaktivieren" }).click();
  await expect(page.getByText(`Artikel „Testartikel geändert“ wurde deaktiviert.`)).toBeVisible();
  await expect(page.getByText("Keine Artikel gefunden.")).toBeVisible();
  await page.getByLabel("Inaktive anzeigen").check();
  await expect(page.getByRole("table", { name: "Artikelliste" }).getByText("Inaktiv")).toBeVisible();

  // The movement history of the deactivated product stays available
  await page.getByRole("table", { name: "Artikelliste" }).getByRole("button", { name: "Testartikel geändert" }).click();
  await expect(page.getByTestId("detail-stock")).toHaveText("7");
  await expect(history.getByRole("row")).toHaveCount(3);
  await expect(history.getByRole("row", { name: /E2E Wareneingang/ })).toContainText("+10");
});

test("stock overview lists levels and filters low stock", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "Bestand");

  const table = page.getByRole("table", { name: "Bestandsliste" });
  await expect(table.getByText("Kein Bestand").first()).toBeVisible();
  const allRows = await table.getByRole("row").count();

  await page.getByLabel("Nur unter Mindestbestand").check();
  await expect(table.getByText("Ausreichend")).toHaveCount(0);
  expect(await table.getByRole("row").count()).toBeLessThan(allRows);
});

test.describe("mobile viewport", () => {
  const { viewport, deviceScaleFactor, isMobile, hasTouch, userAgent } = devices["Pixel 7"];
  test.use({ viewport, deviceScaleFactor, isMobile, hasTouch, userAgent });

  test("all tabs render without horizontal scrolling", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("kpi-Aktive Artikel")).not.toHaveText("–");
    for (const name of ["Übersicht", "Artikel", "Buchungen", "Bestand"]) {
      await openTab(page, name);
      await expect(page.getByRole("tab", { name })).toHaveAttribute("aria-selected", "true");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `horizontal overflow on ${name}`).toBeLessThanOrEqual(0);
    }
  });
});
