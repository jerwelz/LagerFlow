import type {
  DemoInfo,
  InventorySummary,
  Movement,
  MovementType,
  Page,
  Product,
  ProductInput,
  StockLevel,
} from "./types";

/** An error response from the API, in its standard {"error": {code, message, details}} format. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Network error");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `HTTP ${response.status}`,
      error?.details ?? null,
    );
  }
  return response.json() as Promise<T>;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export interface ProductQuery {
  search?: string;
  limit?: number;
  offset?: number;
  includeInactive?: boolean;
}

export interface MovementInput {
  movement_type: MovementType;
  quantity: number;
  reason: string | null;
}

export const api = {
  listProducts: ({ search, limit, offset, includeInactive }: ProductQuery) =>
    request<Page<Product>>(
      `/products${query({
        search: search?.trim(),
        limit,
        offset,
        include_inactive: includeInactive || undefined,
      })}`,
    ),
  getProduct: (id: number) => request<Product>(`/products/${id}`),
  createProduct: (data: ProductInput) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(data) }),
  updateProduct: (id: number, data: Partial<ProductInput>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deactivateProduct: (id: number) =>
    request<Product>(`/products/${id}/deactivate`, { method: "POST" }),
  recordMovement: (id: number, data: MovementInput) =>
    request<Movement>(`/products/${id}/movements`, { method: "POST", body: JSON.stringify(data) }),
  listMovements: (id: number, params: { limit?: number; offset?: number } = {}) =>
    request<Page<Movement>>(`/products/${id}/movements${query(params)}`),
  summary: () => request<InventorySummary>("/inventory/summary"),
  levels: () => request<StockLevel[]>("/inventory/levels"),
  lowStock: () => request<StockLevel[]>("/inventory/low-stock"),
  demoInfo: () => request<DemoInfo>("/demo/info"),
};

const FIELD_NAMES: Record<string, string> = {
  sku: "Artikelnummer",
  name: "Bezeichnung",
  description: "Beschreibung",
  min_stock: "Mindestbestand",
  quantity: "Menge",
  reason: "Grund",
  movement_type: "Buchungsart",
};

/** Turns any error into a German message for the user. */
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Unerwarteter Fehler. Bitte erneut versuchen.";
  const details = (error.details ?? {}) as Record<string, unknown>;
  switch (error.code) {
    case "INSUFFICIENT_STOCK":
      return `Nicht genügend Bestand: angefordert ${details.requested}, verfügbar ${details.available}.`;
    case "PRODUCT_INACTIVE":
      return "Der Artikel ist deaktiviert und kann nicht mehr gebucht werden.";
    case "DUPLICATE_SKU":
      return "Diese Artikelnummer ist bereits vergeben.";
    case "PRODUCT_NOT_FOUND":
      return "Der Artikel wurde nicht gefunden.";
    case "RATE_LIMITED":
      return "Zu viele Änderungen in kurzer Zeit. Bitte einen Moment warten.";
    case "DEMO_LIMIT_REACHED":
      return "Das Limit der Demo ist erreicht. Die Daten werden regelmäßig zurückgesetzt.";
    case "NETWORK_ERROR":
      return "Der Server ist nicht erreichbar. Bitte später erneut versuchen.";
    case "VALIDATION_ERROR": {
      const items = Array.isArray(error.details) ? (error.details as { loc?: unknown[] }[]) : [];
      const fields = items
        .map((item) => String(item.loc?.at(-1) ?? ""))
        .filter(Boolean)
        .map((field) => FIELD_NAMES[field] ?? field);
      const unique = [...new Set(fields)];
      return unique.length ? `Ungültige Eingabe: ${unique.join(", ")}.` : "Ungültige Eingabe.";
    }
    default:
      return error.status ? `Fehler ${error.status}: ${error.message}` : error.message;
  }
}
