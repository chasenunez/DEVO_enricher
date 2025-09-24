#!/usr/bin/env python3
"""
excel_to_csv.py

Convert an Excel file (.xls or .xlsx) to one or more CSV files, one per sheet.
This script handles multiple sheets, user-specified headers, and skips blank rows.

Usage:
    python excel_to_csv.py input.xlsx [--outdir OUTDIR] [--sheets SHEET_LIST] [--header ROW]

Options:
    --outdir OUTDIR        Directory to save CSV files (default: same directory as input file)
    --sheets SHEET_LIST    Comma-separated sheet names or indices (0-based) to convert (default: all sheets)
    --header ROW           Header row index (1-based) for all sheets (skip interactive prompt)
    -h, --help             Show this help message and exit
"""

import os
import argparse
import pandas as pd
from pandas import ExcelFile

def get_sheet_list(excel, sheet_spec):
    """
    Determine which sheets to process based on user specification.
    sheet_spec: comma-separated string of sheet names or indices.
    Returns list of sheet names.
    """
    all_sheets = excel.sheet_names
    if not sheet_spec:
        return all_sheets
    chosen = []
    for part in sheet_spec.split(','):
        part = part.strip()
        if not part:
            continue
        # If numeric index
        if part.isdigit():
            idx = int(part)
            if idx < 0 or idx >= len(all_sheets):
                raise ValueError(f"Sheet index {idx} out of range")
            chosen.append(all_sheets[idx])
        else:
            # Assume sheet name
            if part not in all_sheets:
                raise ValueError(f"Sheet name '{part}' not found")
            chosen.append(part)
    return chosen

def ask_header_row(df_preview, sheet_name):
    """
    Display a preview of the sheet and ask user for header row number.
    Returns 1-based row number of header (or 0 for no header).
    """
    print(f"\nPreview of sheet '{sheet_name}' (first 5 rows):")
    print(df_preview.to_string(index=False, header=False))  # raw preview
    while True:
        resp = input(f"Enter the header row number for sheet '{sheet_name}' (1-based), or 0 for no header: ").strip()
        if resp.isdigit():
            return int(resp)
        print("Invalid input. Please enter a numeric row number or '0' for no header.")

def convert_sheet_to_csv(excel_path, sheet_name, header_row, outpath):
    """
    Read one sheet and save to CSV.
    header_row: 1-based row number of header, or 0 if no header.
    """
    if header_row > 0:
        header_index = header_row - 1
        skip_rows = list(range(header_index))
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0,
                           skiprows=skip_rows, engine=None)
    else:
        # No header: let pandas assign numeric column names
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, engine=None)
    # Drop completely empty rows and columns (all-NaN)
    df.dropna(axis=0, how='all', inplace=True)
    df.dropna(axis=1, how='all', inplace=True)
    # Write CSV
    df.to_csv(outpath, index=False)
    print(f"Wrote CSV: {outpath}")

def main():
    parser = argparse.ArgumentParser(description="Convert Excel sheets to CSV files")
    parser.add_argument("infile", help="Input Excel file path (.xlsx or .xls)")
    parser.add_argument("--outdir", help="Directory for output CSV files (default: input file directory)", default=None)
    parser.add_argument("--sheets", help="Comma-separated sheet names or indices (0-based)", default=None)
    parser.add_argument("--header", help="Header row index (1-based) to use for all sheets (skip interactive prompt)",
                        type=int, default=None)
    args = parser.parse_args()

    infile = args.infile
    outdir = args.outdir or os.path.dirname(os.path.abspath(infile))
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)

    # Load Excel file to get sheet names
    try:
        excel = ExcelFile(infile, engine=None)  # engine auto-detect (openpyxl or xlrd)
    except Exception as e:
        print(f"Error opening Excel file '{infile}': {e}")
        return

    # Determine sheets to process
    try:
        sheets = get_sheet_list(excel, args.sheets)
    except Exception as e:
        print(f"Sheet selection error: {e}")
        return

    for sheet in sheets:
        # Preview first few rows (raw, no header, to assist choosing header row)
        try:
            df_preview = pd.read_excel(infile, sheet_name=sheet, header=None, nrows=5, engine=None)
        except Exception as e:
            print(f"Failed to read sheet '{sheet}': {e}")
            continue

        # Determine header row: use provided or ask user
        if args.header:
            header_row = args.header
        else:
            header_row = ask_header_row(df_preview, sheet)

        # Construct safe output file name
        base = os.path.splitext(os.path.basename(infile))[0]
        safe_sheet = "".join(c if c.isalnum() or c in " _-" else "_" for c in sheet)
        out_filename = f"{base}_{safe_sheet}.csv"
        outpath = os.path.join(outdir, out_filename)

        # Convert the sheet to CSV
        try:
            convert_sheet_to_csv(infile, sheet, header_row, outpath)
        except Exception as e:
            print(f"Error converting sheet '{sheet}': {e}")

if __name__ == "__main__":
    main()
