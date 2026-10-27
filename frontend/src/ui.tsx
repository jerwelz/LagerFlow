// Small shared building blocks. Styling: light, neutral, thin borders.
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { errorMessage } from "./api";
import type { Movement } from "./types";

const number = new Intl.NumberFormat("de-DE");
const dateTime = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });

export const formatNumber = (value: number) => number.format(value);
export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function Card({ title, actions, children, className }: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("min-w-0 rounded-lg border border-slate-200 bg-white shadow-xs", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

type Tone = "neutral" | "green" | "amber" | "red" | "teal";
const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  teal: "bg-teal-50 text-teal-800 ring-teal-200",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        TONES[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Stock status: empty, below minimum, or fine. */
export function StockBadge({ stock, min, active = true }: { stock: number; min: number; active?: boolean }) {
  if (!active) return <Badge>Inaktiv</Badge>;
  if (stock === 0) return <Badge tone="red">Kein Bestand</Badge>;
  if (stock < min) return <Badge tone="amber">Unter Minimum</Badge>;
  return <Badge tone="green">Ausreichend</Badge>;
}

export function MovementBadge({ type }: { type: Movement["movement_type"] }) {
  return type === "IN" ? <Badge tone="teal">Zugang</Badge> : <Badge tone="neutral">Abgang</Badge>;
}

type Variant = "primary" | "secondary" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-teal-700 text-white hover:bg-teal-800 focus-visible:outline-teal-700",
  secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-slate-400",
  danger: "border border-red-200 bg-white text-red-700 hover:bg-red-50 focus-visible:outline-red-500",
};

export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className,
      )}
    />
  );
}

export const inputClass =
  "block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-xs placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 focus:outline-none";

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      <span>{errorMessage(error)}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2">
          Erneut versuchen
        </button>
      )}
    </div>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  return (
    <div role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
      {children}
    </div>
  );
}

export function Spinner({ label = "Wird geladen …" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-6 text-sm text-slate-500" role="status">
      <span className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-teal-700" />
      {label}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="px-4 py-8 text-center text-sm text-slate-500">{children}</p>;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-20 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:items-center">
      <div role="dialog" aria-modal="true" aria-label={title} className="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="font-semibold text-slate-900">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="rounded p-1 text-slate-500 hover:bg-slate-100">
            ✕
          </button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-4 py-2 text-sm text-slate-600">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} von {total}
      </span>
      <div className="flex gap-2">
        <Button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Zurück
        </Button>
        <Button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>
          Weiter
        </Button>
      </div>
    </div>
  );
}

export const th = "px-4 py-2 text-left text-xs font-medium tracking-wide text-slate-500 uppercase";
export const td = "px-4 py-2.5 text-sm";
