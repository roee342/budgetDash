import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# --- הגדרות עמוד ועיצוב ---
st.set_page_config(page_title="WealthFlow OS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stExpander"] { border: 1px solid #30363d; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4f46e5; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- חיבור לנתונים ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl=5).dropna(how="all")
    except:
        cols = {
            "Transactions": ["Date", "Category", "Type", "Amount", "Folder", "Note"],
            "Assets": ["Asset_Type", "Name", "Value", "Last_Update"],
            "Buckets": ["Bucket_Name", "Target_Amount", "Saved_Amount"],
            "Categories": ["Category_Name"] # גיליון חדש לקטגוריות דינמיות
        }
        return pd.DataFrame(columns=cols.get(sheet_name, []))

# --- ניווט צד ---
with st.sidebar:
    st.title("WealthFlow OS")
    st.markdown("---")
    menu = st.radio("תפריט ראשי", [
        "דשבורד כללי", 
        "הזנת תנועה", 
        "תיקיות כסף (Buckets)", 
        "נכסים ופנסיה", 
        "הגדרות קטגוריה"
    ])
    st.markdown("---")

# --- מודולים ---

if menu == "דשבורד כללי":
    st.title("מצב הון משפחתי 📊")
    
    df_trans = get_data("Transactions")
    df_assets = get_data("Assets")
    df_buckets = get_data("Buckets")
    
    total_assets = df_assets["Value"].sum() if not df_assets.empty else 0
    total_saved_in_buckets = df_buckets["Saved_Amount"].sum() if not df_buckets.empty else 0
    net_worth = total_assets + total_saved_in_buckets
    
    m1, m2, m3 = st.columns(3)
    m1.metric("סה\"כ שווי נקי", f"₪{net_worth:,.0f}")
    m2.metric("נכסים", f"₪{total_assets:,.0f}")
    m3.metric("חיסכון בתיקיות", f"₪{total_saved_in_buckets:,.0f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("התפלגות נכסים")
        if not df_assets.empty and total_assets > 0:
            fig = px.pie(df_assets, values='Value', names='Asset_Type', hole=0.5,
                         color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("אין נתוני נכסים או שהשווי הוא 0")

    with col2:
        st.subheader("תזרים חודשי (הוצאות)")
        if not df_trans.empty:
            df_exp = df_trans[df_trans["Type"] == "הוצאה"]
            if not df_exp.empty:
                fig = px.bar(df_exp, x='Category', y='Amount', color='Category', title="הוצאות לפי קטגוריה")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("אין עדיין הוצאות מדווחות.")
        else:
            st.write("אין נתוני תנועות.")

elif menu == "הזנת תנועה":
    st.title("הוספת פעולה חדשה ✨")
    
    df_cats = get_data("Categories")
    cats_list = df_cats["Category_Name"].tolist() if not df_cats.empty else ["אנא הוסף קטגוריות בהגדרות"]
    
    df_buckets = get_data("Buckets")
    folders_list = ["ללא שיוך לתיקייה"] + (df_buckets["Bucket_Name"].tolist() if not df_buckets.empty else [])

    with st.form("new_trans", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("תאריך")
            t_type = st.selectbox("סוג", ["הוצאה", "הכנסה"])
            amount = st.number_input("סכום (₪)", min_value=0.0)
        with c2:
            cat = st.selectbox("קטגוריה", cats_list)
            folder = st.selectbox("שיוך לתיקיית כסף", folders_list)
            note = st.text_input("הערה")
        
        if st.form_submit_button("שמור במערכת"):
            if cat == "אנא הוסף קטגוריות בהגדרות":
                st.error("חובה ליצור קטגוריות במסך ההגדרות לפני הזנת תנועה.")
            else:
                df_trans = get_data("Transactions")
                new_row = pd.DataFrame([[date.strftime("%Y-%m-%d"), cat, t_type, amount, folder, note]], 
                                        columns=df_trans.columns)
                updated = pd.concat([df_trans, new_row], ignore_index=True)
                conn.update(worksheet="Transactions", data=updated)
                st.success("הפעולה נשמרה בהצלחה!")

elif menu == "תיקיות כסף (Buckets)":
    st.title("תיקיות כסף ליעדים 📂")
    st.markdown("כאן אתה פותח ומנהל תיקיות וירטואליות עבור יעדים ספציפיים.")
    
    # טופס פתיחת תיקייה חדשה
    with st.form("new_bucket_form", clear_on_submit=True):
        st.subheader("פתיחת תיקייה חדשה")
        c1, c2 = st.columns(2)
        with c1:
            b_name = st.text_input("שם התיקייה החדשה")
        with c2:
            b_target = st.number_input("סכום יעד", min_value=0.0)
            
        if st.form_submit_button("פתח תיקייה"):
            if b_name.strip() == "":
                st.warning("חובה להזין שם לתיקייה.")
            else:
                df_buckets = get_data("Buckets")
                if b_name in df_buckets["Bucket_Name"].values:
                    st.error("קיימת כבר תיקייה בשם זה.")
                else:
                    new_b = pd.DataFrame([[b_name, b_target, 0]], columns=df_buckets.columns)
                    updated = pd.concat([df_buckets, new_b], ignore_index=True)
                    conn.update(worksheet="Buckets", data=updated)
                    st.success(f"התיקייה '{b_name}' נפתחה בהצלחה!")
                    st.rerun()

    st.markdown("---")
    st.subheader("התיקיות שלך")
    df_buckets = get_data("Buckets")
    if not df_buckets.empty:
        for index, row in df_buckets.iterrows():
            st.write(f"**{row['Bucket_Name']}**")
            progress = min(row['Saved_Amount'] / row['Target_Amount'], 1.0) if row['Target_Amount'] > 0 else 0
            st.progress(progress)
            st.write(f"₪{row['Saved_Amount']:,.0f} מתוך ₪{row['Target_Amount']:,.0f} ({progress*100:.1f}%)")
            
            with st.expander(f"ערוך יתרה - {row['Bucket_Name']}"):
                new_val = st.number_input("עדכן סכום עדכני בתיקייה", value=float(row['Saved_Amount']), key=f"val_{index}")
                if st.button("שמור שינויים", key=f"btn_{index}"):
                    df_buckets.at[index, 'Saved_Amount'] = new_val
                    conn.update(worksheet="Buckets", data=df_buckets)
                    st.rerun()
            st.markdown("---")
    else:
        st.info("עדיין לא פתחת תיקיות. השתמש בטופס למעלה כדי לפתוח את התיקייה הראשונה שלך.")

elif menu == "נכסים ופנסיה":
    st.title("ניהול פורטפוליו נכסים 🏦")
    df_assets = get_data("Assets")
    
    with st.form("asset_update"):
        a_type = st.selectbox("סוג נכס", ["פנסיה", "קרן השתלמות", "קופת גמל", "תיק השקעות", "מזומן", "אחר"])
        a_name = st.text_input("שם המוסד / קופה")
        a_val = st.number_input("ערך נוכחי", min_value=0.0)
        if st.form_submit_button("עדכן נכס"):
            if a_name.strip() != "":
                if not df_assets.empty and a_name in df_assets['Name'].values:
                    df_assets.loc[df_assets['Name'] == a_name, 'Value'] = a_val
                    df_assets.loc[df_assets['Name'] == a_name, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d")
                else:
                    new_asset = pd.DataFrame([[a_type, a_name, a_val, pd.Timestamp.now().strftime("%Y-%m-%d")]], 
                                             columns=df_assets.columns)
                    df_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                conn.update(worksheet="Assets", data=df_assets)
                st.success("עודכן בהצלחה!")
                st.rerun()
    
    if not df_assets.empty:
        st.dataframe(df_assets, use_container_width=True)

elif menu == "הגדרות קטגוריה":
    st.title("ניהול קטגוריות ⚙️")
    st.markdown("כאן אתה מגדיר את קטגוריות ההוצאה/הכנסה שיופיעו במסך הזנת התנועות.")
    
    df_cats = get_data("Categories")
    
    with st.form("new_cat_form"):
        new_cat_name = st.text_input("שם קטגוריה חדשה")
        if st.form_submit_button("הוסף קטגוריה"):
            if new_cat_name.strip() != "":
                if not df_cats.empty and new_cat_name in df_cats['Category_Name'].values:
                    st.warning("הקטגוריה כבר קיימת.")
                else:
                    new_c = pd.DataFrame([[new_cat_name]], columns=["Category_Name"])
                    updated = pd.concat([df_cats, new_c], ignore_index=True)
                    conn.update(worksheet="Categories", data=updated)
                    st.success("נוסף בהצלחה!")
                    st.rerun()
            
    if not df_cats.empty:
        st.subheader("קטגוריות קיימות:")
        st.dataframe(df_cats, use_container_width=True)
