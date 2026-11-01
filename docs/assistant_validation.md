# Working assistant and modified-data validation

## Assistant implementation

The hosted application uses an honestly labeled **rules-based analytical
assistant**. It does not call a paid language-model API. Supported questions are
routed to allowlisted Python functions that calculate from the current uploaded
and filtered data. Every response includes a tool log containing the function
name, arguments, raw `ToolResult`, row count, and filter/date scope.

The application limits each browser session to 15 questions. Because rules mode
uses no external provider, API quota and provider outages do not apply. File and
analytical failures are caught and shown as readable errors; no numerical result
is estimated. `.streamlit/secrets.toml`, `.env`, raw files, and generated outputs
are excluded from Git.

## Exactly $1,000 modified-data test

`scripts/run_modified_data_test.py` creates a temporary copy of `sales.csv`,
changes exactly one stored Revenue value, reloads that separate file through the
normal model functions, runs dashboard/filter/assistant checks, and deletes the
temporary directory. It hashes the original before and after the experiment.

| Changed record / field | Original value | Modified value | Expected total change | Actual total change | Chart / filtered check | Assistant updated? |
|---|---:|---:|---:|---:|---|---|
| `S0020250101` / `Revenue` | $6,780 | $7,780 | Exactly +$1,000 | +$1,000 | Website, Beans, 2025, and January each changed by exactly +$1,000 | Yes; `get_revenue_by_channel()` increased Website revenue by exactly $1,000 |

The original and final SHA-256 fingerprints were identical:
`d382a7aec654599b4db14af02ca2d4c1c724971dc1edb4c4d85b6d53c6b877a3`.
The original file was therefore unchanged/restored after the temporary test.

Run the evidence:

```bash
python scripts/run_modified_data_test.py --data-dir data/processed
```

## Required assistant test log

| Test / question | Function used and arguments | Expected result / behavior | Actual result | Pass / fail | Revision and retest evidence |
|---|---|---|---|---|---|
| 1 — “Show the annual revenue trend.” | `get_annual_revenue_trend`, `{}` | Independently validated annual revenue values | 2025 $7,181,750; 2026 $8,016,950; 2027 $8,824,720; 2028 $8,969,470; 2029 $9,181,550 | Pass | Results match the independent validation table |
| 2 — “How does revenue compare by channel?” | `get_revenue_by_channel`, `{}` | Website $27,218,880; Brick & Mortar $14,955,560 | Raw result returned both expected values; Website exceeds Brick & Mortar by $12,263,320 | Pass | Comparison independently reproduced with the standard-library script |
| 3 — “Which channel is most profitable?” | `explain_limitation`, `{"topic": "profitability"}` | Recognize that revenue alone cannot establish profitability | `can_determine_profitability: false`; missing costs/cost of goods sold | Pass | Explicit limitation tool prevents revenue from being mislabeled as profit |
| 4 — “Does satisfaction cause higher revenue?” | `explain_limitation`, `{"topic": "causation"}` | Distinguish association from causation | `can_establish_causation: false`; observational data supports association only | Pass | Initially unsupported; added the approved limitation function and retest passed |
| 5 — Updated data: “How does revenue compare by channel?” | `get_revenue_by_channel`, `{}` | Website answer rises by exactly $1,000 when the Website row changes | Website changed from $27,218,880 to $27,219,880 | Pass | Temporary modified data reloaded without code edits; original restored |
| Edge — “What is the meaning of life?” | `unsupported_request`, `{}` | Refuse unsupported request without inventing a result | Explicit unsupported response plus structured tool log and supported-topic list | Pass | Refined unsupported handling so even rejected requests show function, arguments, raw result, and scope |

## Correction and retest summary

The first rules router treated the causal-judgment question as a generic
unsupported request. That response was safe but not sufficiently informative.
The smallest correction added `explain_limitation()` with allowlisted
`profitability` and `causation` topics. New tests confirm the assistant now names
the missing cost information and states that observational satisfaction/revenue
data cannot establish causation. Related dispatcher and unsupported-request
tests still pass.
