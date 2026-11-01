# Dashboard validation and independent calculation evidence

## Scope and method

The course Power BI baseline was reproduced in Looker Studio because this
project is being completed on macOS. The **Baseline result** column below records
the validated values used by that Power BI-equivalent report. The **Streamlit
result** column was calculated from the five uploaded CSV exports after all four
many-to-one relationship checks passed.

All comparisons use the full period from January 2025 through December 2029 and
no dashboard filters unless a narrower scope is stated.

## Initial validation table

| Metric / scope | Baseline result | Streamlit result | Match? / explanation |
|---|---:|---:|---|
| Total revenue — five years | $42,174,440 | $42,174,440 | Match |
| Website revenue | $27,218,880 | $27,218,880 | Match |
| Brick-and-mortar revenue | $14,955,560 | $14,955,560 | Match |
| Annual revenue — 2025 | $7,181,750 | $7,181,750 | Match |
| Annual revenue — 2026 | $8,016,950 | $8,016,950 | Match |
| Annual revenue — 2027 | $8,824,720 | $8,824,720 | Match |
| Annual revenue — 2028 | $8,969,470 | $8,969,470 | Match |
| Annual revenue — 2029 | $9,181,550 | $9,181,550 | Match |
| Monthly revenue — January | $3,266,270 | $3,266,270 | Match |
| Monthly revenue — February | $1,616,410 | $1,616,410 | Match |
| Monthly revenue — March | $1,873,190 | $1,873,190 | Match |
| Monthly revenue — April | $2,173,470 | $2,173,470 | Match |
| Monthly revenue — May | $2,411,110 | $2,411,110 | Match |
| Monthly revenue — June | $2,743,370 | $2,743,370 | Match |
| Monthly revenue — July | $2,706,590 | $2,706,590 | Match |
| Monthly revenue — August | $2,718,500 | $2,718,500 | Match |
| Monthly revenue — September | $3,000,500 | $3,000,500 | Match |
| Monthly revenue — October | $3,502,890 | $3,502,890 | Match |
| Monthly revenue — November | $5,361,150 | $5,361,150 | Match |
| Monthly revenue — December | $10,800,990 | $10,800,990 | Match |
| Additional comparison — Espresso Machines revenue | $27,093,220 | $27,093,220 | Match after applying the category filter |

## Discrepancy notes

No numerical discrepancies were found. Before comparing, both reports were
aligned to the same five-year period and unfiltered scope. The Streamlit model
uses `Sales[StoreYear]` to `Survey Results[Survey ID]`; using Store ID for that
relationship would leave survey rows unmatched. Product relationships use
Product ID because product names are not unique.

The five website survey records have missing Satisfaction and Interest values.
They remain null and are excluded from averages rather than treated as zero.

## Independent calculation

`scripts/independent_check.py` independently reads `sales.csv` and `stores.csv`
with Python's standard-library `csv` module and adds revenue with `Decimal`. It
does not import pandas, Streamlit, `analytics.py`, or any dashboard function.
Run it from the repository root:

```bash
python scripts/independent_check.py \
  --sales data/processed/sales.csv \
  --stores data/processed/stores.csv
```

The independent calculation returned 25,200 Sales rows, total revenue of
$42,174,440, Website revenue of $27,218,880, and brick-and-mortar revenue of
$14,955,560. Its annual and monthly results also match the table above.

## Updated-data test

The automated test suite changes an input revenue value in memory, rebuilds the
validated model, and confirms that the dashboard total changes by the same
amount without modifying application code. This demonstrates the required
updated-data behavior while leaving the original course files unchanged.
