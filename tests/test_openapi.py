"""The OpenAPI schema (shown in /docs) must describe the real error format."""

import pytest

from app.main import app

ERROR_REF = "#/components/schemas/ErrorResponse"


@pytest.fixture(scope="module")
def openapi() -> dict:
    return app.openapi()


def response_ref(openapi: dict, method: str, path: str, status: str) -> str:
    response = openapi["paths"][path][method]["responses"][status]
    return response["content"]["application/json"]["schema"]["$ref"]


@pytest.mark.parametrize(
    ("method", "path", "statuses"),
    [
        ("post", "/products", ["409", "422"]),
        ("get", "/products", ["422"]),
        ("get", "/products/{product_id}", ["404", "422"]),
        ("patch", "/products/{product_id}", ["404", "409", "422"]),
        ("post", "/products/{product_id}/deactivate", ["404", "422"]),
        ("post", "/products/{product_id}/movements", ["404", "409", "422"]),
        ("get", "/products/{product_id}/movements", ["404", "422"]),
    ],
)
def test_error_responses_are_documented(openapi, method, path, statuses):
    for status in statuses:
        assert response_ref(openapi, method, path, status) == ERROR_REF


def test_fastapis_default_validation_schema_is_not_used(openapi):
    """FastAPI documents 422 as {"detail": [...]} by default, which we never return."""
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            if "422" in operation["responses"]:
                schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
                assert schema["$ref"] == ERROR_REF


def test_error_schema_matches_the_real_error_shape(openapi):
    schemas = openapi["components"]["schemas"]

    assert set(schemas["ErrorResponse"]["properties"]) == {"error"}
    assert set(schemas["ErrorDetail"]["properties"]) == {"code", "message", "details"}


def test_csv_report_is_documented_as_csv(openapi):
    content = openapi["paths"]["/reports/inventory.csv"]["get"]["responses"]["200"]["content"]

    assert "text/csv" in content
