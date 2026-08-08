"""Declarative upload specs: what each entity file must contain.

Header matching is alias-based and normalisation-insensitive, so all of
``"Sub-Category"``, ``"sub category"`` and ``"SUB_CATEGORY"`` resolve to the
same canonical field. The specs here are also what the API exposes at
``GET /datasets/schema/{entity_type}`` so the UI can show users the expected
shape before they upload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.models.dataset import EntityType

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_header(raw: str) -> str:
    """``"  Sub-Category "`` -> ``"sub_category"``."""
    return _NON_ALNUM.sub("_", str(raw).strip().lower()).strip("_")


class FieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    field_type: FieldType
    required: bool
    description: str
    aliases: tuple[str, ...] = ()
    max_length: int | None = None
    #: Applied after coercion; rows outside the range become row errors.
    min_value: float | None = None
    max_value: float | None = None
    #: Used when the column is absent or the cell is blank (optional fields only).
    default: object | None = None

    @property
    def accepted_headers(self) -> set[str]:
        return {normalize_header(self.name), *(normalize_header(a) for a in self.aliases)}


@dataclass(frozen=True)
class EntitySpec:
    entity_type: EntityType
    columns: tuple[ColumnSpec, ...]
    #: Business key used for duplicate detection within the file and against the DB.
    primary_key: tuple[str, ...]
    description: str = ""
    #: Columns that reference another entity, checked after coercion.
    references: dict[str, str] = field(default_factory=dict)

    @property
    def required_columns(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.required)

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)

    def resolve_headers(self, headers: list[str]) -> tuple[dict[str, str], list[str]]:
        """Map source headers to canonical names.

        Returns ``(source_header -> canonical_name, unmatched_source_headers)``.
        First match wins, so a file with both "Customer ID" and "customer_id"
        keeps the first and reports the second as unexpected.
        """
        lookup: dict[str, str] = {}
        for column in self.columns:
            for header in column.accepted_headers:
                lookup.setdefault(header, column.name)

        mapping: dict[str, str] = {}
        unmatched: list[str] = []
        claimed: set[str] = set()
        for header in headers:
            canonical = lookup.get(normalize_header(header))
            if canonical is not None and canonical not in claimed:
                mapping[header] = canonical
                claimed.add(canonical)
            else:
                unmatched.append(header)
        return mapping, unmatched


# ---------------------------------------------------------------------------
# Entity definitions — modelled on the standard Superstore retail export.
# ---------------------------------------------------------------------------

_ORDERS = EntitySpec(
    entity_type=EntityType.ORDERS,
    description=(
        "Order lines. One row per product on an order. Customer and product "
        "master rows are created automatically from the inline columns when "
        "they have not been uploaded separately."
    ),
    primary_key=("line_ref",),
    references={"customer_ref": "customers", "product_ref": "products"},
    columns=(
        ColumnSpec(
            "line_ref",
            FieldType.STRING,
            required=False,
            description="Unique id for the order line. Generated when absent.",
            aliases=("row id", "row_id", "line id", "line_number", "id"),
            max_length=96,
        ),
        ColumnSpec(
            "order_ref",
            FieldType.STRING,
            required=True,
            description="Order identifier. Shared by every line of the same order.",
            aliases=("order id", "order_number", "order no", "orderid"),
            max_length=64,
        ),
        ColumnSpec(
            "order_date",
            FieldType.DATE,
            required=True,
            description="Date the order was placed.",
            aliases=("order date", "orderdate", "date"),
        ),
        ColumnSpec(
            "ship_date",
            FieldType.DATE,
            required=False,
            description="Date the order shipped.",
            aliases=("ship date", "shipdate", "shipped_date"),
        ),
        ColumnSpec(
            "ship_mode",
            FieldType.STRING,
            required=False,
            description="Shipping service used.",
            aliases=("ship mode", "shipmode", "shipping_mode"),
            max_length=64,
        ),
        ColumnSpec(
            "customer_ref",
            FieldType.STRING,
            required=True,
            description="Customer identifier.",
            aliases=("customer id", "customerid", "customer_number"),
            max_length=64,
        ),
        ColumnSpec(
            "customer_name",
            FieldType.STRING,
            required=False,
            description="Customer name, used to auto-create the customer record.",
            aliases=("customer name", "customername", "client_name"),
            max_length=200,
        ),
        ColumnSpec(
            "segment",
            FieldType.STRING,
            required=False,
            description="Customer segment, e.g. Consumer / Corporate.",
            aliases=("customer_segment",),
            max_length=64,
        ),
        ColumnSpec(
            "country",
            FieldType.STRING,
            required=False,
            description="Country.",
            max_length=80,
        ),
        ColumnSpec(
            "region", FieldType.STRING, required=False, description="Sales region.",
            max_length=64,
        ),
        ColumnSpec(
            "state",
            FieldType.STRING,
            required=False,
            description="State or province.",
            aliases=("province",),
            max_length=80,
        ),
        ColumnSpec("city", FieldType.STRING, required=False, description="City.", max_length=120),
        ColumnSpec(
            "postal_code",
            FieldType.STRING,
            required=False,
            description="Postal or ZIP code.",
            aliases=("postal code", "zip", "zip_code", "postcode"),
            max_length=20,
        ),
        ColumnSpec(
            "product_ref",
            FieldType.STRING,
            required=True,
            description="Product identifier.",
            aliases=("product id", "productid", "sku"),
            max_length=64,
        ),
        ColumnSpec(
            "product_name",
            FieldType.STRING,
            required=False,
            description="Product name, used to auto-create the product record.",
            aliases=("product name", "productname", "item_name"),
            max_length=400,
        ),
        ColumnSpec(
            "category",
            FieldType.STRING,
            required=False,
            description="Product category.",
            max_length=120,
        ),
        ColumnSpec(
            "sub_category",
            FieldType.STRING,
            required=False,
            description="Product sub-category.",
            aliases=("sub category", "subcategory", "sub-category"),
            max_length=120,
        ),
        ColumnSpec(
            "quantity",
            FieldType.INTEGER,
            required=True,
            description="Units sold on this line.",
            aliases=("qty", "units"),
            min_value=0,
            max_value=1_000_000,
        ),
        ColumnSpec(
            "sales",
            FieldType.DECIMAL,
            required=True,
            description="Net line revenue, after discount.",
            aliases=("revenue", "net_sales", "amount", "line_total"),
            min_value=-1e12,
            max_value=1e12,
        ),
        ColumnSpec(
            "discount",
            FieldType.DECIMAL,
            required=False,
            description="Discount as a fraction between 0 and 1.",
            aliases=("discount_rate", "discount_pct"),
            min_value=0,
            max_value=1,
            default=0,
        ),
        ColumnSpec(
            "profit",
            FieldType.DECIMAL,
            required=False,
            description="Line profit. Defaults to 0 when not supplied.",
            aliases=("margin", "gross_profit"),
            min_value=-1e12,
            max_value=1e12,
            default=0,
        ),
        ColumnSpec(
            "unit_price",
            FieldType.DECIMAL,
            required=False,
            description="Realised price per unit. Derived from sales/quantity when absent.",
            aliases=("unit price", "price", "price_per_unit"),
            min_value=0,
            max_value=1e12,
        ),
    ),
)

_CUSTOMERS = EntitySpec(
    entity_type=EntityType.CUSTOMERS,
    description="Customer master data.",
    primary_key=("customer_ref",),
    columns=(
        ColumnSpec(
            "customer_ref",
            FieldType.STRING,
            required=True,
            description="Customer identifier.",
            aliases=("customer id", "customerid", "id"),
            max_length=64,
        ),
        ColumnSpec(
            "name",
            FieldType.STRING,
            required=True,
            description="Customer name.",
            aliases=("customer name", "customername", "full_name"),
            max_length=200,
        ),
        ColumnSpec(
            "segment",
            FieldType.STRING,
            required=False,
            description="Customer segment.",
            aliases=("customer_segment",),
            max_length=64,
        ),
        ColumnSpec("country", FieldType.STRING, required=False, description="Country.",
                   max_length=80),
        ColumnSpec("region", FieldType.STRING, required=False, description="Sales region.",
                   max_length=64),
        ColumnSpec("state", FieldType.STRING, required=False, description="State or province.",
                   aliases=("province",), max_length=80),
        ColumnSpec("city", FieldType.STRING, required=False, description="City.", max_length=120),
        ColumnSpec(
            "postal_code",
            FieldType.STRING,
            required=False,
            description="Postal or ZIP code.",
            aliases=("postal code", "zip", "zip_code", "postcode"),
            max_length=20,
        ),
    ),
)

_PRODUCTS = EntitySpec(
    entity_type=EntityType.PRODUCTS,
    description="Product catalogue.",
    primary_key=("product_ref",),
    columns=(
        ColumnSpec(
            "product_ref",
            FieldType.STRING,
            required=True,
            description="Product identifier.",
            aliases=("product id", "productid", "sku", "id"),
            max_length=64,
        ),
        ColumnSpec(
            "name",
            FieldType.STRING,
            required=True,
            description="Product name.",
            aliases=("product name", "productname", "item_name"),
            max_length=400,
        ),
        ColumnSpec("category", FieldType.STRING, required=False,
                   description="Product category.", max_length=120),
        ColumnSpec(
            "sub_category",
            FieldType.STRING,
            required=False,
            description="Product sub-category.",
            aliases=("sub category", "subcategory", "sub-category"),
            max_length=120,
        ),
        ColumnSpec(
            "unit_price",
            FieldType.DECIMAL,
            required=False,
            description="List price per unit.",
            aliases=("unit price", "price", "list_price"),
            min_value=0,
            max_value=1e12,
        ),
    ),
)

_RETURNS = EntitySpec(
    entity_type=EntityType.RETURNS,
    description="Returned orders. Each row marks one order as returned.",
    primary_key=("order_ref",),
    references={"order_ref": "orders"},
    columns=(
        ColumnSpec(
            "order_ref",
            FieldType.STRING,
            required=True,
            description="Identifier of the returned order.",
            aliases=("order id", "orderid", "order_number"),
            max_length=64,
        ),
        ColumnSpec(
            "returned",
            FieldType.BOOLEAN,
            required=False,
            description="Whether the order was returned. Defaults to true.",
            aliases=("is_returned", "return", "returned_flag"),
            default=True,
        ),
        ColumnSpec(
            "return_date",
            FieldType.DATE,
            required=False,
            description="Date the return was recorded.",
            aliases=("return date", "returndate", "date"),
        ),
        ColumnSpec(
            "reason",
            FieldType.STRING,
            required=False,
            description="Free-text return reason.",
            aliases=("return_reason", "reason_code"),
            max_length=240,
        ),
    ),
)

ENTITY_SPECS: dict[EntityType, EntitySpec] = {
    EntityType.ORDERS: _ORDERS,
    EntityType.CUSTOMERS: _CUSTOMERS,
    EntityType.PRODUCTS: _PRODUCTS,
    EntityType.RETURNS: _RETURNS,
}


def get_spec(entity_type: EntityType) -> EntitySpec:
    return ENTITY_SPECS[entity_type]


__all__ = [
    "ENTITY_SPECS",
    "ColumnSpec",
    "EntitySpec",
    "FieldType",
    "get_spec",
    "normalize_header",
]
