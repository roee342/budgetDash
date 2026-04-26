import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="WealthFlow OS", layout="wide")

# --- Data Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
        return df
    except Exception:
        # סכמה מדויקת של 11 עמודות לפי הבקשה שלך
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
    st.title("WealthFlow OS")
    menu = st.radio("Menu", ["Dashboard", "Log Transaction", "Portfolio", "Fixed Expenses", "Settings"])

# --- Dashboard ---
if menu == "Dashboard":
    st.title("Financial Overview")
    
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    
    total_assets = pd.to_numeric(df_assets["Value"], errors='coerce').sum() if not df_assets.empty else 0
    total_liab = pd.to_numeric(df_liab["Amount"], errors='coerce').sum() if not df_liab.empty else 0
    net_worth = total_assets - total_liab
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Net Worth", f"₪{net_worth:,.0f}")
    m2.metric("Assets", f"₪{total_assets:,.0f}")
    m3.metric("Liabilities", f"₪{total_liab:,.0f}")

    if not df_trans.empty:
        # ניקוי נתונים: הפיכת סכום החיוב למספר
        df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
        
        # המרת עמודת "תאריך עסקה" (הראשונה) לפורמט תאריך לצורך גרפים
        df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
        
        # הגדרת סוג (הוצאה/הכנסה)
        df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')
        
        current_month = datetime.now().strftime("%Y-%m")
        df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
        
        st.subheader("Monthly Expenses")
        df_month = df_trans[(df_trans['Month'] == current_month) & (df_trans['Calc_Type'] == 'Expense')]
        if not df_month.empty and df_month['Charge_Amount'].sum() > 0:
            fig = px.pie(df_month, values='Charge_Amount', names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expense data for this month.")
        
        st.subheader("Income vs Expense Trend")
        df_trend = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().reset_index()
        if not df_trend.empty:
            fig_trend = px.bar(df_trend, x='Month', y='Charge_Amount', color='Calc_Type', barmode='group')
            st.plotly_chart(fig_trend, use_container_width=True)

# --- Log Transaction ---
elif menu == "Log Transaction":
    st.title("New Transaction")
    df_cats = get_data("Categories")
    
    with st.form("tx_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_date = st.date_input("Transaction Date", datetime.now())
            c_date = st.date_input("Charge Date", datetime.now()) # תאריך חיוב
            t_type = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount", min_value=0.0)
        with col2:
            business = st.text_input("Business Name")
            cat_list = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else ["Other"]
            category = st.selectbox("Category", cat_list)
            note = st.text_input("Note")
            
        if st.form_submit_button("Save to Sheets"):
            df_trans = get_data("Transactions")
            # בניית שורה של 11 עמודות בדיוק לפי הסדר
            new_row = pd.DataFrame([[
                t_date.strftime("%d-%m-%Y"), business, category, "App", t_type, amount, "₪", amount, "₪", c_date.strftime("%d-%m-%Y"), note
            ]], columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            conn.update(worksheet="Transactions", data=updated_df)
            st.success("Transaction recorded.")

# --- Portfolio (שאר הקוד נשאר זהה) ---
elif menu == "Portfolio":
    st.title("Assets & History")
    df_assets = get_data("Assets")
    df_history = get_data("Asset_History")
    
    with st.form("asset_form"):
        a_type = st.selectbox("Type", ["Checking (Osh)", "Hishtalmut", "Stock", "ETF", "Pension", "Crypto", "Real Estate"])
        a_name = st.text_input("Asset Name")
        a_val = st.number_input("Value", min_value=0.0)
        a_date = st.date_input("Valuation Date", datetime.now())
        
        if st.form_submit_button("Update Asset"):
            if not df_assets.empty and a_name in df_assets['Name'].values:
                df_assets.loc[df_assets['Name'] == a_name, 'Value'] = a_val
                df_assets.loc[df_assets['Name'] == a_name, 'Last_Update'] = a_date.strftime("%Y-%m-%d")
            else:
                new_asset = pd.DataFrame([[a_type, a_name, a_val, a_date.strftime("%Y-%m-%d")]], columns=["Type", "Name", "Value", "Last_Update"])
                df_assets = pd.concat([df_assets, new_asset], ignore_index=True)
            conn.update(worksheet="Assets", data=df_assets)
            
            new_hist = pd.DataFrame([[a_date.strftime("%Y-%m-%d"), a_name, a_val]], columns=["Date", "Asset_Name", "Value"])
            conn.update(worksheet="Asset_History", data=pd.concat([df_history, new_hist], ignore_index=True))
            st.rerun()

    st.dataframe(df_assets, use_container_width=True)
    
    if not df_history.empty:
        st.subheader("Growth Trend")
        df_history['Date'] = pd.to_datetime(df_history['Date'])
        fig_growth = px.line(df_history.sort_values('Date'), x='Date', y='Value', color='Asset_Name')
        st.plotly_chart(fig_growth, use_container_width=True)

# --- Fixed Expenses & Settings (נשאר זהה) ---
elif menu == "Fixed Expenses":
    st.title("Monthly Fixed Costs")
    df_fixed = get_data("Fixed_Expenses")
    st.dataframe(df_fixed, use_container_width=True)

elif menu == "Settings":
    st.title("Categories")
    df_cats = get_data("Categories")
    st.dataframe(df_cats, use_container_width=True)
