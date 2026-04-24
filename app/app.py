import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- Page Config & Styling ---
st.set_page_config(page_title="WealthFlow OS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stExpander"] { border: 1px solid #30363d; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4f46e5; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- Data Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
        return df
    except:
        cols = {
            "Transactions": ["Date", "Type", "Category", "Amount", "Bucket", "Note"],
            "Assets": ["Type", "Name", "Value", "Last_Update"],
            "Asset_History": ["Date", "Asset_Name", "Value"],
            "Liabilities": ["Type", "Name", "Amount", "Last_Update"],
            "Buckets": ["Name", "Target", "Saved"],
            "Categories": ["Type", "Name"],
            "Fixed_Expenses": ["Name", "Category", "Amount", "Due_Day"] # טבלה חדשה
        }
        return pd.DataFrame(columns=cols.get(sheet_name, []))

# --- Navigation ---
with st.sidebar:
    st.title("WealthFlow OS 🌐")
    st.markdown("---")
    menu = st.radio("Navigation", [
        "Financial Dashboard", 
        "New Transaction", 
        "Fixed Expenses",
        "Wealth Portfolio",
        "Target Buckets", 
        "Settings"
    ])

# --- Modules ---

if menu == "Financial Dashboard":
    st.title("Financial Intelligence 📊")
    
    # Load all data
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    df_buckets = get_data("Buckets")
    df_fixed = get_data("Fixed_Expenses")
    df_history = get_data("Asset_History")
    
    # --- 1. Global Metrics (Net Worth) ---
    total_assets = df_assets["Value"].sum() if not df_assets.empty else 0
    total_liab = df_liab["Amount"].sum() if not df_liab.empty else 0
    total_saved = df_buckets["Saved"].sum() if not df_buckets.empty else 0
    net_worth = (total_assets + total_saved) - total_liab
    
    st.subheader("Global Position")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Worth", f"₪{net_worth:,.0f}")
    m2.metric("Total Assets", f"₪{total_assets:,.0f}")
    m3.metric("Liabilities", f"₪{total_liab:,.0f}", delta_color="inverse")
    
    total_overhead = df_fixed["Amount"].sum() if not df_fixed.empty else 0
    m4.metric("Fixed Monthly Overhead", f"₪{total_overhead:,.0f}")

    st.markdown("---")
    
    # --- 2. Monthly Performance & Savings Rate ---
    current_month = datetime.now().strftime("%Y-%m")
    m_inc, m_exp = 0, 0
    
    if not df_trans.empty:
        df_trans['Date'] = pd.to_datetime(df_trans['Date'])
        df_trans['Month'] = df_trans['Date'].dt.strftime('%Y-%m')
        m_inc = df_trans[(df_trans['Month'] == current_month) & (df_trans['Type'] == 'Income')]['Amount'].sum()
        m_exp = df_trans[(df_trans['Month'] == current_month) & (df_trans['Type'] == 'Expense')]['Amount'].sum()
    
    savings_rate = ((m_inc - m_exp) / m_inc * 100) if m_inc > 0 else 0
    
    st.subheader(f"Monthly Performance ({datetime.now().strftime('%B %Y')})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly Income", f"₪{m_inc:,.0f}")
    c2.metric("Monthly Expenses", f"₪{m_exp:,.0f}")
    
    # Highlight Savings Rate
    savings_color = "normal" if savings_rate >= 0 else "inverse"
    c3.metric("SAVINGS RATE", f"{savings_rate:.1f}%", delta=f"Target: >20%", delta_color="off")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. The Grand Dashboard (4 Charts) ---
    st.subheader("Deep Dive Analytics")
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    
    # Chart 1: Expense Distribution (Current Month)
    with row1_col1:
        if not df_trans.empty and m_exp > 0:
            df_curr_exp = df_trans[(df_trans['Month'] == current_month) & (df_trans['Type'] == 'Expense')]
            if not df_curr_exp.empty:
                fig1 = px.pie(df_curr_exp, values='Amount', names='Category', hole=0.5, title='Expense Distribution (This Month)')
                st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("No expense data for this month.")

    # Chart 2: Asset Allocation
    with row1_col2:
        if not df_assets.empty and total_assets > 0:
            fig2 = px.pie(df_assets, values='Value', names='Type', hole=0.5, title='Asset Allocation')
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No asset data available.")

    # Chart 3: Income vs Expense Trend (Historical)
    with row2_col1:
        if not df_trans.empty:
            df_trend = df_trans.groupby(['Month', 'Type'])['Amount'].sum().reset_index()
            fig3 = px.bar(df_trend, x='Month', y='Amount', color='Type', barmode='group', title='Income & Expense Trends', color_discrete_map={"Income": "#10b981", "Expense": "#ef4444"})
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Not enough data for historical trends.")

    # Chart 4: Portfolio Growth Trend
    with row2_col2:
        if not df_history.empty:
            df_history['Date'] = pd.to_datetime(df_history['Date'])
            df_history = df_history.sort_values('Date')
            # Group by Date and sum up all assets for that date snapshot
            hist_trend = df_history.groupby('Date')['Value'].sum().reset_index()
            fig4 = px.area(hist_trend, x='Date', y='Value', title='Total Portfolio Growth', markers=True)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Update your assets to start tracking portfolio trends.")

elif menu == "New Transaction":
    st.title("Log Transaction ✨")
    df_cats = get_data("Categories")
    df_buckets = get_data("Buckets")
    
    with st.form("new_trans", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("Date")
            t_type = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount (₪)", min_value=0.0)
        with c2:
            filtered_cats = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else []
            cat = st.selectbox("Category", filtered_cats if filtered_cats else ["Other"])
            folder = st.selectbox("Assign to Bucket", ["None"] + (df_buckets["Name"].tolist() if not df_buckets.empty else []))
            note = st.text_input("Note")
        
        if st.form_submit_button("Log Transaction"):
            df_trans = get_data("Transactions")
            new_row = pd.DataFrame([[date.strftime("%Y-%m-%d"), t_type, cat, amount, folder, note]], columns=df_trans.columns)
            conn.update(worksheet="Transactions", data=pd.concat([df_trans, new_row], ignore_index=True))
            st.success("Transaction Logged Successfully!")

elif menu == "Fixed Expenses":
    st.title("Fixed Monthly Overhead 🏠")
    st.markdown("Track your recurring bills and subscriptions. This calculates your baseline cost of living.")
    
    df_fixed = get_data("Fixed_Expenses")
    df_cats = get_data("Categories")
    
    with st.expander("➕ Add New Fixed Expense"):
        with st.form("new_fixed"):
            c1, c2, c3 = st.columns(3)
            with c1: f_name = st.text_input("Expense Name (e.g., Rent, Netflix)")
            with c2: 
                exp_cats = df_cats[df_cats["Type"] == "Expense"]["Name"].tolist() if not df_cats.empty else ["Other"]
                f_cat = st.selectbox("Category", exp_cats)
            with c3: 
                f_amount = st.number_input("Monthly Amount (₪)", min_value=0.0)
                f_day = st.number_input("Billing Day (1-31)", min_value=1, max_value=31, step=1)
            
            if st.form_submit_button("Save Fixed Expense"):
                if f_name:
                    new_f = pd.DataFrame([[f_name, f_cat, f_amount, f_day]], columns=df_fixed.columns)
                    conn.update(worksheet="Fixed_Expenses", data=pd.concat([df_fixed, new_f], ignore_index=True))
                    st.rerun()

    if not df_fixed.empty:
        st.dataframe(df_fixed, use_container_width=True)
        st.info(f"💡 Your total fixed baseline is **₪{df_fixed['Amount'].sum():,.0f}** every month.")

elif menu == "Wealth Portfolio":
    st.title("Wealth Portfolio 📈")
    df_assets = get_data("Assets")
    df_history = get_data("Asset_History")
    
    # Updated highly detailed asset types
    asset_types = ["Checking (Osh)", "Hishtalmut", "Stock", "ETF", "Pension", "Crypto", "Real Estate", "Other"]
    
    with st.form("asset_update"):
        c1, c2, c3 = st.columns(3)
        with c1: a_type = st.selectbox("Asset Type", asset_types)
        with c2: a_name = st.text_input("Asset Name / Ticker (e.g., VOO, Altshuler)")
        with c3: a_val = st.number_input("Current Value (₪)", min_value=0.0)
        a_date = st.date_input("Date of Valuation")
        
        if st.form_submit_button("Update Asset Valuation"):
            if a_name:
                # Update current view
                if not df_assets.empty and a_name in df_assets['Name'].values:
                    df_assets.loc[df_assets['Name'] == a_name, 'Value'] = a_val
                    df_assets.loc[df_assets['Name'] == a_name, 'Type'] = a_type
                    df_assets.loc[df_assets['Name'] == a_name, 'Last_Update'] = a_date.strftime("%Y-%m-%d")
                else:
                    new_asset = pd.DataFrame([[a_type, a_name, a_val, a_date.strftime("%Y-%m-%d")]], columns=df_assets.columns)
                    df_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                conn.update(worksheet="Assets", data=df_assets)
                
                # Update history for trends
                new_hist = pd.DataFrame([[a_date.strftime("%Y-%m-%d"), a_name, a_val]], columns=df_history.columns)
                conn.update(worksheet="Asset_History", data=pd.concat([df_history, new_hist], ignore_index=True))
                st.rerun()

    st.subheader("Current Holdings")
    if not df_assets.empty:
        st.dataframe(df_assets, use_container_width=True)

elif menu == "Target Buckets":
    st.title("Savings Buckets 🎯")
    df_buckets = get_data("Buckets")
    
    with st.expander("➕ Create New Bucket"):
        with st.form("new_b"):
            n = st.text_input("Bucket Name")
            t = st.number_input("Target Amount", min_value=0.0)
            if st.form_submit_button("Add Bucket"):
                new_b = pd.DataFrame([[n, t, 0]], columns=df_buckets.columns)
                conn.update(worksheet="Buckets", data=pd.concat([df_buckets, new_b], ignore_index=True))
                st.rerun()

    for idx, row in df_buckets.iterrows():
        st.write(f"**{row['Name']}**")
        prog = min(row['Saved']/row['Target'], 1.0) if row['Target'] > 0 else 0
        st.progress(prog)
        c1, c2 = st.columns([3, 1])
        with c1:
            val = st.number_input("Current Balance", value=float(row['Saved']), key=f"b_{idx}")
        with c2:
            st.write("") # spacer
            st.write("") # spacer
            if st.button("Save", key=f"btn_{idx}"):
                df_buckets.at[idx, 'Saved'] = val
                conn.update(worksheet="Buckets", data=df_buckets)
                st.rerun()

elif menu == "Settings":
    st.title("System Settings ⚙️")
    df_cats = get_data("Categories")
    
    st.subheader("Category Management")
    with st.form("new_cat"):
        t = st.selectbox("Type", ["Expense", "Income"])
        n = st.text_input("Category Name")
        if st.form_submit_button("Add Category"):
            if n:
                new_c = pd.DataFrame([[t, n]], columns=df_cats.columns)
                conn.update(worksheet="Categories", data=pd.concat([df_cats, new_c], ignore_index=True))
                st.rerun()
                
    if not df_cats.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Expense Categories**")
            st.dataframe(df_cats[df_cats["Type"] == "Expense"], hide_index=True)
        with c2:
            st.write("**Income Categories**")
            st.dataframe(df_cats[df_cats["Type"] == "Income"], hide_index=True)
