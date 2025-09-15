# csv_enrichment engine
# trying to invert some of the frictionless code that makes a schema from iCSV's metadata section in order to ingest a normal CSV, and then spit out a metadata section that can be combined with the [DATA] cetion in order to make an iCSV. the benefit of doing it this way is that we can now *create* a metadata section that makes the best schema for data checking. ideally, then, researchers can just feed in a data csv, get back an icsv, and then have the ability to check their data, as well as ingest into envidat etc. with greater finadability, Accessability, nteroperability, and Reusability.

#!/usr/bin/env python3
"""
make_icsv.py

Generate a self-documented iCSV (iCSV 1.0) from a plain CSV and write a
Frictionless Table Schema JSON for validation.

Usage:
    python make_icsv.py input.csv [--delimiter DELIM] [--application APP] [--nodata NODATA]

Notes:
- Requires: frictionless (pip install frictionless)
- The script uses the frictionless Resource to load the CSV and count rows/columns,
  and uses built-in heuristics to infer types and simple constraints.
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from frictionless import Resource

# Common placeholders considered as missing values
COMMON_MISSING = {"", "NA", "N/A", "na", "n/a", "NULL", "null", "nan", "NaN", "-999", "-999.0", "-999.000000"}


# -------------------------
# Type inference utilities
# -------------------------
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def try_parse_datetime(s: str) -> bool:
    """
    Try to detect if a string is a datetime. We attempt ISO parsing first,
    then try common strptime formats.
    """
    if not s:
        return False
    s = s.strip()
    # Quick heuristic: contains '-' or ':' or 'T' or '/' and digits
    if not re.search(r"[0-9]", s):
        return False

    # 1) Try native ISO parser (Python 3.7+)
    try:
        # fromisoformat supports many ISO-like formats but not all; ignore timezone complexities here
        datetime.fromisoformat(s)
        return True
    except Exception:
        pass

    # 2) Try a few common formats
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
    """
    Infer a Frictionless-style type for a column given sample values.
    Returns one of: 'integer', 'number', 'datetime', 'string'
    """
    # Filter out missing placeholders
    pruned = [v.strip() for v in values if v is not None and v.strip() not in missing_values]
    if not pruned:
        return "string"  # no data -> default to string

    is_int = True
    is_float = True
    is_datetime = True

    for v in pruned:
        if not INT_RE.match(v):
            is_int = False
        if not (INT_RE.match(v) or FLOAT_RE.match(v)):
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
    """
    Given pruned (non-missing) list of numeric-like strings and a declared type,
    compute min and max (return None if not computable).
    """
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
    """
    Compute min/max datetimes and return ISO strings if possible.
    """
    parsed = []
    for v in pruned:
        try:
            # try fromisoformat first, fallback to several formats
            try:
                dt = datetime.fromisoformat(v)
            except Exception:
                # try known formats
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
# CSV / Frictionless helpers
# -------------------------
def detect_delimiter(sample_text: str) -> str:
    """
    Use csv.Sniffer to detect delimiter. Fallback to comma.
    """
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=[",", "|", ";", ":", "\t", "/"])
        return dialect.delimiter
    except Exception:
        return ","


def load_rows_with_frictionless(path: str, delimiter: Optional[str] = None) -> Tuple[List[str], List[List[str]], int]:
    """
    Load header and rows using frictionless (and csv fallback). Returns (header, rows, row_count).
    We still use csv module for reliable delimiter control, but frictionless is used to create a Resource
    to show we used it (and for optional validation later).
    """
    # Try reading a small sample to detect delimiter if not provided
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        sample = "".join([next(fh) for _ in range(10)])
    detected = detect_delimiter(sample) if delimiter is None else delimiter

    # Use frictionless Resource to read and also verify we can open the file
    try:
        # frictionless will also infer schema if needed; we only instantiate to follow the requirement
        _ = Resource(path, format="csv", control={"delimiter": detected})
    except Exception:
        # If frictionless fails, continue — csv fallback will handle it
        pass

    # Use csv module with the detected delimiter to build rows
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


# -------------------------
# Build schema & metadata
# -------------------------
def build_frictionless_schema(header: List[str], col_infos: List[Dict[str, Any]], missing_values: List[str]) -> Dict[str, Any]:
    """
    Build a Frictionless-compatible schema (dict that can be dumped to JSON).
    col_infos is a list of dictionaries containing: name, type, format (optional), constraints (dict)
    """
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
    """
    Prepare lines for the METADATA section (each line without '# ' prefix).
    """
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
    # recommended but optional
    md.append(f"generator = make_icsv.py (frictionless-based)")
    return md


def build_fields_section(header: List[str], col_infos: List[Dict[str, Any]], field_delimiter: str) -> List[str]:
    """
    Build the list of lines in the FIELDS section (without '# ' prefix).
    Each line is 'key = v1{delim}v2{delim}v3...'
    We'll include: fields, types, min, max, missing_count, description
    """
    delim = field_delimiter
    # Helper to join values ensuring delimiter presence is safe (we won't quote inside metadata)
    def _join(vals: List[str]) -> str:
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
    # You could add units, standard_name, timestamp_meaning lines here similarly.
    return lines


# -------------------------
# iCSV writer
# -------------------------
def write_icsv(
    outpath: str,
    header_meta_lines: List[str],
    fields_meta_lines: List[str],
    data_header: List[str],
    rows: List[List[str]],
    field_delimiter: str,
):
    """
    Write the iCSV file with proper '#' header lines and the DATA section.
    """
    with open(outpath, "w", encoding="utf-8", newline="") as fh:
        # Firstline
        fh.write("# iCSV 1.0 UTF-8\n")
        # METADATA
        fh.write("# [METADATA]\n")
        for line in header_meta_lines:
            fh.write(f"# {line}\n")
        fh.write("\n")
        # FIELDS
        fh.write("# [FIELDS]\n")
        for line in fields_meta_lines:
            fh.write(f"# {line}\n")
        fh.write("\n")
        # DATA
        fh.write("# [DATA]\n")
        # Write data using csv.writer so quoting is correct
        writer = csv.writer(fh, delimiter=field_delimiter)
        writer.writerow(data_header)
        for r in rows:
            # ensure row has same length as header
            if len(r) < len(data_header):
                r = r + [""] * (len(data_header) - len(r))
            writer.writerow(r)


# -------------------------
# Heuristics for geometry/srid
# -------------------------
def detect_geometry_hint(header: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Basic heuristics: if header contains 'lat' and 'lon' (or 'latitude'/'longitude'),
    set geometry to 'column:lat,lon' and srid to EPSG:4326.
    If header contains 'geometry' column, return 'column:geometry'.
    Otherwise return (None, None).
    """
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
    """
    Core function: loads CSV, infers metadata, writes iCSV and schema JSON.
    """
    if not out_icsv:
        out_icsv = os.path.splitext(infile)[0] + ".icsv"
    if not out_schema:
        out_schema = os.path.splitext(infile)[0] + "_schema.json"

    header, rows, row_count = load_rows_with_frictionless(infile, delimiter=user_delimiter)

    # Decide on field_delimiter for iCSV: default to '|' if input delimiter is comma to avoid common CSV pitfalls.
    # But prefer the detected delimiter if provided by user or if input file uses something else.
    detected_delim = user_delimiter
    if detected_delim is None:
        # try to detect from infile sample
        with open(infile, "r", encoding="utf-8", errors="ignore") as fh:
            sample = "".join([next(fh) for _ in range(5)])
        detected_delim = detect_delimiter(sample)
    # Choose iCSV field_delimiter: if comma, prefer '|' to make metadata merging less ambiguous.
    icsv_delim = detected_delim if detected_delim != "," else "|"

    # Detect nodata placeholder: if user provided, use that; else try to infer the most common placeholder
    if nodata_override is not None:
        nodata_value = nodata_override
    else:
        # check across cells for common missing placeholders
        placeholder_counts: Dict[str, int] = {}
        for r in rows:
            for c in r:
                if c in COMMON_MISSING:
                    placeholder_counts[c] = placeholder_counts.get(c, 0) + 1
        # pick the most common if any, else empty string
        if placeholder_counts:
            nodata_value = max(placeholder_counts.items(), key=lambda x: x[1])[0]
        else:
            nodata_value = ""

    # Build per-column info
    col_infos: List[Dict[str, Any]] = []
    # transpose columns
    cols: List[List[str]] = []
    if rows:
        # normal transpose: ensure rows are padded to header len
        for r in rows:
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            elif len(r) > len(header):
                r = r[: len(header)]
        cols = list(zip(*rows))  # tuples
    else:
        cols = [()] * len(header)

    # Compute stats and infer types
    for i, name in enumerate(header):
        # column values as strings
        col_values = [str(v).strip() for v in (cols[i] if rows else [])]
        # pruned: non-missing values
        pruned = [v for v in col_values if v not in COMMON_MISSING and v != ""]
        inferred_type = infer_column_type(col_values, COMMON_MISSING)
        info: Dict[str, Any] = {"name": name, "type": inferred_type}
        # constraints and min/max
        if inferred_type in ("integer", "number"):
            mn, mx = compute_numeric_minmax(pruned, inferred_type)
            info["min"] = mn
            info["max"] = mx
            constraints = {}
            if mn is not None:
                constraints["minimum"] = mn
            if mx is not None:
                constraints["maximum"] = mx
            # if column has no missing entries -> required
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
            # strings: maybe set required if no missing
            if len(pruned) == len(col_values) and len(col_values) > 0:
                info["constraints"] = {"required": True}

        # missing count and description (empty for now)
        missing_count = sum(1 for v in col_values if v in COMMON_MISSING or v == "")
        info["missing_count"] = missing_count
        info["description"] = ""  # placeholder: user can fill later
        # convert min/max to simple serializable forms if numeric; leave others as-is
        col_infos.append(info)

    # Build frictionless schema
    schema = build_frictionless_schema(header, col_infos, list(COMMON_MISSING))

    # Detect geometry / srid hints
    geometry_hint, srid_hint = detect_geometry_hint(header)

    # Build metadata section lines
    metadata_lines = build_icsv_metadata_section(
        field_delimiter=icsv_delim,
        header=header,
        rows_count=row_count,
        nodata_value=nodata_value,
        geometry_hint=geometry_hint,
        srid_hint=srid_hint,
        application_profile=application_profile,
    )

    # Build fields section lines
    fields_lines = build_fields_section(header, col_infos, icsv_delim)

    # Write iCSV
    write_icsv(out_icsv, metadata_lines, fields_lines, header, rows, icsv_delim)
    print(f"Wrote iCSV -> {out_icsv}")

    # Write schema JSON
    with open(out_schema, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)
    print(f"Wrote Frictionless schema -> {out_schema}")

    return out_icsv, out_schema


# -------------------------
# CLI
# -------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Convert CSV to iCSV + Frictionless schema.")
    p.add_argument("infile", help="Input CSV file path")
    p.add_argument("--delimiter", "-d", help="Force input delimiter (default: autodetect)", default=None)
    p.add_argument("--nodata", help="Force nodata placeholder value", default=None)
    p.add_argument("--app", help="Optional application profile for iCSV firstline", default=None)
    p.add_argument("--out", help="Output iCSV path (default: <infile>.icsv)", default=None)
    p.add_argument("--schema-out", help="Output schema path (default: <infile>_schema.json)", default=None)
    return p.parse_args()


def main():
    args = parse_args()
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
