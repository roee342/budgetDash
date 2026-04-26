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
    sheets = ["Transactions", "Assets", "Asset_History", "Liabilities", "Buckets", "Categories", "Fixed_Expenses", "Income"]
    data = {}
    for s in sheets:
        try:
            df = conn.read(worksheet=s, ttl=2).dropna(how="all")
            data[s] = df
        except:
            data[s] = pd.DataFrame()
    return data

data = get_all_data()

# --- Helper Logic ---
def calculate_future_installments(df):
    if df.empty: return 0
    future_debt = 0
    for _, row in df.iterrows():
        note = str(row.get('Notes', ''))
        match = re.search(r'תשלום\s+(\d+)\s+מתוך\s+(\d+)', note)
        if match:
            current_idx, total_idx = int(match.group(1)), int(match.group(2))
            charge_amt = pd.to_numeric(row.get('Charge_Amount', 0), errors='coerce')
            remaining = total_idx - current_idx
            if remaining > 0: future_debt += (remaining * charge_amt)
    return future_debt

# --- Sidebar ---
with st.sidebar:
    st.title("💸 WealthFlow Pro")
    menu = st.radio("Navigation", ["Dashboard", "Log Transaction", "Log Income", "Settings"])

# --- 1. Global Dashboard ---
if menu == "Dashboard":
    st.title("Executive Financial Overview")
    
    # Data Prep
    df_trans = data["Transactions"]
    df_fixed = data["Fixed_Expenses"]
    df_inc = data["Income"]
    
    # Calculations
    fixed_total = pd.to_numeric(df_fixed["Amount"], errors='coerce').sum() if not df_fixed.empty else 0
    future_inst_debt = calculate_future_installments(df_trans)
    
    current_month = datetime.now().strftime("%Y-%m")
    next_month = (datetime.now().replace(day=28) + timedelta(days=5)).strftime("%Y-%m")
    
    # Current Month Spending (Variable + Fixed)
    var_exp_curr = 0
    if not df_trans.empty:
        df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
        df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
        df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
        df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')
        var_exp_curr = df_trans[(df_trans['Month'] == current_month) & (df_trans['Calc_Type'] == 'Expense')]['Charge_Amount'].sum()

    # Expected Next Month Start (Fixed + Transactions dated for 1st)
    future_start_exp = fixed_total
    if not df_trans.empty:
        future_start_exp += df_trans[(df_trans['Month'] == next_month) & (df_trans['Calc_Type'] == 'Expense')]['Charge_Amount'].sum()

    # KPI Row
    total_assets = pd.to_numeric(data["Assets"]["Value"], errors='coerce').sum() if not data["Assets"].empty else 0
    total_liab = pd.to_numeric(data["Liabilities"]["Amount"], errors='coerce').sum() if not data["Liabilities"].empty else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Month Spend", f"₪{var_exp_curr + fixed_total:,.0f}", delta=f"Var: ₪{var_exp_curr:,.0f}", delta_color="inverse")
    m2.metric("Next Month Opening", f"₪{future_start_exp:,.0f}", help="Fixed costs + scheduled transactions for next month")
    m3.metric("Installments Debt", f"₪{future_inst_debt:,.0f}")
    m4.metric("Net Worth", f"₪{total_assets - total_liab - future_inst_debt:,.0f}")

    st.divider()

    # CHART 1: MONTHLY SPENDING TREND (Full Width)
    st.subheader("📊 Total Monthly Spending Trend")
    if not df_trans.empty:
        df_trend = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0)
        if 'Expense' not in df_trend.columns: df_trend['Expense'] = 0
        df_trend = df_trend.reset_index()
        df_trend['Total_Expense'] = df_trend['Expense'] + fixed_total
        
        fig1 = px.bar(df_trend, x='Month', y='Total_Expense', text_auto='.2s', color_discrete_sequence=['#e74c3c'])
        fig1.update_layout(height=450, margin=dict(t=20, b=20))
        st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # CHART 2: INCOME VS EXPENSES (Full Width)
    st.subheader("📈 Income vs. Expenses Comparison")
    # Merge Income sheet data with Transactions
    if not df_inc.empty and not df_trans.empty:
        df_inc['date_dt'] = pd.to_datetime(df_inc['date'], format='%d-%m-%Y', errors='coerce')
        df_inc['Month'] = df_inc['date_dt'].dt.strftime('%Y-%m')
        inc_monthly = df_inc.groupby('Month')['income'].sum().reset_index()
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name='Actual Income', x=inc_monthly['Month'], y=inc_monthly['income'], marker_color='#2ecc71'))
        fig2.add_trace(go.Bar(name='Total Expenses', x=df_trend['Month'], y=df_trend['Total_Expense'], marker_color='#e74c3c'))
        fig2.update_layout(height=450, barmode='group')
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # CHART 3: INSTALLMENT LIABILITIES (Full Width)
    st.subheader("💳 Future Debt from Installments")
    inst_df = df_trans[df_trans['Notes'].str.contains('מתוך', na=False)].copy()
    if not inst_df.empty:
        def calc_rem(row):
            m = re.search(r'תשלום\s+(\d+)\s+מתוך\s+(\d+)', str(row['Notes']))
            if m: return (int(m.group(2)) - int(m.group(1))) * row['Charge_Amount']
            return 0
        inst_df['Remaining'] = inst_df.apply(calc_rem, axis=1)
        debt_biz = inst_df.groupby('Business_Name')['Remaining'].sum().reset_index()
        debt_biz = debt_biz[debt_biz['Remaining'] > 0]
        fig3 = px.bar(debt_biz, x='Business_Name', y='Remaining', color='Remaining', color_continuous_scale='Reds')
        fig3.update_layout(height=450)
        st.plotly_chart(fig3, use_container_width=True)

# --- 2. Log Transaction ---
elif menu == "Log Transaction":
    st.title("Log Variable Transaction")
    # Form logic for Transactions (11 columns)
    with st.form("tx_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            t_date = st.date_input("Date", datetime.now())
            t_type = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount (₪)", min_value=0.0)
        with c2:
            biz = st.text_input("Merchant")
            category = st.text_input("Category")
            notes = st.text_input("Notes (use 'תשלום X מתוך Y' for installments)")
        if st.form_submit_button("Save"):
            new_row = pd.DataFrame([[t_date.strftime("%d-%m-%Y"), biz, category, "App", t_type, amount, "₪", amount, "₪", t_date.strftime("%d-%m-%Y"), notes]], 
                                   columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            conn.update(worksheet="Transactions", data=pd.concat([data["Transactions"], new_row], ignore_index=True))
            st.success("Transaction Saved!")

# --- 3. Log Income (New Tab) ---
elif menu == "Log Income":
    st.title("Log Salary / Monthly Income")
    with st.form("inc_form", clear_on_submit=True):
        inc_date = st.date_input("Date", datetime.now())
        inc_amount = st.number_input("Net Income (₪)", min_value=0.0)
        if st.form_submit_button("Save Income"):
            new_inc = pd.DataFrame([[inc_date.strftime("%d-%m-%Y"), inc_amount]], columns=["date", "income"])
            conn.update(worksheet="Income", data=pd.concat([data["Income"], new_inc], ignore_index=True))
            st.success("Income Logged!")

# --- 4. Settings ---
elif menu == "Settings":
    st.title("Settings")
    st.write("View raw data sheets here.")
