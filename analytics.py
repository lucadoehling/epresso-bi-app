"""Business logic. Keep Streamlit code OUT of this file so every function can be
tested on its own and reused by the assistant."""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field

import pandas as pd

EXCEL_EXT = ('.xlsx', '.xlsm', '.xls')
TEXT_EXT = ('.csv', '.txt', '.tsv')

# Checkpoint 1 metadata. These statements describe the source grain; they are
# documentation, not calculated results. Table identity is verified from the
# uploaded columns instead of trusting a filename.
EPRESSO_TABLES = {
    'Sales': {
        'required': {'Sales ID', 'Date', 'Store ID', 'StoreYear', 'Category ID',
                     'Product ID', 'Revenue'},
        'grain': 'One monthly revenue record for one store and one product.',
        'key': 'Sales ID',
    },
    'Categories': {
        'required': {'Category ID', 'Category'},
        'grain': 'One product category per Category ID.',
        'key': 'Category ID',
    },
    'Products': {
        'required': {'Product ID', 'Product'},
        'grain': 'One product per Product ID; product names are not necessarily unique.',
        'key': 'Product ID',
    },
    'Stores': {
        'required': {'ID', 'StoreType', 'Market'},
        'grain': 'One physical store or website sales channel per store ID.',
        'key': 'ID',
    },
    'Survey Results': {
        'required': {'Survey ID', 'Store ID', 'Year', 'Satisfaction', 'Interest'},
        'grain': 'One annual survey result per store or website.',
        'key': 'Survey ID',
    },
}

EPRESSO_RELATIONSHIPS = (
    ('Category', 'Category ID', 'Categories', 'Category ID'),
    ('Product', 'Product ID', 'Products', 'Product ID'),
    ('Store', 'Store ID', 'Stores', 'ID'),
    ('Survey', 'StoreYear', 'Survey Results', 'Survey ID'),
)


# ---------------------------------------------------------------- loading
def excel_sheet_names(file_bytes: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


def load_table(file_bytes: bytes, filename: str, sheet_name=0) -> pd.DataFrame:
    """Read an uploaded CSV / TXT / TSV / Excel file into a DataFrame."""
    name = filename.lower()
    buffer = io.BytesIO(file_bytes)
    if name.endswith(EXCEL_EXT):
        return pd.read_excel(buffer, sheet_name=sheet_name)
    if name.endswith(TEXT_EXT):
        return pd.read_csv(buffer, sep=None, engine='python')  # sniffs the delimiter
    raise ValueError(f'Unsupported file type: {filename}')


def profile_table(df: pd.DataFrame) -> dict:
    """Basic profile: size, duplicates, missing values, data types."""
    missing = df.isna().sum()
    return {
        'rows': len(df),
        'columns': df.shape[1],
        'duplicate_rows': int(df.duplicated().sum()),
        'missing': pd.DataFrame({
            'column': missing.index,
            'missing': missing.values,
            'pct_missing': (missing.values / max(len(df), 1) * 100).round(2),
        }),
        'dtypes': pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str).values}),
    }


def identify_epresso_table(df: pd.DataFrame) -> str | None:
    """Identify an E-Presso table from its required columns.

    Column evidence is safer than a filename: a renamed upload still works, and
    a file with the wrong structure is not silently assigned the wrong grain.
    """
    columns = set(df.columns)
    matches = [name for name, spec in EPRESSO_TABLES.items()
               if spec['required'].issubset(columns)]
    return matches[0] if len(matches) == 1 else None


def key_profile(df: pd.DataFrame, key: str) -> dict:
    """Describe whether a candidate one-side key is complete and unique."""
    if key not in df.columns:
        return {'key': key, 'dtype': 'missing', 'missing': None,
                'duplicate_values': None, 'unique': False}
    return {
        'key': key,
        'dtype': str(df[key].dtype),
        'missing': int(df[key].isna().sum()),
        'duplicate_values': int(df[key].duplicated().sum()),
        'unique': bool(df[key].notna().all() and not df[key].duplicated().any()),
    }


def check_epresso_relationships(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Validate the four proposed joins against the uploaded tables.

    Each relationship is tested as a many-to-one LEFT JOIN from Sales. The
    revenue control is calculated from the upload before and after the join; no
    source row count or revenue amount is hardcoded.
    """
    required_names = {'Sales', 'Categories', 'Products', 'Stores', 'Survey Results'}
    if not required_names.issubset(tables):
        return pd.DataFrame()

    sales = tables['Sales']
    if 'Revenue' not in sales.columns:
        return pd.DataFrame()
    revenue = pd.to_numeric(sales['Revenue'], errors='coerce')
    before_total = float(revenue.sum())
    rows = []

    for label, left_key, table_name, right_key in EPRESSO_RELATIONSHIPS:
        dimension = tables[table_name]
        right = key_profile(dimension, right_key)
        left_dtype = str(sales[left_key].dtype) if left_key in sales.columns else 'missing'
        unmatched = None
        rows_after = None
        revenue_after = None
        passed = False
        issue = ''

        if left_key not in sales.columns or right_key not in dimension.columns:
            issue = 'Required relationship key is missing.'
        elif not right['unique']:
            issue = 'The lookup key is missing values or is not unique; join not attempted.'
        else:
            try:
                # Only the lookup key is needed to test coverage and fan-out.
                # validate='many_to_one' rejects duplicate keys on the right.
                joined = sales.merge(
                    dimension[[right_key]],
                    how='left',
                    left_on=left_key,
                    right_on=right_key,
                    validate='many_to_one',
                    indicator=True,
                )
                unmatched = int((joined['_merge'] == 'left_only').sum())
                rows_after = len(joined)
                revenue_after = float(pd.to_numeric(joined['Revenue'], errors='coerce').sum())
                passed = (unmatched == 0 and rows_after == len(sales)
                          and abs(revenue_after - before_total) < 1e-9)
                if not passed:
                    issue = 'Join has unmatched keys or changed rows/revenue.'
            except (KeyError, pd.errors.MergeError, ValueError) as exc:
                issue = str(exc)

        rows.append({
            'relationship': f'Sales[{left_key}] → {table_name}[{right_key}]',
            'cardinality': 'many-to-one',
            'sales_key_type': left_dtype,
            'lookup_key_type': right['dtype'],
            'lookup_key_unique': right['unique'],
            'unmatched_sales_rows': unmatched,
            'sales_rows_before': len(sales),
            'rows_after_join': rows_after,
            'revenue_before': before_total,
            'revenue_after_join': revenue_after,
            'passed': passed,
            'issue': issue,
        })
    return pd.DataFrame(rows)


def build_epresso_model(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Create the dashboard table after every relationship check passes.

    Sales stays on the left of four many-to-one joins, so the resulting table
    retains one row per store, month, and product. This function deliberately
    has no fallback relationship: invalid or incomplete uploads fail loudly.
    """
    checks = check_epresso_relationships(tables)
    if checks.empty or not checks['passed'].all():
        raise ValueError('All relationship checks must pass before building the dashboard model.')

    sales = tables['Sales'].copy()
    categories = tables['Categories'].copy()
    products = tables['Products'].copy()
    stores = tables['Stores'].copy()
    survey = tables['Survey Results'].copy()

    # The renamed right-side keys make each join visually explicit and avoid
    # ambiguous _x/_y suffixes when source tables contain similar field names.
    model = sales.merge(
        categories.rename(columns={'Category ID': 'Category Key'}),
        how='left', left_on='Category ID', right_on='Category Key',
        validate='many_to_one',
    ).drop(columns='Category Key')
    model = model.merge(
        products.rename(columns={'Product ID': 'Product Key'}),
        how='left', left_on='Product ID', right_on='Product Key',
        validate='many_to_one',
    ).drop(columns='Product Key')
    model = model.merge(
        stores.rename(columns={'ID': 'Store Key'}),
        how='left', left_on='Store ID', right_on='Store Key',
        validate='many_to_one',
    ).drop(columns='Store Key')
    model = model.merge(
        survey.rename(columns={
            'Survey ID': 'Survey Key',
            'Store ID': 'Survey Store ID',
            'Year': 'Survey Year',
        }),
        how='left', left_on='StoreYear', right_on='Survey Key',
        validate='many_to_one',
    ).drop(columns='Survey Key')

    model['Date'] = pd.to_datetime(model['Date'], errors='raise')
    model['Revenue'] = pd.to_numeric(model['Revenue'], errors='raise')
    model['Satisfaction'] = pd.to_numeric(model['Satisfaction'], errors='coerce')
    model['Interest'] = pd.to_numeric(model['Interest'], errors='coerce')
    model['Year'] = model['Date'].dt.year
    model['Month Number'] = model['Date'].dt.month
    model['Month'] = model['Date'].dt.month_name().str.slice(stop=3)
    return model


def filter_dashboard(
    model: pd.DataFrame,
    *,
    categories: list | None = None,
    store_types: list | None = None,
    years: list | None = None,
) -> pd.DataFrame:
    """Apply the user-visible dashboard filters to the validated model."""
    filtered = model
    if categories:
        filtered = filtered[filtered['Category'].isin(categories)]
    if store_types:
        filtered = filtered[filtered['StoreType'].isin(store_types)]
    if years:
        filtered = filtered[filtered['Year'].isin(years)]
    return filtered.copy()


def dashboard_metrics(model: pd.DataFrame) -> dict:
    """Calculate upload-driven KPI values for the currently filtered rows."""
    revenue = pd.to_numeric(model['Revenue'], errors='coerce')
    satisfaction = pd.to_numeric(model['Satisfaction'], errors='coerce')
    return {
        'revenue': float(revenue.sum()),
        'sales_rows': int(len(model)),
        'stores': int(model['Store ID'].nunique()),
        'average_satisfaction': (
            None if satisfaction.notna().sum() == 0 else float(satisfaction.mean())
        ),
    }


# ---------------------------------------------------------- tool contract
@dataclass
class ToolResult:
    """Every analytical function returns this. The assistant may only narrate it.
    Keep `value` to plain Python types (numbers, strings, dicts, lists)."""
    tool: str
    value: object
    definition: str
    scope: dict
    rows_used: int
    caveats: list = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _error(tool: str, message: str, scope: dict | None = None) -> ToolResult:
    return ToolResult(tool=tool, value=None, definition='', scope=scope or {},
                      rows_used=0, caveats=[], error=message)


def _apply_filters(df: pd.DataFrame, filters: dict | None):
    """Validate filters against the LOADED data, then apply them."""
    for col, wanted in (filters or {}).items():
        if col not in df.columns:
            return df, f'Unknown column: {col}'
        wanted_list = list(wanted) if isinstance(wanted, (list, tuple, set)) else [wanted]
        valid = set(df[col].dropna().unique())
        bad = [w for w in wanted_list if w not in valid]
        if bad:
            examples = sorted(map(str, valid))[:20]
            return df, f'{bad} not found in column {col}. Valid values include: {examples}'
        df = df[df[col].isin(wanted_list)]
    return df, None


# ------------------------------------------------------ analytical tools
def get_total(df: pd.DataFrame, value_col: str, filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column, optionally filtered. EXAMPLE tool: replace the
    generic column names with your own definition of revenue."""
    name = 'get_total'
    if value_col not in df.columns:
        return _error(name, f'Unknown column: {value_col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    values = pd.to_numeric(subset[value_col], errors='coerce')
    n_bad = int(values.isna().sum())
    caveats = ['This is a sum of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) had a missing or non-numeric {value_col} and were excluded.')
    return ToolResult(tool=name, value=float(values.sum()), definition=f'Sum of {value_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(values.notna().sum()), caveats=caveats)


def group_total(df: pd.DataFrame, value_col: str, group_col: str,
                filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column by group (store, channel, year, ...)."""
    name = 'group_total'
    for col in (value_col, group_col):
        if col not in df.columns:
            return _error(name, f'Unknown column: {col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    work = subset.assign(**{value_col: pd.to_numeric(subset[value_col], errors='coerce')})
    n_bad = int(work[value_col].isna().sum())
    n_nogroup = int(work[group_col].isna().sum())
    grouped = work.dropna(subset=[value_col, group_col]).groupby(group_col)[value_col].sum()
    caveats = ['Sums of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) with missing or non-numeric {value_col} were excluded.')
    if n_nogroup:
        caveats.append(f'{n_nogroup} row(s) with a missing {group_col} were excluded.')
    return ToolResult(tool=name, value={str(k): float(v) for k, v in grouped.items()},
                      definition=f'Sum of {value_col} by {group_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(len(work) - n_bad - n_nogroup), caveats=caveats)


def data_quality_report(df: pd.DataFrame) -> ToolResult:
    """Row count, duplicate rows, and missing values per column."""
    missing = {c: int(n) for c, n in df.isna().sum().items() if n > 0}
    caveats = []
    if missing:
        caveats.append('Missing values may limit conclusions drawn from those columns.')
    return ToolResult(tool='data_quality_report',
                      value={'rows': len(df), 'duplicate_rows': int(df.duplicated().sum()),
                             'columns_with_missing': missing},
                      definition='Counts of duplicate rows and missing values in the loaded table',
                      scope={'filters': 'none (full table)'}, rows_used=len(df), caveats=caveats)


# ------------------------------------------ E-Presso approved analytical tools
def _epresso_scope(df: pd.DataFrame) -> dict:
    """Describe the exact currently loaded/filtered rows used by a tool."""
    scope = {'rows': int(len(df))}
    if 'Date' in df.columns and len(df):
        dates = pd.to_datetime(df['Date'], errors='coerce').dropna()
        if not dates.empty:
            scope['date_start'] = dates.min().date().isoformat()
            scope['date_end'] = dates.max().date().isoformat()
    for column in ('Category', 'StoreType', 'Year'):
        if column in df.columns:
            scope[column] = sorted(map(str, df[column].dropna().unique()))
    return scope


def get_revenue_by_channel(df: pd.DataFrame) -> ToolResult:
    """Return revenue grouped by Website versus Brick & Mortar."""
    name = 'get_revenue_by_channel'
    required = {'Revenue', 'StoreType'}
    if not required.issubset(df.columns):
        return _error(name, f'Missing required columns: {sorted(required - set(df.columns))}')
    work = df.assign(Revenue=pd.to_numeric(df['Revenue'], errors='coerce'))
    grouped = work.dropna(subset=['Revenue', 'StoreType']).groupby('StoreType')['Revenue'].sum()
    return ToolResult(
        tool=name,
        value={str(key): float(value) for key, value in grouped.items()},
        definition='Sum of Revenue by sales channel/store type',
        scope=_epresso_scope(df),
        rows_used=int(work[['Revenue', 'StoreType']].notna().all(axis=1).sum()),
        caveats=['Revenue is not profit.'],
    )


def get_annual_revenue_trend(df: pd.DataFrame) -> ToolResult:
    """Return annual revenue for the current dashboard subset."""
    name = 'get_annual_revenue_trend'
    if 'Revenue' not in df.columns or ('Year' not in df.columns and 'Date' not in df.columns):
        return _error(name, 'Revenue and Year or Date columns are required.')
    work = df.copy()
    work['Revenue'] = pd.to_numeric(work['Revenue'], errors='coerce')
    if 'Year' not in work.columns:
        work['Year'] = pd.to_datetime(work['Date'], errors='coerce').dt.year
    grouped = work.dropna(subset=['Revenue', 'Year']).groupby('Year')['Revenue'].sum().sort_index()
    return ToolResult(
        tool=name,
        value={str(int(key)): float(value) for key, value in grouped.items()},
        definition='Sum of Revenue by calendar year',
        scope=_epresso_scope(df),
        rows_used=int(work[['Revenue', 'Year']].notna().all(axis=1).sum()),
        caveats=['The trend is descriptive and does not forecast future revenue.'],
    )


def get_monthly_revenue_share(df: pd.DataFrame) -> ToolResult:
    """Return monthly revenue and its share of current-scope revenue.

    The denominator is the sum of Revenue across every row in the current
    dashboard subset, after active filters have been applied.
    """
    name = 'get_monthly_revenue_share'
    if 'Revenue' not in df.columns or ('Month Number' not in df.columns and 'Date' not in df.columns):
        return _error(name, 'Revenue and Month Number or Date columns are required.')
    work = df.copy()
    work['Revenue'] = pd.to_numeric(work['Revenue'], errors='coerce')
    if 'Month Number' not in work.columns:
        work['Month Number'] = pd.to_datetime(work['Date'], errors='coerce').dt.month
    valid = work.dropna(subset=['Revenue', 'Month Number'])
    grouped = valid.groupby('Month Number')['Revenue'].sum().sort_index()
    denominator = float(grouped.sum())
    month_names = pd.Series(range(1, 13)).map(
        {number: pd.Timestamp(2000, number, 1).strftime('%B') for number in range(1, 13)}
    )
    name_by_number = dict(zip(range(1, 13), month_names))
    values = {
        name_by_number[int(month)]: {
            'revenue': float(revenue),
            'share_pct': 0.0 if denominator == 0 else float(revenue / denominator * 100),
        }
        for month, revenue in grouped.items()
    }
    return ToolResult(
        tool=name,
        value=values,
        definition='Monthly Revenue and percentage of total Revenue in the current scope',
        scope={**_epresso_scope(df), 'share_denominator': denominator},
        rows_used=len(valid),
        caveats=['Each share uses current-scope total revenue as its denominator.'],
    )


def get_category_performance(df: pd.DataFrame) -> ToolResult:
    """Return revenue by product category for the current dashboard subset."""
    name = 'get_category_performance'
    required = {'Revenue', 'Category'}
    if not required.issubset(df.columns):
        return _error(name, f'Missing required columns: {sorted(required - set(df.columns))}')
    work = df.assign(Revenue=pd.to_numeric(df['Revenue'], errors='coerce'))
    grouped = (
        work.dropna(subset=['Revenue', 'Category'])
        .groupby('Category')['Revenue'].sum()
        .sort_values(ascending=False)
    )
    return ToolResult(
        tool=name,
        value={str(key): float(value) for key, value in grouped.items()},
        definition='Sum of Revenue by product category',
        scope=_epresso_scope(df),
        rows_used=int(work[['Revenue', 'Category']].notna().all(axis=1).sum()),
        caveats=['Revenue is not profit; category size and costs are not included.'],
    )


# ------------------------------------------------------------ merge check
def check_merge(left: pd.DataFrame, right: pd.DataFrame, on, value_col: str, how: str = 'left'):
    """Merge, and report whether the join changed the row count or the revenue sum.
    `value_col` must be a numeric column in `left`. Returns (merged, report)."""
    before_rows = len(left)
    before_sum = float(pd.to_numeric(left[value_col], errors='coerce').sum())
    merged = left.merge(right, on=on, how=how)
    after_rows = len(merged)
    after_sum = float(pd.to_numeric(merged[value_col], errors='coerce').sum())
    fan_out = after_rows > before_rows or abs(after_sum - before_sum) > 1e-9
    report = {
        'rows_before': before_rows, 'rows_after': after_rows,
        'sum_before': before_sum, 'sum_after': after_sum,
        'changed': fan_out,
        'warning': ('The join changed the row count or the total. Check the grain and keys '
                    'of both tables before using this result.') if fan_out else '',
    }
    return merged, report
