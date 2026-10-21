# Nassau Candy Distributor: Product Profitability & Margin Performance

A reproducible analytics project that evaluates product-level and division-level gross profitability from the supplied `Nassau Candy Distributor.csv`, exposes interactive analysis through Streamlit, and creates research/decision-support documents.

## Contents

```text
Nassau_Candy_Project/
├── app.py                              # Streamlit dashboard (six modules)
├── analysis.py                         # Shared cleaning, KPI, summary, Pareto, factory logic
├── build_outputs.py                    # Rebuild CSV outputs, figures, and Word documents
├── data_dictionary.csv                 # Source/derived field definitions
├── factory_mapping.csv                 # Factory names and supplied coordinates
├── product_factory_mapping.csv         # Brief-provided product-to-factory links
├── data/
│   └── Nassau_Candy_Distributor_raw.csv # Original provided dataset copy
├── outputs/
│   ├── cleaned_dataset.csv
│   ├── data_quality_report.csv
│   ├── cleaning_summary.csv
│   ├── kpi_summary.csv
│   ├── product_summary.csv
│   ├── division_summary.csv
│   ├── region_summary.csv, state_summary.csv, country_summary.csv
│   ├── monthly_summary.csv, annual_summary.csv
│   ├── revenue_pareto.csv, profit_pareto.csv
│   ├── product_factory_review.csv, factory_profitability_summary.csv
│   ├── outlier_diagnostics.csv
│   └── charts/                          # Publication-ready PNG charts
├── tests/
│   └── test_analysis.py                 # KPI, validation, Pareto, and mapping tests
├── Research_Paper_Nassau_Candy.docx
├── Research_Paper_Nassau_Candy.pdf
├── Executive_Summary_Nassau_Candy.docx
├── Executive_Summary_Nassau_Candy.pdf
├── requirements.txt
└── README.md
```

## Project objectives

- Quantify sales, gross profit, cost, weighted gross margin, cost ratio, profit per unit, and monthly margin volatility.
- Rank products on revenue, gross profit, gross margin, unit economics, and contribution.
- Compare divisions while distinguishing weighted margin from average product margin.
- Identify 80% revenue/profit concentration and cost-heavy, low-margin products.
- Examine sales/profit by region, state/province, and country.
- Summarize products by the supplied factory mapping and identify mapping mismatches.
- Provide interactive filtering and exports in Streamlit.

## Dataset requirements

The bundled dataset contains 10,194 rows and the 18 source columns:

`Row ID`, `Order ID`, `Order Date`, `Ship Date`, `Ship Mode`, `Customer ID`, `Country/Region`, `City`, `State/Province`, `Postal Code`, `Division`, `Region`, `Product ID`, `Product Name`, `Sales`, `Units`, `Gross Profit`, `Cost`.

The application also offers an optional CSV upload to analyze a replacement file. The required source columns must be present; column matching is intentionally conservative to avoid silently guessing at financial fields.

## Python version and dependencies

Python 3.10 or newer is recommended. Dependencies are listed in `requirements.txt` and include pandas, NumPy, Streamlit, Plotly, Matplotlib, python-docx, and pytest.

### Install

From the project directory:

```bash
python -m venv .venv
```

Activate it:

- macOS/Linux: `source .venv/bin/activate`
- Windows PowerShell: `.venv\Scripts\Activate.ps1`

Then install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the analytics and regenerate static outputs

```bash
python build_outputs.py
```

This reloads `data/Nassau_Candy_Distributor_raw.csv`, runs the shared analysis functions, recreates CSV summaries and chart PNGs, and writes the research paper and executive summary as DOCX files. PDF copies are included in the project archive; if you regenerate the DOCX files after editing the content, export them to PDF using Microsoft Word, LibreOffice, or another compatible document conversion tool.

## Launch the interactive dashboard

From the project directory:

```bash
streamlit run app.py
```

Streamlit displays a local URL in the terminal, usually `http://localhost:8501`. The dashboard includes:

1. **Product Overview** — KPIs, product leaderboards, margin matrix, and product summary.
2. **Division Performance** — sales/profit comparison, weighted margins, transaction-level margin distributions, and share comparisons.
3. **Cost & Margin Diagnostics** — cost-sales and cost-profit scatter charts, margin flags, and recommended review actions.
4. **Profit Concentration** — revenue and positive-profit Pareto charts and 80% thresholds.
5. **Geography & Factories** — region/state results, supplied factory coordinate map, product matching review, and factory-associated product summaries.
6. **Data Quality & Export** — cleaning log, quality checks, preview, and CSV downloads.

## Deploy on GitHub and Streamlit Community Cloud

1. Create a new GitHub repository named `nassau-candy-profitability-analysis`. If pushing this existing folder, create the repository without adding a second README, license, or `.gitignore`.
2. From this project directory, initialize Git, commit, add the repository URL, and push the `main` branch. See the GitHub Docs guide for the exact workflow: https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
3. Open https://share.streamlit.io/ and sign in with GitHub. Select **Create app**, choose the repository and `main` branch, and set the app file path to `app.py`.
4. Deploy. The app reads the included dataset from `data/Nassau_Candy_Distributor_raw.csv`; keep the `data/` folder and the factory mapping CSVs in the repository.
5. Once deployed, copy the generated `https://…streamlit.app` URL into your submission and optionally add it to this README.

Keep `.env`, API keys, passwords, and `.streamlit/secrets.toml` out of Git. The supplied `.gitignore` excludes common local secrets and virtual environments.

## KPI formulas

- **Total Sales:** `sum(Sales)`
- **Total Gross Profit:** `sum(Gross Profit)`
- **Total Cost:** `sum(Cost)`
- **Weighted Gross Margin (%):** `sum(Gross Profit) / sum(Sales) * 100`
- **Cost Ratio (%):** `sum(Cost) / sum(Sales) * 100`
- **Product Gross Margin (%):** `product sum(Gross Profit) / product sum(Sales) * 100`
- **Profit per Unit:** `sum(Gross Profit) / sum(Units)` where the denominator is available and positive
- **Revenue Contribution (%):** `product Sales / total Sales * 100`
- **Profit Contribution (%):** `product Gross Profit / total Gross Profit * 100`, interpreted only where total gross profit is positive
- **Margin Volatility:** sample standard deviation of monthly weighted margins, expressed in percentage points; it is not the standard deviation of row-level margins.

Ratios use aggregated numerators and denominators. Overall gross margin is not calculated as the simple average of transaction margins.

## Data cleaning and validation rules

1. Check expected source columns, missing values, types, and dates.
2. Detect exact duplicate rows and duplicate `Row ID`s. Exact duplicates are removed; repeated `Order ID`s alone are not treated as duplicates.
3. Coerce financial numeric values without inventing replacements.
4. Exclude only records with missing/non-finite `Sales`, `Cost`, or `Gross Profit`, non-positive Sales, or negative Cost. Negative Gross Profit is preserved as a potentially valid business outcome.
5. Keep missing `Units` as missing; do not impute zero. Unit-based ratios are undefined where units are unavailable or non-positive.
6. Check `Sales - Cost = Gross Profit` using a $0.01 tolerance.
7. Standardize whitespace in text fields and product labels for consistent matching.
8. Use 1.5 × IQR fences to flag potential outliers for review, not to remove valid records automatically.
9. Preserve the raw source copy in `data/` for auditability.

## Important verified data limitations

- The supplied CSV has no missing values, exact duplicate rows, or duplicate Row IDs. All 10,194 records were retained after financial usability checks.
- The financial identity `Sales - Cost = Gross Profit` passes a $0.01 tolerance on all source rows.
- `Order Date` spans 2024-01-02 through 2025-12-31, while `Ship Date` spans 2026-06-30 through 2030-06-28. All order-to-ship gaps exceed 90 days (904–1,642 days). These dates are anomalous and are not used to claim delivery performance or shipping efficiency.
- `Order ID` includes product-related segments in its values; `Sales / distinct Order IDs` is therefore reported only as a descriptive proxy, not definitive basket-level average order value.
- The data contains 15 products, and Chocolate dominates the sample. Sugar has only 40 rows, so its division-level results have limited supporting volume.
- The supplied mapping covers all 15 distinct products by name, but the mapping says Fizzy Lifting Drinks belongs to Other while the dataset labels it Sugar.
- Factory profitability summaries associate product sales/cost/profit with the factory specified in the project brief. They are not measures of manufacturing efficiency, output capacity, distance, shipping time, or actual product origin.
- The data supports geographic concentration, not traffic congestion or delivery-delay inference. Delivery date, route, distance, and delay data are absent.

## Testing

Run the tests with:

```bash
pytest -q
```

The tests cover the financial identity and dataset shape, aggregate product margin formula, preservation of missing Units, zero-sales exclusion, negative gross-profit retention, Pareto logic, and factory mapping coverage.

Validation performed for this submission: `python -m py_compile analysis.py app.py build_outputs.py` passed; `pytest -q` passed all 5 tests; and the dashboard default code path passed a smoke test using a Streamlit API stub. The actual Streamlit package was not available in the build environment, and installation could not reach the package network, so a live browser session was not launched here. On the target machine, install `requirements.txt` and run `streamlit run app.py` to verify the local UI.

## Troubleshooting

- **`ModuleNotFoundError: streamlit`:** activate the virtual environment and run `python -m pip install -r requirements.txt`.
- **CSV columns missing:** compare uploaded file headers with the 18 required fields. Do not rename unrelated columns to financial fields without verification.
- **No records after filtering:** reduce the date/division/geography restrictions, clear product search, or lower the minimum gross-margin threshold.
- **Dashboard charts do not load:** upgrade the environment dependencies and restart `streamlit run app.py`.
- **PDF conversion:** open each DOCX in Microsoft Word or LibreOffice and export as PDF; the DOCX files are the editable source of truth.

## References

- Unified Mentor. (n.d.). *Product line profitability & margin performance analysis for Nassau Candy Distributor* [Project brief].
- Nassau Candy Distributor. (n.d.). *Nassau Candy Distributor dataset* [Data set]. Google Drive. https://drive.google.com/file/d/1c4VDb0Pf7RCgps4aLMiSuLtdaUpU_X49/view?pli=1
- pandas development team. (n.d.). *User guide*. https://pandas.pydata.org/docs/user_guide/
- Plotly Technologies Inc. (n.d.). *Plotly Python graphing library*. https://plotly.com/python/
- Streamlit. (n.d.). *Input widgets*. https://docs.streamlit.io/develop/api-reference/widgets
- Python Software Foundation. (n.d.). *datetime - Basic date and time types*. https://docs.python.org/3/library/datetime.html
