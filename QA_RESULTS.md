# Submission QA Results

- CSV inspection: passed; 10,194 rows and 18 source columns loaded.
- Financial integrity: passed; `Sales - Cost = Gross Profit` within $0.01 for every supplied record.
- Data-quality observations: no missing values, exact duplicate rows, duplicate Row IDs, zero/negative core financial values, or financially unusable rows. Ship Date values are anomalous relative to Order Date and are not interpreted as delivery-performance evidence.
- Python syntax compile: passed for `analysis.py`, `app.py`, and `build_outputs.py`.
- Unit tests: 5 passed.
- Dashboard code-path smoke test: passed using a Streamlit API stub.
- Document quality: research paper rendered to 15 PDF pages and executive summary to 3 pages; page images were visually inspected.
- Live Streamlit launch: not performed. Streamlit was absent from the environment and package installation failed because package-network DNS was unavailable. Run `pip install -r requirements.txt` then `streamlit run app.py` on a network-enabled machine.
