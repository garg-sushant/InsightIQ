"""Turn an uploaded byte stream into a DataFrame, safely.

Everything here is defensive: the input is an arbitrary file from a browser.
Size, extension, content sniffing, row count and encoding are all bounded
*before* Pandas gets a chance to allocate.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import pandas as pd

from app.core.config import settings
from app.core.exceptions import (
    IngestionError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

CSV_EXTENSIONS = {".csv", ".txt", ".tsv"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
ALLOWED_EXTENSIONS = CSV_EXTENSIONS | EXCEL_EXTENSIONS

#: Magic bytes. A .xlsx is a zip; legacy .xls (OLE2) is explicitly rejected
#: rather than silently mis-parsed.
_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0"

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


@dataclass(frozen=True)
class ParsedFile:
    frame: pd.DataFrame
    checksum_sha256: str
    size_bytes: int
    source_headers: list[str]


def _extension(filename: str) -> str:
    name = filename.strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def _validate_filename(filename: str) -> str:
    if not filename or len(filename) > 400:
        raise UnsupportedMediaTypeError("A file with a valid name is required.")
    # Path separators in an upload name are never legitimate.
    if any(sep in filename for sep in ("/", "\\", "\x00")):
        raise UnsupportedMediaTypeError("File name contains illegal characters.")
    extension = _extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"Unsupported file type '{extension or 'unknown'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    return extension


def _decode_csv(content: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionError(
        "The file could not be decoded as text. Save it as UTF-8 CSV and retry."
    )


def _read_csv(content: bytes, extension: str) -> pd.DataFrame:
    text = _decode_csv(content)
    separator = "\t" if extension == ".tsv" else None  # None => sniff
    try:
        return pd.read_csv(
            io.StringIO(text),
            sep=separator,
            engine="python" if separator is None else "c",
            dtype=str,
            keep_default_na=True,
            na_values=["", "NA", "N/A", "null", "NULL", "None", "-"],
            skip_blank_lines=True,
        )
    except pd.errors.EmptyDataError as exc:
        raise IngestionError("The file is empty.") from exc
    except pd.errors.ParserError as exc:
        raise IngestionError(f"The file could not be parsed as CSV: {exc}") from exc


def _read_excel(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(
            io.BytesIO(content),
            dtype=str,
            engine="openpyxl",
            na_values=["", "NA", "N/A", "null", "NULL", "None", "-"],
        )
    except ValueError as exc:
        raise IngestionError(f"The spreadsheet could not be read: {exc}") from exc
    except Exception as exc:  # openpyxl raises a wide variety of types
        raise IngestionError(
            "The spreadsheet could not be read. Confirm it is a valid .xlsx file."
        ) from exc


def parse_upload(filename: str, content: bytes) -> ParsedFile:
    """Validate and parse an uploaded file into a string-typed DataFrame.

    Every cell is read as ``str`` so that type coercion — and the per-row error
    reporting that goes with it — happens in one deliberate place
    (``validators.coerce_frame``) rather than being silently done by Pandas.
    """
    extension = _validate_filename(filename)

    size = len(content)
    if size == 0:
        raise IngestionError("The uploaded file is empty.")
    if size > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"File is {size / 1_048_576:.1f} MB; the limit is {settings.max_upload_mb} MB."
        )

    if extension in EXCEL_EXTENSIONS:
        if content[:4] == _OLE2_MAGIC:
            raise UnsupportedMediaTypeError(
                "Legacy .xls files are not supported. Re-save as .xlsx and retry."
            )
        if content[:4] != _ZIP_MAGIC:
            raise UnsupportedMediaTypeError(
                "This file does not look like a real .xlsx workbook."
            )
        frame = _read_excel(content)
    else:
        frame = _read_csv(content, extension)

    if frame.empty:
        raise IngestionError("The file contains a header but no data rows.")
    if len(frame) > settings.max_upload_rows:
        raise PayloadTooLargeError(
            f"File has {len(frame):,} rows; the limit is {settings.max_upload_rows:,}."
        )

    # Drop Pandas' index-echo column that Excel exports frequently carry.
    unnamed = [c for c in frame.columns if str(c).strip().lower().startswith("unnamed:")]
    if unnamed:
        frame = frame.drop(columns=unnamed)

    source_headers = [str(c) for c in frame.columns]
    if len(set(source_headers)) != len(source_headers):
        raise IngestionError("The file has duplicate column headers.")

    return ParsedFile(
        frame=frame,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=size,
        source_headers=source_headers,
    )


__all__ = [
    "ALLOWED_EXTENSIONS",
    "CSV_EXTENSIONS",
    "EXCEL_EXTENSIONS",
    "ParsedFile",
    "parse_upload",
]
