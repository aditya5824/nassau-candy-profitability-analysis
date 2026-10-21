"""Reusable analytics functions for Nassau Candy Distributor profitability project."""
from __future__ import annotations

from pathlib import Path
import io
import re
from typing import Any
import numpy as np
import pandas as pd

EXPECTED_COLUMNS = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID",
    "Country/Region", "City", "State/Province", "Postal Code", "Division", "Region",
    "Product ID", "Product Name", "Sales", "Units", "Gross Profit", "Cost"
]
NUMERIC_COLUMNS = ["Sales", "Units", "Gross Profit", "Cost"]
DATE_COLUMNS = ["Order Date", "Ship Date"]
TEXT_COLUMNS = [
    "Order ID", "Ship Mode", "Country/Region", "City", "State/Province", "Postal Code",
    "Division", "Region", "Product ID", "Product Name"
]

FACTORY_COORDINATES = [
    {"Factory": "Lot's O' Nuts", "Latitude": 32.881893, "Longitude": -111.768036},
    {"Factory": "Wicked Choccy's", "Latitude": 32.076176, "Longitude": -81.088371},
    {"Factory": "Sugar Shack", "Latitude": 48.119140, "Longitude": -96.181150},
    {"Factory": "Secret Factory", "Latitude": 41.446333, "Longitude": -90.565487},
    {"Factory": "The Other Factory", "Latitude": 35.117500, "Longitude": -89.971107},
]
PRODUCT_FACTORY_MAPPINGS = [
    {"Division": "Chocolate", "Product Name": "Wonka Bar - Nutty Crunch Surprise", "Factory": "Lot's O' Nuts"},
    {"Division": "Chocolate", "Product Name": "Wonka Bar - Fudge Mallows", "Factory": "Lot's O' Nuts"},
    {"Division": "Chocolate", "Product Name": "Wonka Bar -Scrumdiddlyumptious", "Factory": "Lot's O' Nuts"},
    {"Division": "Chocolate", "Product Name": "Wonka Bar - Milk Chocolate", "Factory": "Wicked Choccy's"},
    {"Division": "Chocolate", "Product Name": "Wonka Bar - Triple Dazzle Caramel", "Factory": "Wicked Choccy's"},
    {"Division": "Sugar", "Product Name": "Laffy Taffy", "Factory": "Sugar Shack"},
    {"Division": "Sugar", "Product Name": "SweeTARTS", "Factory": "Sugar Shack"},
    {"Division": "Sugar", "Product Name": "Nerds", "Factory": "Sugar Shack"},
    {"Division": "Sugar", "Product Name": "Fun Dip", "Factory": "Sugar Shack"},
    {"Division": "Other", "Product Name": "Fizzy Lifting Drinks", "Factory": "Sugar Shack"},
    {"Division": "Sugar", "Product Name": "Everlasting Gobstopper", "Factory": "Secret Factory"},
    {"Division": "Sugar", "Product Name": "Hair Toffee", "Factory": "The Other Factory"},
    {"Division": "Other", "Product Name": "Lickable Wallpaper", "Factory": "Secret Factory"},
    {"Division": "Other", "Product Name": "Wonka Gum", "Factory": "Secret Factory"},
    {"Division": "Other", "Product Name": "Kazookles", "Factory": "The Other Factory"},
]


def normalize_product_key(value: Any) -> str:
    """Stable matching key for product labels; does not overwrite the displayed source label."""
    if pd.isna(value):
        return ""
    s = re.sub(r"\s+", " ", str(value)).strip().casefold()
    s = re.sub(r"\s*-\s*", "-", s)
    return s


def standardize_product_label(value: Any) -> Any:
    if pd.isna(value):
        return value
    s = re.sub(r"\s+", " ", str(value)).strip()
    s = re.sub(r"\s*-\s*", " - ", s)
    return s


def read_csv_source(source: Any) -> pd.DataFrame:
    """Read path, bytes, BytesIO, or file-like CSV input."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    df = pd.read_csv(source, dtype={"Postal Code": "string"})
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_and_clean(source: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load data, report data quality, and return valid analysis records without fabricating values.

    Financially invalid records (missing/non-finite sales, cost, or gross profit; sales <= 0;
    negative cost) are excluded. Missing Units are retained and excluded from unit-based sums.
    Negative gross profit is treated as a valid business outcome, not as a data error.
    """
    raw = read_csv_source(source)
    raw_n, raw_p = raw.shape
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in raw.columns]
    if missing_cols:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_cols)}")

    df = raw.copy()
    exact_duplicates = int(df.duplicated().sum())
    duplicate_row_ids = int(df["Row ID"].duplicated().sum())
    missing_report = pd.DataFrame({
        "Column": raw.columns,
        "Missing Count": [int(raw[c].isna().sum()) for c in raw.columns],
        "Missing Percent": [float(raw[c].isna().mean() * 100) for c in raw.columns],
    })

    # Preserve parsed dates only after measuring parse failures.
    date_parse_failures = {}
    for col in DATE_COLUMNS:
        raw_date = df[col].copy()
        parsed = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
        date_parse_failures[col] = int(parsed.isna().sum())
        df[col] = parsed

    for col in TEXT_COLUMNS:
        df[col] = df[col].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    df["Product Name"] = df["Product Name"].map(standardize_product_label).astype("string")
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    nonnumeric_counts = {c: int(df[c].isna().sum()) for c in NUMERIC_COLUMNS}
    negative_counts = {c: int((df[c] < 0).sum()) for c in NUMERIC_COLUMNS}
    zero_counts = {c: int((df[c] == 0).sum()) for c in NUMERIC_COLUMNS}
    financial_identity_delta = (df["Sales"] - df["Cost"] - df["Gross Profit"]).abs()
    identity_mismatch = int((financial_identity_delta > 0.01).sum())
    identity_max_delta = float(financial_identity_delta.max(skipna=True)) if len(financial_identity_delta) else float("nan")

    ship_lag = (df["Ship Date"] - df["Order Date"]).dt.days
    ship_before_order = int((ship_lag < 0).sum())
    ship_lag_over_90 = int((ship_lag > 90).sum())
    ship_lag_min = int(ship_lag.min()) if ship_lag.notna().any() else None
    ship_lag_median = float(ship_lag.median()) if ship_lag.notna().any() else None
    ship_lag_max = int(ship_lag.max()) if ship_lag.notna().any() else None

    # Duplicates are detected and documented. Exact duplicate rows and duplicate Row IDs are not
    # automatically removed unless they are exact duplicate records, because IDs/line items may repeat.
    if exact_duplicates:
        df = df.drop_duplicates().copy()

    core_numeric = df[["Sales", "Cost", "Gross Profit"]]
    finite = np.isfinite(core_numeric.fillna(np.nan)).all(axis=1)
    unusable_financial = (
        ~finite | df["Sales"].isna() | df["Cost"].isna() | df["Gross Profit"].isna()
        | (df["Sales"] <= 0) | (df["Cost"] < 0)
    )
    invalid_financial_rows = int(unusable_financial.sum())
    df = df.loc[~unusable_financial].copy()

    # Keep missing units as missing, never as zero. Negative unit records are flagged, not rewritten.
    df["Gross Margin"] = np.where(df["Sales"] > 0, df["Gross Profit"] / df["Sales"], np.nan)
    df["Cost Ratio"] = np.where(df["Sales"] > 0, df["Cost"] / df["Sales"], np.nan)
    df["Profit per Unit"] = np.where(df["Units"] > 0, df["Gross Profit"] / df["Units"], np.nan)
    df["Order-to-Ship Days"] = (df["Ship Date"] - df["Order Date"]).dt.days
    df["Order Month"] = df["Order Date"].dt.to_period("M").astype("string")
    df["Financial Identity Delta"] = df["Sales"] - df["Cost"] - df["Gross Profit"]

    cleaning_summary = pd.DataFrame([
        {"Step": "Raw input records", "Rows Before": raw_n, "Rows Removed": 0, "Rows After": raw_n, "Rule / Notes": "Loaded from supplied CSV."},
        {"Step": "Exact duplicate rows", "Rows Before": raw_n, "Rows Removed": exact_duplicates, "Rows After": raw_n - exact_duplicates, "Rule / Notes": "Remove exact duplicates only; repeated Order IDs alone are not duplicates."},
        {"Step": "Duplicate Row IDs", "Rows Before": raw_n - exact_duplicates, "Rows Removed": 0, "Rows After": raw_n - exact_duplicates, "Rule / Notes": f"{duplicate_row_ids} duplicate Row ID(s) flagged, not auto-removed."},
        {"Step": "Invalid core financial records", "Rows Before": raw_n - exact_duplicates, "Rows Removed": invalid_financial_rows, "Rows After": raw_n - exact_duplicates - invalid_financial_rows, "Rule / Notes": "Exclude missing core financials, Sales <= 0, or Cost < 0."},
        {"Step": "Missing Units", "Rows Before": raw_n - exact_duplicates - invalid_financial_rows, "Rows Removed": 0, "Rows After": raw_n - exact_duplicates - invalid_financial_rows, "Rule / Notes": f"{int(df['Units'].isna().sum())} missing Units retained; no zero imputation."},
        {"Step": "Final usable analysis records", "Rows Before": raw_n, "Rows Removed": exact_duplicates + invalid_financial_rows, "Rows After": len(df), "Rule / Notes": "No financial imputation; negative Gross Profit remains valid."},
    ])

    dq_rows = [
        ("Source rows", raw_n, "Info", "Raw record count"),
        ("Source columns", raw_p, "Info", "Raw column count"),
        ("Exact duplicate rows", exact_duplicates, "Review", "Removed if present"),
        ("Duplicate Row IDs", duplicate_row_ids, "Review", "Flagged; not automatically removed"),
        ("Financial identity discrepancies > $0.01", identity_mismatch, "Review", "Checks Sales - Cost = Gross Profit"),
        ("Maximum absolute financial identity delta", identity_max_delta, "Info", "Floating-point delta; tolerance is $0.01"),
        ("Order Date parse failures", date_parse_failures["Order Date"], "Review", "Invalid parsed dates remain missing"),
        ("Ship Date parse failures", date_parse_failures["Ship Date"], "Review", "Invalid parsed dates remain missing"),
        ("Ship date before order date", ship_before_order, "Critical" if ship_before_order else "Info", "Impossible sequence if dates are intended to be chronological"),
        ("Order-to-ship gaps > 90 days", ship_lag_over_90, "Critical" if ship_lag_over_90 else "Info", "All rows are flagged if gap exceeds 90 days; not treated as delivery time"),
        ("Minimum order-to-ship days", ship_lag_min, "Info", "Observed only; dates appear anomalous"),
        ("Median order-to-ship days", ship_lag_median, "Info", "Observed only; dates appear anomalous"),
        ("Maximum order-to-ship days", ship_lag_max, "Info", "Observed only; dates appear anomalous"),
        ("Invalid core financial records excluded", invalid_financial_rows, "Review", "See cleaning summary"),
        ("Negative Sales rows", negative_counts["Sales"], "Review", "Count before financial exclusions"),
        ("Zero Sales rows", zero_counts["Sales"], "Review", "Count before financial exclusions"),
        ("Negative Cost rows", negative_counts["Cost"], "Review", "Count before financial exclusions"),
        ("Zero Units rows", zero_counts["Units"], "Review", "Not auto-excluded"),
        ("Negative Units rows", negative_counts["Units"], "Review", "Not auto-excluded"),
    ]
    for col in raw.columns:
        dq_rows.append((f"Missing values - {col}", int(raw[col].isna().sum()), "Review" if raw[col].isna().any() else "Info", "Raw source column missing count"))
    for col in NUMERIC_COLUMNS:
        dq_rows.append((f"Values not numeric or missing - {col}", nonnumeric_counts[col], "Review" if nonnumeric_counts[col] else "Info", "Count after numeric coercion"))
    data_quality = pd.DataFrame(dq_rows, columns=["Check", "Value", "Status", "Description"])
    meta = {
        "raw_rows": raw_n, "raw_columns": raw_p, "exact_duplicates": exact_duplicates,
        "duplicate_row_ids": duplicate_row_ids, "invalid_financial_rows": invalid_financial_rows,
        "final_rows": len(df), "date_parse_failures": date_parse_failures,
        "identity_mismatch_count": identity_mismatch, "identity_max_delta": identity_max_delta,
        "ship_lag_over_90": ship_lag_over_90, "ship_lag_min": ship_lag_min,
        "ship_lag_median": ship_lag_median, "ship_lag_max": ship_lag_max,
        "raw_missing_report": missing_report,
    }
    return df.reset_index(drop=True), data_quality, cleaning_summary, meta


def summarize_products(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Product Name", "Division", "Sales", "Gross Profit", "Cost", "Units", "Rows", "Orders", "Customers", "Gross Margin", "Profit per Unit", "Revenue Contribution (%)", "Profit Contribution (%)", "Cost Ratio (%)"])
    g = df.groupby(["Division", "Product Name"], dropna=False).agg(
        Sales=("Sales", "sum"), **{"Gross Profit": ("Gross Profit", "sum")}, Cost=("Cost", "sum"),
        Units=("Units", lambda s: s.sum(min_count=1)), Rows=("Row ID", "size"), Orders=("Order ID", "nunique"), Customers=("Customer ID", "nunique")
    ).reset_index()
    total_sales = g["Sales"].sum()
    total_profit = g["Gross Profit"].sum()
    g["Gross Margin"] = np.where(g["Sales"] != 0, g["Gross Profit"] / g["Sales"], np.nan)
    g["Profit per Unit"] = np.where(g["Units"] > 0, g["Gross Profit"] / g["Units"], np.nan)
    g["Revenue Contribution (%)"] = np.where(total_sales != 0, g["Sales"] / total_sales * 100, np.nan)
    g["Profit Contribution (%)"] = np.where(total_profit > 0, g["Gross Profit"] / total_profit * 100, np.nan)
    g["Cost Ratio (%)"] = np.where(g["Sales"] != 0, g["Cost"] / g["Sales"] * 100, np.nan)
    # Distribution-based quadrant thresholds are computed from current product aggregates.
    sales_cut = float(g["Sales"].median())
    margin_cut = float(g["Gross Margin"].median())
    g["Sales Segment"] = np.where(g["Sales"] >= sales_cut, "High sales", "Low sales")
    g["Margin Segment"] = np.where(g["Gross Margin"] >= margin_cut, "High margin", "Low margin")
    g["Profitability Quadrant"] = g["Sales Segment"] + " / " + g["Margin Segment"]
    g["Profit Rank"] = g["Gross Profit"].rank(method="min", ascending=False).astype(int)
    g["Sales Rank"] = g["Sales"].rank(method="min", ascending=False).astype(int)
    g["Margin Rank"] = g["Gross Margin"].rank(method="min", ascending=False).astype(int)
    g["Margin Risk"] = np.select(
        [g["Gross Profit"] < 0, g["Gross Margin"] < 0.25, (g["Sales"] >= sales_cut) & (g["Gross Margin"] < margin_cut), g["Cost Ratio (%)"] >= 75],
        ["Negative gross profit", "Very low margin (<25%)", "High sales / below-median margin", "High cost ratio (>=75%)"], default="No rule-based margin flag"
    )
    return g.sort_values("Sales", ascending=False).reset_index(drop=True)


def summarize_divisions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("Division", dropna=False).agg(
        Sales=("Sales", "sum"), **{"Gross Profit": ("Gross Profit", "sum")}, Cost=("Cost", "sum"),
        Units=("Units", lambda s: s.sum(min_count=1)), Rows=("Row ID", "size"), Products=("Product Name", "nunique"),
        Orders=("Order ID", "nunique"), Customers=("Customer ID", "nunique")
    ).reset_index()
    total_sales, total_gp = g["Sales"].sum(), g["Gross Profit"].sum()
    g["Gross Margin (%)"] = np.where(g["Sales"] != 0, g["Gross Profit"] / g["Sales"] * 100, np.nan)
    g["Cost Ratio (%)"] = np.where(g["Sales"] != 0, g["Cost"] / g["Sales"] * 100, np.nan)
    g["Profit per Unit"] = np.where(g["Units"] > 0, g["Gross Profit"] / g["Units"], np.nan)
    g["Revenue Contribution (%)"] = np.where(total_sales != 0, g["Sales"] / total_sales * 100, np.nan)
    g["Profit Contribution (%)"] = np.where(total_gp > 0, g["Gross Profit"] / total_gp * 100, np.nan)
    products = summarize_products(df)
    avg_margins = products.groupby("Division")["Gross Margin"].mean().mul(100).rename("Average Product Margin (%)")
    return g.merge(avg_margins, on="Division", how="left")


def summarize_groups(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()
    g = df.groupby(group_col, dropna=False).agg(
        Sales=("Sales", "sum"), **{"Gross Profit": ("Gross Profit", "sum")}, Cost=("Cost", "sum"),
        Units=("Units", lambda s: s.sum(min_count=1)), Rows=("Row ID", "size"), Orders=("Order ID", "nunique"), Customers=("Customer ID", "nunique")
    ).reset_index()
    total_sales, total_gp = g["Sales"].sum(), g["Gross Profit"].sum()
    g["Gross Margin (%)"] = np.where(g["Sales"] != 0, g["Gross Profit"] / g["Sales"] * 100, np.nan)
    g["Revenue Contribution (%)"] = np.where(total_sales != 0, g["Sales"] / total_sales * 100, np.nan)
    g["Profit Contribution (%)"] = np.where(total_gp > 0, g["Gross Profit"] / total_gp * 100, np.nan)
    return g.sort_values("Sales", ascending=False).reset_index(drop=True)


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Month", "Sales", "Gross Profit", "Cost", "Units", "Rows", "Gross Margin (%)", "Sales Growth (%)", "Profit Growth (%)"])
    x = df.dropna(subset=["Order Date"]).copy()
    x["Month"] = x["Order Date"].dt.to_period("M").astype(str)
    g = x.groupby("Month").agg(Sales=("Sales", "sum"), **{"Gross Profit": ("Gross Profit", "sum")}, Cost=("Cost", "sum"), Units=("Units", lambda s: s.sum(min_count=1)), Rows=("Row ID", "size")).reset_index()
    g["Gross Margin (%)"] = np.where(g["Sales"] != 0, g["Gross Profit"] / g["Sales"] * 100, np.nan)
    g["Sales Growth (%)"] = g["Sales"].pct_change() * 100
    g["Profit Growth (%)"] = g["Gross Profit"].pct_change() * 100
    return g


def pareto_summary(products: pd.DataFrame, metric: str) -> pd.DataFrame:
    if products.empty or metric not in products.columns:
        return pd.DataFrame()
    g = products[["Product Name", "Division", metric]].copy()
    g[metric] = pd.to_numeric(g[metric], errors="coerce").fillna(0.0)
    # Profit concentration uses positive profit only; revenue uses non-negative contribution.
    g["Contribution Base"] = g[metric].clip(lower=0)
    total = float(g["Contribution Base"].sum())
    g = g.sort_values("Contribution Base", ascending=False).reset_index(drop=True)
    g["Contribution (%)"] = g["Contribution Base"] / total * 100 if total > 0 else np.nan
    g["Cumulative Contribution (%)"] = g["Contribution (%)"].cumsum()
    g["Total Positive Base"] = total
    return g


def calculate_kpis(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"Total Sales": 0.0, "Total Gross Profit": 0.0, "Total Cost": 0.0, "Gross Margin (%)": np.nan, "Cost Ratio (%)": np.nan, "Profit per Unit": np.nan, "Units": 0, "Rows": 0, "Orders": 0, "Customers": 0, "Products": 0, "Average value per distinct Order ID": np.nan, "Negative-profit rows": 0, "Negative-profit products": 0, "Monthly margin volatility (percentage points)": np.nan}
    sales = float(df["Sales"].sum())
    gp = float(df["Gross Profit"].sum())
    cost = float(df["Cost"].sum())
    units = float(df["Units"].sum(min_count=1)) if hasattr(df["Units"], "sum") else 0.0
    prod = summarize_products(df)
    monthly = monthly_summary(df)
    monthly_volatility = float(monthly["Gross Margin (%)"].std(ddof=1)) if len(monthly) > 1 else np.nan
    order_count = int(df["Order ID"].nunique())
    return {
        "Total Sales": sales, "Total Gross Profit": gp, "Total Cost": cost,
        "Gross Margin (%)": gp / sales * 100 if sales else np.nan,
        "Cost Ratio (%)": cost / sales * 100 if sales else np.nan,
        "Profit per Unit": gp / units if units and pd.notna(units) else np.nan,
        "Units": units, "Rows": int(len(df)), "Orders": order_count,
        "Customers": int(df["Customer ID"].nunique()), "Products": int(df["Product Name"].nunique()),
        # This is labelled carefully because the provided Order ID is product-coded in the source.
        "Average value per distinct Order ID": sales / order_count if order_count else np.nan,
        "Negative-profit rows": int((df["Gross Profit"] < 0).sum()),
        "Negative-profit products": int((prod["Gross Profit"] < 0).sum()),
        "Monthly margin volatility (percentage points)": monthly_volatility,
    }


def factory_analysis(df: pd.DataFrame, factory_csv: Any = None, product_mapping_csv: Any = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    factories = pd.read_csv(factory_csv) if factory_csv is not None else pd.DataFrame(FACTORY_COORDINATES)
    mappings = pd.read_csv(product_mapping_csv) if product_mapping_csv is not None else pd.DataFrame(PRODUCT_FACTORY_MAPPINGS)
    product_summary = summarize_products(df)
    if product_summary.empty:
        return factories, mappings, pd.DataFrame()
    mappings["_key"] = mappings["Product Name"].map(normalize_product_key)
    product_summary["_key"] = product_summary["Product Name"].map(normalize_product_key)
    mappings = mappings.drop_duplicates("_key", keep="first")
    joined = product_summary.merge(mappings[["Division", "Product Name", "Factory", "_key"]].rename(columns={"Division": "Mapped Division", "Product Name": "Mapped Product Name"}), on="_key", how="left", validate="one_to_one")
    joined["Mapping Status"] = np.where(joined["Factory"].notna(), "Mapped", "Unmapped")
    joined["Division Mapping Check"] = np.where(joined["Factory"].isna(), "No mapping", np.where(joined["Division"] == joined["Mapped Division"], "Consistent", "Division mismatch"))
    factory_agg = joined.loc[joined["Factory"].notna()].groupby("Factory").agg(
        Sales=("Sales", "sum"), **{"Gross Profit": ("Gross Profit", "sum")}, Cost=("Cost", "sum"), Units=("Units", lambda s: s.sum(min_count=1)),
        Products=("Product Name", "nunique"), Rows=("Rows", "sum"),
        **{"Mapped Division Mismatches": ("Division Mapping Check", lambda x: int((x == "Division mismatch").sum()))}
    ).reset_index()
    factory_agg["Gross Margin (%)"] = np.where(factory_agg["Sales"] != 0, factory_agg["Gross Profit"] / factory_agg["Sales"] * 100, np.nan)
    factory_agg["Revenue Contribution (%)"] = factory_agg["Sales"] / factory_agg["Sales"].sum() * 100 if factory_agg["Sales"].sum() else np.nan
    factory_agg = factories.merge(factory_agg, on="Factory", how="left")
    return factories, joined.drop(columns=["_key"], errors="ignore"), factory_agg


def format_currency(value: Any, currency: str = "$", decimals: int = 2) -> str:
    try:
        if pd.isna(value):
            return "N/A"
        return f"{currency}{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"
