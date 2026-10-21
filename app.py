"""Interactive Streamlit dashboard: Nassau Candy product profitability and margin analysis.
Launch from the project directory with: streamlit run app.py
"""
from __future__ import annotations
from pathlib import Path
import io
import sys
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from analysis import (load_and_clean, summarize_products, summarize_divisions, summarize_groups,
                      monthly_summary, pareto_summary, calculate_kpis, factory_analysis, format_currency)

st.set_page_config(page_title="Nassau Candy | Profitability Analytics", page_icon="🍫", layout="wide")

COLORS = {"Chocolate": "#4C2E24", "Sugar": "#E0A526", "Other": "#3B82A0"}

@st.cache_data(show_spinner=False)
def cached_load(data_bytes: bytes):
    return load_and_clean(data_bytes)

@st.cache_data(show_spinner=False)
def cached_factory_inputs():
    return pd.read_csv(BASE_DIR / "factory_mapping.csv"), pd.read_csv(BASE_DIR / "product_factory_mapping.csv")

def money(v):
    return format_currency(v)

def pct(v):
    return "N/A" if pd.isna(v) else f"{v:.2f}%"

def fig_theme(fig, height=420):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=20, r=20, t=60, b=20), legend_title_text="")
    return fig

def safe_bar(df, x, y, title, color=None, horizontal=False, height=420):
    if df.empty:
        st.info("No records match the current filters.")
        return
    if horizontal:
        fig = px.bar(df, x=y, y=x, color=color, orientation="h", title=title, color_discrete_map=COLORS,
                     hover_data={y: ":,.2f"})
        fig.update_yaxes(autorange="reversed")
    else:
        fig = px.bar(df, x=x, y=y, color=color, title=title, color_discrete_map=COLORS,
                     hover_data={y: ":,.2f"})
    st.plotly_chart(fig_theme(fig, height), use_container_width=True)

def kpi_row(kpis):
    cols = st.columns(len(kpis))
    for col, (label, value, help_text) in zip(cols, kpis):
        col.metric(label, value, help=help_text)

def apply_filters(df, start_date, end_date, divisions, regions, states):
    x = df.copy()
    if start_date is not None:
        x = x[x["Order Date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        x = x[x["Order Date"] < pd.Timestamp(end_date) + pd.Timedelta(days=1)]
    if divisions:
        x = x[x["Division"].isin(divisions)]
    if regions:
        x = x[x["Region"].isin(regions)]
    if states:
        x = x[x["State/Province"].isin(states)]
    return x

st.title("Nassau Candy Distributor")
st.subheader("Product Line Profitability & Margin Performance")
st.caption("Interactive analysis of sales, gross profit, product margins, concentration, geography, and supplied factory mappings.")

with st.sidebar:
    st.header("Dataset and filters")
    uploaded = st.file_uploader("Upload replacement CSV (optional)", type=["csv"])
    default_path = BASE_DIR / "data" / "Nassau_Candy_Distributor_raw.csv"
    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        source_label = uploaded.name
    elif default_path.exists():
        raw_bytes = default_path.read_bytes()
        source_label = default_path.name
    else:
        st.error("Default CSV not found. Upload the source CSV to continue.")
        st.stop()
    try:
        full_df, quality_df, cleaning_df, meta = cached_load(raw_bytes)
    except Exception as exc:
        st.error(f"Could not load dataset: {exc}")
        st.stop()
    st.caption(f"Source: {source_label} | {meta['raw_rows']:,} input rows | {len(full_df):,} usable rows")
    minimum_date = full_df["Order Date"].min().date()
    maximum_date = full_df["Order Date"].max().date()
    date_range = st.date_input("Order date range", value=(minimum_date, maximum_date), min_value=minimum_date, max_value=maximum_date)
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date = end_date = date_range
    division_opts = sorted(full_df["Division"].dropna().unique().tolist())
    region_opts = sorted(full_df["Region"].dropna().unique().tolist())
    state_opts = sorted(full_df["State/Province"].dropna().unique().tolist())
    divisions = st.multiselect("Division", division_opts, default=division_opts)
    regions = st.multiselect("Region", region_opts, default=region_opts)
    states = st.multiselect("State / Province", state_opts, default=state_opts)
    min_margin = st.slider("Minimum product gross margin (%)", min_value=0, max_value=100, value=0, step=5,
                           help="Filters products using aggregate Gross Profit / Sales within the current date, division, and geography selection.")
    product_search = st.text_input("Product search", placeholder="Type part of a product name")
    if st.button("Reset filters", use_container_width=True):
        st.session_state.clear()
        st.rerun()

base_filtered = apply_filters(full_df, start_date, end_date, divisions, regions, states)
pre_products = summarize_products(base_filtered)
eligible_products = pre_products.loc[pre_products["Gross Margin"].fillna(-1).ge(min_margin / 100), "Product Name"].astype(str).unique().tolist()
if product_search.strip():
    eligible_products = [p for p in eligible_products if product_search.casefold() in p.casefold()]
active_df = base_filtered[base_filtered["Product Name"].isin(eligible_products)].copy()
product_df = summarize_products(active_df)
division_df = summarize_divisions(active_df)
monthly_df = monthly_summary(active_df)
kpis = calculate_kpis(active_df)
active_filters = f"Date: {start_date} to {end_date} | Divisions: {', '.join(divisions) if divisions else 'None'} | Regions: {', '.join(regions) if regions else 'None'} | States: {len(states)} selected | Minimum margin: {min_margin}%"
st.info(f"**Active filters:** {active_filters}. Product margin and search filters are applied to product-level records and all downstream views.")

if active_df.empty:
    st.warning("No records match the selected filters. Adjust the date range, geography, search, or margin threshold.")
    st.stop()

kpi_row([
    ("Total sales", money(kpis["Total Sales"]), "Sum of Sales for the active selection"),
    ("Gross profit", money(kpis["Total Gross Profit"]), "Sum of Gross Profit for the active selection"),
    ("Weighted gross margin", pct(kpis["Gross Margin (%)"]), "Total Gross Profit divided by total Sales"),
    ("Total cost", money(kpis["Total Cost"]), "Sum of Cost for the active selection"),
    ("Units", f"{kpis['Units']:,.0f}" if pd.notna(kpis["Units"]) else "N/A", "Sum of Units; missing units are not imputed"),
])
st.caption(f"Rows: {kpis['Rows']:,} | Distinct provided Order IDs: {kpis['Orders']:,} | Customers: {kpis['Customers']:,} | Products: {kpis['Products']:,} | Average value per distinct Order ID: {money(kpis['Average value per distinct Order ID'])}. Source Order IDs appear product-coded, so this is not asserted to be a conventional basket-level AOV.")

tabs = st.tabs(["Product Overview", "Division Performance", "Cost & Margin Diagnostics", "Profit Concentration", "Geography & Factories", "Data Quality & Export"])

with tabs[0]:
    st.markdown("### Product profitability overview")
    c1, c2 = st.columns(2)
    with c1:
        top_sales = product_df.nlargest(min(10, len(product_df)), "Sales")
        fig = px.bar(top_sales.sort_values("Sales"), x="Sales", y="Product Name", orientation="h", color="Division",
                     color_discrete_map=COLORS, title="Top products by sales", hover_data={"Sales": ":$,.2f", "Gross Profit": ":$,.2f", "Gross Margin": ":.1%"})
        st.plotly_chart(fig_theme(fig), use_container_width=True)
    with c2:
        top_profit = product_df.nlargest(min(10, len(product_df)), "Gross Profit")
        fig = px.bar(top_profit.sort_values("Gross Profit"), x="Gross Profit", y="Product Name", orientation="h", color="Division",
                     color_discrete_map=COLORS, title="Top products by gross profit", hover_data={"Sales": ":$,.2f", "Gross Profit": ":$,.2f", "Gross Margin": ":.1%"})
        st.plotly_chart(fig_theme(fig), use_container_width=True)
    matrix = px.scatter(product_df, x="Sales", y=product_df["Gross Margin"] * 100, size="Gross Profit", color="Division",
                        color_discrete_map=COLORS, hover_name="Product Name", hover_data={"Sales": ":$,.2f", "Gross Profit": ":$,.2f", "Gross Margin": ":.1%", "Profit per Unit": ":$,.2f"},
                        title="Product sales vs. gross margin", labels={"y": "Gross margin (%)"})
    matrix.add_hline(y=product_df["Gross Margin"].median()*100, line_dash="dash", line_color="#666", annotation_text="Median product margin")
    matrix.add_vline(x=product_df["Sales"].median(), line_dash="dash", line_color="#666", annotation_text="Median product sales")
    st.plotly_chart(fig_theme(matrix, 480), use_container_width=True)
    st.caption("Quadrants use median product sales and median aggregate product gross margin as data-driven thresholds. These relative segments are screening aids, not standalone decisions to discontinue a product.")
    display_cols = ["Product Name", "Division", "Sales", "Gross Profit", "Gross Margin", "Profit per Unit", "Revenue Contribution (%)", "Profit Contribution (%)", "Profitability Quadrant", "Margin Risk"]
    display = product_df[display_cols].copy()
    for col in ["Gross Margin"]:
        display[col] = display[col] * 100
    st.dataframe(display.rename(columns={"Gross Margin": "Gross Margin (%)"}).style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Gross Margin (%)": "{:.2f}%", "Profit per Unit": "${:,.2f}", "Revenue Contribution (%)": "{:.2f}%", "Profit Contribution (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)

with tabs[1]:
    st.markdown("### Division performance")
    if division_df.empty:
        st.info("No division data under current filters.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            b = division_df.melt(id_vars="Division", value_vars=["Sales", "Gross Profit"], var_name="Metric", value_name="Amount")
            fig = px.bar(b, x="Division", y="Amount", color="Metric", barmode="group", title="Revenue versus gross profit")
            st.plotly_chart(fig_theme(fig), use_container_width=True)
        with c2:
            fig = px.bar(division_df.sort_values("Gross Margin (%)"), x="Division", y="Gross Margin (%)", color="Division", color_discrete_map=COLORS,
                         title="Weighted gross margin by division", hover_data={"Average Product Margin (%)": ":.2f%"})
            st.plotly_chart(fig_theme(fig), use_container_width=True)
        row_margins = active_df.assign(**{"Transaction Gross Margin (%)": active_df["Gross Profit"] / active_df["Sales"] * 100})
        fig = px.box(row_margins, x="Division", y="Transaction Gross Margin (%)", color="Division", color_discrete_map=COLORS,
                     points="outliers", title="Transaction-level gross margin distribution")
        st.plotly_chart(fig_theme(fig), use_container_width=True)
        contrib = division_df.melt(id_vars="Division", value_vars=["Revenue Contribution (%)", "Profit Contribution (%)"], var_name="Contribution Type", value_name="Share (%)")
        fig = px.bar(contrib, x="Division", y="Share (%)", color="Contribution Type", barmode="group", title="Revenue share versus profit share")
        st.plotly_chart(fig_theme(fig), use_container_width=True)
        st.dataframe(division_df.style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Cost": "${:,.2f}", "Gross Margin (%)": "{:.2f}%", "Cost Ratio (%)": "{:.2f}%", "Profit per Unit": "${:,.2f}", "Revenue Contribution (%)": "{:.2f}%", "Profit Contribution (%)": "{:.2f}%", "Average Product Margin (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
        st.caption("Weighted gross margin is total division gross profit divided by total division sales. Average product margin gives each product equal weight and can differ sharply for divisions with few low-volume products.")

with tabs[2]:
    st.markdown("### Cost versus margin diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(active_df, x="Sales", y="Cost", color="Division", color_discrete_map=COLORS,
                         hover_name="Product Name", hover_data={"Gross Profit": ":$,.2f", "Units": True}, title="Transaction sales versus cost")
        st.plotly_chart(fig_theme(fig), use_container_width=True)
    with c2:
        fig = px.scatter(active_df, x="Cost", y="Gross Profit", color="Division", color_discrete_map=COLORS,
                         hover_name="Product Name", hover_data={"Sales": ":$,.2f", "Units": True}, title="Transaction cost versus gross profit")
        st.plotly_chart(fig_theme(fig), use_container_width=True)
    margin_chart = product_df.assign(**{"Gross Margin (%)": product_df["Gross Margin"] * 100}).sort_values("Gross Margin (%)")
    fig = px.bar(margin_chart, x="Gross Margin (%)", y="Product Name", color="Margin Risk", orientation="h", title="Aggregate product gross margin and risk flags",
                 hover_data={"Sales": ":$,.2f", "Gross Profit": ":$,.2f", "Cost Ratio (%)": ":.1f"})
    st.plotly_chart(fig_theme(fig, max(420, 24*len(margin_chart))), use_container_width=True)
    risks = product_df.loc[product_df["Margin Risk"] != "No rule-based margin flag"].copy()
    if risks.empty:
        st.success("No products triggered the currently defined rules-based risk flags in this filtered view.")
    else:
        risks["Suggested Review"] = risks["Margin Risk"].map({
            "Negative gross profit": "Validate cost allocation and price/cost terms; check whether losses are recurring.",
            "Very low margin (<25%)": "Review price realization, discounts, product cost and strategic role.",
            "High sales / below-median margin": "Prioritize pricing and cost review because the product has material sales.",
            "High cost ratio (>=75%)": "Investigate supplier/manufacturing cost drivers and margin sensitivity.",
        }).fillna("Investigate with additional pricing, cost, and demand data.")
        st.dataframe(risks[["Product Name", "Division", "Sales", "Gross Profit", "Gross Margin", "Cost Ratio (%)", "Margin Risk", "Suggested Review"]].style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Gross Margin": "{:.2%}", "Cost Ratio (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
    st.caption("A flag is a screening signal, not proof of an incorrect price or inefficient manufacturing. The dataset does not contain list prices, discount reasons, bill-of-material detail, labor, or supplier terms.")

with tabs[3]:
    st.markdown("### Product concentration and dependency")
    for metric, title in [("Sales", "Revenue Pareto"), ("Gross Profit", "Positive gross profit Pareto")]:
        pareto = pareto_summary(product_df, metric)
        if pareto.empty or pareto["Total Positive Base"].iloc[0] <= 0:
            st.info(f"A conventional {title.lower()} is not meaningful because the contribution base is zero or negative.")
            continue
        fig = go.Figure()
        fig.add_trace(go.Bar(x=pareto["Product Name"], y=pareto["Contribution Base"], name="Contribution base", marker_color="#5A7D7C", yaxis="y"))
        fig.add_trace(go.Scatter(x=pareto["Product Name"], y=pareto["Cumulative Contribution (%)"], name="Cumulative contribution", mode="lines+markers", line=dict(color="#C56D3A", width=3), yaxis="y2"))
        fig.add_hline(y=80, line_dash="dash", line_color="#666", yref="y2", annotation_text="80% threshold")
        fig.update_layout(title=title, xaxis_title="Product (ranked high to low)", yaxis=dict(title=metric, tickprefix="$", separatethousands=True),
                          yaxis2=dict(title="Cumulative contribution (%)", overlaying="y", side="right", range=[0, 105]), xaxis_tickangle=-45)
        st.plotly_chart(fig_theme(fig, 500), use_container_width=True)
        hit = pareto.loc[pareto["Cumulative Contribution (%)"] >= 80]
        if not hit.empty:
            n_hit = int(hit.index[0] + 1)
            st.write(f"**80% threshold:** {n_hit} of {len(pareto)} products ({n_hit/len(pareto)*100:.1f}%) reach at least 80% of the selected {metric.lower()} contribution base.")
        else:
            st.write(f"The selected positive {metric.lower()} contribution base does not reach 80% under the current conditions.")
        st.dataframe(pareto[["Product Name", "Division", metric, "Contribution (%)", "Cumulative Contribution (%)"]].style.format({metric: "${:,.2f}", "Contribution (%)": "{:.2f}%", "Cumulative Contribution (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
    st.caption("Concentration is calculated on the active filtered product set. Gross-profit concentration uses positive product profit only, to avoid misleading contribution math if losses exist.")

with tabs[4]:
    st.markdown("### Geographic and factory-associated analysis")
    c1, c2 = st.columns(2)
    with c1:
        region_df = summarize_groups(active_df, "Region")
        fig = px.bar(region_df.sort_values("Sales"), x="Sales", y="Region", orientation="h", title="Revenue by customer region", hover_data={"Gross Profit": ":$,.2f", "Gross Margin (%)": ":.2f"})
        st.plotly_chart(fig_theme(fig), use_container_width=True)
    with c2:
        state_df = summarize_groups(active_df, "State/Province").head(15)
        fig = px.bar(state_df.sort_values("Gross Profit"), x="Gross Profit", y="State/Province", orientation="h", title="Top 15 states / provinces by gross profit", hover_data={"Sales": ":$,.2f", "Gross Margin (%)": ":.2f"})
        st.plotly_chart(fig_theme(fig, 520), use_container_width=True)
    region_df = summarize_groups(active_df, "Region")
    st.dataframe(region_df.style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Cost": "${:,.2f}", "Gross Margin (%)": "{:.2f}%", "Revenue Contribution (%)": "{:.2f}%", "Profit Contribution (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
    factory_df, mapping_df, factory_summary = factory_analysis(active_df, BASE_DIR / "factory_mapping.csv", BASE_DIR / "product_factory_mapping.csv")
    st.markdown("#### Supplied factory coordinates")
    fig = px.scatter_geo(factory_df, lat="Latitude", lon="Longitude", hover_name="Factory", scope="usa", projection="albers usa",
                         title="Factory locations (supplied coordinates)", size_max=14)
    fig.update_traces(marker=dict(size=13, color="#D9822B"))
    st.plotly_chart(fig_theme(fig, 430), use_container_width=True)
    st.caption("Map pins show the supplied coordinates only. They do not represent customer destinations, a shipping route, travel time, capacity, or manufacturing efficiency.")
    full_products = summarize_products(full_df)
    _, full_mapping_review, full_factory_summary = factory_analysis(full_df, BASE_DIR / "factory_mapping.csv", BASE_DIR / "product_factory_mapping.csv")
    mapped_count = int(full_mapping_review["Factory"].notna().sum()) if not full_mapping_review.empty else 0
    mismatch_count = int((full_mapping_review["Division Mapping Check"] == "Division mismatch").sum()) if not full_mapping_review.empty else 0
    unmapped = full_mapping_review.loc[full_mapping_review["Factory"].isna(), "Product Name"].tolist() if not full_mapping_review.empty else []
    st.write(f"**Mapping coverage:** {mapped_count}/{len(full_mapping_review)} products mapped by normalized product name. **Division-label mismatches:** {mismatch_count}. **Unmapped products:** {', '.join(unmapped) if unmapped else 'None in the supplied dataset.'}")
    st.dataframe(full_mapping_review[["Product Name", "Division", "Mapped Division", "Factory", "Sales", "Gross Profit", "Gross Margin", "Division Mapping Check"]].style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Gross Margin": "{:.2%}"}), use_container_width=True, hide_index=True)
    st.markdown("#### Factory-associated profitability summary (active filtered records)")
    st.dataframe(full_factory_summary.style.format({"Sales": "${:,.2f}", "Gross Profit": "${:,.2f}", "Cost": "${:,.2f}", "Gross Margin (%)": "{:.2f}%", "Revenue Contribution (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
    st.caption("Factory figures summarize mapped products only and are not evidence of factory-level manufacturing efficiency. The supplied mapping labels Fizzy Lifting Drinks as Other, while the dataset labels it Sugar.")

with tabs[5]:
    st.markdown("### Data quality and downloadable outputs")
    st.write("**Cleaning summary**")
    st.dataframe(cleaning_df, use_container_width=True, hide_index=True)
    st.write("**Data-quality checks**")
    st.dataframe(quality_df, use_container_width=True, hide_index=True)
    st.write("**Cleaned dataset preview**")
    st.dataframe(active_df.head(100), use_container_width=True, hide_index=True)
    st.download_button("Download active filtered records (CSV)", active_df.to_csv(index=False).encode("utf-8"), "nassau_filtered_records.csv", "text/csv")
    st.download_button("Download product summary (CSV)", product_df.to_csv(index=False).encode("utf-8"), "nassau_product_summary.csv", "text/csv")
    st.download_button("Download division summary (CSV)", division_df.to_csv(index=False).encode("utf-8"), "nassau_division_summary.csv", "text/csv")
    st.download_button("Download full data-quality report (CSV)", quality_df.to_csv(index=False).encode("utf-8"), "nassau_data_quality_report.csv", "text/csv")
    st.download_button("Download cleaning summary (CSV)", cleaning_df.to_csv(index=False).encode("utf-8"), "nassau_cleaning_summary.csv", "text/csv")
    st.download_button("Download monthly summary (CSV)", monthly_df.to_csv(index=False).encode("utf-8"), "nassau_monthly_summary.csv", "text/csv")
    st.download_button("Download mapped product review (CSV)", full_mapping_review.to_csv(index=False).encode("utf-8"), "nassau_product_factory_review.csv", "text/csv")

st.divider()
st.caption("Method note: All headline margins are ratios of aggregated Gross Profit to aggregated Sales. Any exclusions and date concerns are documented in Data Quality & Export. Geographic concentration is reported; traffic congestion or delivery delays are not inferred.")
