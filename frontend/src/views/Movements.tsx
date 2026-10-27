import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { MovementType } from "../types";
import { Button, Card, cx, EmptyState, ErrorAlert, Field, formatNumber, inputClass, Spinner, StockBadge, SuccessAlert } from "../ui";
import { useAsync } from "../useAsync";
import MovementHistory from "./MovementHistory";

interface Props {
  version: number;
  onChanged: () => void;
  productId: number | null;
  onSelectProduct: (productId: number | null) => void;
}

export default function Movements({ version, onChanged, productId, onSelectProduct }: Props) {
  // Only active products can receive movements.
  const products = useAsync(() => api.listProducts({ limit: 100 }), [version]);
  const selected = products.data?.items.find((product) => product.id === productId) ?? null;

  return (
    <div className="grid gap-6 lg:grid-cols-5 lg:items-start">
      <Card title="Buchung erfassen" className="lg:col-span-2">
        {products.error ? (
          <div className="p-4"><ErrorAlert error={products.error} onRetry={products.reload} /></div>
        ) : !products.data ? (
          <Spinner />
        ) : (
          <div className="space-y-4 p-4">
            <Field label="Artikel">
              <select
                className={inputClass}
                value={selected?.id ?? ""}
                onChange={(event) => onSelectProduct(event.target.value ? Number(event.target.value) : null)}
              >
                <option value="">Bitte auswählen …</option>
                {products.data.items.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.sku} – {product.name}
                  </option>
                ))}
              </select>
            </Field>
            {selected && (
              <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm">
                <span>
                  Aktueller Bestand: <strong className="tabular-nums" data-testid="current-stock">{formatNumber(selected.current_stock)}</strong>
                  <span className="text-slate-500"> (Minimum {formatNumber(selected.min_stock)})</span>
                </span>
                <StockBadge stock={selected.current_stock} min={selected.min_stock} />
              </div>
            )}
            {selected ? (
              <MovementForm key={selected.id} productId={selected.id} onBooked={onChanged} />
            ) : (
              <p className="text-sm text-slate-500">Wählen Sie einen Artikel, um einen Zugang oder Abgang zu buchen.</p>
            )}
          </div>
        )}
      </Card>

      <Card title={selected ? `Buchungshistorie: ${selected.name}` : "Buchungshistorie"} className="lg:col-span-3">
        {selected ? (
          <MovementHistory productId={selected.id} version={version} />
        ) : (
          <EmptyState>Kein Artikel ausgewählt.</EmptyState>
        )}
      </Card>
    </div>
  );
}

export function MovementForm({ productId, onBooked }: { productId: number; onBooked: () => void }) {
  const [type, setType] = useState<MovementType>("IN");
  const [quantity, setQuantity] = useState("1");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const movement = await api.recordMovement(productId, {
        movement_type: type,
        quantity: Number(quantity),
        reason: reason.trim() || null,
      });
      setSuccess(
        `${movement.movement_type === "IN" ? "Zugang" : "Abgang"} von ${formatNumber(movement.quantity)} Einheiten gebucht.`,
      );
      setReason("");
      onBooked();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Buchungsart</legend>
        <div className="grid grid-cols-2 gap-2">
          {(["IN", "OUT"] as const).map((value) => (
            <label
              key={value}
              className={cx(
                "flex cursor-pointer items-center justify-center rounded-md border px-3 py-2 text-sm font-medium",
                type === value ? "border-teal-700 bg-teal-50 text-teal-800" : "border-slate-300 text-slate-600 hover:bg-slate-50",
              )}
            >
              <input
                type="radio"
                name="movement_type"
                value={value}
                checked={type === value}
                onChange={() => setType(value)}
                className="sr-only"
              />
              {value === "IN" ? "Zugang (Wareneingang)" : "Abgang (Entnahme)"}
            </label>
          ))}
        </div>
      </fieldset>
      <Field label="Menge">
        <input
          className={inputClass}
          type="number"
          min={1}
          max={1000000}
          step={1}
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          required
        />
      </Field>
      <Field label="Grund (optional)">
        <input
          className={inputClass}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={255}
          placeholder="z. B. Lieferung 4711, Kundenauftrag"
        />
      </Field>
      <ErrorAlert error={error} />
      {success && <SuccessAlert>{success}</SuccessAlert>}
      <Button type="submit" variant="primary" disabled={busy} className="w-full">
        Buchung speichern
      </Button>
    </form>
  );
}
