import { useState } from "react";
import { api } from "../api";
import { EmptyState, ErrorAlert, formatDateTime, formatNumber, MovementBadge, Pagination, Spinner, td, th } from "../ui";
import { useAsync } from "../useAsync";

const PAGE_SIZE = 10;

/** Paginated movement history of one product (GET /products/{id}/movements). */
export default function MovementHistory({ productId, version }: { productId: number; version: number }) {
  const [offset, setOffset] = useState(0);
  const [prevProduct, setPrevProduct] = useState(productId);
  if (prevProduct !== productId) {
    setPrevProduct(productId);
    setOffset(0);
  }
  const history = useAsync(
    () => api.listMovements(productId, { limit: PAGE_SIZE, offset }),
    [productId, offset, version],
  );

  if (history.error) return <div className="p-4"><ErrorAlert error={history.error} onRetry={history.reload} /></div>;
  if (!history.data) return <Spinner />;
  if (history.data.total === 0) return <EmptyState>Noch keine Buchungen für diesen Artikel.</EmptyState>;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200" aria-label="Buchungshistorie">
          <thead className="bg-slate-50">
            <tr>
              <th className={th}>Datum</th>
              <th className={th}>Art</th>
              <th className={`${th} text-right`}>Menge</th>
              <th className={th}>Grund</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {history.data.items.map((movement) => (
              <tr key={movement.id}>
                <td className={`${td} whitespace-nowrap text-slate-600`}>{formatDateTime(movement.created_at)}</td>
                <td className={td}><MovementBadge type={movement.movement_type} /></td>
                <td className={`${td} text-right font-medium tabular-nums`}>
                  {movement.movement_type === "IN" ? "+" : "−"}
                  {formatNumber(movement.quantity)}
                </td>
                <td className={`${td} text-slate-600`}>{movement.reason ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination total={history.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
    </>
  );
}
