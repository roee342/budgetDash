import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

# --- Config ---
st.set_page_config(page_title="WealthFlow Pro", layout="wide")

# --- Connection & Data Schema ---
conn = st.connection("gsheets", type=GSheetsConnection)

SHEET_SCHEMAS = {
    "Transactions": ["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"],
    "Income": ["date", "income"],
    "Assets": ["Type", "Name", "Value", "Last_Update"],
    "Asset_History": ["Date", "Asset_Name", "Value"],
    "Liabilities": ["Type", "Name", "Amount", "Last_Update"],
    "Fixed_Expenses": ["Name", "Category", "Amount", "Due_Day"],
    "Categories": ["Type", "Name"]
}

def get_all_data():
    data = {}
    for sheet_name, cols in SHEET_SCHEMAS.items():
        try:
            df = conn.read(worksheet=sheet_name, ttl=2).dropna(how="all")
            if df.empty: df = pd.DataFrame(columns=cols)
            data[sheet_name] = df
        except:
            data[sheet_name] = pd.DataFrame(columns=cols)
    return data

data = get_all_data()

# --- Time Logic ---
now = datetime.now()
curr_month_str = now.strftime("%Y-%m") # 2026-04
# Next month logic for Salary/Fixed linkage
next_month_date = (now.replace(day=28) + pd.Timedelta(days=5))
next_month_str = next_month_date.strftime("%Y-%m") # 2026-05

# --- Installment Logic Upgrade ---
def calculate_active_installments(df):
    if 'Notes' not in df.columns or df.empty: return 0
    future_debt = 0
    for _, row in df.iterrows():
        note = str(row.get('Notes', ''))
        match = re.search(r'תשלום\s+(\d+)\s+מתוך\s+(\d+)', note)
        if match:
            current_idx, total_idx = int(match.group(1)), int(match.group(2))
            # Check if it's already finished
            if current_idx < total_idx:
                # Check if the transaction date suggests it's still active relative to today
                charge_amt = pd.to_numeric(row.get('Charge_Amount', 0), errors='coerce')
                remaining = total_idx - current_idx
                future_debt += (remaining * charge_amt)
    return future_debt

# --- Sidebar ---
with st.sidebar:
    st.title("💸 WealthFlow Pro")
    menu = st.radio("Navigation", ["Global Dashboard", "Log Transaction", "Log Salary", "Settings"])

# --- 1. Global Dashboard ---
if menu == "Global Dashboard":
    st.title(f"Executive Dashboard - {now.strftime('%B %Y')}")
    
    # 1. Process Transactions
    df_trans = data["Transactions"]
    df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
    df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
    df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
    df_trans['Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')

    # 2. Process Fixed & Salary (Value Month Logic)
    # Filter Salary for 'Next Month' (e.g. May)
    df_inc = data["Income"]
    if not df_inc.empty:
        df_inc['dt'] = pd.to_datetime(df_inc['date'], format='%d-%m-%Y', errors='coerce')
        df_inc['Month'] = df_inc['dt'].dt.strftime('%Y-%m')
    
    salary_val = df_inc[df_inc['Month'] == next_month_str]['income'].sum() if not df_inc.empty else 0
    fixed_val = pd.to_numeric(data["Fixed_Expenses"]["Amount"], errors='coerce').sum() if not data["Fixed_Expenses"].empty else 0
    
    # 3. Variable Expenses (Current Month)
    var_exp_curr = df_trans[(df_trans['Month'] == curr_month_str) & (df_trans['Type'] == 'Expense')]['Charge_Amount'].sum()
    
    # 4. Installments
    inst_debt = calculate_active_installments(df_trans)

    # Top Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("April Variable Spend", f"₪{var_exp_curr:,.0f}")
    m2.metric("May Opening Salary", f"₪{salary_val:,.0f}")
    m3.metric("Monthly Fixed Costs", f"₪{fixed_val:,.0f}")
    m4.metric("Active Installments", f"₪{inst_debt:,.0f}")

    st.divider()

    # GRAPH 1: TOTAL SPENDING TREND
    st.subheader("📊 Total Monthly Spending Trend (Variable + Fixed)")
    df_trend = df_trans[df_trans['Type'] == 'Expense'].groupby('Month')['Charge_Amount'].sum().reset_index()
    df_trend['Total'] = df_trend['Charge_Amount'] + fixed_val
    fig1 = px.bar(df_trend, x='Month', y='Total', text_auto='.2s', color_discrete_sequence=['#e74c3c'])
    fig1.update_layout(height=500)
    st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # GRAPH 2: INCOME VS EXPENSES (Linked Logic)
    st.subheader("📈 Salary (Next Month) vs Expenses (Current Month)")
    # Grouping income by the month it was received
    if not df_inc.empty:
        comparison_data = []
        for m in df_trend['Month'].unique():
            # Get next month's salary for this month's expense
            m_dt = datetime.strptime(m, "%Y-%m")
            next_m = (m_dt.replace(day=28) + pd.Timedelta(days=5)).strftime("%Y-%m")
            
            inc = df_inc[df_inc['Month'] == next_m]['income'].sum()
            exp = df_trend[df_trend['Month'] == m]['Total'].sum()
            comparison_data.append({"Month": m, "Salary_for_this": inc, "Total_Exp": exp})
        
        df_comp = pd.DataFrame(comparison_data)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name='Expected Salary (1st of Next)', x=df_comp['Month'], y=df_comp['Salary_for_this'], marker_color='#2ecc71'))
        fig2.add_trace(go.Bar(name='Current Month Expenses', x=df_comp['Month'], y=df_comp['Total_Exp'], marker_color='#e74c3c'))
        fig2.update_layout(height=500, barmode='group')
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # GRAPH 3: ASSET DISTRIBUTION (RESTORED)
    st.subheader("📂 Asset Allocation")
    if not data["Assets"].empty:
        fig3 = px.treemap(data["Assets"], path=['Type', 'Name'], values='Value', 
                          color='Value', color_continuous_scale='RdYlGn')
        fig3.update_layout(height=600)
        st.plotly_chart(fig3, use_container_width=True)

# --- 2. Log Transaction ---
elif menu == "Log Transaction":
    st.title("Log Variable Transaction")
    with st.form("tx_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            t_date = st.date_input("Date", datetime.now())
            t_type = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount (₪)", min_value=0.0)
        with c2:
            biz = st.text_input("Merchant")
            cat = st.text_input("Category")
            notes = st.text_input("Notes (e.g., תשלום 1 מתוך 3)")
        if st.form_submit_button("Save"):
            new_row = pd.DataFrame([[t_date.strftime("%d-%m-%Y"), biz, cat, "App", t_type, amount, "₪", amount, "₪", t_date.strftime("%d-%m-%Y"), notes]], 
                                   columns=SHEET_SCHEMAS["Transactions"])
            conn.update(worksheet="Transactions", data=pd.concat([data["Transactions"], new_row], ignore_index=True))
            st.success("Transaction Logged!")

# --- 3. Log Salary ---
elif menu == "Log Salary":
    st.title("Log Salary (Entry for the 1st of Next Month)")
    st.info("Example: Entering April salary which is received on May 1st. Set date to May 1st.")
    with st.form("inc_form", clear_on_submit=True):
        i_date = st.date_input("Date Received", datetime.now())
        i_amt = st.number_input("Net Salary (₪)", min_value=0.0)
        if st.form_submit_button("Save Salary"):
            new_inc = pd.DataFrame([[i_date.strftime("%d-%m-%Y"), i_amt]], columns=SHEET_SCHEMAS["Income"])
            conn.update(worksheet="Income", data=pd.concat([data["Income"], new_inc], ignore_index=True))
            st.success("Salary Recorded!")

# --- 4. Settings ---
elif menu == "Settings":
    st.title("Data Preview")
    st.dataframe(data["Transactions"], use_container_width=True)
