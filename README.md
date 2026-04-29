# DEVO_enricher

Takes a plain CSV, looks at every column (type, min/max, missing values), and writes:

- a self-documenting **iCSV** file (with `# [METADATA]`, `# [FIELDS]`, `# [DATA]` sections), and
- a **Frictionless** schema JSON suitable for validation.

Sister tool to **DEVO_validator**, which does the validation step. The pipeline:

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

Uses [frictionless](https://framework.frictionlessdata.io) only for schema compatibility; the rest is standard library.

## Install

```bash
pip install frictionless
```

Python 3.8+.

## Run

```bash
python DEVO_enricher.py data.csv
# → data.icsv, data_schema.json
```

Common flags:

```
--delimiter, -d   Force input delimiter (default: autodetect)
--nodata          Force the nodata placeholder (default: detect from data)
--app             Application profile string for the iCSV first line
--out             Output iCSV path
--schema-out      Output schema path
```

Examples:

```bash
python DEVO_enricher.py observations.csv --delimiter ";" --nodata "-999"
python DEVO_enricher.py observations.csv --out obs.icsv --app METEO
```

A separate Excel-to-CSV pre-step lives at `Features/xls_to_csv.py` for `.xlsx` inputs.

## What you get

```
# iCSV 1.0 UTF-8
# [METADATA]
# iCSV_version = 1.0
# application_profile = METEO
# field_delimiter = |
# rows = 12345
# columns = 6
# creation_date = 2025-09-15T12:34:56Z
# nodata = -999
# generator = DEVO_enricher.py (frictionless-based)
#
# [FIELDS]
# fields = timestamp|temp_C|RH|station_id|lat|lon
# types  = datetime|number|number|string|number|number
# min    = 2020-01-01T00:00:00| -20.5| 0.0| | -90.0| -180.0
# max    = 2025-01-01T12:00:00| 45.0| 1.0| | 90.0| 180.0
# missing_count = 0|12|5|0|0|0
#
# [DATA]
timestamp|temp_C|RH|station_id|lat|lon
2020-01-01T00:00:00|2.5|0.41|ST123|46.95|7.44
...
```

The `field_delimiter` defaults to `|` to avoid ambiguity if the input is comma-separated.

The schema includes `missingValues` (with common placeholders like `-999`, `NA`, `NaN`) and per-field `constraints` (`minimum`, `maximum`, `required`). Use it like any Frictionless schema:

```python
from frictionless import Resource
report = Resource(path="data_clean.csv", schema="data_schema.json").validate()
print(report.as_descriptor())
```

## Limitations

- Type inference is conservative: integer → number → datetime → string. Mixed-format columns fall back to string.
- Datetime parsing uses `datetime.fromisoformat()` plus a small list of common `strptime` formats. For more exotic dates, add `python-dateutil` or supply a custom schema.
- Column descriptions are left blank — fill them in by hand.
- The script doesn't change your raw data; it only writes the iCSV header and copies the data through (padding rows to header length where needed).

## License

MIT. See `LICENSE`.
