import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Product, ProductInput } from "../types";
import {
  Button,
  Card,
  cx,
  EmptyState,
  ErrorAlert,
  Field,
  formatDateTime,
  formatNumber,
  inputClass,
  Modal,
  Pagination,
  Spinner,
  StockBadge,
  SuccessAlert,
  td,
  th,
} from "../ui";
import { useAsync, useDebounced } from "../useAsync";
import MovementHistory from "./MovementHistory";

const PAGE_SIZE = 20;

interface Props {
  version: number;
  onChanged: () => void;
  onBook: (productId: number) => void;
}

export default function Products({ version, onChanged, onBook }: Props) {
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const debouncedSearch = useDebounced(search);

  const list = useAsync(
    () => api.listProducts({ search: debouncedSearch, includeInactive, limit: PAGE_SIZE, offset }),
    [debouncedSearch, includeInactive, offset, version],
  );

  const saved = (product: Product, created: boolean) => {
    setEditing(null);
    setSelectedId(product.id);
    setNotice(created ? `Artikel „${product.name}“ wurde angelegt.` : `Artikel „${product.name}“ wurde gespeichert.`);
    onChanged();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-5 lg:items-start">
      <Card
        title="Artikel"
        className="lg:col-span-3"
        actions={<Button variant="primary" onClick={() => setEditing("new")}>Neuer Artikel</Button>}
      >
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-3">
          <input
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            placeholder="Suche nach Artikelnummer oder Bezeichnung"
            aria-label="Artikel suchen"
            maxLength={100}
            className={cx(inputClass, "max-w-sm flex-1")}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => {
                setIncludeInactive(event.target.checked);
                setOffset(0);
              }}
              className="size-4 rounded border-slate-300 accent-teal-700"
            />
            Inaktive anzeigen
          </label>
        </div>
        {notice && <div className="px-4 pt-3"><SuccessAlert>{notice}</SuccessAlert></div>}
        {list.error ? (
          <div className="p-4"><ErrorAlert error={list.error} onRetry={list.reload} /></div>
        ) : !list.data ? (
          <Spinner />
        ) : list.data.items.length === 0 ? (
          <EmptyState>Keine Artikel gefunden.</EmptyState>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200" aria-label="Artikelliste">
                <thead className="bg-slate-50">
                  <tr>
                    <th className={th}>Artikelnr.</th>
                    <th className={th}>Bezeichnung</th>
                    <th className={`${th} text-right`}>Bestand</th>
                    <th className={th}>Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {list.data.items.map((product) => (
                    <tr
                      key={product.id}
                      onClick={() => setSelectedId(product.id)}
                      className={cx(
                        "cursor-pointer hover:bg-slate-50",
                        selectedId === product.id && "bg-teal-50/60 hover:bg-teal-50",
                        !product.is_active && "text-slate-400",
                      )}
                    >
                      <td className={`${td} font-mono text-xs whitespace-nowrap`}>{product.sku}</td>
                      <td className={td}>
                        <button
                          type="button"
                          className="text-left font-medium hover:text-teal-700"
                          onClick={() => setSelectedId(product.id)}
                        >
                          {product.name}
                        </button>
                      </td>
                      <td className={`${td} text-right whitespace-nowrap tabular-nums`}>
                        {formatNumber(product.current_stock)}
                        <span className="text-slate-400"> / {formatNumber(product.min_stock)}</span>
                      </td>
                      <td className={td}>
                        <StockBadge stock={product.current_stock} min={product.min_stock} active={product.is_active} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination total={list.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>

      <div className="min-w-0 lg:col-span-2">
        {selectedId === null ? (
          <Card title="Details">
            <EmptyState>Artikel in der Liste auswählen, um Details und Buchungen zu sehen.</EmptyState>
          </Card>
        ) : (
          <ProductDetail
            productId={selectedId}
            version={version}
            onEdit={setEditing}
            onBook={onBook}
            onDeactivated={(product) => {
              setNotice(`Artikel „${product.name}“ wurde deaktiviert.`);
              onChanged();
            }}
          />
        )}
      </div>

      {editing && (
        <ProductForm
          product={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}

function ProductDetail({ productId, version, onEdit, onBook, onDeactivated }: {
  productId: number;
  version: number;
  onEdit: (product: Product) => void;
  onBook: (productId: number) => void;
  onDeactivated: (product: Product) => void;
}) {
  const product = useAsync(() => api.getProduct(productId), [productId, version]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const deactivate = async (current: Product) => {
    setBusy(true);
    setError(null);
    try {
      onDeactivated(await api.deactivateProduct(current.id));
      setConfirming(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (product.error) return <Card title="Details"><div className="p-4"><ErrorAlert error={product.error} onRetry={product.reload} /></div></Card>;
  if (!product.data) return <Card title="Details"><Spinner /></Card>;
  const p = product.data;

  return (
    <div className="space-y-6">
      <Card title="Details">
        <div className="space-y-4 p-4">
          <div>
            <p className="font-mono text-xs text-slate-500">{p.sku}</p>
            <h3 className="text-lg font-semibold text-slate-900">{p.name}</h3>
            {p.description && <p className="mt-1 text-sm text-slate-600">{p.description}</p>}
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-slate-500">Bestand</dt>
              <dd className="text-xl font-semibold tabular-nums" data-testid="detail-stock">{formatNumber(p.current_stock)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Mindestbestand</dt>
              <dd className="text-xl font-semibold tabular-nums">{formatNumber(p.min_stock)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Status</dt>
              <dd className="mt-0.5"><StockBadge stock={p.current_stock} min={p.min_stock} active={p.is_active} /></dd>
            </div>
            <div>
              <dt className="text-slate-500">Angelegt</dt>
              <dd className="mt-0.5 text-slate-700">{formatDateTime(p.created_at)}</dd>
            </div>
          </dl>
          <ErrorAlert error={error} />
          {p.is_active && (
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => onBook(p.id)}>Buchen</Button>
              <Button onClick={() => onEdit(p)}>Bearbeiten</Button>
              {confirming ? (
                <>
                  <Button variant="danger" disabled={busy} onClick={() => deactivate(p)}>Wirklich deaktivieren</Button>
                  <Button onClick={() => setConfirming(false)}>Abbrechen</Button>
                </>
              ) : (
                <Button variant="danger" onClick={() => setConfirming(true)}>Deaktivieren</Button>
              )}
            </div>
          )}
          {!p.is_active && (
            <p className="text-sm text-slate-500">Deaktivierte Artikel bleiben mit ihrer Historie erhalten, können aber nicht mehr gebucht werden.</p>
          )}
        </div>
      </Card>
      <Card title="Buchungshistorie">
        <MovementHistory productId={p.id} version={version} />
      </Card>
    </div>
  );
}

function ProductForm({ product, onClose, onSaved }: {
  product: Product | null;
  onClose: () => void;
  onSaved: (product: Product, created: boolean) => void;
}) {
  const [values, setValues] = useState({
    sku: product?.sku ?? "",
    name: product?.name ?? "",
    description: product?.description ?? "",
    min_stock: String(product?.min_stock ?? 0),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const set = (field: keyof typeof values) => (event: { target: { value: string } }) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    // Stock is deliberately not part of this form: it only changes through movements.
    const data: ProductInput = {
      sku: values.sku,
      name: values.name,
      description: values.description.trim() || null,
      min_stock: Number(values.min_stock),
    };
    try {
      const result = product ? await api.updateProduct(product.id, data) : await api.createProduct(data);
      onSaved(result, !product);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  };

  return (
    <Modal title={product ? "Artikel bearbeiten" : "Neuer Artikel"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Artikelnummer (SKU)" hint="Buchstaben, Ziffern, Punkt, Binde- und Unterstrich; wird in Großbuchstaben gespeichert.">
          <input className={inputClass} value={values.sku} onChange={set("sku")} required maxLength={50} />
        </Field>
        <Field label="Bezeichnung">
          <input className={inputClass} value={values.name} onChange={set("name")} required maxLength={200} />
        </Field>
        <Field label="Beschreibung (optional)">
          <textarea className={inputClass} rows={3} value={values.description} onChange={set("description")} maxLength={2000} />
        </Field>
        <Field label="Mindestbestand">
          <input className={inputClass} type="number" min={0} step={1} value={values.min_stock} onChange={set("min_stock")} required />
        </Field>
        {!product && (
          <p className="text-xs text-slate-500">Neue Artikel starten mit Bestand 0. Bestand entsteht nur durch Buchungen.</p>
        )}
        <ErrorAlert error={error} />
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>Abbrechen</Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {product ? "Speichern" : "Anlegen"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
