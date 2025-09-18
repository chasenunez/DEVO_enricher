#!/usr/bin/env python3
"""
make_icsv.py

Convert a plain CSV or Excel spreadsheet (.xls/.xlsx) into a self-documented iCSV,
and generate a Frictionless Table Schema JSON for validation.

Usage:
    python make_icsv.py input.csv
    python make_icsv.py input.xlsx

Notes:
- CSV files: uses frictionless + csv for reading and inspection.
- Excel files: uses pandas to read the first sheet, converts to rows of strings.
- Recommended dependencies (add to requirements.txt):
    frictionless
    pandas
    openpyxl      # for .xlsx
    xlrd==1.2.0   # for old .xls support (optional)
    pytest (dev)
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from itertools import islice

# frictionless is required by spec; import it (raise helpful error if missing)
try:
    from frictionless import Resource
except Exception as e:
    raise RuntimeError(
        "frictionless is required. Install with: pip install frictionless"
    ) from e

# pandas is optional (only needed for Excel). We'll lazy-import it when needed.
PANDAS_AVAILABLE = True
try:
    import pandas as pd
except Exception:
    PANDAS_AVAILABLE = False

# Common placeholders considered as missing values
COMMON_MISSING = {"", "NA", "N/A", "na", "n/a", "NULL", "null", "nan", "NaN", "-999", "-999.0", "-999.000000"}

# -------------------------
# Type inference utilities
# -------------------------
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")


def try_parse_datetime(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    if not re.search(r"[0-9]", s):
        return False
    try:
        datetime.fromisoformat(s)
        return True
    except Exception:
        pass
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%Y%m%dT%H%M%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in fmts:
        try:
            datetime.strptime(s, fmt)
            return True
        except Exception:
            continue
    return False


def infer_column_type(values: List[str], missing_values: set) -> str:
    pruned = [v.strip() for v in values if v is not None and v.strip() not in missing_values]
    if not pruned:
        return "string"
    is_int = True
    is_float = True
    is_datetime = True
    for v in pruned:
        if not INT_RE.match(v):
            is_int = False
        if not FLOAT_RE.match(v) and not INT_RE.match(v):
            is_float = False
        if not try_parse_datetime(v):
            is_datetime = False
    if is_int:
        return "integer"
    if is_float:
        return "number"
    if is_datetime:
        return "datetime"
    return "string"


# -------------------------
# Aggregation / stats
# -------------------------
def compute_numeric_minmax(pruned: List[str], as_type: str) -> Tuple[Optional[float], Optional[float]]:
    if not pruned:
        return None, None
    try:
        if as_type == "integer":
            nums = [int(x) for x in pruned]
        else:
            nums = [float(x) for x in pruned]
        return min(nums), max(nums)
    except Exception:
        return None, None


def compute_datetime_minmax(pruned: List[str]) -> Tuple[Optional[str], Optional[str]]:
    parsed = []
    for v in pruned:
        try:
            try:
                dt = datetime.fromisoformat(v)
            except Exception:
                fmts = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%d.%m.%Y",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%Y/%m/%d",
                    "%d-%m-%Y",
                    "%Y%m%dT%H%M%S",
                ]
                dt = None
                for fmt in fmts:
                    try:
                        dt = datetime.strptime(v, fmt)
                        break
                    except Exception:
                        pass
                if dt is None:
                    continue
            parsed.append(dt)
        except Exception:
            continue
    if not parsed:
        return None, None
    min_dt = min(parsed).isoformat()
    max_dt = max(parsed).isoformat()
    return min_dt, max_dt


# -------------------------
# CSV / Excel loaders
# -------------------------
def detect_delimiter(sample_text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=[",", "|", ";", ":", "\t", "/"])
        return dialect.delimiter
    except Exception:
        return ","


def load_csv_rows(path: str, delimiter: Optional[str] = None) -> Tuple[List[str], List[List[str]], int]:
    """
    Load header and rows from CSV. Returns (header, rows, row_count).
    Uses csv module with delimiter detection. Reads safely (doesn't assume N lines).
    """
    # sample a few lines to detect delimiter
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        sample = "".join(islice(fh, 10))
    detected = detect_delimiter(sample) if delimiter is None else delimiter

    # Use frictionless Resource to show we used it (optional)
    try:
        _ = Resource(path, format="csv", control={"delimiter": detected})
    except Exception:
        # resource instantiation is best-effort
        pass

    header = []
    rows: List[List[str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as fh:
        reader = csv.reader(fh, delimiter=detected)
        for i, r in enumerate(reader):
            if i == 0:
                header = [c.strip() for c in r]
            else:
                rows.append([c for c in r])
    return header, rows, len(rows)


def load_excel_rows(path: str) -> Tuple[List[str], List[List[str]], int]:
    """
    Load the first sheet of an .xls/.xlsx file and return header, rows, row_count.
    Uses pandas to read (pandas must be installed).
    Converts all values to strings and replaces missing values with ''.
    """
    if not PANDAS_AVAILABLE:
        raise RuntimeError(
            "Reading Excel files requires pandas. Install with: pip install pandas openpyxl xlrd==1.2.0"
        )
    # Read first sheet
    try:
        # read_excel will pick a suitable engine if available (openpyxl for xlsx).
        df = pd.read_excel(path, sheet_name=0, engine=None)
    except Exception as e:
        # Try explicit engines fallback
        try:
            df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
        except Exception:
            # last try for older .xls
            try:
                df = pd.read_excel(path, sheet_name=0, engine="xlrd")
            except Exception as e2:
                raise RuntimeError(f"Failed to read Excel file '{path}': {e} / {e2}") from e2

    # Replace NaN/NA with empty strings, convert to string for downstream processing
    df = df.fillna("")
    # Ensure column names are strings
    header = [str(c) for c in df.columns.tolist()]
    # Convert rows to lists of strings
    rows: List[List[str]] = []
    for idx, row in df.iterrows():
        # row may contain numbers/datetimes; cast each to string and strip
        row_vals = []
        for c in header:
            val = row.get(c, "")
            # If pandas Timestamp, convert to ISO
            if hasattr(val, "isoformat"):
                try:
                    sval = val.isoformat()
                except Exception:
                    sval = str(val)
            else:
                sval = "" if (pd.isna(val) or val is None) else str(val)
            row_vals.append(sval)
        rows.append(row_vals)
    return header, rows, len(rows)


def load_rows(path: str, delimiter: Optional[str] = None) -> Tuple[List[str], List[List[str]], int]:
    """
    Unified loader: handles .csv, .xls, .xlsx based on file extension.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv",):
        return load_csv_rows(path, delimiter=delimiter)
    elif ext in (".xls", ".xlsx"):
        return load_excel_rows(path)
    else:
        raise ValueError(f"Unsupported file extension '{ext}'. Supported: .csv, .xls, .xlsx")


# -------------------------
# Schema & metadata builders (unchanged logic)
# -------------------------
def build_frictionless_schema(header: List[str], col_infos: List[Dict[str, Any]], missing_values: List[str]) -> Dict[str, Any]:
    schema = {
        "fields": [],
        "missingValues": missing_values,
    }
    for info in col_infos:
        field = {"name": info["name"], "type": info["type"]}
        if "format" in info and info["format"]:
            field["format"] = info["format"]
        if "description" in info and info["description"]:
            field["description"] = info["description"]
        if "constraints" in info and info["constraints"]:
            field["constraints"] = info["constraints"]
        schema["fields"].append(field)
    return schema


def build_icsv_metadata_section(
    field_delimiter: str,
    header: List[str],
    rows_count: int,
    nodata_value: Optional[str],
    geometry_hint: Optional[str],
    srid_hint: Optional[str],
    application_profile: Optional[str],
) -> List[str]:
    md = []
    md.append(f"iCSV_version = 1.0")
    if application_profile:
        md.append(f"application_profile = {application_profile}")
    md.append(f"field_delimiter = {field_delimiter}")
    md.append(f"rows = {rows_count}")
    md.append(f"columns = {len(header)}")
    md.append(f"creation_date = {datetime.utcnow().isoformat()}Z")
    if nodata_value is not None:
        md.append(f"nodata = {nodata_value}")
    if geometry_hint:
        md.append(f"geometry = {geometry_hint}")
    if srid_hint:
        md.append(f"srid = {srid_hint}")
    md.append(f"generator = make_icsv.py (frictionless-based)")
    return md


def build_fields_section(header: List[str], col_infos: List[Dict[str, Any]], field_delimiter: str) -> List[str]:
    delim = field_delimiter
    def _join(vals: List[Any]) -> str:
        return delim.join(["" if v is None else str(v) for v in vals])
    fields_vals = header
    types_vals = [c.get("type", "") for c in col_infos]
    min_vals = [c.get("min", "") if c.get("min", "") is not None else "" for c in col_infos]
    max_vals = [c.get("max", "") if c.get("max", "") is not None else "" for c in col_infos]
    missing_count_vals = [c.get("missing_count", 0) for c in col_infos]
    desc_vals = [c.get("description", "") or "" for c in col_infos]
    lines = []
    lines.append(f"fields = {_join(fields_vals)}")
    lines.append(f"types = {_join(types_vals)}")
    lines.append(f"min = {_join(min_vals)}")
    lines.append(f"max = {_join(max_vals)}")
    lines.append(f"missing_count = {_join(missing_count_vals)}")
    lines.append(f"description = {_join(desc_vals)}")
    return lines


def write_icsv(
    outpath: str,
    header_meta_lines: List[str],
    fields_meta_lines: List[str],
    data_header: List[str],
    rows: List[List[str]],
    field_delimiter: str,
):
    with open(outpath, "w", encoding="utf-8", newline="") as fh:
        fh.write("# iCSV 1.0 UTF-8\n")
        fh.write("# [METADATA]\n")
        for line in header_meta_lines:
            fh.write(f"# {line}\n")
        fh.write("\n")
        fh.write("# [FIELDS]\n")
        for line in fields_meta_lines:
            fh.write(f"# {line}\n")
        fh.write("\n")
        fh.write("# [DATA]\n")
        writer = csv.writer(fh, delimiter=field_delimiter)
        writer.writerow(data_header)
        for r in rows:
            if len(r) < len(data_header):
                r = r + [""] * (len(data_header) - len(r))
            writer.writerow(r)


def detect_geometry_hint(header: List[str]) -> Tuple[Optional[str], Optional[str]]:
    lower = [h.lower() for h in header]
    if "geometry" in lower:
        idx = lower.index("geometry")
        return f"column:{header[idx]}", None
    lat_idx = None
    lon_idx = None
    for i, h in enumerate(lower):
        if h in ("lat", "latitude"):
            lat_idx = i
        if h in ("lon", "lng", "longitude"):
            lon_idx = i
    if lat_idx is not None and lon_idx is not None:
        return f"column:{header[lat_idx]},{header[lon_idx]}", "EPSG:4326"
    return None, None


# -------------------------
# Main pipeline
# -------------------------
def make_icsv_from_csv(
    infile: str,
    out_icsv: Optional[str] = None,
    out_schema: Optional[str] = None,
    user_delimiter: Optional[str] = None,
    nodata_override: Optional[str] = None,
    application_profile: Optional[str] = None,
):
    if not out_icsv:
        out_icsv = os.path.splitext(infile)[0] + ".icsv"
    if not out_schema:
        out_schema = os.path.splitext(infile)[0] + "_schema.json"

    header, rows, row_count = load_rows(infile, delimiter=user_delimiter)

    # If input is CSV we use detected delim; for Excel choose '|' by default to avoid issues in iCSV header
    detected_delim = user_delimiter
    if detected_delim is None and infile.lower().endswith(".csv"):
        # sample first up to 5 lines safely
        with open(infile, "r", encoding="utf-8", errors="ignore") as fh:
            sample = "".join(islice(fh, 5))
        detected_delim = detect_delimiter(sample)
    icsv_delim = detected_delim if detected_delim and detected_delim != "," else "|"

    # Detect nodata placeholder
    if nodata_override is not None:
        nodata_value = nodata_override
    else:
        placeholder_counts: Dict[str, int] = {}
        for r in rows:
            for c in r:
                if c in COMMON_MISSING:
                    placeholder_counts[c] = placeholder_counts.get(c, 0) + 1
        nodata_value = max(placeholder_counts.items(), key=lambda x: x[1])[0] if placeholder_counts else ""

    # Build per-column info
    col_infos: List[Dict[str, Any]] = []
    # transpose columns safely
    cols: List[List[str]] = []
    if rows:
        # pad/truncate rows to header length
        fixed_rows = []
        for r in rows:
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            elif len(r) > len(header):
                r = r[: len(header)]
            fixed_rows.append(r)
        cols = list(zip(*fixed_rows))
    else:
        cols = [()] * len(header)

    for i, name in enumerate(header):
        col_values = [str(v).strip() for v in (cols[i] if rows else [])]
        pruned = [v for v in col_values if v not in COMMON_MISSING and v != ""]
        inferred_type = infer_column_type(col_values, COMMON_MISSING)
        info: Dict[str, Any] = {"name": name, "type": inferred_type}
        if inferred_type in ("integer", "number"):
            mn, mx = compute_numeric_minmax(pruned, inferred_type)
            info["min"] = mn
            info["max"] = mx
            constraints = {}
            if mn is not None:
                constraints["minimum"] = mn
            if mx is not None:
                constraints["maximum"] = mx
            if len(pruned) == len(col_values) and len(col_values) > 0:
                constraints["required"] = True
            if constraints:
                info["constraints"] = constraints
        elif inferred_type == "datetime":
            mn_dt, mx_dt = compute_datetime_minmax(pruned)
            info["min"] = mn_dt
            info["max"] = mx_dt
            constraints = {}
            if mn_dt is not None:
                constraints["minimum"] = mn_dt
            if mx_dt is not None:
                constraints["maximum"] = mx_dt
            if len(pruned) == len(col_values) and len(col_values) > 0:
                constraints["required"] = True
            if constraints:
                info["constraints"] = constraints
        else:
            if len(pruned) == len(col_values) and len(col_values) > 0:
                info["constraints"] = {"required": True}
        missing_count = sum(1 for v in col_values if v in COMMON_MISSING or v == "")
        info["missing_count"] = missing_count
        info["description"] = ""
        col_infos.append(info)

    schema = build_frictionless_schema(header, col_infos, list(COMMON_MISSING))
    geometry_hint, srid_hint = detect_geometry_hint(header)
    metadata_lines = build_icsv_metadata_section(
        field_delimiter=icsv_delim,
        header=header,
        rows_count=row_count,
        nodata_value=nodata_value,
        geometry_hint=geometry_hint,
        srid_hint=srid_hint,
        application_profile=application_profile,
    )
    fields_lines = build_fields_section(header, col_infos, icsv_delim)
    write_icsv(out_icsv, metadata_lines, fields_lines, header, rows, icsv_delim)
    print(f"Wrote iCSV -> {out_icsv}")
    with open(out_schema, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)
    print(f"Wrote Frictionless schema -> {out_schema}")
    return out_icsv, out_schema


# -------------------------
# CLI
# -------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Convert CSV or Excel (.xls/.xlsx) to iCSV + Frictionless schema.")
    p.add_argument("infile", help="Input CSV or Excel file path (.csv, .xls, .xlsx)")
    p.add_argument("--delimiter", "-d", help="Force input delimiter (CSV only; autodetect otherwise)", default=None)
    p.add_argument("--nodata", help="Force nodata placeholder value", default=None)
    p.add_argument("--app", help="Optional application profile for iCSV firstline", default=None)
    p.add_argument("--out", help="Output iCSV path (default: <infile>.icsv)", default=None)
    p.add_argument("--schema-out", help="Output schema path (default: <infile>_schema.json)", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    if args.infile.lower().endswith((".xls", ".xlsx")) and not PANDAS_AVAILABLE:
        print("ERROR: pandas is required to read Excel files. Install with:")
        print("  pip install pandas openpyxl xlrd==1.2.0")
        raise SystemExit(2)
    make_icsv_from_csv(
        infile=args.infile,
        out_icsv=args.out,
        out_schema=args.schema_out,
        user_delimiter=args.delimiter,
        nodata_override=args.nodata,
        application_profile=args.app,
    )


if __name__ == "__main__":
    main()
