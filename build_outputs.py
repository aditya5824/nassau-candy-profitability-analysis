"""Rebuild reports, figures, and CSV outputs from the bundled source dataset."""
from pathlib import Path
import sys, math, textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

BASE = Path(__file__).resolve().parent
OUT = BASE / 'outputs'
CHARTS = OUT / 'charts'
OUT.mkdir(exist_ok=True); CHARTS.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE))
from analysis import (load_and_clean, calculate_kpis, summarize_products, summarize_divisions,
                      summarize_groups, monthly_summary, pareto_summary, factory_analysis,
                      FACTORY_COORDINATES, PRODUCT_FACTORY_MAPPINGS)

SOURCE_CSV = BASE / 'data' / 'Nassau_Candy_Distributor_raw.csv'
CURRENCY = '$'
NAVY = '#17324D'; TEAL = '#4E807A'; GOLD = '#D9A441'; RUST = '#B45B43'; LIGHT = '#EAF0F4'; DARK = '#263746'


def currency(v):
    return 'N/A' if pd.isna(v) else f'${v:,.2f}'
def percent(v, decimals=2):
    return 'N/A' if pd.isna(v) else f'{v:.{decimals}f}%'
def clean_df_for_csv(df):
    x = df.copy()
    for col in x.columns:
        if pd.api.types.is_datetime64_any_dtype(x[col]):
            x[col] = x[col].dt.strftime('%Y-%m-%d')
    return x

# ---------- data preparation ----------
raw = pd.read_csv(SOURCE_CSV, dtype={'Postal Code':'string'})
df, dq, cleaning, meta = load_and_clean(SOURCE_CSV)
products = summarize_products(df)
divisions = summarize_divisions(df)
regions = summarize_groups(df, 'Region')
states = summarize_groups(df, 'State/Province')
countries = summarize_groups(df, 'Country/Region')
monthly = monthly_summary(df)
revenue_pareto = pareto_summary(products, 'Sales')
profit_pareto = pareto_summary(products, 'Gross Profit')
factories, mapping_review, factory_summary = factory_analysis(df)
kpis = calculate_kpis(df)

# Additional audit/summary outputs.
full_columns = [
    ('Row ID','Integer identifier assigned to each source record.'),('Order ID','Order identifier supplied in the CSV; appears product-coded in the source format.'),
    ('Order Date','Order date parsed day-first from the source; used as primary sales-analysis date.'),('Ship Date','Shipment date parsed day-first; dates are anomalously far after Order Date and should not be treated as validated delivery performance.'),
    ('Ship Mode','Shipping service/mode label.'),('Customer ID','Customer identifier.'),('Country/Region','Customer country or country/region label.'),('City','Customer city.'),
    ('State/Province','Customer state or province.'),('Postal Code','Postal/ZIP code; retained as text to preserve formatting.'),('Division','Product division label.'),('Region','Customer sales region label.'),
    ('Product ID','Product identifier.'),('Product Name','Product name; whitespace standardized and spaces around hyphens normalized for consistency.'),('Sales','Supplied sales amount.'),('Units','Supplied units sold; missing values are not imputed.'),
    ('Gross Profit','Supplied gross profit; validated against Sales minus Cost.'),('Cost','Supplied manufacturing cost.'),('Gross Margin','Derived row-level Gross Profit / Sales.'),('Cost Ratio','Derived row-level Cost / Sales.'),
    ('Profit per Unit','Derived row-level Gross Profit / Units where Units > 0.'),('Order-to-Ship Days','Derived calendar-day difference Ship Date minus Order Date; flagged as anomalous, not a delivery-time KPI.'),
    ('Order Month','Derived YYYY-MM from Order Date.'),('Financial Identity Delta','Derived Sales - Cost - Gross Profit; validated using $0.01 tolerance.')]
data_dict = pd.DataFrame(full_columns, columns=['Field','Definition / Treatment'])
data_dict.to_csv(BASE/'data_dictionary.csv', index=False)
pd.DataFrame(FACTORY_COORDINATES).to_csv(BASE/'factory_mapping.csv', index=False)
pd.DataFrame(PRODUCT_FACTORY_MAPPINGS).to_csv(BASE/'product_factory_mapping.csv', index=False)

# Helper files.
products.to_csv(OUT/'product_summary.csv', index=False)
divisions.to_csv(OUT/'division_summary.csv', index=False)
regions.to_csv(OUT/'region_summary.csv', index=False)
states.to_csv(OUT/'state_summary.csv', index=False)
countries.to_csv(OUT/'country_summary.csv', index=False)
monthly.to_csv(OUT/'monthly_summary.csv', index=False)
revenue_pareto.to_csv(OUT/'revenue_pareto.csv', index=False)
profit_pareto.to_csv(OUT/'profit_pareto.csv', index=False)
dq.to_csv(OUT/'data_quality_report.csv', index=False)
cleaning.to_csv(OUT/'cleaning_summary.csv', index=False)
factories.to_csv(OUT/'factory_coordinates.csv', index=False)
mapping_review.to_csv(OUT/'product_factory_review.csv', index=False)
factory_summary.to_csv(OUT/'factory_profitability_summary.csv', index=False)
clean_df_for_csv(df).to_csv(OUT/'cleaned_dataset.csv', index=False)

# KPI export table.
kpi_table = pd.DataFrame([
    {'KPI':'Total Sales','Value':kpis['Total Sales'],'Definition':'Sum of Sales on validated records.'},
    {'KPI':'Total Gross Profit','Value':kpis['Total Gross Profit'],'Definition':'Sum of supplied Gross Profit on validated records.'},
    {'KPI':'Total Cost','Value':kpis['Total Cost'],'Definition':'Sum of supplied Cost on validated records.'},
    {'KPI':'Weighted Gross Margin (%)','Value':kpis['Gross Margin (%)'],'Definition':'Sum(Gross Profit) / Sum(Sales) * 100.'},
    {'KPI':'Cost Ratio (%)','Value':kpis['Cost Ratio (%)'],'Definition':'Sum(Cost) / Sum(Sales) * 100.'},
    {'KPI':'Profit per Unit','Value':kpis['Profit per Unit'],'Definition':'Sum(Gross Profit) / Sum(Units), when units are available and positive.'},
    {'KPI':'Total Units','Value':kpis['Units'],'Definition':'Sum of supplied Units; missing units are not filled.'},
    {'KPI':'Distinct products','Value':kpis['Products'],'Definition':'Count of distinct standardized product labels.'},
    {'KPI':'Distinct provided Order IDs','Value':kpis['Orders'],'Definition':'Distinct Order ID field values; source IDs appear product-coded.'},
    {'KPI':'Distinct customers','Value':kpis['Customers'],'Definition':'Distinct Customer ID values.'},
    {'KPI':'Rows with negative gross profit','Value':kpis['Negative-profit rows'],'Definition':'Count of source rows where Gross Profit < 0.'},
    {'KPI':'Products with negative gross profit','Value':kpis['Negative-profit products'],'Definition':'Count of product aggregates with total Gross Profit < 0.'},
    {'KPI':'Monthly gross-margin volatility (percentage points)','Value':kpis['Monthly margin volatility (percentage points)'],'Definition':'Sample standard deviation (ddof=1) of monthly weighted margins, expressed in percent units.'},
])
kpi_table.to_csv(OUT/'kpi_summary.csv', index=False)

# IQR/outlier diagnostics - retain them, do not classify as invalid solely from distribution.
outlier_rows = []
for col in ['Sales','Cost','Gross Profit','Units']:
    series = pd.to_numeric(df[col], errors='coerce').dropna()
    q1, q3 = series.quantile([.25,.75]); iqr = q3-q1
    lo, hi = q1-1.5*iqr, q3+1.5*iqr
    count = int(((df[col] < lo) | (df[col] > hi)).sum())
    outlier_rows.append({'Field':col,'Q1':q1,'Q3':q3,'IQR':iqr,'Lower Fence':lo,'Upper Fence':hi,'Rows Outside IQR Fences':count,'Treatment':'Retained; statistical outlier is a review cue, not proof of invalidity.'})
pd.DataFrame(outlier_rows).to_csv(OUT/'outlier_diagnostics.csv', index=False)

# Data interpretation values.
annual = df.assign(Year=df['Order Date'].dt.year).groupby('Year').agg(Sales=('Sales','sum'), **{'Gross Profit':('Gross Profit','sum')}, Cost=('Cost','sum'), Units=('Units','sum'), Rows=('Row ID','size')).reset_index()
annual.to_csv(OUT/'annual_summary.csv', index=False)

def save_fig(path):
    plt.tight_layout()
    plt.savefig(CHARTS/path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close()

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':12,'axes.labelsize':9,'figure.titlesize':14})
# Chart 1 top product sales and gross profit
fig, ax = plt.subplots(figsize=(9.0, 5.4))
plot = products.nlargest(10,'Gross Profit').sort_values('Gross Profit')
ax.barh(plot['Product Name'], plot['Gross Profit'], color=TEAL, label='Gross profit')
ax.set_title('Top Products by Gross Profit'); ax.set_xlabel('Gross profit ($)'); ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}'))
ax.spines[['top','right','left']].set_visible(False); ax.grid(axis='x', alpha=.22); ax.set_axisbelow(True)
save_fig('top_products_gross_profit.png')
# Chart 2 product margin
fig, ax = plt.subplots(figsize=(9.0, 5.4))
plot = products.sort_values('Gross Margin')
bar_colors = [RUST if (m < .25) else (GOLD if m < .60 else TEAL) for m in plot['Gross Margin']]
ax.barh(plot['Product Name'], plot['Gross Margin']*100, color=bar_colors)
ax.axvline(products['Gross Margin'].median()*100, color=NAVY, linestyle='--', linewidth=1.5, label='Median product margin')
ax.set_title('Aggregate Gross Margin by Product'); ax.set_xlabel('Gross margin (%)'); ax.legend(frameon=False)
ax.spines[['top','right','left']].set_visible(False); ax.grid(axis='x', alpha=.22); ax.set_axisbelow(True)
save_fig('product_margins.png')
# Chart 3 division sales/profit
fig, ax = plt.subplots(figsize=(8.6,4.8)); ix=np.arange(len(divisions)); w=.34
ax.bar(ix-w/2, divisions['Sales'], w, label='Sales', color=NAVY)
ax.bar(ix+w/2, divisions['Gross Profit'], w, label='Gross profit', color=GOLD)
ax.set_xticks(ix, divisions['Division']); ax.set_ylabel('Amount ($)'); ax.set_title('Division Revenue and Gross Profit'); ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_: f'${x:,.0f}'))
ax.legend(frameon=False,ncol=2); ax.spines[['top','right']].set_visible(False); ax.grid(axis='y',alpha=.22); ax.set_axisbelow(True)
save_fig('division_revenue_profit.png')
# Chart 4 division weighted margins
fig, ax = plt.subplots(figsize=(7.8,4.6)); v=divisions.sort_values('Gross Margin (%)')
ax.bar(v['Division'],v['Gross Margin (%)'],color=[RUST if val<50 else TEAL for val in v['Gross Margin (%)']])
for i,val in enumerate(v['Gross Margin (%)']): ax.text(i,val+1.2,f'{val:.1f}%',ha='center',fontsize=9)
ax.set_ylim(0,80);ax.set_ylabel('Weighted gross margin (%)');ax.set_title('Weighted Gross Margin by Division');ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
save_fig('division_margins.png')
# Chart 5 revenue pareto
fig, ax = plt.subplots(figsize=(9.4,5.2)); p= revenue_pareto.copy(); idx=np.arange(len(p))
ax.bar(idx,p['Contribution Base'],color=TEAL)
ax.set_ylabel('Sales ($)');ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_: f'${x:,.0f}'))
ax.set_xticks(idx, [t.replace('Wonka Bar - ','') for t in p['Product Name']], rotation=65,ha='right',fontsize=7)
ax2=ax.twinx();ax2.plot(idx,p['Cumulative Contribution (%)'],color=RUST,marker='o',linewidth=2);ax2.axhline(80,color=NAVY,linestyle='--');ax2.set_ylabel('Cumulative contribution (%)');ax2.set_ylim(0,105)
ax.set_title('Revenue Concentration by Product (Pareto)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines['top'].set_visible(False);ax2.spines['top'].set_visible(False)
save_fig('revenue_pareto.png')
# Chart 6 cost vs sales sample
fig, ax = plt.subplots(figsize=(7.8,5.0))
for div, group in df.groupby('Division'):
    ax.scatter(group['Sales'],group['Cost'],label=div,alpha=.35,s=20)
ax.set_xlabel('Sales ($)');ax.set_ylabel('Cost ($)');ax.set_title('Transaction Sales versus Cost');ax.legend(frameon=False);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
save_fig('sales_vs_cost.png')
# Chart 7 monthly sales and margin
fig, ax = plt.subplots(figsize=(9.1,4.8)); xx=np.arange(len(monthly))
ax.plot(xx,monthly['Sales'],color=NAVY,marker='o',markersize=3,label='Sales')
ax.set_ylabel('Sales ($)');ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_: f'${x:,.0f}'));ax.set_xticks(xx,monthly['Month'],rotation=60,ha='right',fontsize=7)
ax2=ax.twinx();ax2.plot(xx,monthly['Gross Margin (%)'],color=GOLD,marker='.',linewidth=1.6,label='Weighted margin');ax2.set_ylabel('Gross margin (%)');ax2.set_ylim(60,70)
ax.set_title('Monthly Sales and Weighted Gross Margin');ax.grid(axis='y',alpha=.2);ax.spines['top'].set_visible(False);ax2.spines['top'].set_visible(False)
lines,labels=ax.get_legend_handles_labels();lines2,labels2=ax2.get_legend_handles_labels();ax.legend(lines+lines2,labels+labels2,frameon=False,loc='upper left',ncol=2)
save_fig('monthly_sales_margin.png')
# Chart 8 regional sales
fig, ax = plt.subplots(figsize=(7.8,4.6)); r=regions.sort_values('Sales')
ax.barh(r['Region'],r['Sales'],color=TEAL)
ax.set_xlabel('Sales ($)');ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_: f'${x:,.0f}'));ax.set_title('Revenue by Customer Region');ax.spines[['top','right','left']].set_visible(False);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
save_fig('regional_sales.png')
# Chart 9 factory coordinates (simple coordinate plot, not road routing)
fig, ax=plt.subplots(figsize=(7.8,4.8)); fac=pd.DataFrame(FACTORY_COORDINATES)
ax.scatter(fac['Longitude'],fac['Latitude'],s=90,color=GOLD,edgecolor=NAVY,linewidth=.7)
for _,row in fac.iterrows():
    ax.annotate(row['Factory'],(row['Longitude'],row['Latitude']),xytext=(5,5),textcoords='offset points',fontsize=7)
ax.set_xlabel('Longitude');ax.set_ylabel('Latitude');ax.set_title('Supplied Factory Coordinates (not a route map)');ax.grid(alpha=.25);ax.spines[['top','right']].set_visible(False)
save_fig('factory_coordinates.png')
# Chart 10 revenue vs profit share division
fig,ax=plt.subplots(figsize=(7.8,4.6)); x=np.arange(len(divisions));w=.36
ax.bar(x-w/2,divisions['Revenue Contribution (%)'],w,label='Revenue share',color=NAVY)
ax.bar(x+w/2,divisions['Profit Contribution (%)'],w,label='Profit share',color=GOLD)
ax.set_xticks(x,divisions['Division']);ax.set_ylabel('Share of total (%)');ax.set_title('Division Revenue Share vs Profit Share');ax.legend(frameon=False);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
save_fig('division_contribution.png')

# ---------- reporting helpers ----------
def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)
def set_cell_margins(cell, top=70, start=90, bottom=70, end=90):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr(); tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None: tcMar = OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for m,v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        node=tcMar.find(qn('w:'+m))
        if node is None: node=OxmlElement('w:'+m); tcMar.append(node)
        node.set(qn('w:w'),str(v));node.set(qn('w:type'),'dxa')
def set_repeat_table_header(row):
    trPr = row._tr.get_or_add_trPr(); tblHeader = OxmlElement('w:tblHeader'); tblHeader.set(qn('w:val'),'true'); trPr.append(tblHeader)
def prevent_row_split(row):
    trPr = row._tr.get_or_add_trPr(); cant = OxmlElement('w:cantSplit'); trPr.append(cant)
def setup_doc(doc, short_title):
    sec=doc.sections[0]; sec.top_margin=Inches(.72); sec.bottom_margin=Inches(.68); sec.left_margin=Inches(.78); sec.right_margin=Inches(.78)
    styles=doc.styles
    styles['Normal'].font.name='Aptos';styles['Normal'].font.size=Pt(9.5);styles['Normal'].font.color.rgb=RGBColor(38,55,70)
    styles['Normal'].paragraph_format.space_after=Pt(5);styles['Normal'].paragraph_format.line_spacing=1.12
    for style_name,size,color in [('Title',30,NAVY),('Heading 1',17,NAVY),('Heading 2',12,TEAL),('Heading 3',10,GOLD)]:
        st=styles[style_name]; st.font.name='Aptos Display';st.font.size=Pt(size);st.font.bold=True;st.font.color.rgb=RGBColor.from_string(color.strip('#'))
        st.paragraph_format.space_before=Pt(12 if style_name!='Title' else 0);st.paragraph_format.space_after=Pt(5)
    header=sec.header.paragraphs[0];header.text='NASSAU CANDY DISTRIBUTOR  |  PRODUCT PROFITABILITY';header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    for r in header.runs:r.font.size=Pt(7);r.font.color.rgb=RGBColor(110,125,136)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=footer.add_run(f'{short_title}  •  ');run.font.size=Pt(8);run.font.color.rgb=RGBColor(110,125,136)
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
def add_paragraph(doc,text='',style=None,bold_lead=None):
    p=doc.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold=True;p.add_run(text[len(bold_lead):])
    else:p.add_run(str(text))
    return p
def add_bullets(doc, items):
    for item in items:
        p=doc.add_paragraph(style='List Bullet');p.paragraph_format.space_after=Pt(2)
        parts = str(item).split('**')
        for i, part in enumerate(parts):
            run = p.add_run(part)
            if i % 2 == 1: run.bold = True
def add_numbered(doc, items):
    for i, item in enumerate(items, start=1):
        p=doc.add_paragraph();p.paragraph_format.left_indent=Inches(.24);p.paragraph_format.first_line_indent=Inches(-.22);p.paragraph_format.space_after=Pt(3)
        p.add_run(f'{i}.  {item}')
def add_table(doc, df_table, formats=None, max_rows=None, widths=None, font_size=7.5):
    if df_table is None or df_table.empty:
        add_paragraph(doc,'No rows available for this table.');return
    dat=df_table.head(max_rows).copy() if max_rows else df_table.copy()
    table=doc.add_table(rows=1,cols=len(dat.columns));table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.style='Table Grid'
    set_repeat_table_header(table.rows[0]); prevent_row_split(table.rows[0])
    for j,c in enumerate(dat.columns):
        cell=table.rows[0].cells[j];cell.text=str(c);set_cell_shading(cell,NAVY);set_cell_margins(cell)
        for p in cell.paragraphs:
            p.paragraph_format.space_after=Pt(0)
            for r in p.runs:r.font.bold=True;r.font.size=Pt(font_size);r.font.color.rgb=RGBColor(255,255,255)
    for _,row in dat.iterrows():
        new_row = table.add_row(); prevent_row_split(new_row); cells=new_row.cells
        for j,c in enumerate(dat.columns):
            val=row[c]
            if formats and c in formats:
                try: val=formats[c](val)
                except Exception: pass
            if pd.isna(val): text='N/A'
            elif isinstance(val,(float,np.floating)): text=f'{float(val):,.2f}'
            else: text=str(val)
            cells[j].text=text;cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;set_cell_margins(cells[j])
            for p in cells[j].paragraphs:
                p.paragraph_format.space_after=Pt(0)
                for r in p.runs:r.font.size=Pt(font_size)
    for i,row in enumerate(table.rows[1:]):
        if i%2==1:
            for cell in row.cells:set_cell_shading(cell,'F3F6F8')
    if widths:
        for row in table.rows:
            for cell,w in zip(row.cells,widths): cell.width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return table
def add_figure(doc, name, caption, width=6.6):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(CHARTS/name),width=Inches(width))
    cap=doc.add_paragraph();cap.alignment=WD_ALIGN_PARAGRAPH.CENTER;cap.paragraph_format.space_after=Pt(7)
    r=cap.add_run(caption);r.italic=True;r.font.size=Pt(8);r.font.color.rgb=RGBColor(95,108,120)
def title_page(doc,title,subtitle,author_line):
    p=doc.add_paragraph();p.paragraph_format.space_before=Pt(90);p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    r=p.add_run('NASSAU CANDY\n');r.bold=True;r.font.size=Pt(17);r.font.color.rgb=RGBColor.from_string(TEAL.strip('#'))
    r=p.add_run('DISTRIBUTOR ANALYTICS');r.bold=True;r.font.size=Pt(17);r.font.color.rgb=RGBColor.from_string(NAVY.strip('#'))
    doc.add_paragraph('')
    p=doc.add_paragraph(style='Title');p.add_run(title)
    p=doc.add_paragraph();r=p.add_run(subtitle);r.font.size=Pt(14);r.font.color.rgb=RGBColor.from_string(TEAL.strip('#'))
    doc.add_paragraph('')
    p=doc.add_paragraph();r=p.add_run(author_line);r.font.size=Pt(10);r.font.color.rgb=RGBColor(80,95,105)
    doc.add_paragraph('')
    p=doc.add_paragraph();r=p.add_run('Prepared from the supplied Nassau Candy Distributor CSV and project brief.');r.font.size=Pt(9);r.italic=True;r.font.color.rgb=RGBColor(110,125,136)
    doc.add_page_break()

# Common source-based result strings.
whole_margin=kpis['Gross Margin (%)']; cost_ratio=kpis['Cost Ratio (%)']; profit_per_unit=kpis['Profit per Unit']
prod_gp_top=products.sort_values('Gross Profit',ascending=False).iloc[0]
prod_sales_top=products.sort_values('Sales',ascending=False).iloc[0]
prod_margin_top=products.sort_values('Gross Margin',ascending=False).iloc[0]
prod_margin_low=products.sort_values('Gross Margin').iloc[0]
div_choc=divisions.loc[divisions['Division']=='Chocolate'].iloc[0]
div_other=divisions.loc[divisions['Division']=='Other'].iloc[0]
div_sugar=divisions.loc[divisions['Division']=='Sugar'].iloc[0]
revenue_80 = int((revenue_pareto['Cumulative Contribution (%)']>=80).idxmax()+1) if (revenue_pareto['Cumulative Contribution (%)']>=80).any() else len(revenue_pareto)
profit_80 = int((profit_pareto['Cumulative Contribution (%)']>=80).idxmax()+1) if (profit_pareto['Cumulative Contribution (%)']>=80).any() else len(profit_pareto)
monthly_margin_min=monthly.loc[monthly['Gross Margin (%)'].idxmin()]
monthly_margin_max=monthly.loc[monthly['Gross Margin (%)'].idxmax()]
annual_growth = float((annual.loc[annual['Year']==2025,'Sales'].iloc[0]/annual.loc[annual['Year']==2024,'Sales'].iloc[0]-1)*100)
state_top=states.iloc[0]
region_top=regions.iloc[0]

# ---------- Research paper ----------
research=Document();setup_doc(research,'Research Paper')
title_page(research,'Product Line Profitability & Margin Performance Analysis for Nassau Candy Distributor',
           'Data cleaning, exploratory analysis, profit concentration, and decision support',
           'Research paper | Prepared 21 October 2026 | Academic and business decision-support submission')
research.add_heading('Abstract',level=1)
add_paragraph(research,f"This project evaluates product-line profitability for Nassau Candy Distributor using {meta['final_rows']:,} usable records from {df['Order Date'].min():%d %B %Y} to {df['Order Date'].max():%d %B %Y}. The CSV contains {df['Product Name'].nunique()} products in three divisions, with sales, cost, gross profit, units, dates, and customer geography. The analysis validates financial identities, computes aggregated profitability KPIs, ranks products and divisions, evaluates revenue and positive-profit concentration, examines monthly and geographic patterns, and attaches the brief's product-to-factory mapping. Total sales were {currency(kpis['Total Sales'])}, gross profit was {currency(kpis['Total Gross Profit'])}, and weighted gross margin was {percent(whole_margin)}. Chocolate accounted for {percent(div_choc['Revenue Contribution (%)'])} of revenue and {percent(div_choc['Profit Contribution (%)'])} of gross profit. The top five products represented {percent(revenue_pareto.iloc[4]['Cumulative Contribution (%)'])} of revenue and {percent(profit_pareto.iloc[4]['Cumulative Contribution (%)'])} of positive gross profit. One major quality caveat is that every observed Ship Date is 904–1,642 days after its Order Date, so shipment timing is treated as anomalous rather than interpreted as delivery performance. Recommendations emphasize product-specific pricing/cost reviews, portfolio concentration monitoring, and source-date verification.")
add_paragraph(research,'Keywords: gross margin, product profitability, Pareto analysis, cost diagnostics, Streamlit, distribution analytics')

research.add_heading('1. Introduction',level=1)
add_paragraph(research,'Sales growth is not synonymous with profit performance. Product profitability analysis compares revenue with associated costs and gross profit so management can prioritize products and divisions using more than sales volume alone. This paper applies descriptive and diagnostic analysis to the supplied distributor records and turns the findings into recommendations for pricing, cost management, promotions, and portfolio review.')
research.add_heading('2. Background and business context',level=1)
add_paragraph(research,'The project brief frames Nassau Candy as a distributor with product divisions Chocolate, Sugar, and Other. It asks for a common view of product revenue, gross profit, gross margin, regional performance, cost exposure, profit concentration, and factory-associated product summaries. The supplied table is transaction-row data; it does not include list prices, promotion reasons, supplier contracts, detailed manufacturing cost components, delivery dates, or route-level telemetry.')
research.add_heading('3. Problem statement',level=1)
add_paragraph(research,'The primary analytical problem is limited visibility into whether revenue is translating into gross profit and whether profit depends disproportionately on a narrow product set. Secondary questions cover division efficiency, cost-heavy low-margin products, geographical concentration, monthly trends, and mapping product profitability to the factories specified by the project brief.')
research.add_heading('4. Project objectives and research questions',level=1)
add_numbered(research,[
    'Measure total sales, gross profit, cost, weighted gross margin, cost ratio, profit per unit, and monthly margin variability.',
    'Rank products by revenue, gross profit, margin, and contribution; segment products with transparent relative thresholds.',
    'Compare division-level revenue share, profit share, weighted margin, and average product margin.',
    'Quantify the product counts required to reach at least 80% of revenue and positive gross profit.',
    'Identify rule-based margin risks and separate observed signals from causal claims.',
    'Summarize performance by region, state/province, country, and supplied product-to-factory mapping.',
    'Provide a reproducible Streamlit dashboard and technical artifacts.'
])
research.add_heading('5. Dataset description',level=1)
add_paragraph(research,f"The primary source is the supplied file Nassau Candy Distributor.csv. It has {meta['raw_rows']:,} rows and {meta['raw_columns']} source columns. The source includes {df['Order ID'].nunique():,} distinct provided Order IDs, {df['Customer ID'].nunique():,} customers, {df['Product Name'].nunique()} products, {df['Division'].nunique()} divisions, {df['Region'].nunique()} customer regions, {df['State/Province'].nunique()} states/provinces, and {df['Country/Region'].nunique()} country labels. The Order Date coverage is {df['Order Date'].min():%d %B %Y} through {df['Order Date'].max():%d %B %Y}. Postal codes were loaded as text to preserve formatting.")
add_table(research,pd.DataFrame([{'Attribute':'Rows','Value':f"{meta['raw_rows']:,}"},{'Attribute':'Source columns','Value':meta['raw_columns']},{'Attribute':'Final usable records','Value':f"{len(df):,}"},{'Attribute':'Distinct products','Value':df['Product Name'].nunique()},{'Attribute':'Divisions','Value':', '.join(sorted(df['Division'].dropna().unique()))},{'Attribute':'Countries','Value':', '.join(sorted(df['Country/Region'].dropna().unique()))},{'Attribute':'Order dates','Value':f"{df['Order Date'].min():%Y-%m-%d} to {df['Order Date'].max():%Y-%m-%d}"}]),font_size=8)
research.add_heading('6. Data cleaning and validation',level=1)
add_paragraph(research,f"All {meta['raw_rows']:,} raw rows passed the core financial usability rules; {len(df):,} records remain in the analysis. The source has {meta['exact_duplicates']} exact duplicate rows and {meta['duplicate_row_ids']} duplicate Row IDs. No raw source column has missing values, and all supplied numeric columns parse without missing/nonnumeric values. No negative or zero Sales values, negative Cost values, negative Units, or zero Units rows were found. The largest absolute difference in Sales - Cost - Gross Profit is {meta['identity_max_delta']:.2e}, far below the chosen $0.01 tolerance; no financial identity discrepancy exceeded that tolerance.")
add_table(research,cleaning[['Step','Rows Before','Rows Removed','Rows After','Rule / Notes']],max_rows=6,font_size=7)
add_paragraph(research,f"The dominant concern is date consistency. Order Date runs from {df['Order Date'].min():%Y-%m-%d} to {df['Order Date'].max():%Y-%m-%d}, but Ship Date runs from {df['Ship Date'].min():%Y-%m-%d} to {df['Ship Date'].max():%Y-%m-%d}. All {meta['ship_lag_over_90']:,} records have an order-to-ship gap above 90 days; the observed range is {meta['ship_lag_min']} to {meta['ship_lag_max']} days, with median {meta['ship_lag_median']:.0f} days. Because these dates are implausibly distant, the elapsed gap is retained as a flagged data-quality diagnostic and is not treated as operational shipping time. Repeated Order IDs are retained because repeated IDs alone do not prove duplicate records. Product labels are whitespace-normalized, and supplied source data remains available in the raw-data folder.")
research.add_heading('7. Exploratory data analysis methodology',level=1)
add_paragraph(research,'EDA used counts, descriptive statistics, aggregated product/division/geography summaries, monthly aggregates, and charts. Potential distributional outliers were flagged using the 1.5 × IQR rule for review, but records were not removed on outlier status alone. Summary calculations use pandas aggregation; plots were generated with Matplotlib and the interactive dashboard uses Plotly inside Streamlit (pandas development team, n.d.; Plotly Technologies Inc., n.d.; Streamlit, n.d.).')
research.add_heading('8. KPI definitions and formulas',level=1)
kpi_defs=pd.DataFrame([
 {'KPI':'Total Sales','Formula':'Sum(Sales)','Interpretation':'Total recorded revenue in the selected records.'},
 {'KPI':'Total Gross Profit','Formula':'Sum(Gross Profit)','Interpretation':'Total supplied gross profit; retains supplied values after validation.'},
 {'KPI':'Total Cost','Formula':'Sum(Cost)','Interpretation':'Total supplied cost.'},
 {'KPI':'Weighted gross margin','Formula':'Sum(Gross Profit) / Sum(Sales) × 100','Interpretation':'Aggregate profitability; not a simple mean of row-level margins.'},
 {'KPI':'Cost ratio','Formula':'Sum(Cost) / Sum(Sales) × 100','Interpretation':'Share of sales absorbed by supplied cost.'},
 {'KPI':'Product gross margin','Formula':'Product Sum(Gross Profit) / Product Sum(Sales) × 100','Interpretation':'Aggregate product margin, weighted by its sales.'},
 {'KPI':'Profit per unit','Formula':'Sum(Gross Profit) / Sum(Units)','Interpretation':'Calculated only where units are available and positive.'},
 {'KPI':'Revenue contribution','Formula':'Product Sales / Total Sales × 100','Interpretation':'Product share of current analysis sales.'},
 {'KPI':'Profit contribution','Formula':'Product Gross Profit / Total Gross Profit × 100','Interpretation':'Displayed where total gross profit is positive.'},
 {'KPI':'Monthly margin volatility','Formula':'Sample SD of monthly weighted margins (percentage units)','Interpretation':'Variation between monthly aggregated margins, not transaction-level standard deviation.'},
 {'KPI':'Average value per distinct Order ID','Formula':'Sum(Sales) / Distinct Order IDs','Interpretation':'Descriptive proxy only; source IDs appear product-coded, so it may not be basket-level average order value.'},
])
add_table(research,kpi_defs,font_size=7.2)
research.add_heading('9. Overall profitability results',level=1)
add_paragraph(research,f"The dataset records {currency(kpis['Total Sales'])} in sales, {currency(kpis['Total Gross Profit'])} in gross profit, and {currency(kpis['Total Cost'])} in cost, with {kpis['Units']:,.0f} units reported. The weighted gross margin is {percent(whole_margin)} and cost ratio is {percent(cost_ratio)}. Aggregate gross profit per unit is {currency(profit_per_unit)}. There are {kpis['Negative-profit rows']} rows and {kpis['Negative-profit products']} product aggregates with negative gross profit in this source. The sample standard deviation of the 24 monthly weighted gross margins is {kpis['Monthly margin volatility (percentage points)']:.3f} percentage points, with monthly margin ranging from {monthly_margin_min['Gross Margin (%)']:.2f}% ({monthly_margin_min['Month']}) to {monthly_margin_max['Gross Margin (%)']:.2f}% ({monthly_margin_max['Month']}).")
add_table(research,pd.DataFrame([
 {'Measure':'Sales','Value':currency(kpis['Total Sales'])},{'Measure':'Gross profit','Value':currency(kpis['Total Gross Profit'])},{'Measure':'Cost','Value':currency(kpis['Total Cost'])},{'Measure':'Weighted gross margin','Value':percent(whole_margin)},{'Measure':'Cost ratio','Value':percent(cost_ratio)},{'Measure':'Profit per unit','Value':currency(profit_per_unit)},{'Measure':'Reported units','Value':f"{kpis['Units']:,.0f}"},{'Measure':'Margin volatility, monthly SD','Value':f"{kpis['Monthly margin volatility (percentage points)']:.3f} percentage points"}]),font_size=8)
add_figure(research,'monthly_sales_margin.png','Figure 1. Monthly sales and monthly weighted gross margin. Sales rise in the second year while aggregate margins remain relatively stable.',width=6.5)
research.add_heading('10. Product-level profitability analysis',level=1)
add_paragraph(research,f"The highest gross-profit product is {prod_gp_top['Product Name']} at {currency(prod_gp_top['Gross Profit'])}; its aggregate gross margin is {percent(prod_gp_top['Gross Margin']*100)}. The highest-sales product is {prod_sales_top['Product Name']} with {currency(prod_sales_top['Sales'])} in sales. The highest aggregate margin is {prod_margin_top['Product Name']} at {percent(prod_margin_top['Gross Margin']*100)}, but it has only {currency(prod_margin_top['Sales'])} sales and {int(prod_margin_top['Rows'])} rows, so it should not be prioritized on margin percentage alone. The lowest-margin product is {prod_margin_low['Product Name']} with {percent(prod_margin_low['Gross Margin']*100)} margin and {percent(prod_margin_low['Cost Ratio (%)'])} cost ratio.")
add_figure(research,'top_products_gross_profit.png','Figure 2. Top products ranked by total gross profit.',width=6.5)
add_figure(research,'product_margins.png','Figure 3. Product aggregate margins, with median-product-margin reference.',width=6.5)
short_prod=products.sort_values('Gross Profit',ascending=False).head(10).copy()
short_prod['Sales']=short_prod['Sales'].map(currency);short_prod['Gross Profit']=short_prod['Gross Profit'].map(currency);short_prod['Gross Margin']=short_prod['Gross Margin'].map(lambda v:percent(v*100));short_prod['Revenue Contribution (%)']=short_prod['Revenue Contribution (%)'].map(percent);short_prod['Profit Contribution (%)']=short_prod['Profit Contribution (%)'].map(percent)
research.add_page_break()
add_table(research,short_prod[['Product Name','Division','Sales','Gross Profit','Gross Margin','Revenue Contribution (%)','Profit Contribution (%)']],font_size=6.8)
add_paragraph(research,'A distribution-based product matrix uses median aggregate sales and median aggregate product margin as quadrant thresholds. The five Chocolate products sit in the high-sales/high-margin group by these relative cutoffs. Lickable Wallpaper and Wonka Gum have meaningful margins but fall below the median product margin; Kazookles is the clearest numerical margin risk at 7.69%. Very-low-sales products with margins above 75% have tiny samples and are not evidence of scalable demand or stable unit economics.')
research.add_heading('11. Division-level performance',level=1)
add_paragraph(research,f"Chocolate recorded {currency(div_choc['Sales'])} in sales and {currency(div_choc['Gross Profit'])} in gross profit, for {percent(div_choc['Gross Margin (%)'])} weighted margin. It contributed {percent(div_choc['Revenue Contribution (%)'])} of revenue and {percent(div_choc['Profit Contribution (%)'])} of gross profit. Other recorded {currency(div_other['Sales'])} in sales and {currency(div_other['Gross Profit'])} in gross profit; its weighted margin was {percent(div_other['Gross Margin (%)'])}, with cost ratio {percent(div_other['Cost Ratio (%)'])}. Sugar recorded {currency(div_sugar['Sales'])} in sales across seven products but only 40 rows; its apparent {percent(div_sugar['Gross Margin (%)'])} weighted margin should be read as low-volume evidence rather than as a robust division benchmark.")
add_figure(research,'division_revenue_profit.png','Figure 4. Division-level revenue compared with gross profit.',width=6.2)
add_figure(research,'division_margins.png','Figure 5. Weighted margin by division.',width=6.2)
add_figure(research,'division_contribution.png','Figure 6. Revenue share versus profit share. Chocolate over-indexes on profit contribution; Other under-indexes.',width=6.2)
div_table=divisions[['Division','Sales','Gross Profit','Cost','Units','Products','Rows','Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)','Average Product Margin (%)']].copy()
for col in ['Sales','Gross Profit','Cost']:div_table[col]=div_table[col].map(currency)
for col in ['Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)','Average Product Margin (%)']:div_table[col]=div_table[col].map(percent)
research.add_page_break()
add_table(research,div_table,font_size=6.6)
add_paragraph(research,'Weighted division margin differs from average product margin because weighted margin gives greater influence to high-revenue products, while average product margin gives each product equal weight. Other has the lowest weighted margin and a profit-share deficit relative to sales share, indicating the first place for a targeted product/cost review. Chocolate is both the largest and most profitable division, but that dominance creates portfolio dependency risk.')
research.add_heading('12. Pareto and profit concentration analysis',level=1)
add_paragraph(research,f"The smallest number of products reaching at least 80% of revenue is {revenue_80} of {len(revenue_pareto)} products ({revenue_80/len(revenue_pareto)*100:.1f}%); the top five reach {revenue_pareto.iloc[revenue_80-1]['Cumulative Contribution (%)']:.2f}% of revenue. For positive gross profit, {profit_80} of {len(profit_pareto)} products ({profit_80/len(profit_pareto)*100:.1f}%) reach at least 80%; the top five generate {profit_pareto.iloc[profit_80-1]['Cumulative Contribution (%)']:.2f}% of positive gross profit. Four products reach 76.26% of revenue and 77.30% of gross profit; the fifth product lifts both totals beyond 80%. This means product-level disruption in one of the leading five Chocolate products could materially affect revenue and profit, even though all products are currently profitable in gross terms.")
add_figure(research,'revenue_pareto.png','Figure 7. Product revenue concentration; cumulative contribution crosses the 80% threshold with the fifth product.',width=6.5)
add_table(research,pd.DataFrame([
 {'Metric':'Revenue','Products to >=80%':revenue_80,'Share of product set':f'{revenue_80/len(revenue_pareto)*100:.1f}%','Top-five cumulative share':percent(revenue_pareto.iloc[4]['Cumulative Contribution (%)'])},
 {'Metric':'Positive gross profit','Products to >=80%':profit_80,'Share of product set':f'{profit_80/len(profit_pareto)*100:.1f}%','Top-five cumulative share':percent(profit_pareto.iloc[4]['Cumulative Contribution (%)'])},
]),font_size=8)
research.add_heading('13. Cost structure and margin diagnostics',level=1)
add_paragraph(research,f"Across all product aggregates, Kazookles has {currency(prod_margin_low['Cost'])} cost on {currency(prod_margin_low['Sales'])} sales and {currency(prod_margin_low['Gross Profit'])} gross profit. Its 92.31% cost ratio leaves a 7.69% gross margin. This is an observed arithmetic relationship rather than proof of mispricing or manufacturing inefficiency. Lickable Wallpaper shows {percent(float(products.loc[products['Product Name']=='Lickable Wallpaper','Gross Margin'].iloc[0])*100)} margin and {currency(float(products.loc[products['Product Name']=='Lickable Wallpaper','Gross Profit'].iloc[0]))} gross profit; because its sales are much greater than the long tail but margin is below the product median, it merits a price/cost decomposition review. No product has negative gross profit in the supplied records.")
add_figure(research,'sales_vs_cost.png','Figure 8. Transaction sales versus supplied cost. Relationships are descriptive and do not establish causal production cost drivers.',width=6.2)
add_bullets(research,[
    'Kazookles: review the product cost basis, discounts, and realized selling price; cost is 92.31% of sales.',
    'Lickable Wallpaper: evaluate price realization and cost terms because its volume is material but margin sits below the median product margin.',
    'Wonka Gum: margin is 52.00%; check whether its role is strategic, complementary, or promotion-led before changing the portfolio.',
    'Use product pricing, discount, supplier, labor, packaging, and detailed bill-of-material data to confirm root causes before repricing or rationalization.'
])
research.add_heading('14. Geographic and regional analysis',level=1)
add_paragraph(research,f"Pacific is the largest customer region with {currency(region_top['Sales'])} sales ({percent(region_top['Revenue Contribution (%)'])} of sales) and {percent(region_top['Gross Margin (%)'])} gross margin. California leads state/province revenue at {currency(state_top['Sales'])}, or {percent(state_top['Revenue Contribution (%)'])} of total sales; New York and Texas follow. The top three states together account for 40.11% of revenue. The United States contributes {currency(float(countries.loc[countries['Country/Region']=='United States','Sales'].iloc[0]))} in sales while Canada contributes {currency(float(countries.loc[countries['Country/Region']=='Canada','Sales'].iloc[0]))}. This is geographic commercial concentration, not evidence of traffic congestion or shipping delays.")
add_figure(research,'regional_sales.png','Figure 9. Sales by customer region.',width=6.0)
region_table=regions[['Region','Sales','Gross Profit','Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)']].copy()
for c in ['Sales','Gross Profit']:region_table[c]=region_table[c].map(currency)
for c in ['Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)']:region_table[c]=region_table[c].map(percent)
add_table(research,region_table,font_size=7.2)
research.add_heading('15. Factory mapping and factory-associated summaries',level=1)
add_paragraph(research,f"All {len(mapping_review)} distinct products in the supplied dataset match one of the 15 supplied product-to-factory mappings after case and whitespace normalization. One mapping has a division-label mismatch: the project brief assigns Fizzy Lifting Drinks to the Other division, but the dataset labels it Sugar. Factory-associated results are product aggregates grouped using the supplied mapping, not proof of factory-level manufacturing efficiency, capacity, travel route, delivery timing, or operating cost causality.")
add_figure(research,'factory_coordinates.png','Figure 10. Supplied factory coordinates. The plot is coordinate-based only and is not a routing or service-level map.',width=6.2)
ft=factory_summary[['Factory','Sales','Gross Profit','Cost','Products','Gross Margin (%)','Revenue Contribution (%)','Mapped Division Mismatches']].copy()
for c in ['Sales','Gross Profit','Cost']:ft[c]=ft[c].map(currency)
for c in ['Gross Margin (%)','Revenue Contribution (%)']:ft[c]=ft[c].map(percent)
add_table(research,ft,font_size=6.8)
research.add_heading('16. Time-series analysis',level=1)
add_paragraph(research,f"Order Date provides 24 months between January 2024 and December 2025. Revenue rose from {currency(float(annual.loc[annual['Year']==2024,'Sales'].iloc[0]))} in 2024 to {currency(float(annual.loc[annual['Year']==2025,'Sales'].iloc[0]))} in 2025, a 44.64% increase. Gross profit rose from {currency(float(annual.loc[annual['Year']==2024,'Gross Profit'].iloc[0]))} to {currency(float(annual.loc[annual['Year']==2025,'Gross Profit'].iloc[0]))}. The increase is an observed year-over-year comparison; no causal interpretation is made because seasonality, price, distribution, and data generation effects are not separately identified. Monthly gross margin was comparatively stable, with a standard deviation of 0.525 percentage points. Ship Date is excluded from delivery-performance interpretation because of the extreme date gap described above.")
research.add_heading('17. Dashboard design and implementation',level=1)
add_paragraph(research,'The Streamlit dashboard is implemented in app.py and uses shared functions from analysis.py so tables and KPIs follow common definitions. It provides six modules: Product Overview; Division Performance; Cost & Margin Diagnostics; Profit Concentration; Geography & Factories; and Data Quality & Export. Sidebar controls include order-date range, division, region, state/province, minimum product gross-margin threshold, and product search. An optional uploader accepts a replacement CSV. Interactive charts use Plotly; data tables and exports reflect active filters (Streamlit, n.d.; Plotly Technologies Inc., n.d.).')
research.add_heading('18. Results and key findings',level=1)
add_numbered(research,[
    f'Portfolio profitability: weighted gross margin is {percent(whole_margin)} on {currency(kpis["Total Sales"])} in sales; all observed products have positive aggregate gross profit.',
    f'Product leaders: {prod_gp_top["Product Name"]} leads gross profit at {currency(prod_gp_top["Gross Profit"])}; the top five products account for about {percent(profit_pareto.iloc[4]["Cumulative Contribution (%)"])} of positive gross profit.',
    f'Division imbalance: Chocolate contributes {percent(div_choc["Revenue Contribution (%)"])} of revenue and {percent(div_choc["Profit Contribution (%)"])} of gross profit; Other contributes {percent(div_other["Revenue Contribution (%)"])} of revenue but only {percent(div_other["Profit Contribution (%)"])} of gross profit.',
    f'Margin risk: Kazookles margin is {percent(prod_margin_low["Gross Margin"]*100)} with {percent(prod_margin_low["Cost Ratio (%)"])} cost ratio.',
    f'Geographic concentration: California produces {percent(state_top["Revenue Contribution (%)"])} of sales; the top three states generate 40.11%.',
    f'Data reliability: financial identities are consistent, but all {meta["ship_lag_over_90"]:,} order-to-ship elapsed-time records exceed 90 days.'
])
research.add_heading('19. Business recommendations',level=1)
add_numbered(research,[
    'Prioritize a focused cost-and-pricing review for Kazookles. Reconcile its realized price and cost build; validate whether the low margin is recurring before changing price or product status.',
    'Run a product-level price realization and supplier-cost review on Lickable Wallpaper and Wonka Gum, with emphasis on discount history, cost components, and volume response.',
    'Protect and monitor the top five Chocolate products with availability and margin dashboards. Consider diversification opportunities, but do not pursue a broad portfolio expansion without demand and contribution economics.',
    'Set explicit review gates for low-volume high-margin products. Tiny sales bases should not be treated as evidence of scalable profitability; test demand through controlled distribution or promotions.',
    'Investigate Other division cost structure and item mix because its weighted margin is only 44.84% and profit contribution is below revenue contribution.',
    'Verify source Ship Date semantics and refresh dates from the system of record before using shipment KPIs. Do not infer congestion or delivery delays from this file.',
    'Use monthly margin and profit-contribution monitoring as a recurring process. Investigate changes, rather than reacting to gross margin in isolation.'
])
research.add_heading('20. Limitations and assumptions',level=1)
add_bullets(research,[
    'Gross Profit is accepted as supplied after validation against Sales - Cost; Cost is interpreted as manufacturing cost because the brief describes it that way, but no cost-component breakdown is provided.',
    'Order ID appears to contain product-specific elements. The descriptive average value per distinct provided Order ID may not equal true basket-level average order value.',
    'Shipment dates are anomalous: 100% of records have a gap greater than 90 days. Shipping efficiency, delivery delays, and route congestion cannot be inferred.',
    'Factory figures are product-associated aggregates based on the brief mapping and coordinates; they do not prove factory-level performance or actual production origin.',
    'Only 15 distinct product names are present, with 98% of records in Chocolate; the Sugar division has only 40 rows and seven products, so product/division comparisons are imbalanced.',
    'Gross margin does not include selling, marketing, distribution, inventory carrying, returns, overhead allocation, or demand elasticity unless already embedded in the supplied Cost field.',
    'The 80% Pareto threshold is a descriptive concentration rule, not an optimal product assortment target.'
])
research.add_heading('21. Conclusion',level=1)
add_paragraph(research,f"The supplied data supports a consistent gross-profit view: {currency(kpis['Total Sales'])} sales and {currency(kpis['Total Gross Profit'])} gross profit at {percent(whole_margin)} weighted gross margin. The main commercial finding is dependency: the five Chocolate products represent most revenue and profit. The main product-level review item is Kazookles due to a 7.69% gross margin; Other division's 44.84% weighted margin also merits structured cost and price investigation. The supplied data does not justify immediate discontinuations or claims of manufacturing inefficiency. The source's anomalous Ship Date values need correction before any logistics-performance conclusion. The original brief ends with a conclusion about shipping-route efficiency; that topic does not match the stated product-profitability project and is therefore not used as the principal conclusion here.")
research.add_heading('22. References',level=1)
refs=[
    'Nassau Candy Distributor. (n.d.). *Nassau Candy Distributor dataset* [Data set]. Google Drive. https://drive.google.com/file/d/1c4VDb0Pf7RCgps4aLMiSuLtdaUpU_X49/view?pli=1',
    'pandas development team. (n.d.). *User guide*. https://pandas.pydata.org/docs/user_guide/',
    'Plotly Technologies Inc. (n.d.). *Plotly Python graphing library*. https://plotly.com/python/',
    'Python Software Foundation. (n.d.). *datetime - Basic date and time types*. https://docs.python.org/3/library/datetime.html',
    'Streamlit. (n.d.). *Input widgets*. https://docs.streamlit.io/develop/api-reference/widgets',
    'Unified Mentor. (n.d.). *Product line profitability & margin performance analysis for Nassau Candy Distributor* [Project brief].',
]
for ref in refs:
    p=research.add_paragraph();p.paragraph_format.left_indent=Inches(.28);p.paragraph_format.first_line_indent=Inches(-.28);p.paragraph_format.space_after=Pt(4)
    parts=ref.split('*')
    for i,part in enumerate(parts):
        run=p.add_run(part)
        if i % 2 == 1: run.italic=True
research.add_heading('23. Appendix A: data dictionary and audit outputs',level=1)
add_paragraph(research,'The package contains data_dictionary.csv, data_quality_report.csv, cleaning_summary.csv, outlier_diagnostics.csv, annual_summary.csv, product_summary.csv, division_summary.csv, geographic summaries, monthly_summary.csv, Pareto calculations, product-factory review, and factory-associated summaries. Values in the dashboard and report are generated through the same reusable calculation module.')
research.add_heading('24. Appendix B: recommended reproducibility steps',level=1)
add_numbered(research,['Install dependencies listed in requirements.txt.','Run pytest -q from the project directory.','Run python build_outputs.py to regenerate static outputs and report documents.','Run streamlit run app.py to launch the dashboard.','When using a replacement CSV, confirm the required 18 source columns and inspect the updated data-quality panel before interpreting results.'])
research_path=BASE/'Research_Paper_Nassau_Candy.docx';research.save(research_path)

# ---------- executive summary ----------
execdoc=Document();setup_doc(execdoc,'Executive Summary')
title_page(execdoc,'Executive Summary','Product profitability and margin performance','Decision-maker briefing | Prepared 21 October 2026')
execdoc.add_heading('Purpose and approach',level=1)
add_paragraph(execdoc,f"This analysis tests whether Nassau Candy Distributor's recorded sales translate into gross profit and identifies where management should focus product pricing, cost management, and portfolio reviews. It uses {meta['final_rows']:,} usable rows from the supplied dataset, 15 products, and three product divisions. Data checks found no missing values, exact duplicate rows, or material mismatch in Gross Profit = Sales - Cost. All records remain usable for financial analysis. The major data caveat is that every Ship Date is 904-1,642 days after Order Date; shipment-performance conclusions are not reliable until those dates are verified.")
execdoc.add_heading('Headline indicators',level=1)
headline=pd.DataFrame([
 {'Indicator':'Total sales','Result':currency(kpis['Total Sales'])},
 {'Indicator':'Total gross profit','Result':currency(kpis['Total Gross Profit'])},
 {'Indicator':'Total cost','Result':currency(kpis['Total Cost'])},
 {'Indicator':'Weighted gross margin','Result':percent(whole_margin)},
 {'Indicator':'Cost as share of sales','Result':percent(cost_ratio)},
 {'Indicator':'Units recorded','Result':f"{kpis['Units']:,.0f}"},
 {'Indicator':'Distinct products / customers','Result':f"{kpis['Products']} / {kpis['Customers']:,}"},
 {'Indicator':'Monthly margin volatility','Result':f"{kpis['Monthly margin volatility (percentage points)']:.3f} percentage points (SD)"},
])
add_table(execdoc,headline,font_size=8.5)
execdoc.add_heading('What the analysis says',level=1)
add_bullets(execdoc,[
    f"**Chocolate is the earnings engine.** It generates {currency(div_choc['Sales'])} in sales, {currency(div_choc['Gross Profit'])} gross profit, {percent(div_choc['Revenue Contribution (%)'])} of revenue, and {percent(div_choc['Profit Contribution (%)'])} of gross profit. Its weighted gross margin is {percent(div_choc['Gross Margin (%)'])}.",
    f"**Profit is concentrated in five products.** The top five account for {percent(revenue_pareto.iloc[4]['Cumulative Contribution (%)'])} of revenue and {percent(profit_pareto.iloc[4]['Cumulative Contribution (%)'])} of positive gross profit. Protecting availability and margin on these products is a priority.",
    f"**Kazookles is the clearest margin-review candidate.** It has {currency(float(prod_margin_low['Sales']))} sales, {currency(float(prod_margin_low['Gross Profit']))} gross profit, {percent(float(prod_margin_low['Gross Margin'])*100)} gross margin, and {percent(float(prod_margin_low['Cost Ratio (%)']))} cost ratio. Review realized prices, discounts, cost components, and the product's strategic role before making any assortment decision.",
    f"**Other underperforms its revenue share.** Its {percent(div_other['Gross Margin (%)'])} weighted margin produces {percent(div_other['Profit Contribution (%)'])} of profit from {percent(div_other['Revenue Contribution (%)'])} of revenue. A product mix and cost review is warranted.",
    f"**High percentages on tiny products are weak evidence.** Everlasting Gobstopper has {percent(float(prod_margin_top['Gross Margin'])*100)} margin but only {currency(float(prod_margin_top['Sales']))} sales and {int(prod_margin_top['Rows'])} source rows. Validate demand before scaling it.",
    f"**Geographic exposure is measurable.** Pacific is the largest region at {currency(float(region_top['Sales']))} revenue ({percent(float(region_top['Revenue Contribution (%)']))}); California is the largest state at {currency(float(state_top['Sales']))} ({percent(float(state_top['Revenue Contribution (%)']))}). This is customer concentration, not proof of delivery congestion.",
])
execdoc.add_heading('Division comparison',level=1)
divs=divisions[['Division','Sales','Gross Profit','Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)','Rows','Products']].copy()
for c in ['Sales','Gross Profit']:divs[c]=divs[c].map(currency)
for c in ['Gross Margin (%)','Revenue Contribution (%)','Profit Contribution (%)']:divs[c]=divs[c].map(percent)
add_table(execdoc,divs,font_size=7.2)
execdoc.add_heading('Prioritized recommendations',level=1)
add_numbered(execdoc,[
    'Immediately verify the upstream Ship Date field and clarify what those dates mean. Do not use order-to-ship elapsed time as a logistics performance score until corrected.',
    'Run a focused product review for Kazookles: validate cost calculation, supplier/manufacturing cost, discounts, and net realized price; only then decide on repricing or further action.',
    'Review pricing, cost structure, and discount history for Lickable Wallpaper and Wonka Gum; use contribution profit and demand information, not margin alone.',
    'Protect the top five Chocolate products with regular availability and margin monitoring; assess portfolio diversification as a resilience measure rather than assuming low-selling products will scale.',
    "Investigate Other division's product mix and high cost burden; establish a monthly weighted-margin and contribution dashboard by product.",
    'Validate the supplied product-factory mapping. Product name coverage is 15/15, but Fizzy Lifting Drinks has a division-label mismatch between the brief and the dataset.',
])
execdoc.add_heading('Data limitations and interpretation guardrails',level=1)
add_bullets(execdoc,[
    'All products show positive aggregate gross profit in this dataset; no product should be called loss-making from the provided financial records.',
    'Gross margin is gross profit divided by sales, not full net profitability. Selling, distribution, overhead, discount, return, and demand-elasticity details are not supplied.',
    'The supplied Order ID appears product-coded, so sales divided by distinct Order IDs is not treated as definitive basket-level average order value.',
    "Factory summaries associate products with the brief's named factories; they do not measure factory operating efficiency, capacity, or actual shipment routes.",
    "The project brief's final sentence about shipping route efficiency conflicts with the central product-profitability scope; this deliverable focuses on product economics."
])
execdoc.add_heading('Bottom line',level=1)
add_paragraph(execdoc,f"The business generates a {percent(whole_margin)} weighted gross margin, but results are highly concentrated in five Chocolate products. The clearest near-term analytical action is to validate and investigate Kazookles' {percent(float(prod_margin_low['Gross Margin'])*100)} margin and review the Other division's cost burden, while correcting shipment dates before expanding into logistics KPIs. Repricing and discontinuation decisions should wait for validated price, cost-component, and demand evidence.")
exec_path=BASE/'Executive_Summary_Nassau_Candy.docx';execdoc.save(exec_path)

print('Generated outputs in', OUT)
print('Research paper:', research_path)
print('Executive summary:', exec_path)
print('KPI headline:', kpis)
