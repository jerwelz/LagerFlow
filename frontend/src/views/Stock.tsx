import { useState } from "react";
import { api } from "../api";
import { Button, Card, cx, EmptyState, ErrorAlert, formatNumber, Spinner, StockBadge, td, th } from "../ui";
import { useAsync } from "../useAsync";

export default function Stock({ version, onBook }: { version: number; onBook: (productId: number) => void }) {
  const [onlyLow, setOnlyLow] = useState(false);
  const levels = useAsync(() => api.levels(), [version]);
  const rows = levels.data?.filter((level) => !onlyLow || level.is_low) ?? [];

  return (
    <Card
      title="Bestandsübersicht (aktive Artikel)"
      actions={
        <label className="flex items-center gap-2 text-sm font-normal text-slate-600">
          <input
            type="checkbox"
            checked={onlyLow}
            onChange={(event) => setOnlyLow(event.target.checked)}
            className="size-4 rounded border-slate-300 accent-teal-700"
          />
          Nur unter Mindestbestand
        </label>
      }
    >
      {levels.error ? (
        <div className="p-4"><ErrorAlert error={levels.error} onRetry={levels.reload} /></div>
      ) : !levels.data ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState>{onlyLow ? "Kein Artikel liegt unter dem Mindestbestand." : "Keine aktiven Artikel."}</EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200" aria-label="Bestandsliste">
            <thead className="bg-slate-50">
              <tr>
                <th className={th}>Artikelnr.</th>
                <th className={th}>Bezeichnung</th>
                <th className={`${th} text-right`}>Bestand</th>
                <th className={`${th} text-right`}>Minimum</th>
                <th className={`${th} hidden sm:table-cell`}>Füllstand</th>
                <th className={th}>Status</th>
                <th className={th}><span className="sr-only">Aktion</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((level) => (
                <tr key={level.id} className={cx(level.is_low && "bg-amber-50/40")}>
                  <td className={`${td} font-mono text-xs whitespace-nowrap`}>{level.sku}</td>
                  <td className={`${td} font-medium`}>{level.name}</td>
                  <td className={`${td} text-right tabular-nums`}>{formatNumber(level.current_stock)}</td>
                  <td className={`${td} text-right text-slate-500 tabular-nums`}>{formatNumber(level.min_stock)}</td>
                  <td className={`${td} hidden w-40 sm:table-cell`}>
                    <FillBar stock={level.current_stock} min={level.min_stock} />
                  </td>
                  <td className={td}><StockBadge stock={level.current_stock} min={level.min_stock} /></td>
                  <td className={`${td} text-right`}>
                    <Button onClick={() => onBook(level.id)}>Buchen</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/** Stock relative to twice the minimum, so the minimum sits in the middle of the bar. */
function FillBar({ stock, min }: { stock: number; min: number }) {
  const scale = Math.max(min * 2, stock, 1);
  const percent = Math.round((stock / scale) * 100);
  const color = stock === 0 ? "bg-red-500" : stock < min ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="relative h-2 rounded-full bg-slate-100" aria-hidden="true">
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${percent}%` }} />
      {min > 0 && <div className="absolute top-[-2px] h-3 w-px bg-slate-400" style={{ left: `${(min / scale) * 100}%` }} />}
    </div>
  );
}
