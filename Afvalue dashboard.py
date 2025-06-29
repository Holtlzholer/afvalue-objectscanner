import streamlit as st
import pandas as pd
import os
from datetime import datetime
import altair as alt

# === AFVALUE huisstijl kleuren ===
AFVALUE_GREEN = "#00C853"
AFVALUE_DARK = "#263238"
AFVALUE_ACCENT = "#546E7A"
FONT_FAMILY = "'Poppins', sans-serif"

# === Styling ===
def apply_afvalue_style():
    st.markdown(f"""
        <style>
        html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; color: {AFVALUE_DARK}; }}
        h1, h2, h3 {{ color: {AFVALUE_DARK}; font-weight: 600; }}
        .stButton button {{ background-color: {AFVALUE_GREEN}; color: white; border: none; padding: 0.5em 1.2em; border-radius: 6px; font-weight: 600; }}
        .stButton button:hover {{ background-color: #00a843; }}
        .stAlert {{ background-color: #E0F2F1; border-left: 5px solid {AFVALUE_GREEN}; }}
        </style>
    """, unsafe_allow_html=True)

# === Config ===
EXCEL_LOG = "resultaten_log.xlsx"

# === Pagina setup ===
st.set_page_config(page_title="Afvalue Resultaten Dashboard", layout="wide")
apply_afvalue_style()
st.title("📊 Afvalue Resultaten Dashboard")

# === Data laden ===
if os.path.exists(EXCEL_LOG):
    df = pd.read_excel(EXCEL_LOG)
else:
    st.error(f"Logbestand '{EXCEL_LOG}' niet gevonden.")
    st.stop()

# Conversie tijdkolom
df['Tijd'] = pd.to_datetime(df['Tijd'], errors='coerce')

# === Filters ===
st.sidebar.header("🔍 Filters")
locaties = ["Alle"] + sorted(df['Locatie'].dropna().unique().tolist())
kies_locatie = st.sidebar.selectbox("Locatie filter", locaties)

start_datum = st.sidebar.date_input("Startdatum", value=df['Tijd'].min().date())
eind_datum = st.sidebar.date_input("Einddatum", value=df['Tijd'].max().date())

# Filter toepassing
filtered_df = df[(df['Tijd'].dt.date >= start_datum) & (df['Tijd'].dt.date <= eind_datum)]
if kies_locatie != "Alle":
    filtered_df = filtered_df[filtered_df['Locatie'] == kies_locatie]

# === Metrics ===
st.subheader("📈 Kernstatistieken")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Aantal scans", len(filtered_df))
col2.metric("Gemiddelde score", round(filtered_df['Score'].mean(), 2))
col3.metric("Unieke categorieën", filtered_df['Categorie'].nunique())
col4.metric("Periode", f"{start_datum} - {eind_datum}")

# === Tabel ===
st.subheader("🗂️ Gedetailleerde resultaten")
st.dataframe(filtered_df, use_container_width=True)

# === Grafiek: Aantal per categorie ===
st.subheader("📊 Aantal herkende objecten per categorie")
categorie_chart = (
    alt.Chart(filtered_df)
    .mark_bar()
    .encode(
        x=alt.X('count()', title='Aantal'),
        y=alt.Y('Categorie:N', sort='-x'),
        color=alt.Color('Categorie:N', legend=None, scale=alt.Scale(scheme='tableau20')),
        tooltip=['Categorie:N', 'count()']
    )
    .properties(height=400)
)
st.altair_chart(categorie_chart, use_container_width=True)

# === Grafiek: Scores distributie ===
st.subheader("⭐ Scoreverdeling")
score_chart = (
    alt.Chart(filtered_df)
    .mark_bar()
    .encode(
        x=alt.X('Score:O', title='Score (0-5)'),
        y=alt.Y('count()', title='Aantal'),
        color=alt.Color('Score:O', legend=None, scale=alt.Scale(scheme='greenblue')),
        tooltip=['Score:O', 'count()']
    )
    .properties(height=300)
)
st.altair_chart(score_chart, use_container_width=True)

# === Download optie ===
st.subheader("💾 Download resultaten")
st.download_button(
    label="📥 Download gefilterde resultaten als CSV",
    data=filtered_df.to_csv(index=False).encode('utf-8'),
    file_name=f"afvalue_resultaten_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime='text/csv'
)
