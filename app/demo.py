"""Fictional demo data for the public live demo.

The demo runs on its own database file (its name must contain "demo") and is
reset to this data on every start and periodically while running. All products,
movements and reasons are invented.

Usage: python -m app.demo reset   (requires LAGERFLOW_DEMO_MODE=true)
"""

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import MovementType, Product, StockMovement

IN, OUT = MovementType.IN, MovementType.OUT


@dataclass(frozen=True)
class SeedProduct:
    sku: str
    name: str
    description: str | None
    min_stock: int
    # (days ago, type, quantity, reason); listed oldest first.
    movements: tuple[tuple[int, MovementType, int, str], ...]
    is_active: bool = True


SEED_PRODUCTS: tuple[SeedProduct, ...] = (
    SeedProduct(
        "EL-KAB-NYM315",
        "Installationskabel NYM-J 3x1,5 mm², Ring 50 m",
        "Mantelleitung für feste Verlegung im Innenbereich.",
        10,
        (
            (28, IN, 30, "Wareneingang Lieferung 4711"),
            (21, OUT, 6, "Auftrag Elektroinstallation Halle B"),
            (12, OUT, 4, "Werkstattbedarf"),
            (3, IN, 10, "Wareneingang Lieferung 4790"),
        ),
    ),
    SeedProduct(
        "EL-KLEM-3P",
        "Hebelklemme 3-polig, 100 Stück",
        "Verbindungsklemme für ein- und feindrähtige Leiter.",
        20,
        (
            (27, IN, 40, "Wareneingang Lieferung 4712"),
            (15, OUT, 18, "Auftrag Sanierung Bürogebäude"),
            (2, OUT, 9, "Auftrag Elektroinstallation Halle B"),
        ),
    ),
    SeedProduct(
        "EL-LSS-B16",
        "Leitungsschutzschalter B16, 1-polig",
        None,
        15,
        (
            (25, IN, 50, "Wareneingang Lieferung 4715"),
            (9, OUT, 12, "Auftrag Verteilerbau"),
        ),
    ),
    SeedProduct(
        "EL-LED-P12",
        "LED-Panel 12 W, neutralweiß",
        "Aufbaupanel 30x30 cm, 4000 K.",
        8,
        (
            (26, IN, 12, "Wareneingang Lieferung 4713"),
            (14, OUT, 8, "Auftrag Ladenbau Innenstadt"),
            (5, OUT, 4, "Auftrag Ladenbau Innenstadt"),
        ),
    ),
    SeedProduct(
        "BF-SKS-M6X30",
        "Sechskantschraube M6x30, verzinkt, 100 Stück",
        "DIN 933, Festigkeitsklasse 8.8.",
        25,
        (
            (29, IN, 80, "Wareneingang Lieferung 4701"),
            (18, OUT, 15, "Werkstattbedarf"),
            (7, OUT, 10, "Auftrag Regalmontage"),
        ),
    ),
    SeedProduct(
        "BF-HS-4X40",
        "Holzschraube 4x40, Torx, 200 Stück",
        None,
        30,
        (
            (24, IN, 60, "Wareneingang Lieferung 4720"),
            (11, OUT, 25, "Auftrag Regalmontage"),
            (4, OUT, 14, "Auftrag Messestand"),
        ),
    ),
    SeedProduct(
        "BF-DUE-8",
        "Spreizdübel 8 mm, 100 Stück",
        None,
        20,
        (
            (23, IN, 50, "Wareneingang Lieferung 4720"),
            (10, OUT, 12, "Auftrag Regalmontage"),
            (1, IN, 20, "Retoure Baustelle Nord"),
        ),
    ),
    SeedProduct(
        "WZ-ABS-18V",
        "Akku-Bohrschrauber 18 V",
        "Inklusive zwei Akkus und Ladegerät.",
        3,
        (
            (30, IN, 8, "Wareneingang Lieferung 4699"),
            (16, OUT, 2, "Ausgabe Montageteam"),
        ),
    ),
    SeedProduct(
        "WZ-BIT-32",
        "Bit-Set 32-teilig",
        None,
        5,
        (
            (22, IN, 10, "Wareneingang Lieferung 4721"),
            (8, OUT, 4, "Ausgabe Montageteam"),
            (2, OUT, 3, "Ausgabe Werkstatt"),
        ),
    ),
    SeedProduct(
        "WZ-MB-5M",
        "Maßband 5 m",
        None,
        4,
        (
            (20, IN, 6, "Wareneingang Lieferung 4725"),
            (6, OUT, 6, "Ausgabe Montageteam"),
        ),
    ),
    SeedProduct(
        "VP-KART-M",
        "Versandkarton 400x300x200 mm",
        "Zweiwellig, braun.",
        100,
        (
            (27, IN, 500, "Wareneingang Lieferung 4714"),
            (13, OUT, 140, "Versand Kundenaufträge KW"),
            (3, OUT, 95, "Versand Kundenaufträge KW"),
        ),
    ),
    SeedProduct(
        "VP-LPF-50",
        "Luftpolsterfolie 50 cm x 100 m",
        None,
        5,
        (
            (19, IN, 8, "Wareneingang Lieferung 4730"),
            (5, OUT, 5, "Versand Kundenaufträge KW"),
        ),
    ),
    SeedProduct(
        "VP-PB-50",
        "Packband braun 50 mm, 6 Rollen",
        None,
        12,
        (
            (18, IN, 40, "Wareneingang Lieferung 4730"),
            (4, OUT, 10, "Versand Kundenaufträge KW"),
        ),
    ),
    SeedProduct(
        "WS-HS-L",
        "Arbeitshandschuhe Größe L, Paar",
        "Nitril-beschichtet.",
        20,
        (
            (17, IN, 60, "Wareneingang Lieferung 4733"),
            (9, OUT, 15, "Ausgabe Lager"),
            (1, OUT, 8, "Ausgabe Montageteam"),
        ),
    ),
    SeedProduct(
        "WS-REIN-5L",
        "Werkstattreiniger 5 l",
        "Auslaufartikel, wird nicht mehr nachbestellt.",
        0,
        (
            (29, IN, 6, "Wareneingang Lieferung 4702"),
            (15, OUT, 4, "Werkstattbedarf"),
        ),
        is_active=False,
    ),
)


def stock_from_movements(movements: tuple[tuple[int, MovementType, int, str], ...]) -> int:
    """Final stock after all movements. Raises if the balance would ever go negative."""
    stock = 0
    for _days_ago, movement_type, quantity, _reason in movements:
        stock += quantity if movement_type is IN else -quantity
        if stock < 0:
            raise ValueError("Seed movements would make the stock negative.")
    return stock


def ensure_demo_database(settings: Settings, engine: Engine) -> None:
    """Refuse to touch anything but a dedicated demo database file."""
    if not settings.demo_mode:
        raise RuntimeError("Demo data can only be reset with LAGERFLOW_DEMO_MODE=true.")
    db_file = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not db_file or "demo" not in Path(db_file).name:
        raise RuntimeError(
            "Refusing to reset: the database file name must contain 'demo' "
            f"(got {engine.url.render_as_string(hide_password=True)!r})."
        )


def reset_demo_data(settings: Settings, engine: Engine, now: datetime | None = None) -> None:
    """Replace all data with the seed data in one transaction. Safe to run repeatedly."""
    ensure_demo_database(settings, engine)
    now = now or datetime.now(UTC)
    with Session(engine) as session, session.begin():
        session.execute(delete(StockMovement))
        session.execute(delete(Product))
        for index, seed in enumerate(SEED_PRODUCTS):
            first_day = seed.movements[0][0] if seed.movements else 0
            product = Product(
                sku=seed.sku,
                name=seed.name,
                description=seed.description,
                min_stock=seed.min_stock,
                current_stock=stock_from_movements(seed.movements),
                is_active=seed.is_active,
                created_at=now - timedelta(days=first_day + 1, minutes=index),
            )
            session.add(product)
            session.flush()  # assigns product.id
            for position, (days_ago, movement_type, quantity, reason) in enumerate(seed.movements):
                session.add(
                    StockMovement(
                        product_id=product.id,
                        movement_type=movement_type,
                        quantity=quantity,
                        reason=reason,
                        # Spread over the working day so the order is stable and realistic.
                        created_at=now
                        - timedelta(days=days_ago, hours=6 - index % 6, minutes=position),
                    )
                )


def main(argv: list[str]) -> int:
    from app.config import settings
    from app.database import engine

    if argv != ["reset"]:
        print("Usage: python -m app.demo reset", file=sys.stderr)
        return 2
    reset_demo_data(settings, engine)
    print(f"Demo data reset: {len(SEED_PRODUCTS)} products.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
