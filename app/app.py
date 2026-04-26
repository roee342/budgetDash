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
        df = conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
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
    menu = st.radio("תפריט", ["דשבורד מרכזי", "הזנת תנועה", "ניהול נכסים", "הוצאות קבועות", "הגדרות"])

# --- Helper: Date Formatters ---
def format_date(dt):
    return dt.strftime("%d-%m-%Y")

# --- Dashboard ---
if menu == "דשבורד מרכזי":
    st.title("תמונת מצב פיננסית")
    
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_liab = get_data("Liabilities")
    df_fixed = get_data("Fixed_Expenses")
    
    # 1. Basic Metrics
    total_assets = pd.to_numeric(df_assets["Value"], errors='coerce').sum() if not df_assets.empty else 0
    total_liab = pd.to_numeric(df_liab["Amount"], errors='coerce').sum() if not df_liab.empty else 0
    net_worth = total_assets - total_liab
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("שווי נקי", f"₪{net_worth:,.0f}")
    col2.metric("נכסים", f"₪{total_assets:,.0f}")
    col3.metric("התחייבויות", f"₪{total_liab:,.0f}")
    
    # Calculate Fixed Costs Total
    fixed_monthly = pd.to_numeric(df_fixed["Amount"], errors='coerce').sum() if not df_fixed.empty else 0
    col4.metric("קבועות בחודש", f"₪{fixed_monthly:,.0f}")

    if not df_trans.empty:
        df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
        df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
        df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')
        df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
        
        current_month = datetime.now().strftime("%Y-%m")
        
        # 2. Income vs Expense (Including Fixed)
        st.subheader("תזרים מזומנים (כולל קבועות)")
        
        # Aggregating monthly actuals
        df_monthly = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0).reset_index()
        
        # Adding fixed expenses to the 'Expense' column for each month
        if 'Expense' in df_monthly.columns:
            df_monthly['Expense'] += fixed_monthly
        else:
            df_monthly['Expense'] = fixed_monthly
            
        fig_flow = go.Figure()
        fig_flow.add_trace(go.Bar(name='הכנסות', x=df_monthly['Month'], y=df_monthly.get('Income', [0]), marker_color='#2ecc71'))
        fig_flow.add_trace(go.Bar(name='הוצאות', x=df_monthly['Month'], y=df_monthly['Expense'], marker_color='#e74c3c'))
        fig_flow.update_layout(barmode='group', width='stretch')
        st.plotly_chart(fig_flow, width='stretch')
        
        # 3. Savings Rate Gauge
        curr_inc = df_monthly[df_monthly['Month'] == current_month]['Income'].sum() if 'Income' in df_monthly.columns else 0
        curr_exp = df_monthly[df_monthly['Month'] == current_month]['Expense'].sum()
        
        if curr_inc > 0:
            savings_rate = ((curr_inc - curr_exp) / curr_inc) * 100
            st.subheader(f"יחס חיסכון החודש: {savings_rate:.1f}%")
            
# --- Log Transaction ---
elif menu == "הזנת תנועה":
    st.title("רישום פעולה חדשה")
    df_cats = get_data("Categories")
    
    with st.form("tx_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_type = st.selectbox("סוג פעולה", ["Expense", "Income"])
            # Logic for next month's 1st
            next_month = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1)
            date_selection = st.radio("תאריך", ["היום", "1 בחודש הבא (הכנסה צפויה)", "אחר"])
            
            if date_selection == "היום":
                final_date = datetime.now()
            elif date_selection == "1 בחודש הבא (הכנסה צפויה)":
                final_date = next_month
            else:
                final_date = st.date_input("בחר תאריך", datetime.now())
                
            amount = st.number_input("סכום", min_value=0.0)
            
        with col2:
            business = st.text_input("שם בית עסק / מקור")
            cat_list = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else ["Other"]
            category = st.selectbox("קטגוריה", cat_list)
            note = st.text_input("הערות")
            
        if st.form_submit_button("שמור בשיטס"):
            df_trans = get_data("Transactions")
            new_row = pd.DataFrame([[
                final_date.strftime("%d-%m-%Y"), business, category, "App", t_type, amount, "₪", amount, "₪", final_date.strftime("%d-%m-%Y"), note
            ]], columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            conn.update(worksheet="Transactions", data=updated_df)
            st.success(f"הפעולה נרשמה לתאריך {final_date.strftime('%d/%m')}")

# --- Portfolio & Fixed Expenses Logic remains similarly updated for 1.56.0 syntax ---
elif menu == "ניהול נכסים":
    st.title("נכסים והשקעות")
    df_assets = get_data("Assets")
    st.dataframe(df_assets, width="stretch")
    # Asset update form logic...

elif menu == "הוצאות קבועות":
    st.title("הוצאות קבועות (Subscriptions/Rent)")
    df_fixed = get_data("Fixed_Expenses")
    with st.form("fixed_form"):
        f_name = st.text_input("שם ההוצאה (למשל: ספוטיפיי)")
        f_amt = st.number_input("סכום", min_value=0.0)
        f_day = st.number_input("יום החיוב בחודש", 1, 31)
        if st.form_submit_button("הוסף הוצאה קבועה"):
            new_fixed = pd.DataFrame([[f_name, "Fixed", f_amt, f_day]], columns=["Name", "Category", "Amount", "Due_Day"])
            conn.update(worksheet="Fixed_Expenses", data=pd.concat([df_fixed, new_fixed], ignore_index=True))
            st.rerun()
    st.dataframe(df_fixed, width="stretch")

elif menu == "הגדרות":
    st.title("ניהול קטגוריות")
    df_cats = get_data("Categories")
    st.dataframe(df_cats, width="stretch")
