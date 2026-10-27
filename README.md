[Deutsch](README.md) | [English](README.en.md)

# LagerFlow

**[▶ Live-Demo](https://lagerflow-demo.onrender.com)** · [API-Dokumentation (Swagger UI)](https://lagerflow-demo.onrender.com/docs) · [Quellcode auf GitHub](https://github.com/jerwelz/LagerFlow)

> Die Demo arbeitet ausschließlich mit fiktiven Lagerdaten. Besucher können alles ausprobieren: Artikel anlegen, Bestände buchen, bearbeiten und deaktivieren. Änderungen sind nur vorübergehend und werden alle 60 Minuten sowie bei jedem Neustart zurückgesetzt. Die Demo läuft im kostenlosen Tarif von Render; nach längerer Inaktivität kann die erste Anfrage daher etwa eine Minute dauern, bis der Dienst wieder gestartet ist.

LagerFlow ist eine REST-API zur Lagerverwaltung eines kleinen Unternehmens. Sie verwaltet einen Artikelstamm, erfasst Warenein- und -ausgänge und führt eine vollständige Buchungshistorie. Außerdem zeigt sie, welche Artikel ihren Mindestbestand unterschritten haben, und exportiert den Lagerbestand als CSV.

Im Mittelpunkt steht ein kleines Backend, das korrekt, getestet und gut nachvollziehbar ist, statt eines großen Funktionsumfangs. Ein React-Dashboard (auf Deutsch) zeigt die API im Einsatz; die API lässt sich außerdem direkt über die interaktive FastAPI-Dokumentation unter `/docs` nutzen.

## Live-Demo

**Live-Demo:** https://lagerflow-demo.onrender.com – ein interaktives, deutschsprachiges Dashboard auf Basis der REST-API. Sie können Artikel suchen, anlegen und bearbeiten, Zu- und Abgänge buchen und dabei zusehen, wie sich die Bestandszahlen ändern. Die Swagger UI läuft auf demselben Server unter https://lagerflow-demo.onrender.com/docs, sodass sich jeder Endpunkt auch direkt ausprobieren lässt.

Die Demo verwendet **ausschließlich fiktive Daten**, wird von allen Besuchern gemeinsam genutzt und regelmäßig zurückgesetzt. Die Schutzmaßnahmen beschreibt der Abschnitt [Demo-Modus](#demo-modus), eine eigene Instanz lässt sich wie unter [Deployment](#deployment) beschrieben einrichten.

Das Dashboard hat vier Bereiche:

- **Übersicht:** Kennzahlen (aktive Artikel, Gesamtbestand, Artikel unter Mindestbestand und ohne Bestand), letzte Buchungen und eine Nachbestellliste
- **Artikel:** durchsuchbare Artikeltabelle, Detailansicht mit Buchungshistorie, Anlegen, Bearbeiten und Deaktivieren
- **Buchungen:** Zugänge (`IN`) und Abgänge (`OUT`) buchen; Fehler wie ein unzureichender Bestand werden verständlich angezeigt
- **Bestand:** Bestände im Vergleich zum Mindestbestand, mit Filter auf Artikel unter Mindestbestand

Links zur API-Dokumentation und zum CSV-Export befinden sich in der Kopfzeile. Das Dashboard nutzt ausschließlich die öffentliche REST-API; Bestandsänderungen laufen immer über den Buchungs-Endpunkt.

## Technologien

- Python 3.12
- FastAPI (HTTP-Schicht und OpenAPI-Dokumentation)
- SQLAlchemy 2.x ORM mit SQLite
- Alembic (Datenbankmigrationen)
- Pydantic v2 (Validierung von Anfragen und Antwortschemas)
- pytest und HTTPX über den `TestClient` von FastAPI
- Ruff (Linting und Formatierung)

Dashboard (`frontend/`):

- React 19 und TypeScript, gebaut mit Vite
- Tailwind CSS (keine Komponentenbibliothek, kein Router, keine State-Management-Bibliothek)
- Vitest und Testing Library (Unit-Tests), Playwright (End-to-End-Tests)

## Funktionen

- **Artikel:** anlegen, abrufen, auflisten mit Suche und Paginierung, teilweise aktualisieren, deaktivieren (Soft Delete)
- **Lagerbuchungen:** Zugänge (`IN`) und Abgänge (`OUT`) mit optionalem Grund erfassen
- **Buchungshistorie** je Artikel, neueste zuerst, paginiert
- **Bestandsüberwachung:** aktuelle Bestände, Artikel unter Mindestbestand, Gesamtkennzahlen
- **CSV-Export** des aktuellen Lagerbestands
- **Ein einheitliches Fehlerformat** für alle Fehlerantworten, auch in `/docs` dokumentiert

Regeln, die die API garantiert:

- Der Bestand ändert sich nur durch Lagerbuchungen. Die Artikel-Endpunkte lehnen `current_stock` mit 422 ab.
- Der Bestand kann nie negativ werden, auch nicht bei gleichzeitigen Anfragen (siehe [Datenintegrität](#datenintegrität)).
- Bestandsänderung und zugehörige Buchung werden in einer Transaktion gespeichert: entweder beide oder keine.
- SKUs (Artikelnummern) sind eindeutig. Sie werden von Leerzeichen bereinigt und in Großbuchstaben gespeichert, `abc-1` und `ABC-1` sind also dieselbe SKU.
- Artikel werden nie gelöscht, sondern nur deaktiviert. Ihre Buchungshistorie bleibt erhalten.
- Inaktive Artikel können keine Buchungen erhalten und erscheinen nicht in Listen, in der Bestandsüberwachung und im CSV-Export.

## Architektur

```
app/
├── main.py            FastAPI-App: Router, Fehlerbehandlung, liefert das gebaute Dashboard aus
├── config.py          Einstellungen (Datenbank-URL, Demo-Modus) aus Umgebungsvariablen
├── database.py        Engine, Session-Factory, get_db-Dependency, SQLite-Fremdschlüssel
├── models.py          SQLAlchemy-Modelle: Product, StockMovement
├── schemas.py         Pydantic-Modelle für Anfragen und Antworten
├── errors.py          Anwendungsfehler und das JSON-Fehlerformat
├── api/               HTTP-Schicht: Routen, Statuscodes, Parameter
├── services/          Geschäftsregeln und Transaktionssteuerung
├── repositories/      Ausschließlich Datenbankabfragen
├── demo.py            Fiktive Demodaten und das abgesicherte Zurücksetzen
└── demo_guard.py      Demo-Schutzmaßnahmen: Ratenbegrenzung, Obergrenzen, regelmäßiges Zurücksetzen
alembic/               Datenbankmigrationen
tests/                 pytest-Testsuite
frontend/              React-Dashboard (Vite-Projekt)
├── src/api.ts         Typisierter API-Client und deutsche Fehlermeldungen
├── src/views/         Übersicht, Artikel, Buchungen, Bestand
└── e2e/               Playwright-End-to-End-Tests
render.yaml            Deployment-Blueprint für Render
```

Wenn `frontend/dist` vorhanden ist, liefert FastAPI das gebaute Dashboard aus (`/` und `/assets`). Browser und API teilen sich einen Origin, daher ist keine CORS-Konfiguration nötig. Unbekannte Pfade liefern weiterhin das JSON-Fehlerformat.

Jede Anfrage durchläuft drei Schichten:

| Schicht | Aufgabe | Beispiel |
|---|---|---|
| `api/` | Anfrage auswerten, Service aufrufen, Antwort zurückgeben | `POST /products/{id}/movements` |
| `services/` | Geschäftsregeln anwenden, über den Commit entscheiden | „Ein `OUT` darf den Bestand nicht übersteigen“ |
| `repositories/` | SQL-Abfragen ausführen, nie committen | Das bedingte `UPDATE` des Bestands |

Nur Services rufen `commit()` auf, eine Service-Funktion entspricht also genau einer Transaktion. Services lösen Exceptions wie `NotFoundError` oder `ConflictError` aus. Zentrale Handler in `errors.py` wandeln sie in JSON-Antworten um, sodass Routen nie selbst Fehlerantworten erzeugen.

### Datenbankschema

```
products                                stock_movements
─────────────────────────────           ──────────────────────────────────
id             INTEGER PK               id             INTEGER PK
sku            VARCHAR(50) UNIQUE       product_id     INTEGER FK → products.id
name           VARCHAR(200)                            (ON DELETE RESTRICT)
description    TEXT NULL                movement_type  'IN' | 'OUT' (CHECK)
current_stock  INTEGER CHECK >= 0       quantity       INTEGER CHECK > 0
min_stock      INTEGER CHECK >= 0       reason         VARCHAR(255) NULL
is_active      BOOLEAN                  created_at     DATETIME (UTC)
created_at     DATETIME (UTC)
```

Indizes: ein Unique-Index auf `products.sku`, ein Index auf `products.name` und ein Index auf `stock_movements(product_id, created_at)` für die Buchungshistorie.

### Datenintegrität

Negative Bestände werden auf drei Ebenen verhindert:

1. **Prüfung im Service.** Der Service vergleicht die angeforderte Menge mit dem Bestand und liefert einen eindeutigen Fehler `409 INSUFFICIENT_STOCK`.
2. **Bedingtes UPDATE.** Der Bestand wird geändert mit
   `UPDATE products SET current_stock = current_stock + :delta WHERE id = :id AND is_active AND current_stock + :delta >= 0 RETURNING current_stock`.
   Die Datenbank prüft und ändert den Wert in einer einzigen Anweisung. Konkurrieren zwei Anfragen um die letzten Stücke, trifft nur ein UPDATE die Zeile. Die andere Anfrage erhält 409.
3. **Datenbank-Constraint.** `CHECK (current_stock >= 0)` ist das letzte Sicherheitsnetz.

Das UPDATE des Bestands und das Einfügen des `StockMovement` laufen in derselben Transaktion. Jeder Fehler macht beides rückgängig. Die Testsuite simuliert Fehler an beiden Stellen und startet 20 Threads, die gleichzeitig Ware entnehmen wollen.

## Installation

Voraussetzung: Python 3.12 oder neuer.

```bash
git clone https://github.com/jerwelz/LagerFlow.git lager-flow
cd lager-flow
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Das Extra `dev` installiert pytest, HTTPX und Ruff. Wer nur die Laufzeitabhängigkeiten der Anwendung braucht, verwendet `pip install -e .`.

### Konfiguration

| Umgebungsvariable | Standardwert | Zweck |
|---|---|---|
| `LAGERFLOW_DATABASE_URL` | `sqlite:///./lagerflow.db` | SQLAlchemy-Datenbank-URL |
| `LAGERFLOW_DEMO_MODE` | `false` | Aktiviert die Schutzmaßnahmen und Startdaten der öffentlichen Demo (siehe [Demo-Modus](#demo-modus)) |
| `LAGERFLOW_DEMO_RESET_MINUTES` | `60` | Nur Demo: Intervall des automatischen Zurücksetzens |
| `LAGERFLOW_DEMO_MAX_PRODUCTS` / `LAGERFLOW_DEMO_MAX_MOVEMENTS` | `60` / `2000` | Nur Demo: Obergrenzen |
| `LAGERFLOW_DEMO_WRITE_LIMIT_PER_MINUTE` / `LAGERFLOW_DEMO_GLOBAL_WRITE_LIMIT_PER_MINUTE` | `20` / `120` | Nur Demo: schreibende Anfragen pro Client / insgesamt |

Die Variablen lassen sich auch in einer Datei `.env` im Projektverzeichnis setzen. Git ignoriert diese Datei.

## Datenbankmigrationen

Datenbankschema anlegen oder aktualisieren:

```bash
alembic upgrade head
```

Nach einer Modelländerung eine neue Migration erzeugen und vor dem Anwenden prüfen:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Die Testsuite prüft, dass Migrationen und Modelle dasselbe Schema beschreiben.

## Anwendung starten

```bash
uvicorn app.main:app --reload
```

- Interaktive Dokumentation: http://127.0.0.1:8000/docs
- OpenAPI-Schema: http://127.0.0.1:8000/openapi.json

### Dashboard

Voraussetzung: Node.js 20.19 oder neuer, bis einschließlich Version 24.

```bash
cd frontend
npm ci
npm run dev       # http://localhost:5173, leitet API-Anfragen an uvicorn auf Port 8000 weiter
```

`uvicorn` läuft dabei in einem zweiten Terminal weiter. Alternativ einmal mit `npm run build` bauen; uvicorn liefert das Dashboard dann selbst unter http://127.0.0.1:8000/ aus.

Lokal arbeitet das Dashboard mit der normalen `lagerflow.db`. Um es stattdessen mit den Demodaten auszuprobieren, eine separate Datenbankdatei verwenden, deren Name `demo` enthält:

```bash
# Linux / macOS (Windows PowerShell: $env:LAGERFLOW_DEMO_MODE="true"; ...)
export LAGERFLOW_DEMO_MODE=true LAGERFLOW_DATABASE_URL=sqlite:///./lagerflow-demo.db
alembic upgrade head
uvicorn app.main:app
```

## API-Endpunkte

| Methode | Pfad | Beschreibung | Erfolg | Fehler |
|---|---|---|---|---|
| GET | `/health` | Verfügbarkeitsprüfung | 200 | – |
| POST | `/products` | Artikel anlegen (Bestand beginnt bei 0) | 201 | 409, 422 |
| GET | `/products` | Artikel auflisten. Query: `search`, `limit` (1–100, Standard 20), `offset`, `include_inactive` | 200 | 422 |
| GET | `/products/{id}` | Einzelnen Artikel abrufen (auch inaktive) | 200 | 404, 422 |
| PATCH | `/products/{id}` | `sku`, `name`, `description`, `min_stock` ändern | 200 | 404, 409, 422 |
| POST | `/products/{id}/deactivate` | Artikel deaktivieren (idempotent) | 200 | 404, 422 |
| POST | `/products/{id}/movements` | Buchung `IN` oder `OUT` erfassen | 201 | 404, 409, 422 |
| GET | `/products/{id}/movements` | Buchungshistorie, neueste zuerst. Query: `limit`, `offset` | 200 | 404, 422 |
| GET | `/inventory/levels` | Bestand aller aktiven Artikel mit Kennzeichen `is_low` | 200 | – |
| GET | `/inventory/low-stock` | Aktive Artikel mit `current_stock < min_stock` | 200 | – |
| GET | `/inventory/summary` | Kennzahlen über alle aktiven Artikel | 200 | – |
| GET | `/reports/inventory.csv` | CSV-Download aller aktiven Artikel | 200 | – |

Paginierte Endpunkte liefern `{"items": [...], "total": n, "limit": n, "offset": n}`. `total` zählt alle passenden Einträge, nicht nur die der aktuellen Seite.

### Fehlerformat

Alle Fehlerantworten haben dieselbe Struktur:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Insufficient stock: requested 15, available 10.", "details": { "requested": 15, "available": 10 } } }
```

| Status | Code | Bedeutung |
|---|---|---|
| 400 | `HTTP_ERROR` | Anfragekörper konnte nicht dekodiert werden (z. B. kein UTF-8) |
| 404 | `PRODUCT_NOT_FOUND` | Kein Artikel mit dieser ID |
| 404 / 405 | `HTTP_ERROR` | Unbekannte Route oder falsche HTTP-Methode |
| 409 | `DUPLICATE_SKU` | Ein anderer Artikel verwendet diese SKU bereits |
| 409 | `INSUFFICIENT_STOCK` | Die `OUT`-Menge übersteigt den aktuellen Bestand |
| 409 | `PRODUCT_INACTIVE` | Buchung auf einen deaktivierten Artikel |
| 409 | `CONFLICT` | Bestand wurde gleichzeitig auf unerwartete Weise geändert. Die Anfrage kann wiederholt werden |
| 422 | `VALIDATION_ERROR` | Ungültige Eingabe. `details` listet jedes Problem auf |
| 500 | `INTERNAL_ERROR` | Unerwarteter Serverfehler. Es werden keine internen Details preisgegeben |

## Beispiele

Diese Antworten wurden gegen eine frische Datenbank aufgezeichnet. Die Meldungen der API sind englisch; das Dashboard übersetzt sie für die Anzeige ins Deutsche.

**Artikel anlegen.** Die SKU wird in Großbuchstaben umgewandelt:

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{"sku": "scr-4x40", "name": "Wood screw 4x40", "description": "Box of 100", "min_stock": 8}'
```
```json
201 Created
{"id": 1, "sku": "SCR-4X40", "name": "Wood screw 4x40", "description": "Box of 100",
 "current_stock": 0, "min_stock": 8, "is_active": true, "created_at": "2026-10-27T10:17:53.057723Z"}
```

**Zugang buchen:**

```bash
curl -X POST http://127.0.0.1:8000/products/1/movements \
  -H "Content-Type: application/json" \
  -d '{"movement_type": "IN", "quantity": 10, "reason": "Delivery 2026-10-27"}'
```
```json
201 Created
{"id": 1, "product_id": 1, "movement_type": "IN", "quantity": 10,
 "reason": "Delivery 2026-10-27", "created_at": "2026-10-27T10:17:53.572459Z"}
```

**Versuch, mehr zu entnehmen als vorhanden ist:**

```bash
curl -X POST http://127.0.0.1:8000/products/1/movements \
  -H "Content-Type: application/json" \
  -d '{"movement_type": "OUT", "quantity": 15}'
```
```json
409 Conflict
{"error": {"code": "INSUFFICIENT_STOCK", "message": "Insufficient stock: requested 15, available 10.",
           "details": {"requested": 15, "available": 10}}}
```

**Versuch, den Bestand direkt zu setzen:**

```bash
curl -X PATCH http://127.0.0.1:8000/products/1 \
  -H "Content-Type: application/json" -d '{"current_stock": 999}'
```
```json
422 Unprocessable Content
{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.",
           "details": [{"type": "extra_forbidden", "loc": ["body", "current_stock"],
                        "msg": "Extra inputs are not permitted", "input": 999}]}}
```

**Buchungshistorie** nach einem weiteren `OUT` über 5 Stück:

```bash
curl "http://127.0.0.1:8000/products/1/movements?limit=2"
```
```json
200 OK
{"items": [
   {"id": 2, "product_id": 1, "movement_type": "OUT", "quantity": 5, "reason": "Order 1001",
    "created_at": "2026-10-27T10:17:54.098172Z"},
   {"id": 1, "product_id": 1, "movement_type": "IN", "quantity": 10, "reason": "Delivery 2026-10-27",
    "created_at": "2026-10-27T10:17:53.572459Z"}],
 "total": 2, "limit": 2, "offset": 0}
```

**Artikel unter Mindestbestand und Kennzahlen:**

```bash
curl http://127.0.0.1:8000/inventory/low-stock
curl http://127.0.0.1:8000/inventory/summary
```
```json
[{"id": 1, "sku": "SCR-4X40", "name": "Wood screw 4x40", "current_stock": 5, "min_stock": 8, "is_low": true}]

{"active_products": 1, "total_units": 5, "low_stock_products": 1, "out_of_stock_products": 0}
```

**CSV-Export:**

```bash
curl -OJ http://127.0.0.1:8000/reports/inventory.csv   # speichert inventory-YYYY-MM-DD.csv
```
```csv
id,sku,name,description,current_stock,min_stock,is_low
1,SCR-4X40,Wood screw 4x40,Box of 100,5,8,true
```

Die Datei ist UTF-8 mit Byte-Order-Mark, damit Excel Umlaute korrekt anzeigt. Textzellen, die mit `=`, `+`, `-` oder `@` beginnen, erhalten ein vorangestelltes `'`, damit Tabellenkalkulationen sie nicht als Formel ausführen.

> Unter Windows Anfragekörper mit Nicht-ASCII-Zeichen als UTF-8 senden, zum Beispiel mit `--data-binary @body.json`. Manche Terminals senden eine andere Kodierung, die die API mit `400` ablehnt.

## Demo-Modus

Die öffentliche Demo hat keine Anmeldung, daher ergänzt `LAGERFLOW_DEMO_MODE=true` einige Schutzmaßnahmen. Sie sind standardmäßig ausgeschaltet und verändern die API nicht, solange sie deaktiviert sind.

- **Getrennte, fiktive Daten.** Die Demo nutzt eine eigene Datenbankdatei. Das Zurücksetzen verweigert die Ausführung, sofern nicht der Demo-Modus aktiv ist **und** der Dateiname der Datenbank `demo` enthält; `lagerflow.db` kann es daher nie löschen. Die Startdaten (`app/demo.py`) enthalten 15 erfundene Artikel (Elektromaterial, Befestigungstechnik, Werkzeug, Verpackung, Werkstattbedarf) mit normalem, niedrigem und leerem Bestand sowie einen inaktiven Artikel. Ihr Bestand wird aus der Buchungshistorie berechnet, und ein Test prüft, dass beides übereinstimmt.
- **Zurücksetzen.** Bei jedem Start und alle 60 Minuten werden die Daten in einer Transaktion durch die Startdaten ersetzt. `python -m app.demo reset` macht dasselbe manuell.
- **Ratenbegrenzung.** Höchstens 20 schreibende Anfragen pro Minute und Client sowie 120 insgesamt. Weitere Schreibzugriffe erhalten `429 RATE_LIMITED` mit einem `Retry-After`-Header. Lesezugriffe sind nicht begrenzt. Ein Client wird über den Header `CF-Connecting-IP` erkannt, den Cloudflare vor Render setzt, andernfalls über den letzten Eintrag in `X-Forwarded-For`.
- **Obergrenzen.** Höchstens 60 Artikel und 2000 Buchungen; weitere Anlagen erhalten `409 DEMO_LIMIT_REACHED`.
- **Integrität unverändert.** Alle Schreibzugriffe laufen über die regulären Services und Datenbank-Constraints, negative Bestände bleiben also ausgeschlossen.
- `GET /demo/info` zeigt den nächsten Zeitpunkt des Zurücksetzens und die Grenzen; der Endpunkt existiert nur im Demo-Modus.

Die Grenzen werden im Arbeitsspeicher gehalten. Das genügt für einen einzelnen Serverprozess, und so läuft die Demo.

## Deployment

Das Repository enthält einen [Render](https://render.com)-Blueprint (`render.yaml`) für einen kostenlosen Webdienst. Ein einziger Prozess liefert API, `/docs` und Dashboard aus:

- Build: `pip install -e . && cd frontend && npm ci && npm run build`
- Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Umgebung: `LAGERFLOW_DEMO_MODE=true`, `LAGERFLOW_DATABASE_URL=sqlite:///./lagerflow-demo.db`
- Python 3.12 (`.python-version`), Node.js gemäß `frontend/package.json`

Eigene Instanz bereitstellen: im Render-Dashboard **New → Blueprint** wählen, das Repository verbinden und den Dienst `lagerflow-demo` bestätigen. Es werden keine Secrets benötigt.

Kostenlose Render-Dienste haben ein flüchtiges Dateisystem und werden nach 15 Minuten ohne Zugriffe angehalten. Das passt zur Demo: Jeder Start beginnt mit frischen Startdaten. Die erste Anfrage nach einer Pause dauert etwa eine Minute.

## Tests

```bash
pytest            # Testsuite ausführen
ruff check .      # Linting
ruff format --check .
```

Dashboard:

```bash
cd frontend
npm run lint      # TypeScript-Typprüfung
npm test          # Vitest-Unit-Tests
npm run build
npx playwright install chromium   # einmalig
npm run e2e       # Playwright: startet die API im Demo-Modus auf einer temporären Datenbank
BASE_URL=https://<your-demo-url> npm run e2e   # dieselben Tests gegen eine bereitgestellte Demo
```

Jeder Test läuft gegen eine frische SQLite-Datenbank im Arbeitsspeicher. Die Dependency `get_db` wird in `tests/conftest.py` ersetzt, sodass die Tests `lagerflow.db` nie berühren. Die Suite deckt ab:

- jeden Endpunkt, mit Erfolgs- und Fehlerfällen
- das einheitliche Fehlerformat und seine OpenAPI-Dokumentation
- die Datenbank-Constraints, unabhängig vom Anwendungscode
- den Rollback der Transaktion, wenn das Speichern der Buchung fehlschlägt, einschließlich eines echten Fremdschlüsselfehlers beim Commit
- Race Conditions, darunter 20 Threads, die gleichzeitig Ware aus einer dateibasierten Datenbank entnehmen
- die Übereinstimmung von Bestand und Buchungshistorie
- die Alembic-Migrationen (Upgrade, Downgrade und Übereinstimmung mit den Modellen)
- den Demo-Modus: Konsistenz der Startdaten, idempotentes Zurücksetzen, die Schutzprüfung beim Zurücksetzen, Ratenbegrenzung, Obergrenzen und dass sich ohne Demo-Modus nichts ändert
- die Auslieferung des Dashboards, ohne andere Dateien preiszugeben

Die Unit-Tests des Frontends decken den API-Client und seine deutschen Fehlermeldungen ab. Die End-to-End-Tests steuern einen echten Browser durch das Dashboard: Suche, Anlegen, Buchungen `IN` und `OUT`, den Fehler bei unzureichendem Bestand, Bearbeiten, Deaktivieren, Bestandsfilter, den CSV-Export und den Link auf `/docs`.

## Bekannte Einschränkungen

- **Keine Authentifizierung oder Autorisierung.** Wer die API erreicht, kann Daten ändern.
- **Die Live-Demo ist eine gemeinsam genutzte Spielwiese, kein Produktivsystem.** Alle Besucher sehen dieselben Daten; Änderungen verschwinden beim nächsten Zurücksetzen. Ratenbegrenzung und Obergrenzen erschweren Missbrauch, sind aber einfache Zähler im Arbeitsspeicher für einen einzelnen Prozess. Mehrbenutzerbetrieb wird nicht unterstützt.
- **Kaltstarts.** Der kostenlose Hosting-Tarif hält die Demo bei Inaktivität an; die erste Anfrage danach dauert etwa eine Minute.
- Die **letzten Buchungen** im Dashboard werden aus der Buchungshistorie der einzelnen Artikel zusammengesetzt (eine Anfrage pro Artikel), da die API keine artikelübergreifende Buchungsliste hat. Für die 15 Artikel der Demo reicht das, für große Bestände nicht.
- **SQLite** erlaubt nur einen Schreibzugriff gleichzeitig. Unter hoher paralleler Last schlägt eine Anfrage, die länger als das 5-Sekunden-Sperr-Timeout von SQLite wartet, mit 500 fehl. Das Muster des bedingten UPDATE funktioniert auch mit PostgreSQL, das Projekt wurde aber nur mit SQLite getestet. Das UPDATE verwendet `RETURNING`, was SQLite 3.35+ oder PostgreSQL voraussetzt.
- **Deaktivieren ist endgültig.** Es gibt keinen Endpunkt, um einen Artikel wieder zu aktivieren.
- **Buchungen werden nur angefügt.** Eine falsche Buchung wird durch eine Gegenbuchung korrigiert, nicht durch Bearbeiten oder Löschen.
- `/inventory/levels`, `/inventory/low-stock` und der CSV-Export sind **nicht paginiert**. Für einen kleinen Artikelstamm genügt das, für Zehntausende Artikel nicht.
- Die **Artikelsuche** verwendet `LIKE '%term%'` und kann daher keinen Index nutzen.
- Der **CSV-Export** ist kommagetrennt. Ein deutsches Excel erwartet möglicherweise Semikolons und zeigt dann alles in einer Spalte; in diesem Fall über *Daten → Aus Text/CSV* importieren.
- Alle **Zeitstempel sind in UTC.**
- pytest zeigt eine **Deprecation-Warnung** von Starlette, die für den Testclient `httpx2` statt `httpx` empfiehlt. Das Projekt bleibt wie geplant bei `httpx`.

## Lizenz

MIT. Siehe [LICENSE](LICENSE).
