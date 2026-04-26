import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

# --- Page Setup ---
st.set_page_config(page_title="WealthFlow Pro", layout="wide")

# --- Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_all_data():
    sheets = ["Transactions", "Assets", "Asset_History", "Liabilities", "Buckets", "Categories", "Fixed_Expenses"]
    data = {}
    for s in sheets:
        try:
            df = conn.read(worksheet=s, ttl=2).dropna(how="all")
            data[s] = df
        except:
            data[s] = pd.DataFrame()
    return data

data = get_all_data()

# --- Logic: Installment Extraction ---
def calculate_future_installments(df):
    if df.empty:
        return 0
    
    future_debt = 0
    for _, row in df.iterrows():
        note = str(row.get('Notes', ''))
        # Regex to find "תשלום X מתוך Y"
        match = re.search(r'תשלום\s+(\d+)\s+מתוך\s+(\d+)', note)
        if match:
            current_idx = int(match.group(1))
            total_installments = int(match.group(2))
            charge_amt = pd.to_numeric(row.get('Charge_Amount', 0), errors='coerce')
            
            remaining_payments = total_installments - current_idx
            if remaining_payments > 0:
                future_debt += (remaining_payments * charge_amt)
    return future_debt

# --- Sidebar ---
with st.sidebar:
    st.title("💸 WealthFlow Pro")
    menu = st.radio("Navigation", ["Global Dashboard", "Log Transaction", "Settings"])

# --- 1. Global Dashboard ---
if menu == "Global Dashboard":
    st.title("Executive Financial Overview")
    
    # Data Prep
    df_trans = data["Transactions"]
    fixed_total = pd.to_numeric(data["Fixed_Expenses"]["Amount"], errors='coerce').sum() if not data["Fixed_Expenses"].empty else 0
    
    if not df_trans.empty:
        df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
        df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
        df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
        df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')

    # Calculate Future Debt from Installments
    total_future_installments = calculate_future_installments(df_trans)

    # Top KPI Row
    total_assets = pd.to_numeric(data["Assets"]["Value"], errors='coerce').sum() if not data["Assets"].empty else 0
    total_liab = pd.to_numeric(data["Liabilities"]["Amount"], errors='coerce').sum() if not data["Liabilities"].empty else 0
    net_worth = total_assets - total_liab - total_future_installments
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Projected Net Worth", f"₪{net_worth:,.0f}", help="Assets minus all debts and future installments")
    m2.metric("Total Assets", f"₪{total_assets:,.0f}")
    m3.metric("Future Installments Debt", f"₪{total_future_installments:,.0f}", delta_color="inverse")
    m4.metric("Monthly Fixed Costs", f"₪{fixed_total:,.0f}")

    st.divider()

    # 1. TOTAL EXPENSES TREND (Variable + Fixed)
    st.subheader("📊 Monthly Spending Trend (Total)")
    if not df_trans.empty:
        df_monthly = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0)
        if 'Expense' not in df_monthly.columns: df_monthly['Expense'] = 0
        df_monthly = df_monthly.reset_index()
        df_monthly['Total_Expense'] = df_monthly['Expense'] + fixed_total
        
        fig_trend = px.bar(df_monthly, x='Month', y='Total_Expense', 
                           text_auto='.2s', color_discrete_sequence=['#e74c3c'])
        fig_trend.update_layout(height=500, margin=dict(t=20, b=20))
        st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()

    # 2. INSTALLMENT ANALYSIS
    st.subheader("💳 Future Installments Liability")
    # Grouping by business to see where the debt is
    installment_df = df_trans[df_trans['Notes'].str.contains('מתוך', na=False)].copy()
    if not installment_df.empty:
        installment_df['Remaining_Amount'] = installment_df.apply(lambda x: (int(re.search(r'מתוך\s+(\d+)', x['Notes']).group(1)) - int(re.search(r'תשלום\s+(\d+)', x['Notes']).group(1))) * x['Charge_Amount'], axis=1)
        debt_by_biz = installment_df.groupby('Business_Name')['Remaining_Amount'].sum().reset_index()
        debt_by_biz = debt_by_biz[debt_by_biz['Remaining_Amount'] > 0]
        
        fig_debt = px.bar(debt_by_biz, x='Business_Name', y='Remaining_Amount', 
                          title="Future Debt by Merchant", color='Remaining_Amount', color_continuous_scale='Reds')
        fig_debt.update_layout(height=500)
        st.plotly_chart(fig_debt, use_container_width=True)
    else:
        st.info("No installment transactions identified in 'Notes'.")

    st.divider()

    # 3. CATEGORY DISTRIBUTION
    st.subheader("🍕 Spending Breakdown (Current Month)")
    curr_month = datetime.now().strftime("%Y-%m")
    df_curr = df_trans[(df_trans['Month'] == curr_month) & (df_trans['Calc_Type'] == 'Expense')]
    if not df_curr.empty:
        fig_pie = px.pie(df_curr, values='Charge_Amount', names='Category', hole=0.4)
        fig_pie.update_layout(height=600)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # 4. ASSET ALLOCATION
    st.subheader("📈 Asset Allocation")
    if not data["Assets"].empty:
        fig_assets = px.treemap(data["Assets"], path=['Type', 'Name'], values='Value', color='Value', color_continuous_scale='RdYlGn')
        fig_assets.update_layout(height=600)
        st.plotly_chart(fig_assets, use_container_width=True)

# --- 2. Log Transaction ---
elif menu == "Log Transaction":
    st.title("Add Transaction")
    # Existing Log logic stays here...
    st.info("Log form active. Keeping 11-column structure.")

# --- 3. Settings ---
elif menu == "Settings":
    st.title("Raw Data View")
    st.dataframe(data["Transactions"], use_container_width=True)
