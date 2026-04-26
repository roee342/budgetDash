import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(page_title="WealthFlow Pro", layout="wide")

# --- Data Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=2).dropna(how="all")
        return df
    except Exception:
        cols = {
            "Transactions": ["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"],
            "Assets": ["Type", "Name", "Value", "Last_Update"],
            "Asset_History": ["Date", "Asset_Name", "Value"],
            "Liabilities": ["Type", "Name", "Amount", "Last_Update"],
            "Buckets": ["Name", "Target", "Saved"],
            "Categories": ["Type", "Name"],
            "Fixed_Expenses": ["Name", "Category", "Amount", "Due_Day"]
        }
        return pd.DataFrame(columns=cols.get(sheet_name, []))

# --- Navigation ---
with st.sidebar:
    st.title("WealthFlow Pro")
    menu = st.radio("Menu", ["Dashboard", "Log Transaction", "Portfolio", "Fixed Expenses", "Settings"])

# --- Dashboard ---
if menu == "Dashboard":
    st.title("Financial Overview")
    
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    df_fixed = get_data("Fixed_Expenses")
    
    total_assets = pd.to_numeric(df_assets["Value"], errors='coerce').sum() if not df_assets.empty else 0
    total_liab = pd.to_numeric(df_liab["Amount"], errors='coerce').sum() if not df_liab.empty else 0
    net_worth = total_assets - total_liab
    fixed_total = pd.to_numeric(df_fixed["Amount"], errors='coerce').sum() if not df_fixed.empty else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Worth", f"₪{net_worth:,.0f}")
    m2.metric("Assets", f"₪{total_assets:,.0f}")
    m3.metric("Liabilities", f"₪{total_liab:,.0f}")
    m4.metric("Fixed (Monthly)", f"₪{fixed_total:,.0f}")

    if not df_trans.empty:
        df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
        # תמיכה בפורמט התאריך של האשראי
        df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
        df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
        df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')
        
        st.subheader("Income vs Expenses Trend")
        # יצירת Pivot יציב
        df_trend = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0)
        
        # וידוא קיום עמודות כדי למנוע את ה-ValueError
        if 'Income' not in df_trend.columns: df_trend['Income'] = 0.0
        if 'Expense' not in df_trend.columns: df_trend['Expense'] = 0.0
        
        df_trend = df_trend.reset_index()
        df_trend['Expense'] += fixed_total  # הוספת קבועות

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(name='Income', x=df_trend['Month'], y=df_trend['Income'], marker_color='#2ecc71'))
        fig_trend.add_trace(go.Bar(name='Expenses', x=df_trend['Month'], y=df_trend['Expense'], marker_color='#e74c3c'))
        fig_trend.update_layout(barmode='group', margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_trend, use_container_width=True)

# --- Log Transaction ---
elif menu == "Log Transaction":
    st.title("New Action")
    df_cats = get_data("Categories")
    
    with st.form("tx_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            next_month_1st = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1)
            date_type = st.radio("Date Selection", ["Today", "1st of Next Month", "Manual"])
            
            if date_type == "Today": final_t_date = datetime.now()
            elif date_type == "1st of Next Month": final_t_date = next_month_1st
            else: final_t_date = st.date_input("Pick Date", datetime.now())
                
            t_type = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount", min_value=0.0)
            
        with col2:
            business = st.text_input("Business / Source")
            cat_list = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else ["Other"]
            category = st.selectbox("Category", cat_list)
            note = st.text_input("Notes")
            
        if st.form_submit_button("Save"):
            df_trans = get_data("Transactions")
            # 11 עמודות בסדר ברזל
            new_row = pd.DataFrame([[
                final_t_date.strftime("%d-%m-%Y"), business, category, "App", t_type, amount, "₪", amount, "₪", final_t_date.strftime("%d-%m-%Y"), note
            ]], columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            conn.update(worksheet="Transactions", data=updated_df)
            st.success("Saved Successfully!")

# --- Navigation Placeholders ---
elif menu in ["Portfolio", "Fixed Expenses", "Settings"]:
    st.info(f"Section {menu} is active. Use the sidebar to navigate.")
