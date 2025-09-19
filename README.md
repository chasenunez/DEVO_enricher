# make\_icsv

Generate self-documented iCSV files and a Frictionless Table Schema from plain CSV **or Excel** files.

`make_icsv` inspects tabular files and produces:

* a self-documented **iCSV** file (with `# iCSV 1.0 UTF-8`, `# [METADATA]`, `# [FIELDS]`, `# [DATA]` sections), and
* a **Frictionless** `schema.json` suitable for validation.

This README has been updated to reflect support for `.csv`, `.xls`, and `.xlsx` inputs (Excel support requires `pandas` and an Excel engine such as `openpyxl`).

## Key features

* Read `.csv`, `.xls`, `.xlsx` (first sheet) inputs.
* Automatic delimiter detection for CSVs (option to override).
* Conservative, robust type inference: `integer`, `number`, `datetime`, `string`.
* Per-column stats: min/max, missing value counts, `required` constraint where appropriate.
* Writes an iCSV header per the iCSV specification and a Frictionless Table Schema JSON.
* CLI: `python make_icsv.py input.csv` or `python make_icsv.py input.xlsx`.

## Requirements

**Python 3.8+**

Minimum runtime dependencies (add these to `requirements.txt`):

```
frictionless
pandas
openpyxl       # for .xlsx
xlrd==1.2.0    # optional: for legacy .xls support (only if you must support old .xls)
pytest         # dev / tests
python-dateutil  # optional, improves date parsing
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If you only need CSV support, `frictionless` is the minimal runtime requirement.

> If you run the script on an Excel file but `pandas` (or the appropriate engine) is missing, the script will print a friendly error and exit. Install `pandas` + `openpyxl` to enable Excel ingestion.

## Quick start

Save `make_icsv.py` in your repo (or clone) and run:

```bash
# CSV
python make_icsv.py data.csv

# Excel (XLSX)
python make_icsv.py workbook.xlsx
```

By default the tool will create:

* `data.icsv` — the iCSV file with metadata header and data section.
* `data_schema.json` — the generated Frictionless schema for validation.

## CLI usage

```
usage: make_icsv.py infile [--delimiter DELIM] [--nodata NODATA] [--app APP] [--out OUT] [--schema-out SCHEMA_OUT]

Convert CSV or Excel (.xls/.xlsx) to iCSV + Frictionless schema.

positional arguments:
  infile                Input CSV or Excel file path (.csv, .xls, .xlsx)

optional arguments:
  -h, --help            show this help message and exit
  --delimiter, -d       Force input delimiter (CSV only; autodetect otherwise)
  --nodata              Force nodata placeholder value (default: auto-detect)
  --app                 Optional application profile for iCSV firstline (written into METADATA)
  --out                 Output iCSV path (default: <infile>.icsv)
  --schema-out          Output schema path (default: <infile>_schema.json)
```

Examples:

```bash
# CSV default autodetect
python make_icsv.py observations.csv

# Force delimiter and nodata for CSV
python make_icsv.py observations.csv --delimiter ";" --nodata "-999"

# Excel input; pandas & engine required
python make_icsv.py observations.xlsx --out obs.icsv --schema-out obs_schema.json --app METEO
```

## Example iCSV header (generated)

Example of what the top of a produced iCSV looks like:

```
# iCSV 1.0 UTF-8
# [METADATA]
# iCSV_version = 1.0
# application_profile = METEO
# field_delimiter = |
# rows = 12345
# columns = 6
# creation_date = 2025-09-15T12:34:56.789012Z
# nodata = -999
# generator = make_icsv.py (frictionless-based)

# [FIELDS]
# fields = timestamp|temp_C|RH|station_id|lat|lon
# types  = datetime|number|number|string|number|number
# min    = 2020-01-01T00:00:00| -20.5| 0.0| | -90.0| -180.0
# max    = 2025-01-01T12:00:00| 45.0| 1.0| | 90.0| 180.0
# missing_count = 0|12|5|0|0|0
# description = |Air temperature (C) |Relative humidity fraction |Station identifier |Latitude |Longitude

# [DATA]
timestamp|temp_C|RH|station_id|lat|lon
2020-01-01T00:00:00|2.5|0.41|ST123|46.95|7.44
...
```

Notes:

* If the input CSV uses comma as delimiter, the tool typically chooses `|` for the iCSV `field_delimiter` to avoid ambiguity in metadata lines.
* All header lines in METADATA and FIELDS are prefixed with `#` per the iCSV spec.

## What the generated `schema.json` contains

* `fields` array with `name`, `type` and (when detected) `format`, `description`, and `constraints` (`minimum`, `maximum`, `required`).
* `missingValues` listing commonly-detected placeholders like `-999`, `NA`, `NaN`, and blank strings.

You can validate data with Frictionless:

```python
from frictionless import Resource
report = Resource(path="data_clean.csv", schema="data_schema.json").validate()
print(report.as_descriptor())
```

## Excel support — important caveats

Excel files are more complicated than CSVs. the script reads **only the first worksheet** and converts all cell values to strings (with special handling for date/time-like cells). That choice is conservative and avoids surprising type coercions, but has consequences:

* **Merged cells**: may be expanded to values or empty cells depending on engine — inspect the sheet first.
* **Formulas**: the reader typically returns last calculated values, not the formula text.
* **Multiple sheets**: only the first sheet is read by default.
* **Rich formatting / comments / macros**: these are ignored; if those are important you should pre-process or export to CSV.
* **Numeric formatting**: Excel-formatted numbers/dates may require additional handling; the script attempts ISO date detection from cell values where possible.

Recommendations:

* Prefer exporting to CSV if you control the upstream workflow.
* Add a manual review step on complex spreadsheets.
* If you need to read a specific sheet, add a `--sheet` flag (not currently included) — contact me and I’ll add it.

## Design decisions & limitations

* Type inference is conservative: integer → number → datetime → string. Mixed-format columns often fall back to `string`.
* Datetime detection is based on `datetime.fromisoformat()` plus common `strptime` formats. Installing `python-dateutil` improves parsing coverage.
* Column `description` fields are left blank by default; you can populate them manually or via an external mapping / LLM.
* The tool attempts not to change raw data — it writes an iCSV header and the input data rows (padding/truncating rows to match header length if necessary).

## Tests & CI

* A suggested test (included in repo) uses `pytest` to run a small smoke-test: create a tiny CSV/XLSX and run `make_icsv.py` to confirm outputs are written.
* For CI (GitLab/GitHub Actions), use a Python image and install `requirements.txt` before running `pytest`. If your CI previously relied on `herokuish buildpack test`, replace that with an explicit `pip install -r requirements.txt` + `pytest` step (see project CI config).

## Extending the tool (ideas)

* `--sheet` flag to choose an Excel worksheet.
* Option to preserve numeric types from Excel (avoid casting everything to strings) — would improve numeric detection but increase complexity.
* `--validate` flag to run Frictionless validation automatically and emit a validation report.
* Optional LLM-based automatic column descriptions (careful with sensitive data).

## Contributing

Contributions welcome! Suggested workflow:

1. Fork the repo and create a feature branch.
2. Add tests and update documentation for new features.
3. Open a pull request describing the change.

Follow PEP8 and include tests for major parsing/inference behaviors. See `CONTRIBUTING.md` for more details.

## License

This project is provided under the **MIT License**. See `LICENSE` for details.

If you want, I can:

* add a short section with an example Excel-based pytest test (creates an XLSX and runs the script), or
* add a `--sheet` CLI option and update the script and tests accordingly — pick one and I’ll produce the code change.
