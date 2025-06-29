import streamlit as st
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime

# === AFVALUE huisstijl ===
AFVALUE_GREEN = "#00C853"
AFVALUE_DARK = "#263238"
AFVALUE_ACCENT = "#546E7A"
FONT_FAMILY = "'Poppins', sans-serif"

def apply_afvalue_style():
    st.markdown(f"""
        <style>
        html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; color: {AFVALUE_DARK}; }}
        .category-box {{ background-color: #F1F8E9; padding: 1em; border-radius: 10px;
            text-align: center; font-size: 1.5em; font-weight: 600; color: {AFVALUE_DARK}; margin-bottom: 1em; }}
        .score-box {{ background-color: #E8F5E9; padding: 0.5em 1em; border-radius: 10px;
            text-align: center; font-size: 1.2em; font-weight: 500; color: {AFVALUE_ACCENT}; margin-bottom: 1em; }}
        </style>
    """, unsafe_allow_html=True)

API_KEY = st.secrets["OPENAI_API_KEY"]
DB_PATH = "object_db.sqlite"
EXCEL_LOG = "resultaten_log.xlsx"

st.set_page_config(page_title="Objectherkenner Afvalue", layout="centered")
apply_afvalue_style()
st.title("♻️ Objectherkenner Afvalue")

# === AI analyse functie ===
def analyze_image_with_openai(image_path):
    categories = (
        "Antiek en Kunst, Audio Tv en Foto, Auto's, Auto-onderdelen, Auto diversen, Boeken, Caravans en Kamperen, "
        "Cd's en Dvd's, Computers en Software, Contacten en Berichten, Diensten en Vakmensen, Dieren en Toebehoren, "
        "Doe-het-zelf en Verbouw, Fietsen en Brommers, Hobby en Vrije tijd, Huis en Inrichting, Huizen en Kamers, "
        "Kinderen en Baby's, Kleding Dames, Kleding Heren, Motoren, Muziek en Instrumenten, Postzegels en Munten, "
        "Sieraden Tassen en Uiterlijk, Spelcomputers en Games, Sport en Fitness, Telecommunicatie, Tickets en Kaartjes, "
        "Tuin en Terras, Vacatures, Vakantie, Verzamelen, Watersport en Boten, Witgoed en Apparatuur, Zakelijke goederen, Diversen"
    )
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = (
        f"Herken dit object. Kies uit deze categorieën: {categories}. Geef alleen de beste categorie exact terug. "
        "Geef daarnaast een score 0-5 over de staat van het object. Antwoord als volgt: 'Categorie: <categorie> | Score: <score>'."
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]
        }],
        "max_tokens": 100
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    result = response.json()
    return result["choices"][0]["message"]["content"]

def extract_category_and_score(text):
    cat_match = re.search(r"Categorie:\s*(.*?)\s*\|", text)
    score_match = re.search(r"Score:\s*(\d)", text)
    category = cat_match.group(1) if cat_match else "Onbekend"
    score = int(score_match.group(1)) if score_match else -1
    return category, score

def render_score_stars(score):
    if score == -1:
        return "⛔ Staat onbekend"
    stars = "⭐" * score + "☆" * (5 - score)
    return f"{stars} (Score: {score}/5)"

def save_to_excel(img_path, label, category, score, location):
    row = {"Tijd": datetime.now().isoformat(), "Locatie": location, "Afbeelding": img_path,
           "Beschrijving": label, "Categorie": category, "Score": score}
    df_new = pd.DataFrame([row])
    if os.path.exists(EXCEL_LOG):
        df_existing = pd.read_excel(EXCEL_LOG)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_excel(EXCEL_LOG, index=False)

# === UI logica ===
if "step" not in st.session_state:
    st.session_state.step = "start"
if "location" not in st.session_state:
    st.session_state.location = ""

if st.session_state.step == "start":
    st.session_state.location = st.text_input("📍 Voer de locatie in")
    uploaded_photo = st.camera_input("📷 Maak een foto van het object")
    if uploaded_photo:
        with open("object.jpg", "wb") as f:
            f.write(uploaded_photo.getbuffer())
        st.session_state.img_path = "object.jpg"
        st.session_state.step = "analyze"
        st.rerun()

elif st.session_state.step == "analyze":
    st.image(st.session_state.img_path, caption="⏳ Analyse bezig...", use_column_width=True)
    with st.spinner("AI analyseert het object..."):
        desc = analyze_image_with_openai(st.session_state.img_path)
    st.session_state.description = desc
    st.session_state.step = "result"
    st.rerun()

elif st.session_state.step == "result":
    st.image(st.session_state.img_path, caption="📷 Gekozen foto", use_column_width=True)
    st.subheader("🧠 AI-analyse")
    st.markdown(f"**Beschrijving:** {st.session_state.description}")
    category, score = extract_category_and_score(st.session_state.description)
    st.markdown(f"<div class='category-box'>📂 {category}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='score-box'>{render_score_stars(score)}</div>", unsafe_allow_html=True)
    st.markdown(f"**📍 Locatie:** `{st.session_state.location or 'Niet opgegeven'}`")
    st.markdown(f"**🕓 Tijd:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    save_to_excel(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)
    st.success("✅ Gegevens opgeslagen in Excel.")
    if st.button("📸 Nieuwe foto maken"):
        st.session_state.step = "start"
        st.rerun()
