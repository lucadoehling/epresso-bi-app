#!/usr/bin/env python3
"""Run the required exact +$1,000 current-data test without altering originals."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

# Allow the repository modules to be imported when this file runs as a script.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent  # noqa: E402
import analytics  # noqa: E402


def file_hash(path: Path) -> str:
    """Return a SHA-256 fingerprint used to prove the original was restored."""
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def load_tables(folder: Path, sales_path: Path) -> dict[str, pd.DataFrame]:
    return {
        'Categories': pd.read_csv(folder / 'categories.csv'),
        'Products': pd.read_csv(folder / 'products.csv'),
        'Stores': pd.read_csv(folder / 'stores.csv'),
        'Survey Results': pd.read_csv(folder / 'survey_results.csv'),
        'Sales': pd.read_csv(sales_path),
    }


def run(folder: Path) -> dict:
    original_path = folder / 'sales.csv'
    original_hash_before = file_hash(original_path)
    original_tables = load_tables(folder, original_path)
    original_model = analytics.build_epresso_model(original_tables)

    # Select one valid stored revenue record and change nothing except Revenue.
    record_index = original_tables['Sales'].index[0]
    record = original_tables['Sales'].loc[record_index]
    sales_id = str(record['Sales ID'])
    original_value = float(record['Revenue'])
    modified_value = original_value + 1000.0

    with tempfile.TemporaryDirectory(prefix='epresso-1000-test-') as temp_folder:
        modified_path = Path(temp_folder) / 'sales_modified_1000.csv'
        modified_sales = original_tables['Sales'].copy()
        modified_sales.loc[record_index, 'Revenue'] = modified_value
        modified_sales.to_csv(modified_path, index=False)

        # Reload the separate CSV through the same input path used by current data.
        modified_tables = load_tables(folder, modified_path)
        modified_model = analytics.build_epresso_model(modified_tables)

        original_total = analytics.dashboard_metrics(original_model)['revenue']
        modified_total = analytics.dashboard_metrics(modified_model)['revenue']

        changed_row = modified_model.loc[modified_model['Sales ID'].astype(str) == sales_id].iloc[0]
        store_type = str(changed_row['StoreType'])
        category = str(changed_row['Category'])
        year = int(changed_row['Year'])
        month = str(changed_row['Month'])

        def scoped_total(model, **filters):
            subset = analytics.filter_dashboard(model, **filters)
            return analytics.dashboard_metrics(subset)['revenue']

        filter_changes = {
            'store_type': scoped_total(modified_model, store_types=[store_type])
                          - scoped_total(original_model, store_types=[store_type]),
            'category': scoped_total(modified_model, categories=[category])
                        - scoped_total(original_model, categories=[category]),
            'year': scoped_total(modified_model, years=[year])
                    - scoped_total(original_model, years=[year]),
        }
        original_month = original_model.loc[original_model['Month'] == month, 'Revenue'].sum()
        modified_month = modified_model.loc[modified_model['Month'] == month, 'Revenue'].sum()

        original_answer = agent.answer_question('How does revenue compare by channel?', original_model)
        modified_answer = agent.answer_question('How does revenue compare by channel?', modified_model)
        original_channels = original_answer['tool_log'][0]['result']['value']
        modified_channels = modified_answer['tool_log'][0]['result']['value']
        assistant_change = modified_channels[store_type] - original_channels[store_type]

        evidence = {
            'changed_record': sales_id,
            'changed_field': 'Revenue',
            'original_value': original_value,
            'modified_value': modified_value,
            'expected_total_change': 1000.0,
            'actual_total_change': modified_total - original_total,
            'affected_scope': {
                'store_type': store_type,
                'category': category,
                'year': year,
                'month': month,
            },
            'filtered_total_changes': filter_changes,
            'monthly_chart_source_change': float(modified_month - original_month),
            'assistant_function': modified_answer['tool_log'][0]['tool'],
            'assistant_channel_change': float(assistant_change),
            'temporary_modified_file_removed': True,
        }

    original_hash_after = file_hash(original_path)
    evidence['original_hash_before'] = original_hash_before
    evidence['original_hash_after'] = original_hash_after
    evidence['original_restored'] = original_hash_before == original_hash_after

    assert evidence['actual_total_change'] == 1000.0
    assert all(change == 1000.0 for change in filter_changes.values())
    assert evidence['monthly_chart_source_change'] == 1000.0
    assert evidence['assistant_channel_change'] == 1000.0
    assert evidence['original_restored']
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data/processed'))
    args = parser.parse_args()
    print(json.dumps(run(args.data_dir), indent=2))


if __name__ == '__main__':
    main()
