import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from io import BytesIO

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="StockSense",
    page_icon="📦",
    layout="wide"
)

# =========================================================
# CUSTOM CSS FOR PREMIUM LOOK
# =========================================================
st.markdown("""
<style>
    .main {
        background-color: #F8FAFC;
    }

    .hero-container {
        background: linear-gradient(135deg, #0F172A, #1E3A8A, #14B8A6);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    }

    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }

    .hero-subtitle {
        font-size: 1.25rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }

    .hero-owner {
        font-size: 1rem;
        opacity: 0.95;
    }

    .section-box {
        background: white;
        padding: 1.2rem 1.4rem;
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.8rem;
    }

    .callout-box {
        background: linear-gradient(135deg, #ECFDF5, #CCFBF1);
        border-left: 6px solid #14B8A6;
        padding: 1rem 1.2rem;
        border-radius: 14px;
        margin-top: 1rem;
        margin-bottom: 1rem;
        color: #0F172A;
        font-weight: 600;
    }

    .footer {
        text-align: center;
        color: #64748B;
        font-size: 0.9rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #CBD5E1;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HERO HEADER
# =========================================================
st.markdown("""
<div class="hero-container">
    <div class="hero-title">StockSense</div>
    <div class="hero-subtitle">Inventory Replenishment & Scenario Intelligence System</div>
    <div class="hero-owner">Developed by Chandra Kiran (Final Year Project – Working Model)</div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# CORE MODEL FUNCTION
# =========================================================
def run_inventory_model(df, scenario_name):
    df = df.copy()

    # Add scenario name
    df['scenario_name'] = scenario_name

    # Ensure valid service level range
    df['service_level'] = df['service_level'].clip(lower=0.0001, upper=0.9999)

    # Dynamic z-score using inverse normal distribution
    df['z_score'] = df['service_level'].apply(lambda x: norm.ppf(x))

    # Safety Stock
    df['safety_stock'] = df['z_score'] * df['demand_std_dev'] * np.sqrt(df['lead_time_days'])

    # Reorder Point
    df['reorder_point'] = (df['avg_daily_demand'] * df['lead_time_days']) + df['safety_stock']

    # Reorder decision
    df['reorder_needed'] = np.where(df['current_stock'] <= df['reorder_point'], 'Yes', 'No')

    # Stock gap
    df['stock_gap'] = df['reorder_point'] - df['current_stock']

    # Target stock for 30 days
    df['target_stock_30_days'] = df['avg_daily_demand'] * 30

    # Suggested order quantity
    df['suggested_order_qty'] = df['target_stock_30_days'] - df['current_stock']
    df['suggested_order_qty'] = df['suggested_order_qty'].clip(lower=0)

    # Stock risk classification
    conditions = [
        df['current_stock'] < df['reorder_point'] * 0.8,
        (df['current_stock'] >= df['reorder_point'] * 0.8) & (df['current_stock'] <= df['reorder_point']),
        df['current_stock'] > df['reorder_point']
    ]

    choices = ['High', 'Medium', 'Low']
    df['stock_risk'] = np.select(conditions, choices, default='Low')

    # Inventory value at risk
    df['inventory_value_risk'] = np.where(
        df['reorder_needed'] == 'Yes',
        (df['reorder_point'] - df['current_stock']).clip(lower=0) * df['unit_cost'],
        0
    )

    # Priority rank
    df['priority_rank'] = df['inventory_value_risk'].rank(method='dense', ascending=False).astype(int)

    # Round numeric columns
    round_cols = [
        'z_score',
        'lead_time_days',
        'safety_stock',
        'reorder_point',
        'stock_gap',
        'target_stock_30_days',
        'suggested_order_qty',
        'inventory_value_risk'
    ]

    for col in round_cols:
        if col == 'z_score':
            df[col] = df[col].round(4)
        else:
            df[col] = df[col].round(2)

    # Sort by priority rank
    df = df.sort_values(by='priority_rank')

    return df

# =========================================================
# SCENARIO SUMMARY FUNCTION
# =========================================================
def create_summary(df, scenario_name):
    return {
        'scenario_name': scenario_name,
        'total_skus': len(df),
        'reorder_count': int((df['reorder_needed'] == 'Yes').sum()),
        'high_risk_count': int((df['stock_risk'] == 'High').sum()),
        'medium_risk_count': int((df['stock_risk'] == 'Medium').sum()),
        'low_risk_count': int((df['stock_risk'] == 'Low').sum()),
        'total_inventory_value_at_risk': round(df['inventory_value_risk'].sum(), 2),
        'total_suggested_order_qty': round(df['suggested_order_qty'].sum(), 2)
    }

# =========================================================
# EXCEL EXPORT FUNCTION
# =========================================================
def generate_excel_download(base_output, demand_output, lead_output, service_output, scenario_summary):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        base_output.to_excel(writer, sheet_name='Base_Case', index=False)
        demand_output.to_excel(writer, sheet_name='Demand_Surge_20', index=False)
        lead_output.to_excel(writer, sheet_name='Lead_Time_Disruption_30', index=False)
        service_output.to_excel(writer, sheet_name='Service_Level_Upgrade', index=False)
        scenario_summary.to_excel(writer, sheet_name='Scenario_Summary', index=False)

    processed_data = output.getvalue()
    return processed_data

# =========================================================
# UPLOAD SECTION
# =========================================================
st.markdown('<div class="section-box">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📂 Upload Inventory Dataset</div>', unsafe_allow_html=True)

st.write("Upload an Excel file with the following required columns:")
st.code("sku_id, item_name, avg_daily_demand, demand_std_dev, lead_time_days, current_stock, service_level, unit_cost")

uploaded_file = st.file_uploader("Choose your inventory Excel file", type=["xlsx"])

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# PROCESS FILE AFTER UPLOAD
# =========================================================
if uploaded_file is not None:
    try:
        df_input = pd.read_excel(uploaded_file)

        required_columns = [
            'sku_id',
            'item_name',
            'avg_daily_demand',
            'demand_std_dev',
            'lead_time_days',
            'current_stock',
            'service_level',
            'unit_cost'
        ]

        missing_cols = [col for col in required_columns if col not in df_input.columns]

        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
        else:
            st.success("File uploaded successfully and all required columns are present.")

            # =========================================================
            # CREATE SCENARIOS
            # =========================================================
            df_base = df_input.copy()

            df_demand = df_input.copy()
            df_demand['avg_daily_demand'] = df_demand['avg_daily_demand'] * 1.20

            df_lead = df_input.copy()
            df_lead['lead_time_days'] = df_lead['lead_time_days'] * 1.30

            df_service = df_input.copy()
            df_service['service_level'] = np.where(df_service['service_level'] == 0.95, 0.99, df_service['service_level'])

            # =========================================================
            # RUN MODEL
            # =========================================================
            base_output = run_inventory_model(df_base, "Base Case")
            demand_output = run_inventory_model(df_demand, "Demand +20%")
            lead_output = run_inventory_model(df_lead, "Lead Time +30%")
            service_output = run_inventory_model(df_service, "Service Level Upgrade")

            # =========================================================
            # BUILD SCENARIO SUMMARY
            # =========================================================
            summary_data = [
                create_summary(base_output, "Base Case"),
                create_summary(demand_output, "Demand +20%"),
                create_summary(lead_output, "Lead Time +30%"),
                create_summary(service_output, "Service Level Upgrade")
            ]

            scenario_summary = pd.DataFrame(summary_data)

            base_reorder_count = scenario_summary.loc[scenario_summary['scenario_name'] == 'Base Case', 'reorder_count'].values[0]
            base_high_risk_count = scenario_summary.loc[scenario_summary['scenario_name'] == 'Base Case', 'high_risk_count'].values[0]
            base_value_at_risk = scenario_summary.loc[scenario_summary['scenario_name'] == 'Base Case', 'total_inventory_value_at_risk'].values[0]
            base_order_qty = scenario_summary.loc[scenario_summary['scenario_name'] == 'Base Case', 'total_suggested_order_qty'].values[0]

            scenario_summary['new_reorders_vs_base'] = scenario_summary['reorder_count'] - base_reorder_count
            scenario_summary['new_high_risk_skus_vs_base'] = scenario_summary['high_risk_count'] - base_high_risk_count
            scenario_summary['additional_value_at_risk_vs_base'] = scenario_summary['total_inventory_value_at_risk'] - base_value_at_risk
            scenario_summary['additional_order_qty_vs_base'] = scenario_summary['total_suggested_order_qty'] - base_order_qty

            scenario_summary['additional_value_at_risk_vs_base'] = scenario_summary['additional_value_at_risk_vs_base'].round(2)
            scenario_summary['additional_order_qty_vs_base'] = scenario_summary['additional_order_qty_vs_base'].round(2)

            # =========================================================
            # BASE CASE EXECUTIVE SUMMARY
            # =========================================================
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📊 Base Case Executive Summary</div>', unsafe_allow_html=True)

            total_skus = len(base_output)
            reorder_skus = int((base_output['reorder_needed'] == 'Yes').sum())
            high_risk_skus = int((base_output['stock_risk'] == 'High').sum())
            total_value_at_risk = round(base_output['inventory_value_risk'].sum(), 2)

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total SKUs", total_skus)
            col2.metric("Reorder SKUs", reorder_skus)
            col3.metric("High Risk SKUs", high_risk_skus)
            col4.metric("Value at Risk", f"₹ {total_value_at_risk:,.2f}")

            st.markdown('</div>', unsafe_allow_html=True)

            # =========================================================
            # SCENARIO DASHBOARD
            # =========================================================
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🚀 Scenario Intelligence Dashboard</div>', unsafe_allow_html=True)

            st.write("### Scenario Comparison Summary")
            st.dataframe(scenario_summary, use_container_width=True)

            # Strongest scenario callout
            highest_risk_scenario = scenario_summary.loc[
                scenario_summary['total_inventory_value_at_risk'].idxmax(), 'scenario_name'
            ]
            highest_risk_value = scenario_summary['total_inventory_value_at_risk'].max()

            st.markdown(
                f"""
                <div class="callout-box">
                    Highest Financial Exposure Scenario: <b>{highest_risk_scenario}</b> 
                    (Value at Risk = ₹ {highest_risk_value:,.2f})
                </div>
                """,
                unsafe_allow_html=True
            )

            # =========================================================
            # CHART 1: VALUE AT RISK BY SCENARIO
            # =========================================================
            st.write("### Financial Exposure by Scenario")

            fig1, ax1 = plt.subplots(figsize=(10, 5))
            ax1.bar(
                scenario_summary['scenario_name'],
                scenario_summary['total_inventory_value_at_risk']
            )
            ax1.set_title("Total Inventory Value at Risk by Scenario")
            ax1.set_xlabel("Scenario")
            ax1.set_ylabel("Inventory Value at Risk")
            plt.xticks(rotation=15)
            st.pyplot(fig1)

            # =========================================================
            # CHART 2: ORDER QUANTITY BY SCENARIO
            # =========================================================
            st.write("### Procurement Burden by Scenario")

            fig2, ax2 = plt.subplots(figsize=(10, 5))
            ax2.bar(
                scenario_summary['scenario_name'],
                scenario_summary['total_suggested_order_qty']
            )
            ax2.set_title("Total Suggested Order Quantity by Scenario")
            ax2.set_xlabel("Scenario")
            ax2.set_ylabel("Suggested Order Quantity")
            plt.xticks(rotation=15)
            st.pyplot(fig2)

            st.markdown('</div>', unsafe_allow_html=True)

            # =========================================================
            # TOP PRIORITY ITEMS (BASE CASE)
            # =========================================================
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">⚠️ Top Priority Items (Base Case)</div>', unsafe_allow_html=True)

            top_priority = base_output[['sku_id', 'item_name', 'stock_risk', 'inventory_value_risk', 'priority_rank']].head(10)
            st.dataframe(top_priority, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)

            # =========================================================
            # DOWNLOAD SECTION
            # =========================================================
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">⬇️ Download Scenario Output</div>', unsafe_allow_html=True)

            excel_data = generate_excel_download(
                base_output,
                demand_output,
                lead_output,
                service_output,
                scenario_summary
            )

            st.download_button(
                label="Download Full Scenario Analysis Excel File",
                data=excel_data,
                file_name="inventory_scenario_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
<div class="footer">
    © 2026 Chandra Kiran | MBA Final Year Project | Roll No: 24MBMA83
</div>
""", unsafe_allow_html=True)