import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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

# --- Sidebar ---
with st.sidebar:
    st.title("💸 WealthFlow Pro")
    st.write(f"Logged in: {datetime.now().strftime('%b %d, %Y')}")
    menu = st.radio("Navigation", ["Global Dashboard", "Log Transaction", "Settings"])

# --- Logic: Data Processing ---
df_trans = data["Transactions"]
if not df_trans.empty:
    df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
    # Supporting DD-MM-YYYY (Israel format) and ISO fallback
    df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
    df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
    df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')

fixed_monthly_total = pd.to_numeric(data["Fixed_Expenses"]["Amount"], errors='coerce').sum() if not data["Fixed_Expenses"].empty else 0

# --- 1. Global Dashboard ---
if menu == "Global Dashboard":
    st.title("Executive Financial Overview")
    
    # KPIs Row
    total_assets = pd.to_numeric(data["Assets"]["Value"], errors='coerce').sum() if not data["Assets"].empty else 0
    total_liab = pd.to_numeric(data["Liabilities"]["Amount"], errors='coerce').sum() if not data["Liabilities"].empty else 0
    net_worth = total_assets - total_liab
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Net Worth", f"₪{net_worth:,.0f}")
    k2.metric("Total Assets", f"₪{total_assets:,.0f}")
    k3.metric("Liabilities", f"₪{total_liab:,.0f}")
    k4.metric("Fixed Costs", f"₪{fixed_monthly_total:,.0f}", help="Sum of all subscription/rent entries")

    st.divider()

    # Trends & Forecasts Row
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Monthly Income vs. All Expenses")
        if not df_trans.empty:
            df_monthly = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0)
            if 'Income' not in df_monthly.columns: df_monthly['Income'] = 0
            if 'Expense' not in df_monthly.columns: df_monthly['Expense'] = 0
            
            df_monthly = df_monthly.reset_index()
            # Adding fixed expenses to the bars
            df_monthly['Total_Expense'] = df_monthly['Expense'] + fixed_monthly_total
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(name='Income', x=df_monthly['Month'], y=df_monthly['Income'], marker_color='#2ecc71'))
            fig_trend.add_trace(go.Bar(name='Total Expenses', x=df_monthly['Month'], y=df_monthly['Total_Expense'], marker_color='#e74c3c'))
            fig_trend.update_layout(barmode='group', height=400)
            st.plotly_chart(fig_trend, use_container_width=True)

    with col_right:
        st.subheader("Net Worth Growth")
        df_hist = data["Asset_History"]
        if not df_hist.empty:
            df_hist['Date'] = pd.to_datetime(df_hist['Date'])
            df_growth = df_hist.groupby('Date')['Value'].sum().reset_index()
            fig_growth = px.line(df_growth, x='Date', y='Value', line_shape='spline', markers=True)
            fig_growth.update_traces(line_color='#3498db')
            st.plotly_chart(fig_growth, use_container_width=True)

    st.divider()

    # Distribution & Categories Row
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Spending by Category (Current Month)")
        curr_month = datetime.now().strftime("%Y-%m")
        df_curr = df_trans[(df_trans['Month'] == curr_month) & (df_trans['Calc_Type'] == 'Expense')]
        if not df_curr.empty:
            fig_pie = px.pie(df_curr, values='Charge_Amount', names='Category', hole=0.5, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No variable expenses logged this month.")

    with c2:
        st.subheader("Asset Allocation")
        if not data["Assets"].empty:
            fig_assets = px.treemap(data["Assets"], path=['Type', 'Name'], values='Value', color='Value', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_assets, use_container_width=True)

# --- 2. Log Transaction ---
elif menu == "Log Transaction":
    st.title("Add New Transaction")
    df_cats = data["Categories"]
    
    with st.form("tx_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_type = st.selectbox("Transaction Type", ["Expense", "Income"])
            next_1st = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1)
            date_mode = st.radio("Date", ["Today", "1st of Next Month (Expected)", "Custom"])
            
            if date_mode == "Today": final_date = datetime.now()
            elif date_mode == "1st of Next Month (Expected)": final_date = next_1st
            else: final_date = st.date_input("Pick Date", datetime.now())
                
            amount = st.number_input("Amount (₪)", min_value=0.0)
            
        with col2:
            biz = st.text_input("Merchant / Source")
            cat_list = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else ["General"]
            category = st.selectbox("Category", cat_list)
            note = st.text_input("Notes")
            
        if st.form_submit_button("Submit to WealthFlow"):
            df_trans = data["Transactions"]
            new_row = pd.DataFrame([[
                final_date.strftime("%d-%m-%Y"), biz, category, "Manual", t_type, amount, "₪", amount, "₪", final_date.strftime("%d-%m-%Y"), note
            ]], columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            conn.update(worksheet="Transactions", data=updated_df)
            st.success(f"Successfully logged ₪{amount} to {category} on {final_date.strftime('%d-%m-%Y')}")

# --- 3. Settings ---
elif menu == "Settings":
    st.title("Data Management")
    tabs = st.tabs(["Categories", "Fixed Expenses", "Assets"])
    
    with tabs[0]:
        st.dataframe(data["Categories"], use_container_width=True)
    with tabs[1]:
        st.dataframe(data["Fixed_Expenses"], use_container_width=True)
    with tabs[2]:
        st.dataframe(data["Assets"], use_container_width=True)
