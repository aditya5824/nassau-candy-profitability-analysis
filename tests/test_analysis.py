from pathlib import Path
import sys
import io
import pandas as pd
import numpy as np
import pytest
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from analysis import load_and_clean, calculate_kpis, summarize_products, summarize_divisions, pareto_summary, factory_analysis
DATA = BASE / 'data' / 'Nassau_Candy_Distributor_raw.csv'


def test_supplied_dataset_financial_identity_and_dimensions():
    df, quality, cleaning, meta = load_and_clean(DATA)
    assert df.shape[0] == 10194
    assert meta['final_rows'] == 10194
    assert meta['raw_columns'] == 18
    assert meta['identity_mismatch_count'] == 0
    assert df['Financial Identity Delta'].abs().max() < 0.01
    assert df['Product Name'].nunique() == 15


def test_weighted_margin_is_aggregate_ratio():
    df, _, _, _ = load_and_clean(DATA)
    kpis = calculate_kpis(df)
    assert kpis['Gross Margin (%)'] == pytest.approx(df['Gross Profit'].sum() / df['Sales'].sum() * 100)
    product = summarize_products(df)
    row = product.loc[product['Product Name'] == 'Kazookles'].iloc[0]
    subset = df[df['Product Name'] == 'Kazookles']
    assert row['Gross Margin'] == pytest.approx(subset['Gross Profit'].sum() / subset['Sales'].sum())


def _minimal_csv(units=None, sales=10.0, cost=12.0, profit=-2.0):
    row = {
        'Row ID': 1, 'Order ID': 'ORD-1', 'Order Date': '01-01-2024', 'Ship Date': '02-01-2024',
        'Ship Mode': 'Standard', 'Customer ID': 1, 'Country/Region': 'United States', 'City': 'X',
        'State/Province': 'Y', 'Postal Code': '00001', 'Division': 'Other', 'Region': 'West',
        'Product ID': 'P1', 'Product Name': 'Sample - Product', 'Sales': sales, 'Units': units,
        'Gross Profit': profit, 'Cost': cost,
    }
    return pd.DataFrame([row]).to_csv(index=False).encode('utf-8')


def test_missing_units_are_not_filled_and_negative_profit_is_retained():
    df, _, _, meta = load_and_clean(_minimal_csv(units=np.nan))
    assert len(df) == 1
    assert pd.isna(df.loc[0, 'Units'])
    assert pd.isna(df.loc[0, 'Profit per Unit'])
    assert df.loc[0, 'Gross Profit'] == -2.0
    assert calculate_kpis(df)['Negative-profit rows'] == 1


def test_zero_sales_record_is_excluded():
    df, _, cleaning, meta = load_and_clean(_minimal_csv(units=1, sales=0.0, cost=0.0, profit=0.0))
    assert df.empty
    assert meta['invalid_financial_rows'] == 1
    assert int(cleaning.loc[cleaning['Step'] == 'Invalid core financial records', 'Rows Removed'].iloc[0]) == 1


def test_pareto_and_factory_mapping():
    df, _, _, _ = load_and_clean(DATA)
    product = summarize_products(df)
    pareto = pareto_summary(product, 'Sales')
    assert pareto['Cumulative Contribution (%)'].is_monotonic_increasing
    assert pareto['Cumulative Contribution (%)'].iloc[-1] == pytest.approx(100)
    _, mapping, factory_summary = factory_analysis(df)
    assert mapping['Product Name'].nunique() == 15
    assert mapping['Factory'].notna().all()
    assert (mapping['Division Mapping Check'] == 'Division mismatch').sum() == 1
    assert factory_summary['Sales'].sum() == pytest.approx(df['Sales'].sum())
    assert factory_summary['Gross Profit'].sum() == pytest.approx(df['Gross Profit'].sum())
