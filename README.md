**DEVO_enricher** is a small, modular Python tool that:
- a plain comma separated values file (CSV)
- inspects each column (type inference, min/max, missing values)
- Generates a self-documented **iCSV** file (with `# iCSV 1.0 UTF-8`, `# [METADATA]`, `# [FIELDS]`, `# [DATA]` sections), and
* a **Frictionless** `schema.json` suitable for validation.

It uses the [frictionless](https://framework.frictionlessdata.io) library for reading and schema compatibility and only otherwise depends on Python’s standard library.

### Data Enrichment and Validation Orchestrator (DEVO) construct
```
       User                           Admin
     Front-End                       Back-End 
┌─────────────────┐ ┌──────────────────────────────────────────┐
│                 │ │                        ┌─────────────┐   │
│ ┌─────────────┐ │ │  ┌────────────────┐    │  Validation │   │
│ │   Standard  │ │ │  │                ├───►│    Schema   ├─┐ │
│ │  .CSV file  ├─┼─┼─►│    **DEVO**    │    └─────────────┘ │ │
│ └─────────────┘ │ │  │  **enricher**  │    ┌─────────────┐ │ │
│                 │ │  │                ├───►│   Enriched  │ │ │
│                 │ │  └────────────────┘    │  .iCSV file ├─┤ │
│                 │ │                        └─────────────┘ │ │
│               ◄─┼─┼────────────────────────────────────────┘ │
│                 │ │                        ┌─────────────┐   │
│                 │ │  ┌────────────────┐    │ Informative │   │
│ ┌─────────────┐ │ │  │                ├───►│    Errors   ├─┐ │
│ │   Enriched  │ │ │  │      DEVO      │    └─────────────┘ │ │
│ │  .iCSV file ├─┼─┼─►│    validator   │    ┌─────────────┐ │ │
│ └─────────────┘ │ │  │                ├───►│  Validated  │ │ │
│                 │ │  └────────────────┘    │ .iCSV file  ├─┤ │
│                 │ │                        └─────────────┘ │ │
│               ◄─┼─┼────────────────────────────────────────┘ │
│ ┌─────────────┐ │ │  ┌────────────────┬──── To EnviDat Repo ─┼──►
│ │  Validated  │─┼─┼─►│   WSL/ENVIDAT  │    ┌─────────────┐   │
│ │ .iCSV file  │ │ │  │    UPLOADER    ├───►│     DOI     ├─┐ │
│ └─────────────┘ │ │  └────────────────┘    └─────────────┘ │ │
│               ◄─┼─┼────────────────────────────────────────┘ │
└─────────────────┘ └──────────────────────────────────────────┘

```

# Features

* Automatic delimiter detection (with the option to override).
* Conservative, robust type inference: `integer`, `number`, `datetime`, `string`.
* Per-column stats: min/max, missing value counts, `required` constraint where appropriate.
* Writes an iCSV header with required and recommended metadata keys.
* Produces a Frictionless-compatible schema JSON (including `missingValues` and field `constraints`).
* CLI: `python DEVO_enricher.py input.csv` — easy to integrate into workflows.

# Requirements

* Python 3.8+ (works with 3.9, 3.10, 3.11)
* `frictionless` (installable via pip)

Install dependency:

```bash
pip install frictionless
```

# Quick start

Save the script as `DEVO_enricher.py` (or clone this repo) and run:

```bash
python DEVO_enricher.py data.csv
```

By default this will create:

* `data.icsv` — the iCSV file with metadata header and data section.
* `data_schema.json` — the generated Frictionless schema for validation.

# Usage & CLI options

```text
usage: DEVO_enricher.py infile [--delimiter DELIM] [--nodata NODATA] [--app APP] [--out OUT] [--schema-out SCHEMA_OUT]

Convert CSV to iCSV + Frictionless schema.

positional arguments:
  infile                Input CSV file path

optional arguments:
  -h, --help            show this help message and exit
  --delimiter, -d       Force input delimiter (default: autodetect)
  --nodata              Force nodata placeholder value (default: auto-detect)
  --app                 Optional application profile for iCSV firstline (written into METADATA)
  --out                 Output iCSV path (default: <infile>.icsv)
  --schema-out          Output schema path (default: <infile>_schema.json)
```

Examples:

```bash
# Basic
python DEVO_enricher.py observations.csv

# Force delimiter and nodata
python DEVO_enricher.py observations.csv --delimiter ";" --nodata "-999"

# Custom output names and app profile
python DEVO_enricher.py observations.csv --out obs.icsv --schema-out obs_schema.json --app METEO
```

# Example iCSV header (generated)

Below is a short example of what the beginning of an iCSV file produced by `DEVO_enricher.py` looks like.

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
# generator = DEVO_enricher.py (frictionless-based)

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

* `field_delimiter` in the metadata is chosen to avoid ambiguity (if the input CSV uses `,`, the tool prefers `|` for the iCSV header).
* All metadata header lines are prefixed with `#` as required by the iCSV spec.

# What the generated `schema.json` contains

* `fields` with `name`, `type` and optionally `format`, `description` and `constraints` (`minimum`, `maximum`, `required`).
* `missingValues` listing commonly-detected placeholders like `-999`, `NA`, `NaN`, `""`.

This schema can be used with Frictionless `Resource` validation:

```python
from frictionless import Resource
report = Resource(path="data_clean.csv", schema="data_schema.json").validate()
print(report.as_descriptor())
```

# Design decisions & limitations

* Type inference is conservative: it tests integer → number → datetime → string. If the uploaded data contains complex formats (mixed types in a column), the script will fall back to `string`. This probably a problem for dates. therefore:
* Datetime detection uses `datetime.fromisoformat()` and a set of common `strptime` formats. For more robust parsing, consider adding `python-dateutil` (not included to avoid extra dependency).
* Column `description` fields are left blank by default. You can fill them manually or extend the script to call an LLM or a mapping dictionary for domain-specific descriptions.
* The script prefers not to change the raw data; it only writes a cleaned iCSV header and writes the CSV data as-is (padding/truncating rows to match the header length where needed).

# Extending the tool (ideas)

* Add `--validate` flag to run Frictionless validation automatically after generation and write a validation report.
* date handling is a bit fragile, so we could integrate `dateutil.parser` for robust date parsing.

# Contributing

Contributions welcome! Suggested workflow:

1. Fork the repo and create a feature branch.
2. Add tests and update documentation for new features.
3. Open a pull request describing the changes.

Please follow idiomatic Python style (PEP8) and include tests for major parsing/inference behaviors.

# License

This project is provided under the **MIT License**. See `LICENSE` for details.
