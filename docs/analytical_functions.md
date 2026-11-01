# Approved analytical functions and test evidence

## Scope contract

The rules-based assistant receives the same validated rows selected by the
Category, Store Type, and Year controls on the Dashboard tab. Each function
therefore describes its exact row and date scope in its `ToolResult`. It does not
read a separate hidden dataset, memorize the original totals, or bypass active
filters.

Every function returns:

- approved function name;
- raw value calculated from the current rows;
- metric definition;
- filter/date scope;
- number of rows used;
- caveats or a structured error.

## Function inventory

| Approved function | Question answered | Allowed arguments / scope | Expected result and independent check | Outcome / limitation |
|---|---|---|---|---|
| `get_revenue_by_channel()` | How does revenue compare between Website and Brick & Mortar? | No user-supplied arguments; current validated dashboard subset | Tiny fixture: one channel totaling $350. Full-data result agrees with the independent standard-library check. | Revenue is not profit. |
| `get_annual_revenue_trend()` | How much revenue was recorded in each calendar year? | No user-supplied arguments; current validated dashboard subset | Tiny fixture: 2025 = $350. Full-data annual values agree with `docs/dashboard_validation.md`. | Descriptive historical trend, not a forecast. |
| `get_monthly_revenue_share()` | Which months contribute the most revenue, and what share does each month represent? | No user-supplied arguments; current validated dashboard subset | Tiny fixture: January = $350 and 100%. Full-data revenue agrees with all 12 monthly controls. | Denominator is total revenue in the current filtered subset. |
| `get_category_performance()` | Which product categories generate the most revenue? | No user-supplied arguments; current validated dashboard subset | Tiny fixture: Machines = $350. Full-data category totals reconcile to total revenue. | Revenue does not account for category costs or margins. |
| `data_quality_report()` | Are there missing values or duplicate rows? | No user-supplied arguments; current assistant dataset | Fixture confirms one missing amount and correct duplicate count. | Counts issues but does not silently repair them. |

## Dispatcher and routing controls

`agent.py` contains the only approved tool registry. `run_tool()` rejects names
outside that registry and rejects arguments that are not declared for the chosen
function. It never calls `eval`, `exec`, generated Python, generated SQL, a
DataFrame agent, or a code interpreter.

The rules router supports these question families:

- channel, store type, Website, or brick-and-mortar revenue;
- annual, yearly, or trend questions;
- month, monthly, season, or share questions;
- category performance;
- missing, duplicate, blank, or quality questions.

Other requests return an explicit unsupported response rather than a fabricated
answer.

## Test evidence

`tests/test_analytics.py` independently checks every function using a two-row
model whose total is $350 and can be verified by hand. Parameterized routing
tests confirm that each supported question invokes the expected approved tool.
Additional tests confirm that unknown tools, unexpected arguments, missing
columns, failed relationships, and unsupported questions are rejected.

Run the evidence:

```bash
pytest -q
```

The full-data smoke test also executed all four E-Presso functions against
25,200 validated rows without errors.
