"""API tests for inventory monitoring and the CSV report."""

import csv
import io


def by_sku(items: list[dict]) -> dict[str, dict]:
    return {item["sku"]: item for item in items}


# --- GET /inventory/levels -------------------------------------------------------


def test_levels_list_active_products_sorted_by_sku(client, make_product):
    make_product(sku="B-2", current_stock=1, min_stock=5)
    make_product(sku="A-1", current_stock=10, min_stock=5)
    make_product(sku="C-3", is_active=False)

    response = client.get("/inventory/levels")

    assert response.status_code == 200
    items = response.json()
    assert [item["sku"] for item in items] == ["A-1", "B-2"]
    assert set(items[0]) == {"id", "sku", "name", "current_stock", "min_stock", "is_low"}


def test_levels_flag_products_below_minimum(client, make_product):
    make_product(sku="LOW", current_stock=4, min_stock=5)
    make_product(sku="EXACT", current_stock=5, min_stock=5)
    make_product(sku="PLENTY", current_stock=6, min_stock=5)

    items = by_sku(client.get("/inventory/levels").json())

    assert items["LOW"]["is_low"] is True
    assert items["EXACT"]["is_low"] is False
    assert items["PLENTY"]["is_low"] is False


def test_levels_are_empty_without_products(client):
    assert client.get("/inventory/levels").json() == []


# --- GET /inventory/low-stock ----------------------------------------------------


def test_low_stock_lists_only_active_products_strictly_below_minimum(client, make_product):
    make_product(sku="LOW-B", current_stock=0, min_stock=1)
    make_product(sku="LOW-A", current_stock=2, min_stock=10)
    make_product(sku="AT-MIN", current_stock=5, min_stock=5)
    make_product(sku="NO-MIN", current_stock=0, min_stock=0)
    make_product(sku="INACTIVE", current_stock=0, min_stock=10, is_active=False)

    response = client.get("/inventory/low-stock")

    assert response.status_code == 200
    assert [item["sku"] for item in response.json()] == ["LOW-A", "LOW-B"]
    assert all(item["is_low"] for item in response.json())


def test_low_stock_reacts_to_stock_movements(client, make_product):
    product = make_product(sku="WATCH", current_stock=0, min_stock=3)
    assert [p["sku"] for p in client.get("/inventory/low-stock").json()] == ["WATCH"]

    client.post(f"/products/{product.id}/movements", json={"movement_type": "IN", "quantity": 3})

    assert client.get("/inventory/low-stock").json() == []


# --- GET /inventory/summary ------------------------------------------------------


def test_summary_counts_active_products(client, make_product):
    make_product(current_stock=10, min_stock=5)
    make_product(current_stock=2, min_stock=5)  # low
    make_product(current_stock=0, min_stock=1)  # low and out of stock
    make_product(current_stock=0, min_stock=0)  # out of stock, not low
    make_product(current_stock=99, min_stock=500, is_active=False)  # ignored

    response = client.get("/inventory/summary")

    assert response.status_code == 200
    assert response.json() == {
        "active_products": 4,
        "total_units": 12,
        "low_stock_products": 2,
        "out_of_stock_products": 2,
    }


def test_summary_without_products_is_all_zero(client):
    assert client.get("/inventory/summary").json() == {
        "active_products": 0,
        "total_units": 0,
        "low_stock_products": 0,
        "out_of_stock_products": 0,
    }


# --- GET /reports/inventory.csv --------------------------------------------------


def read_csv(response) -> list[dict]:
    text = response.content.decode("utf-8-sig")  # strips the BOM
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_download_headers(client):
    response = client.get("/reports/inventory.csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="inventory-')
    assert disposition.endswith('.csv"')
    assert response.content.startswith("﻿".encode())


def test_csv_without_products_contains_only_the_header(client):
    response = client.get("/reports/inventory.csv")

    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines == ["id,sku,name,description,current_stock,min_stock,is_low"]


def test_csv_contains_one_row_per_active_product(client, make_product):
    product = make_product(sku="B-1", name="Schraube", current_stock=3, min_stock=5)
    make_product(sku="A-1", name="Mutter", current_stock=8, min_stock=2)
    make_product(sku="Z-9", is_active=False)

    rows = read_csv(client.get("/reports/inventory.csv"))

    assert [row["sku"] for row in rows] == ["A-1", "B-1"]
    assert rows[1] == {
        "id": str(product.id),
        "sku": "B-1",
        "name": "Schraube",
        "description": "",
        "current_stock": "3",
        "min_stock": "5",
        "is_low": "true",
    }
    assert rows[0]["is_low"] == "false"


def test_csv_quotes_special_characters_and_keeps_umlauts(client, make_product):
    make_product(name='Dübel, 6mm "Profi"', description="Line one\nLine two")

    row = read_csv(client.get("/reports/inventory.csv"))[0]

    assert row["name"] == 'Dübel, 6mm "Profi"'
    assert row["description"] == "Line one\nLine two"


def test_csv_neutralizes_spreadsheet_formulas(client, make_product):
    make_product(sku="F-1", name='=HYPERLINK("http://evil")', description="+1+1")
    make_product(sku="F-2", name="-10% sale", description="@SUM(A1)")

    rows = by_sku(read_csv(client.get("/reports/inventory.csv")))

    assert rows["F-1"]["name"] == '\'=HYPERLINK("http://evil")'
    assert rows["F-1"]["description"] == "'+1+1"
    assert rows["F-2"]["name"] == "'-10% sale"
    assert rows["F-2"]["description"] == "'@SUM(A1)"
