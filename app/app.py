import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
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
        return conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
    except:
        cols = {
            "Transactions": ["Date", "Type", "Category", "Amount", "Bucket", "Note"],
            "Assets": ["Type", "Name", "Value", "Last_Update"],
            "Asset_History": ["Date", "Asset_Name", "Value"],
            "Liabilities": ["Type", "Name", "Amount", "Last_Update"],
            "Buckets": ["Name", "Target", "Saved"],
            "Categories": ["Type", "Name"]
        }
        return pd.DataFrame(columns=cols.get(sheet_name, []))

# --- Navigation ---
with st.sidebar:
    st.title("WealthFlow OS 🌐")
    st.markdown("---")
    menu = st.radio("Navigation", [
        "Financial Dashboard", 
        "New Transaction", 
        "Wealth Portfolio",
        "Target Buckets", 
        "Settings"
    ])

# --- Modules ---

if menu == "Financial Dashboard":
    st.title("Financial Overview 📊")
    
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    df_buckets = get_data("Buckets")
    
    total_assets = df_assets["Value"].sum() if not df_assets.empty else 0
    total_liab = df_liab["Amount"].sum() if not df_liab.empty else 0
    total_saved = df_buckets["Saved"].sum() if not df_buckets.empty else 0
    net_worth = (total_assets + total_saved) - total_liab
    
    # Net Worth & High-level metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Worth", f"₪{net_worth:,.0f}")
    m2.metric("Total Assets", f"₪{total_assets:,.0f}")
    m3.metric("Savings Buckets", f"₪{total_saved:,.0f}")
    m4.metric("Liabilities", f"₪{total_liab:,.0f}", delta_color="inverse")

    st.markdown("---")
    
    # Monthly Cashflow
    if not df_trans.empty:
        df_trans['Date'] = pd.to_datetime(df_trans['Date'])
        current_month = datetime.now().strftime("%Y-%m")
        df_trans['Month'] = df_trans['Date'].dt.strftime('%Y-%m')
        
        m_inc = df_trans[(df_trans['Month'] == current_month) & (df_trans['Type'] == 'Income')]['Amount'].sum()
        m_exp = df_trans[(df_trans['Month'] == current_month) & (df_trans['Type'] == 'Expense')]['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Income (Month)", f"₪{m_inc:,.0f}")
        c2.metric("Expense (Month)", f"₪{m_exp:,.0f}")
        c3.metric("Savings Rate", f"{((m_inc-m_exp)/m_inc*100):.1f}%" if m_inc > 0 else "0%")

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
            folder = st.selectbox("Bucket", ["None"] + (df_buckets["Name"].tolist() if not df_buckets.empty else []))
            note = st.text_input("Note")
        
        if st.form_submit_button("Log Transaction"):
            df_trans = get_data("Transactions")
            new_row = pd.DataFrame([[date.strftime("%Y-%m-%d"), t_type, cat, amount, folder, note]], columns=df_trans.columns)
            conn.update(worksheet="Transactions", data=pd.concat([df_trans, new_row], ignore_index=True))
            st.success("Logged!")

elif menu == "Wealth Portfolio":
    st.title("Wealth Portfolio & Trends 📈")
    df_assets = get_data("Assets")
    df_history = get_data("Asset_History")
    
    tab1, tab2 = st.tabs(["Asset Management", "Performance Trends"])
    
    with tab1:
        with st.form("asset_update"):
            c1, c2, c3 = st.columns(3)
            with c1: a_name = st.text_input("Security/Asset Name (e.g. IB Portfolio)")
            with c2: a_val = st.number_input("Current Value (₪)", min_value=0.0)
            with c3: a_date = st.date_input("Validity Date (Update Date)")
            
            a_type = st.selectbox("Asset Type", ["Pension", "Study Fund", "Brokerage", "Crypto", "Cash", "Real Estate"])
            
            if st.form_submit_button("Update Portfolio Entry"):
                if a_name:
                    # 1. Update Current Assets Sheet
                    if not df_assets.empty and a_name in df_assets['Name'].values:
                        df_assets.loc[df_assets['Name'] == a_name, 'Value'] = a_val
                        df_assets.loc[df_assets['Name'] == a_name, 'Last_Update'] = a_date.strftime("%Y-%m-%d")
                    else:
                        new_asset = pd.DataFrame([[a_type, a_name, a_val, a_date.strftime("%Y-%m-%d")]], columns=df_assets.columns)
                        df_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                    conn.update(worksheet="Assets", data=df_assets)
                    
                    # 2. Record in History for Trends
                    new_hist = pd.DataFrame([[a_date.strftime("%Y-%m-%d"), a_name, a_val]], columns=df_history.columns)
                    conn.update(worksheet="Asset_History", data=pd.concat([df_history, new_hist], ignore_index=True))
                    
                    st.success(f"Updated {a_name} for date {a_date}")
                    st.rerun()

        st.dataframe(df_assets, use_container_width=True)

    with tab2:
        if not df_history.empty:
            df_history['Date'] = pd.to_datetime(df_history['Date'])
            df_history = df_history.sort_values('Date')
            
            # Grouping for Multi-month trend
            asset_to_track = st.selectbox("Select Asset to View Trend", ["All Assets"] + df_history['Asset_Name'].unique().tolist())
            
            if asset_to_track == "All Assets":
                # Resample to monthly if needed or just show all
                fig = px.line(df_history, x='Date', y='Value', color='Asset_Name', title="Asset Value Over Time")
            else:
                filtered_h = df_history[df_history['Asset_Name'] == asset_to_track]
                fig = px.area(filtered_h, x='Date', y='Value', title=f"Trend for {asset_to_track}")
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data yet. Start updating assets to see trends.")

elif menu == "Target Buckets":
    st.title("Savings Buckets 🎯")
    df_buckets = get_data("Buckets")
    
    with st.expander("Create New Bucket"):
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
        val = st.number_input("Update Saved Amount", value=float(row['Saved']), key=f"b_{idx}")
        if st.button("Save", key=f"btn_{idx}"):
            df_buckets.at[idx, 'Saved'] = val
            conn.update(worksheet="Buckets", data=df_buckets)
            st.rerun()

elif menu == "Settings":
    st.title("Settings ⚙️")
    df_cats = get_data("Categories")
    with st.form("new_cat"):
        t = st.selectbox("Type", ["Expense", "Income"])
        n = st.text_input("Category Name")
        if st.form_submit_button("Add Category"):
            new_c = pd.DataFrame([[t, n]], columns=df_cats.columns)
            conn.update(worksheet="Categories", data=pd.concat([df_cats, new_c], ignore_index=True))
            st.rerun()
    st.dataframe(df_cats)
