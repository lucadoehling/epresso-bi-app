"""Tests use a tiny made-up table so you can check every answer by hand."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agent  # noqa: E402
import analytics  # noqa: E402


@pytest.fixture
def df():
    return pd.DataFrame({
        'store': ['A', 'A', 'B', 'B', 'B'],
        'channel': ['web', 'shop', 'web', 'shop', 'shop'],
        'amount': [100, 200, 50, None, 150],
    })


def test_total_all_rows(df):
    r = analytics.get_total(df, 'amount')
    assert r.value == 500 and r.rows_used == 4
    assert any('missing' in c for c in r.caveats)


def test_total_filtered(df):
    assert analytics.get_total(df, 'amount', {'store': 'A'}).value == 300


def test_unknown_filter_value_returns_error_not_zero(df):
    r = analytics.get_total(df, 'amount', {'store': 'Z'})
    assert r.error and r.value is None


def test_group_total(df):
    assert analytics.group_total(df, 'amount', 'store').value == {'A': 300.0, 'B': 200.0}


def test_data_quality(df):
    r = analytics.data_quality_report(df)
    assert r.value['columns_with_missing'] == {'amount': 1}


def test_merge_without_fan_out(df):
    stores = pd.DataFrame({'store': ['A', 'B'], 'city': ['X', 'Y']})
    _, rep = analytics.check_merge(df, stores, on='store', value_col='amount')
    assert not rep['changed']


def test_merge_fan_out_is_detected(df):
    dup = pd.DataFrame({'store': ['A', 'A', 'B'], 'city': ['X', 'X2', 'Y']})
    _, rep = analytics.check_merge(df, dup, on='store', value_col='amount')
    assert rep['changed'] and rep['sum_after'] > rep['sum_before']


def test_dispatcher_rejects_unknown_tool_and_arguments(df):
    log = []
    assert agent.run_tool('run_python', {}, df, log).error
    assert agent.run_tool('get_total', {'value_col': 'amount', 'code': 'x'}, df, log).error


def test_unsupported_question(df):
    out = agent.answer_question('What is the meaning of life?', df)
    assert 'cannot answer' in out['findings']


@pytest.fixture
def epresso_tables():
    """Tiny five-table model with totals that can be checked by hand."""
    return {
        'Sales': pd.DataFrame({
            'Sales ID': ['S1', 'S2'],
            'Date': ['2025-01-31', '2025-01-31'],
            'Store ID': ['SH01', 'SH02'],
            'StoreYear': ['SH01_25', 'SH02_25'],
            'Category ID': ['C1', 'C1'],
            'Product ID': ['P1', 'P1'],
            'Revenue': [100, 250],
        }),
        'Categories': pd.DataFrame({'Category ID': ['C1'], 'Category': ['Machines']}),
        'Products': pd.DataFrame({'Product ID': ['P1'], 'Product': ['Model A']}),
        'Stores': pd.DataFrame({
            'ID': ['SH01', 'SH02'],
            'StoreType': ['Brick & Mortar', 'Brick & Mortar'],
            'Market': ['North', 'South'],
        }),
        'Survey Results': pd.DataFrame({
            'Survey ID': ['SH01_25', 'SH02_25'],
            'Store ID': ['SH01', 'SH02'],
            'Year': [2025, 2025],
            'Satisfaction': [4.0, 4.5],
            'Interest': [80, 90],
        }),
    }


def test_identify_epresso_tables(epresso_tables):
    for expected, table in epresso_tables.items():
        assert analytics.identify_epresso_table(table) == expected


def test_relationship_checks_preserve_uploaded_revenue(epresso_tables):
    checks = analytics.check_epresso_relationships(epresso_tables)
    assert len(checks) == 4
    assert checks['passed'].all()
    assert (checks['sales_rows_before'] == 2).all()
    assert (checks['rows_after_join'] == 2).all()
    assert (checks['revenue_before'] == 350).all()
    assert (checks['revenue_after_join'] == 350).all()


def test_relationship_check_rejects_duplicate_lookup_key(epresso_tables):
    epresso_tables['Products'] = pd.concat(
        [epresso_tables['Products'], epresso_tables['Products']], ignore_index=True
    )
    checks = analytics.check_epresso_relationships(epresso_tables)
    product_check = checks.loc[checks['relationship'].str.contains('Product ID')].iloc[0]
    assert not product_check['passed']
    assert not product_check['lookup_key_unique']
