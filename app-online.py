# Afvalue Objectscanner SaaS - verbeterde styling en layout responsive versie

import streamlit as st
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime

# === AFVALUE huisstijl kleuren en fonts ===
AFVALUE_GREEN = "#00C853"
AFVALUE_DARK = "#263238"
AFVALUE_ACCENT = "#546E7A"
FONT_FAMILY = "'Poppins', sans-serif"

# === Custom CSS voor consistente AFVALUE styling ===
def apply_afvalue_style():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
        html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; color: {AFVALUE_DARK}; }}
        h1, h2, h3 {{ color: {AFVALUE_DARK}; font-weight: 600; }}
        .stButton button {{
            background-color: {AFVALUE_GREEN}; color: white; border: none;
            padding: 0.6em 1.5em; border-radius: 8px; font-weight: 600; font-size: 1em;
        }}
        .stButton button:hover {{ background-color: #00a843; }}
        .stAlert {{ background-color: #E0F2F1; border-left: 5px solid {AFVALUE_GREEN}; }}
        .category-box {{
            background-color: #F1F8E9; padding: 1em; border-radius: 10px;
            text-align: center; font-size: 1.5em; font-weight: 600; color: {AFVALUE_DARK};
            margin-bottom: 1em;
        }}
        .score-box {{
            background-color: #E8F5E9; padding: 0.5em 1em; border-radius: 10px;
            text-align: center; font-size: 1.2em; font-weight: 500; color: {AFVALUE_ACCENT};
            margin-bottom: 1em;
        }}
        @media only screen and (max-width: 768px) {{
            .stButton button {{ width: 100%; }}
        }}
        </style>
    """, unsafe_allow_html=True)

# === Config ===
API_KEY = st.secrets["OPENAI_API_KEY"]
EXCEL_PATH = "categorie_mapping_nl_100_uniek.xlsx"
DB_PATH = "object_db.sqlite"
EXCEL_LOG = "resultaten_log.xlsx"

st.set_page_config(page_title="Objectherkenner Afvalue", layout="centered")
apply_afvalue_style()
st.title("♻️ Objectherkenner Afvalue")
st.caption("Gebruik op iPhone via Safari - AI analyse, categorisatie, score en logging.")

# === Laden van de 10 unieke categorieën uit Excel ===
df_categories = pd.read_excel(EXCEL_PATH)
unieke_categorieen = df_categories['Categorie'].dropna().unique().tolist()
categorie_lijst = ", ".join(unieke_categorieen)

# === AI-analyse functie zonder image, als tijdelijke werkbare fallback ===
def analyze_image_with_openai(image_path):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    prompt = (
        "Je bent een AI-assistent die objecten categoriseert voor hergebruik. "
        "Stel dat je een foto krijgt van een object, en je moet raden wat het is en in welke staat het verkeert "
        "(0 = zeer slecht, 5 = nieuwstaat). Kies daarna de BESTE categorie voor dit object uit de volgende lijst "
        f"(kies er MAAR ÉÉN): {categorie_lijst}. "
        "Geef het antwoord strikt in dit formaat:\n\n"
        "Beschrijving: <korte beschrijving>\n"
        "Score: <0-5>\n"
        "Categorie: <exact 1 categorie uit de lijst>"
    )

    payload = {
        "model": "gpt-4o-preview",
        "messages": [{
            "role": "system",
            "content": "Je bent een behulpzame AI-assistent."
        },
        {
            "role": "user",
            "content": prompt
        }],
        "max_tokens": 400
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        result = response.json()
        st.write("🔍 API raw result:", result)  # Debug voor pilots

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        st.error(f"❌ AI-analyse mislukt: {e}")
        st.info("Controleer API-sleutel/credits of probeer later opnieuw.")
        return "Beschrijving: Analyse mislukt\nScore: 0\nCategorie: Onbekend"


# === Extract functies ===
def extract_score(text):
    match = re.search(r"Score:\s*([0-5])", text)
    return int(match.group(1)) if match else 0

def extract_ai_object_type(text):
    match = re.search(r"Categorie:\s*(.+)", text)
    return match.group(1).strip().lower() if match else "onbekend"

def match_category_with_synonyms(ai_object_type, df):
    ai_lower = ai_object_type.lower()
    for idx, row in df.iterrows():
        label_lower = row['Label'].lower()
        synonyms_lower = [syn.strip().lower() for syn in str(row['Synoniemen']).split(",") if syn]
        if ai_lower == label_lower or ai_lower in synonyms_lower:
            return row['Categorie']
    return "Onbekend"

def save_to_db(img_path, label, category, score, location):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            image_path TEXT,
            label TEXT,
            category TEXT,
            score INTEGER,
            location TEXT
        )
    """)
    cur.execute("INSERT INTO objects VALUES (?, ?, ?, ?, ?, ?, ?)", (
        None, datetime.now().isoformat(), img_path, label, category, score, location
    ))
    conn.commit()
    conn.close()

def save_to_excel(img_path, label, category, score, location):
    row = {
        "Tijd": datetime.now().isoformat(),
        "Locatie": location,
        "Afbeelding": img_path,
        "Beschrijving": label,
        "Categorie": category,
        "Score": score
    }
    df_new = pd.DataFrame([row])
    if os.path.exists(EXCEL_LOG):
        df_existing = pd.read_excel(EXCEL_LOG)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_excel(EXCEL_LOG, index=False)

# === UI Logica ===
if "step" not in st.session_state:
    st.session_state.step = "start"
if "location" not in st.session_state:
    st.session_state.location = ""

if st.session_state.step == "start":
    st.session_state.location = st.text_input("📍 Voer de locatie in (bijv. Gemeente Arnhem)")
    uploaded_photo = st.camera_input("📷 Maak een foto van het object")
    if uploaded_photo:
        with open("object.jpg", "wb") as f:
            f.write(uploaded_photo.getbuffer())
        st.session_state.img_path = "object.jpg"
        st.session_state.step = "confirm"
        st.rerun()

elif st.session_state.step == "confirm":
    st.image(st.session_state.img_path, caption="📸 Gemaakte foto", use_column_width=True)
    st.write("Wil je deze foto gebruiken voor analyse?")
    col1, col2 = st.columns(2)
    if col1.button("🔁 Opnieuw nemen"):
        st.session_state.step = "start"
        st.rerun()
    if col2.button("✅ Verstuur naar AI"):
        st.session_state.step = "analyze"
        st.rerun()

elif st.session_state.step == "analyze":
    st.image(st.session_state.img_path, caption="⏳ AI-analyse bezig...", use_column_width=True)
    with st.spinner("AI denkt na over het object..."):
        desc = analyze_image_with_openai(st.session_state.img_path)
    st.session_state.description = desc
    st.session_state.step = "result"
    st.rerun()

elif st.session_state.step == "result":
    st.image(st.session_state.img_path, caption="📷 Gekozen foto", use_column_width=True)
    st.subheader("🧠 AI-analyse")
    st.markdown("**📋 Beschrijving:**")
    st.info(st.session_state.description)

    score = extract_score(st.session_state.description)
    ai_object_type = extract_ai_object_type(st.session_state.description)
    df = pd.read_excel(EXCEL_PATH)
    category = match_category_with_synonyms(ai_object_type, df)

    st.markdown(f"<div class='category-box'>📂 {category}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='score-box'>⭐ Score: {score}/5</div>", unsafe_allow_html=True)

    st.markdown(f"**📍 Locatie:** `{st.session_state.location or 'Niet opgegeven'}`")
    st.markdown(f"**🕓 Tijd:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

    save_to_db(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)
    save_to_excel(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)

    st.success("✅ Gegevens opgeslagen in database en Excel.")

    if st.button("📸 Nieuwe foto maken"):
        st.session_state.step = "start"
        st.rerun()
