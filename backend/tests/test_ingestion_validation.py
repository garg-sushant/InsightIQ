"""Ingestion validator: type coercion, range checks, duplicates, atomic rejection."""

from __future__ import annotations

from app.models.dataset import EntityType
from app.services.ingestion.parser import parse_upload
from app.services.ingestion.spec import get_spec
from app.services.ingestion.validators import validate_frame

ORDERS_CSV = b"""Row ID,Order ID,Order Date,Ship Date,Customer ID,Customer Name,Product ID,Product Name,Category,Sales,Quantity,Discount,Profit
1,ORD-1,1/5/2024,1/8/2024,C1,Alice,P1,Widget,Office Supplies,"$1,234.56",3,10%,123.45
2,ORD-1,1/5/2024,1/8/2024,C1,Alice,P2,Gadget,Office Supplies,500,2,0,50
3,ORD-2,not-a-date,1/9/2024,C2,Bob,P1,Widget,Office Supplies,200,1,0,20
4,ORD-3,1/6/2024,1/9/2024,C2,Bob,P1,Widget,Office Supplies,300,-5,0,30
5,ORD-1,1/5/2024,1/8/2024,C1,Alice,P1,Widget,Office Supplies,500,2,0,50
"""


def test_currency_and_percent_parsing() -> None:
    parsed = parse_upload("orders.csv", ORDERS_CSV)
    outcome = validate_frame(parsed.frame, get_spec(EntityType.ORDERS))

    row1 = outcome.frame.iloc[0]
    assert row1["sales"] == __import__("decimal").Decimal("1234.56")
    assert row1["discount"] == __import__("decimal").Decimal("0.1")


def test_bad_date_rejected_as_row_error() -> None:
    parsed = parse_upload("orders.csv", ORDERS_CSV)
    outcome = validate_frame(parsed.frame, get_spec(EntityType.ORDERS))
    assert "invalid_date" in outcome.error_counts
    assert outcome.error_counts["invalid_date"] == 1


def test_negative_quantity_out_of_range() -> None:
    parsed = parse_upload("orders.csv", ORDERS_CSV)
    outcome = validate_frame(parsed.frame, get_spec(EntityType.ORDERS))
    assert "out_of_range" in outcome.error_counts


def test_missing_required_column_rejects_whole_batch() -> None:
    csv = b"Order Date,Sales\n1/1/2024,100\n"
    parsed = parse_upload("orders.csv", csv)
    outcome = validate_frame(parsed.frame, get_spec(EntityType.ORDERS))
    assert not outcome.is_valid
    assert outcome.rows_accepted == 0
    assert "order_ref" in outcome.missing_required_columns


def test_alias_headers_resolve_to_canonical_names() -> None:
    csv = (
        b"row id,order id,order date,customer id,product id,sales,quantity\n"
        b"1,O1,1/1/2024,C1,P1,100,2\n"
    )
    parsed = parse_upload("orders.csv", csv)
    outcome = validate_frame(parsed.frame, get_spec(EntityType.ORDERS))
    assert outcome.is_valid
    assert "order_ref" in outcome.frame.columns
    assert outcome.frame.iloc[0]["order_ref"] == "O1"


def test_empty_file_rejected() -> None:
    from app.core.exceptions import IngestionError
    import pytest

    with pytest.raises(IngestionError):
        parse_upload("empty.csv", b"")


def test_oversized_row_count_rejected(monkeypatch) -> None:
    import pytest
    from app.core.exceptions import PayloadTooLargeError
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_rows", 2)
    csv = b"Order ID\nA\nB\nC\n"
    with pytest.raises(PayloadTooLargeError):
        parse_upload("orders.csv", csv)
