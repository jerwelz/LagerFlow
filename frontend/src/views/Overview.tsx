import { api } from "../api";
import type { Tab } from "../App";
import type { Movement, Product } from "../types";
import { Button, Card, EmptyState, ErrorAlert, formatDateTime, formatNumber, MovementBadge, Spinner, StockBadge } from "../ui";
import { useAsync } from "../useAsync";

const RECENT_COUNT = 8;

/**
 * Recent activity across all products. The API has no global movement list, so this
 * reads the newest movements of each active product and merges them.
 */
async function loadRecentActivity(): Promise<{ movement: Movement; product: Product }[]> {
  const products = await api.listProducts({ limit: 100 });
  const histories = await Promise.all(
    products.items.map(async (product) => {
      const page = await api.listMovements(product.id, { limit: 5 });
      return page.items.map((movement) => ({ movement, product }));
    }),
  );
  return histories
    .flat()
    .sort((a, b) => b.movement.created_at.localeCompare(a.movement.created_at) || b.movement.id - a.movement.id)
    .slice(0, RECENT_COUNT);
}

export default function Overview({ version, onNavigate }: { version: number; onNavigate: (tab: Tab) => void }) {
  const summary = useAsync(() => api.summary(), [version]);
  const lowStock = useAsync(() => api.lowStock(), [version]);
  const recent = useAsync(loadRecentActivity, [version]);

  return (
    <div className="space-y-6">
      <section aria-label="Kennzahlen">
        <ErrorAlert error={summary.error} onRetry={summary.reload} />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Kpi label="Aktive Artikel" value={summary.data?.active_products} />
          <Kpi label="Gesamtbestand (Einheiten)" value={summary.data?.total_units} />
          <Kpi label="Unter Mindestbestand" value={summary.data?.low_stock_products} tone="amber" />
          <Kpi label="Ohne Bestand" value={summary.data?.out_of_stock_products} tone="red" />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-5 lg:items-start">
        <Card
          title="Letzte Buchungen"
          className="lg:col-span-3"
          actions={<Button onClick={() => onNavigate("movements")}>Neue Buchung</Button>}
        >
          {recent.error ? (
            <div className="p-4"><ErrorAlert error={recent.error} onRetry={recent.reload} /></div>
          ) : !recent.data ? (
            <Spinner />
          ) : recent.data.length === 0 ? (
            <EmptyState>Noch keine Buchungen vorhanden.</EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {recent.data.map(({ movement, product }) => (
                <li key={movement.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <MovementBadge type={movement.movement_type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-800">{product.name}</p>
                    <p className="truncate text-xs text-slate-500">
                      {formatDateTime(movement.created_at)}
                      {movement.reason && ` · ${movement.reason}`}
                    </p>
                  </div>
                  <span className="font-medium whitespace-nowrap tabular-nums">
                    {movement.movement_type === "IN" ? "+" : "−"}
                    {formatNumber(movement.quantity)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Nachbestellen"
          className="lg:col-span-2"
          actions={<Button onClick={() => onNavigate("stock")}>Bestand ansehen</Button>}
        >
          {lowStock.error ? (
            <div className="p-4"><ErrorAlert error={lowStock.error} onRetry={lowStock.reload} /></div>
          ) : !lowStock.data ? (
            <Spinner />
          ) : lowStock.data.length === 0 ? (
            <EmptyState>Alle Artikel haben ausreichend Bestand.</EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {lowStock.data.map((item) => (
                <li key={item.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-800">{item.name}</p>
                    <p className="text-xs text-slate-500">
                      {item.sku} · Bestand {formatNumber(item.current_stock)} / Minimum {formatNumber(item.min_stock)}
                    </p>
                  </div>
                  <StockBadge stock={item.current_stock} min={item.min_stock} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: number | undefined; tone?: "amber" | "red" }) {
  const highlight = value ? (tone === "amber" ? "text-amber-700" : tone === "red" ? "text-red-700" : "") : "";
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-xs">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${highlight}`} data-testid={`kpi-${label}`}>
        {value === undefined ? "–" : formatNumber(value)}
      </p>
    </div>
  );
}
