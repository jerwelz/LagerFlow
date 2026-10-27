import { useCallback, useState } from "react";
import { api } from "./api";
import { cx, formatDateTime } from "./ui";
import { useAsync } from "./useAsync";
import Movements from "./views/Movements";
import Overview from "./views/Overview";
import Products from "./views/Products";
import Stock from "./views/Stock";

const REPO_URL = "https://github.com/jerwelz/LagerFlow";

const TABS = [
  { id: "overview", label: "Übersicht" },
  { id: "products", label: "Artikel" },
  { id: "movements", label: "Buchungen" },
  { id: "stock", label: "Bestand" },
] as const;
export type Tab = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  // Incremented after every change, so all views reload their data.
  const [version, setVersion] = useState(0);
  const [movementProductId, setMovementProductId] = useState<number | null>(null);
  const demo = useAsync(() => api.demoInfo(), [version]);

  const changed = useCallback(() => setVersion((value) => value + 1), []);
  const openMovements = useCallback((productId: number) => {
    setMovementProductId(productId);
    setTab("movements");
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <h1 className="text-base leading-tight font-semibold">LagerFlow</h1>
              <p className="text-xs text-slate-500">Lagerverwaltung · REST-API-Demo</p>
            </div>
            {demo.data?.demo_mode && (
              <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200 ring-inset">
                Demo-Modus
              </span>
            )}
          </div>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" aria-label="Links">
            <a className="text-slate-600 hover:text-teal-700" href="/docs" target="_blank" rel="noreferrer">
              API-Dokumentation
            </a>
            <a className="text-slate-600 hover:text-teal-700" href="/reports/inventory.csv" download>
              CSV-Export
            </a>
            <a className="text-slate-600 hover:text-teal-700" href={REPO_URL} target="_blank" rel="noreferrer">
              GitHub
            </a>
          </nav>
        </div>
      </header>

      {demo.data?.demo_mode && (
        <div className="border-b border-amber-200 bg-amber-50 text-sm text-amber-900">
          <p className="mx-auto max-w-6xl px-4 py-2">
            Öffentliche Demo mit <strong>fiktiven Daten</strong>. Änderungen sind für alle Besucher sichtbar
            und werden regelmäßig zurückgesetzt (nächste Zurücksetzung: {formatDateTime(demo.data.next_reset_at)}).
          </p>
        </div>
      )}

      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-6 overflow-x-auto border-b border-slate-200">
          <div role="tablist" aria-label="Bereiche" className="flex gap-1">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                onClick={() => setTab(item.id)}
                className={cx(
                  "-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap",
                  tab === item.id
                    ? "border-teal-700 text-teal-800"
                    : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <main>
          {tab === "overview" && <Overview version={version} onNavigate={setTab} />}
          {tab === "products" && <Products version={version} onChanged={changed} onBook={openMovements} />}
          {tab === "movements" && (
            <Movements
              version={version}
              onChanged={changed}
              productId={movementProductId}
              onSelectProduct={setMovementProductId}
            />
          )}
          {tab === "stock" && <Stock version={version} onBook={openMovements} />}
        </main>

        <footer className="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
          LagerFlow · Python, FastAPI, SQLAlchemy, SQLite · Oberfläche: React, TypeScript, Tailwind CSS ·{" "}
          <a className="underline underline-offset-2 hover:text-teal-700" href={REPO_URL} target="_blank" rel="noreferrer">
            Quellcode
          </a>
        </footer>
      </div>
    </div>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden="true">
      <rect width="32" height="32" rx="7" className="fill-teal-700" />
      <path d="M8 12l8-4 8 4v9l-8 4-8-4z" fill="none" stroke="white" strokeWidth="2" strokeLinejoin="round" />
      <path d="M8 12l8 4 8-4M16 16v9" fill="none" stroke="white" strokeWidth="2" />
    </svg>
  );
}
