# E-Presso BI Analyst

Streamlit business intelligence application for E-Presso sales and customer
survey analysis, developed from the official course starter template.

## What this application does

The application lets a manager upload a CSV, tab-delimited text file, or Excel
workbook and immediately inspect its rows, columns, duplicate records, missing
values, data types, and preview. Later checkpoints will add validated E-Presso
KPIs, interactive charts, and a controlled analytical assistant.

## Live app

The Streamlit Community Cloud URL will be added after the Checkpoint 0 deployment.
The completed prerequisite analysis is available in the
[live Looker Studio report](https://datastudio.google.com/reporting/8d641dde-a08f-4db8-bf05-8e6a3a089f44).

## How to use it

1. Open the hosted app or run it locally.
2. Use the sidebar to upload a CSV, TXT, TSV, XLSX, or XLS file.
3. For an Excel workbook, select the worksheet to inspect.
4. Review the profile and first 50 rows on **Data and profile**.

The original E-Presso sources are an Access sales database, an Excel survey
workbook, and a tab-delimited stores file. The local preparation script converts
them into uploadable CSV files. Raw data and generated outputs are excluded from
Git.

## Data model

The Sales table contains 25,200 rows at the grain of one store, month, and
product. The verified model uses four many-to-one left joins:

| Sales key | Lookup key | Added information |
|---|---|---|
| `Category ID` | `Categories[Category ID]` | Category name |
| `Product ID` | `Products[Product ID]` | Product name |
| `Store ID` | `Stores[ID]` | Store type and geography |
| `StoreYear` | `Survey Results[Survey ID]` | Annual survey values |

`StoreYear` must join to `Survey ID`; joining `Store ID` directly to `Survey ID`
produces no matches. Product joins use `Product ID` because product names are not
unique. Each merge is validated as many-to-one and checked for unmatched keys,
changed row counts, and changed revenue.

## Metric definitions

- **Revenue:** sum of the source `Revenue` field for the selected scope.
- **Channel revenue:** revenue grouped by Website or Brick & Mortar.
- **Annual trend:** revenue grouped by calendar year.
- **Monthly pattern:** revenue grouped by calendar month.
- **Average satisfaction:** mean of non-null annual Satisfaction scores.

Revenue is not profit because the source data does not include costs. Missing
survey values are excluded from averages rather than treated as zero.

## Assistant

The current starter uses a rules-based dispatcher. It may call only approved,
tested functions in `analytics.py`; it cannot execute generated code or modify
data. At Checkpoint 0, its implemented route reports duplicate and missing-value
counts. Later checkpoints will add E-Presso-specific analytical tools.

## Validation

The local preparation pipeline checks source row counts, key uniqueness, missing
values, relationship coverage, and revenue preservation after every join. The
prepared table remains at 25,200 rows and reconciles to the independently checked
five-year revenue control total of **$42,174,440**. The starter test suite also
uses small, hand-checkable examples to verify totals, filters, grouping, merge
fan-out detection, and assistant restrictions.

Detailed evidence:

- [Data dictionary](docs/data_dictionary.md)
- [PBIX migration, command-line methods, and AI-use report](docs/pbix_migration_methods.md)

## Analytical methodology

The original sources were profiled before analysis. On macOS, `mdb-export` from
`mdbtools` reads the Access tables without modifying them; pandas and openpyxl
read the text and Excel sources. Identifiers and postal codes stay as text,
sales dates and revenue are converted to analytical types, and missing website
survey scores remain null. `scripts/prepare_data.py` performs the four documented
joins and stops if a join changes the sales grain or revenue total. The validated
flat table supplies the Looker Studio prerequisite and will support the
Streamlit analysis.

## Limitations

- Revenue cannot answer profitability questions without cost data.
- The website has no Satisfaction or Interest survey values.
- Survey association does not establish causation.
- The Checkpoint 0 app profiles one uploaded table; multi-table E-Presso analysis
  is added in later checkpoints.

## Files

| File | Purpose |
|---|---|
| `streamlit_app.py` | Screen layout, upload, and interaction |
| `analytics.py` | Testable metrics and analytical functions |
| `agent.py` | Approved tool registry, dispatcher, and router |
| `scripts/prepare_data.py` | Commented source preparation and validated joins |
| `tests/` | Tests with hand-checkable answers |
| `docs/` | Data model, migration method, and AI-use documentation |
| `requirements.txt` | Packages required by the hosted app |

## Run it

Install the development requirements and start the app:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
streamlit run streamlit_app.py
```

To rebuild the validated analytical files on macOS, first install `mdbtools`,
then run:

```bash
brew install mdbtools
python scripts/prepare_data.py --input-dir .. --output-dir data/processed
```

Deploy this repository on Streamlit Community Cloud with branch `main` and main
file `streamlit_app.py`.

## Secrets

Never commit API keys. Use Streamlit Secrets and follow
`.streamlit/secrets.toml.example` if a later checkpoint adds an external model.
