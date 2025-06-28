import streamlit as st
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime

# === Custom CSS voor AFVALUE huisstijl ===
def apply_afvalue_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
        html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }
        h1, h2, h3 { color: #000000; }
        .stButton button {
            background-color: #00C853; color: white; border: none;
            padding: 0.5em 1.2em; border-radius: 5px; font-weight: 600;
        }
        .stButton button:hover { background-color: #00a843; }
        .stAlert { background-color: #E0F2F1; border-left: 5px solid #00C853; }
        </style>
    """, unsafe_allow_html=True)

# === Config ===
API_KEY = "JOUW_OPENAI_API_KEY_HIER"
EXCEL_PATH = "categorie_mapping_nl_100_uniek.xlsx"
DB_PATH = "object_db.sqlite"
EXCEL_LOG = "resultaten_log.xlsx"

st.set_page_config(page_title="Objectherkenner Afvalue", layout="centered")
apply_afvalue_style()
st.title("♻️ Objectherkenner voor Afvalue (Mobile Ready)")
st.caption("Gebruik op iPhone via Safari - AI analyse, categorisatie, score en logging.")

# === AI-analyse functie ===
def analyze_image_with_openai(image_path):
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = (
        "Wat voor object is dit en in welke staat verkeert het? "
        "Geef een score van 0 (slecht) tot 5 (nieuwstaat). "
        "Geef vervolgens in ÉÉN WOORD het beste objecttype zoals mok, stoel, emmer."
    )
    payload = {
        "model": "gpt-4o",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]
        }],
        "max_tokens": 400
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    try:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"AI-analyse mislukt: {e}")
        return "AI-analyse mislukt"

# === Extract functies ===
def extract_score(text):
    match = re.search(r"\b([0-5])\b", text)
    return int(match.group(1)) if match else 0

def extract_ai_object_type(text):
    lines = text.strip().split("\n")
    last_line = lines[-1] if lines else ""
    return last_line.strip().lower()

# === Matching met synoniemen en labels ===
def match_category_with_synonyms(ai_object_type, df):
    ai_lower = ai_object_type.lower()
    for idx, row in df.iterrows():
        label_lower = row['Label'].lower()
        synonyms_lower = [syn.strip().lower() for syn in str(row['Synoniemen']).split(",") if syn]
        if ai_lower == label_lower or ai_lower in synonyms_lower:
            return row['Categorie']
    return "Onbekend"

# === Opslag functies ===
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
    st.image(st.session_state.img_path, caption="📸 Gemaakte foto", width=400)
    st.write("Wil je deze foto gebruiken voor analyse?")
    col1, col2 = st.columns(2)
    if col1.button("🔁 Opnieuw nemen"):
        st.session_state.step = "start"
        st.rerun()
    if col2.button("✅ Verstuur naar AI"):
        st.session_state.step = "analyze"
        st.rerun()

elif st.session_state.step == "analyze":
    st.image(st.session_state.img_path, caption="⏳ AI-analyse bezig...", width=400)
    with st.spinner("AI denkt na over het object..."):
        desc = analyze_image_with_openai(st.session_state.img_path)
    st.session_state.description = desc
    st.session_state.step = "result"
    st.rerun()

elif st.session_state.step == "result":
    st.image(st.session_state.img_path, caption="📷 Gekozen foto", width=400)
    st.subheader("🧠 AI-analyse")
    st.markdown("**📋 Beschrijving:**")
    st.info(st.session_state.description)

    score = extract_score(st.session_state.description)
    ai_object_type = extract_ai_object_type(st.session_state.description)
    df = pd.read_excel(EXCEL_PATH)
    category = match_category_with_synonyms(ai_object_type, df)

    st.markdown(f"**📂 Categorie:** `{category}`")
    st.markdown(f"**🪪 Objecttype (AI):** `{ai_object_type}`")
    st.markdown(f"**⭐ Score (0–5):** `{score}`")
    st.markdown(f"**📍 Locatie:** `{st.session_state.location or 'Niet opgegeven'}`")
    st.markdown(f"**🕓 Tijd:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

    save_to_db(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)
    save_to_excel(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)

    st.success("✅ Gegevens opgeslagen in database en Excel.")

    if st.button("🔄 Nieuwe foto maken"):
        st.session_state.step = "start"
        st.rerun()