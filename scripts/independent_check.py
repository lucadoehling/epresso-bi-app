#!/usr/bin/env python3
"""Independently total E-Presso CSV exports without pandas or app functions.

This script is intentionally separate from analytics.py. It uses only Python's
standard library so the dashboard's most important revenue calculations can be
reproduced through a different implementation.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def calculate(sales_path: Path, stores_path: Path) -> dict:
    """Return independent total, channel, year, and month revenue controls."""
    with stores_path.open(newline='', encoding='utf-8-sig') as handle:
        store_types = {row['ID']: row['StoreType'] for row in csv.DictReader(handle)}

    total = Decimal('0')
    by_channel = defaultdict(lambda: Decimal('0'))
    by_year = defaultdict(lambda: Decimal('0'))
    by_month = defaultdict(lambda: Decimal('0'))
    rows = 0

    with sales_path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            revenue = Decimal(row['Revenue'])
            date = datetime.fromisoformat(row['Date'])
            channel = store_types[row['Store ID']]
            total += revenue
            by_channel[channel] += revenue
            by_year[str(date.year)] += revenue
            by_month[date.strftime('%B')] += revenue
            rows += 1

    def numbers(values):
        return {key: float(value) for key, value in sorted(values.items())}

    return {
        'sales_rows': rows,
        'total_revenue': float(total),
        'revenue_by_store_type': numbers(by_channel),
        'revenue_by_year': numbers(by_year),
        'revenue_by_month': numbers(by_month),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sales', type=Path, default=Path('data/processed/sales.csv'))
    parser.add_argument('--stores', type=Path, default=Path('data/processed/stores.csv'))
    args = parser.parse_args()
    print(json.dumps(calculate(args.sales, args.stores), indent=2))


if __name__ == '__main__':
    main()
