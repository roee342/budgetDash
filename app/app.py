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
        df = conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
        return df
    except:
        cols = {
            "Transactions": ["Date", "Type", "Category", "Amount", "Bucket", "Note"],
            "Assets": ["Type", "Name", "Value", "Last_Update"],
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
    st.markdown("---")

# --- Modules ---

if menu == "Financial Dashboard":
    st.title("Financial Overview 📊")
    
    # Load Data
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    df_buckets = get_data("Buckets")
    
    # Net Worth Calculation
    total_assets = df_assets["Value"].sum() if not df_assets.empty else 0
    total_liab = df_liab["Amount"].sum() if not df_liab.empty else 0
    total_saved = df_buckets["Saved"].sum() if not df_buckets.empty else 0
    net_worth = (total_assets + total_saved) - total_liab
    
    # Monthly Cashflow Calculation
    current_month = datetime.now().strftime("%Y-%m")
    monthly_income = 0
    monthly_expense = 0
    
    if not df_trans.empty:
        df_trans['Date'] = pd.to_datetime(df_trans['Date'])
        df_trans['Month'] = df_trans['Date'].dt.strftime('%Y-%m')
        current_month_data = df_trans[df_trans['Month'] == current_month]
        
        monthly_income = current_month_data[current_month_data["Type"] == "Income"]["Amount"].sum()
        monthly_expense = current_month_data[current_month_data["Type"] == "Expense"]["Amount"].sum()
        
    savings_rate = ((monthly_income - monthly_expense) / monthly_income * 100) if monthly_income > 0 else 0

    # Top Metrics
    st.subheader("Global Position")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Worth", f"₪{net_worth:,.0f}")
    m2.metric("Total Assets", f"₪{total_assets:,.0f}")
    m3.metric("Target Buckets", f"₪{total_saved:,.0f}")
    m4.metric("Total Liabilities", f"₪{total_liab:,.0f}", delta=f"-₪{total_liab:,.0f}", delta_color="inverse")

    st.markdown("---")
    
    st.subheader(f"Cashflow: {datetime.now().strftime('%B %Y')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly Income", f"₪{monthly_income:,.0f}")
    c2.metric("Monthly Expenses", f"₪{monthly_expense:,.0f}")
    c3.metric("Savings Rate", f"{savings_rate:.1f}%")

    # Charts
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    with col1:
        if not df_trans.empty and monthly_expense > 0:
            df_exp = current_month_data[current_month_data["Type"] == "Expense"]
            if not df_exp.empty:
                fig = px.pie(df_exp, values='Amount', names='Category', title='Expenses by Category', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expense data for this month.")

    with col2:
        if not df_trans.empty:
            df_trend = df_trans.groupby(['Month', 'Type'])['Amount'].sum().reset_index()
            fig = px.bar(df_trend, x='Month', y='Amount', color='Type', barmode='group', title='Income vs Expense Trend')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No transaction history available.")

elif menu == "New Transaction":
    st.title("Log Transaction ✨")
    
    df_cats = get_data("Categories")
    df_buckets = get_data("Buckets")
    
    with st.form("new_trans", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("Date")
            t_type = st.selectbox("Transaction Type", ["Expense", "Income"])
            amount = st.number_input("Amount (₪)", min_value=0.0, step=50.0)
        with c2:
            # Filter categories based on selected type
            if not df_cats.empty:
                filtered_cats = df_cats[df_cats["Type"] == t_type]["Name"].tolist()
            else:
                filtered_cats = ["Please add categories in Settings"]
                
            cat = st.selectbox("Category", filtered_cats if filtered_cats else ["No categories found"])
            
            folders_list = ["None"] + (df_buckets["Name"].tolist() if not df_buckets.empty else [])
            folder = st.selectbox("Assign to Bucket (Optional)", folders_list)
            note = st.text_input("Notes")
        
        if st.form_submit_button("Submit Transaction"):
            if cat in ["Please add categories in Settings", "No categories found"]:
                st.error("Please set up your categories in the Settings page first.")
            else:
                df_trans = get_data("Transactions")
                new_row = pd.DataFrame([[date.strftime("%Y-%m-%d"), t_type, cat, amount, folder, note]], 
                                        columns=df_trans.columns)
                updated = pd.concat([df_trans, new_row], ignore_index=True)
                conn.update(worksheet="Transactions", data=updated)
                st.success("Transaction logged successfully!")

elif menu == "Wealth Portfolio":
    st.title("Assets & Liabilities 🏦")
    
    tab1, tab2 = st.tabs(["Assets", "Liabilities"])
    
    with tab1:
        df_assets = get_data("Assets")
        with st.form("asset_update"):
            c1, c2, c3 = st.columns(3)
            with c1: a_type = st.selectbox("Type", ["Pension", "Study Fund", "Brokerage", "Crypto", "Cash", "Real Estate", "Other"])
            with c2: a_name = st.text_input("Institution / Name")
            with c3: a_val = st.number_input("Current Value (₪)", min_value=0.0)
            
            if st.form_submit_button("Update Asset"):
                if a_name.strip() != "":
                    if not df_assets.empty and a_name in df_assets['Name'].values:
                        df_assets.loc[df_assets['Name'] == a_name, 'Value'] = a_val
                        df_assets.loc[df_assets['Name'] == a_name, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d")
                    else:
                        new_asset = pd.DataFrame([[a_type, a_name, a_val, pd.Timestamp.now().strftime("%Y-%m-%d")]], columns=df_assets.columns)
                        df_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                    conn.update(worksheet="Assets", data=df_assets)
                    st.success("Asset updated!")
                    st.rerun()
        if not df_assets.empty: st.dataframe(df_assets, use_container_width=True)

    with tab2:
        df_liab = get_data("Liabilities")
        with st.form("liab_update"):
            c1, c2, c3 = st.columns(3)
            with c1: l_type = st.selectbox("Type", ["Credit Card", "Bank Loan", "Mortgage", "Personal Loan"])
            with c2: l_name = st.text_input("Liability Name")
            with c3: l_val = st.number_input("Outstanding Balance (₪)", min_value=0.0)
            
            if st.form_submit_button("Update Liability"):
                if l_name.strip() != "":
                    if not df_liab.empty and l_name in df_liab['Name'].values:
                        df_liab.loc[df_liab['Name'] == l_name, 'Amount'] = l_val
                        df_liab.loc[df_liab['Name'] == l_name, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d")
                    else:
                        new_liab = pd.DataFrame([[l_type, l_name, l_val, pd.Timestamp.now().strftime("%Y-%m-%d")]], columns=df_liab.columns)
                        df_liab = pd.concat([df_liab, new_liab], ignore_index=True)
                    conn.update(worksheet="Liabilities", data=df_liab)
                    st.success("Liability updated!")
                    st.rerun()
        if not df_liab.empty: st.dataframe(df_liab, use_container_width=True)

elif menu == "Target Buckets":
    st.title("Savings Buckets 🎯")
    
    with st.expander("➕ Create New Bucket"):
        with st.form("new_bucket_form"):
            c1, c2 = st.columns(2)
            with c1: b_name = st.text_input("Bucket Name")
            with c2: b_target = st.number_input("Target Amount (₪)", min_value=0.0)
            if st.form_submit_button("Create Bucket"):
                if b_name.strip() != "":
                    df_buckets = get_data("Buckets")
                    new_b = pd.DataFrame([[b_name, b_target, 0]], columns=["Name", "Target", "Saved"])
                    updated = pd.concat([df_buckets, new_b], ignore_index=True)
                    conn.update(worksheet="Buckets", data=updated)
                    st.success(f"Bucket '{b_name}' created!")
                    st.rerun()

    df_buckets = get_data("Buckets")
    if not df_buckets.empty:
        for index, row in df_buckets.iterrows():
            st.write(f"**{row['Name']}**")
            progress = min(row['Saved'] / row['Target'], 1.0) if row['Target'] > 0 else 0
            st.progress(progress)
            st.write(f"₪{row['Saved']:,.0f} / ₪{row['Target']:,.0f} ({progress*100:.1f}%)")
            
            with st.expander("Update Balance"):
                new_val = st.number_input("Current Balance", value=float(row['Saved']), key=f"val_{index}")
                if st.button("Save", key=f"btn_{index}"):
                    df_buckets.at[index, 'Saved'] = new_val
                    conn.update(worksheet="Buckets", data=df_buckets)
                    st.rerun()
            st.markdown("---")

elif menu == "Settings":
    st.title("System Settings ⚙️")
    
    st.subheader("Manage Categories")
    df_cats = get_data("Categories")
    
    with st.form("new_cat_form"):
        c1, c2 = st.columns(2)
        with c1: cat_type = st.selectbox("Category Type", ["Expense", "Income"])
        with c2: new_cat_name = st.text_input("Category Name")
        
        if st.form_submit_button("Add Category"):
            if new_cat_name.strip() != "":
                new_c = pd.DataFrame([[cat_type, new_cat_name]], columns=["Type", "Name"])
                updated = pd.concat([df_cats, new_c], ignore_index=True)
                conn.update(worksheet="Categories", data=updated)
                st.success("Category added!")
                st.rerun()
            
    if not df_cats.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Expense Categories**")
            st.dataframe(df_cats[df_cats["Type"] == "Expense"]["Name"], hide_index=True)
        with c2:
            st.write("**Income Categories**")
            st.dataframe(df_cats[df_cats["Type"] == "Income"]["Name"], hide_index=True)
