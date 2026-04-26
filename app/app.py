import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Config ---
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
    st.info(f"שלום {datetime.now().strftime('%d/%m/%Y')}")
    menu = st.radio("ניווט", ["דשבורד מרכזי", "ניתוח הוצאות", "ניהול נכסים", "הזנת תנועה"])

# --- Logic: Data Prep ---
df_trans = data["Transactions"]
if not df_trans.empty:
    df_trans['Charge_Amount'] = pd.to_numeric(df_trans['Charge_Amount'], errors='coerce').fillna(0)
    df_trans['Date_DT'] = pd.to_datetime(df_trans['Transaction_Date'], format='%d-%m-%Y', errors='coerce').fillna(pd.to_datetime(df_trans['Transaction_Date'], errors='coerce'))
    df_trans['Month'] = df_trans['Date_DT'].dt.strftime('%Y-%m')
    df_trans['Calc_Type'] = df_trans['Deal_Type'].apply(lambda x: 'Income' if str(x).strip().lower() == 'income' else 'Expense')

fixed_monthly_sum = pd.to_numeric(data["Fixed_Expenses"]["Amount"], errors='coerce').sum() if not data["Fixed_Expenses"].empty else 0

# --- 1. Main Dashboard ---
if menu == "דשבורד מרכזי":
    st.title("תקציר מנהלים")
    
    # Metrics
    total_assets = pd.to_numeric(data["Assets"]["Value"], errors='coerce').sum() if not data["Assets"].empty else 0
    total_liab = pd.to_numeric(data["Liabilities"]["Amount"], errors='coerce').sum() if not data["Liabilities"].empty else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("שווי נקי", f"₪{total_assets - total_liab:,.0f}")
    col2.metric("נכסים", f"₪{total_assets:,.0f}")
    col3.metric("התחייבויות", f"₪{total_liab:,.0f}")
    col4.metric("הוצאות קבועות", f"₪{fixed_monthly_sum:,.0f}")

    # Cash Flow Graph
    if not df_trans.empty:
        st.subheader("תזרים חודשי (הוצאות משתנות + קבועות)")
        df_monthly = df_trans.groupby(['Month', 'Calc_Type'])['Charge_Amount'].sum().unstack(fill_value=0)
        if 'Income' not in df_monthly.columns: df_monthly['Income'] = 0
        if 'Expense' not in df_monthly.columns: df_monthly['Expense'] = 0
        
        df_monthly = df_monthly.reset_index()
        df_monthly['Total_Expense'] = df_monthly['Expense'] + fixed_monthly_sum
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='הכנסות', x=df_monthly['Month'], y=df_monthly['Income'], marker_color='#00C49F'))
        fig.add_trace(go.Bar(name='סך הוצאות', x=df_monthly['Month'], y=df_monthly['Total_Expense'], marker_color='#FF8042'))
        fig.update_layout(barmode='group', margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

# --- 2. Expense Analysis ---
elif menu == "ניתוח הוצאות":
    st.title("לאן הכסף הולך?")
    
    if not df_trans.empty:
        current_month = datetime.now().strftime("%Y-%m")
        df_curr = df_trans[(df_trans['Month'] == current_month) & (df_trans['Calc_Type'] == 'Expense')]
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("התפלגות לפי קטגוריות")
            fig_pie = px.pie(df_curr, values='Charge_Amount', names='Category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.subheader("הוצאות גדולות החודש")
            top_spenders = df_curr.sort_values('Charge_Amount', ascending=False).head(10)
            st.table(top_spenders[['Business_Name', 'Charge_Amount', 'Transaction_Date']])

# --- 3. Assets ---
elif menu == "ניהול נכסים":
    st.title("תיק נכסים")
    if not data["Assets"].empty:
        fig_assets = px.treemap(data["Assets"], path=['Type', 'Name'], values='Value', color='Type')
        st.plotly_chart(fig_assets, use_container_width=True)
        st.dataframe(data["Assets"], use_container_width=True)

# --- 4. Log Transaction ---
elif menu == "הזנת תנועה":
    st.title("הזנה מהירה")
    df_cats = data["Categories"]
    
    with st.form("quick_log", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_type = st.selectbox("סוג", ["Expense", "Income"])
            next_1st = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1)
            date_opt = st.radio("תאריך", ["היום", "1 לחודש הבא (הכנסה צפויה)", "ידני"])
            
            if date_opt == "היום": final_d = datetime.now()
            elif date_opt == "1 לחודש הבא (הכנסה צפויה)": final_d = next_1st
            else: final_d = st.date_input("בחר", datetime.now())
            
            amount = st.number_input("סכום", min_value=0.0)
            
        with col2:
            biz = st.text_input("עסק / מקור")
            cat_list = df_cats[df_cats["Type"] == t_type]["Name"].tolist() if not df_cats.empty else ["Other"]
            cat = st.selectbox("קטגוריה", cat_list)
            note = st.text_input("הערה")
            
        if st.form_submit_button("שמור"):
            new_row = pd.DataFrame([[
                final_d.strftime("%d-%m-%Y"), biz, cat, "App", t_type, amount, "₪", amount, "₪", final_d.strftime("%d-%m-%Y"), note
            ]], columns=["Transaction_Date", "Business_Name", "Category", "Card_Digits", "Deal_Type", "Charge_Amount", "Charge_Currency", "Deal_Amount", "Deal_Currency", "Charge_Date", "Notes"])
            
            updated = pd.concat([df_trans, new_row], ignore_index=True)
            conn.update(worksheet="Transactions", data=updated)
            st.success("נשמר!")
