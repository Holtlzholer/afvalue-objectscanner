import streamlit as st
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime
import difflib  # Voor fuzzy matching

# === AFVALUE huisstijl ===
AFVALUE_GREEN = "#00C853"
AFVALUE_DARK = "#263238"
AFVALUE_ACCENT = "#546E7A"
FONT_FAMILY = "'Poppins', sans-serif"

def apply_afvalue_style():
    st.markdown(f"""
        <style>
        html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; color: {AFVALUE_DARK}; }}
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
        </style>
    """, unsafe_allow_html=True)

API_KEY = st.secrets["OPENAI_API_KEY"]
EXCEL_PATH = "categorie_mapping_nl_100_uniek.xlsx"
DB_PATH = "object_db.sqlite"
EXCEL_LOG = "resultaten_log.xlsx"

st.set_page_config(page_title="Objectherkenner Afvalue", layout="centered")
apply_afvalue_style()
st.title("♻️ Objectherkenner Afvalue mobile v2")

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
    result = response.json()
    return result["choices"][0]["message"]["content"]

def extract_score(text):
    match = re.search(r"\b([0-5])\b", text)
    return int(match.group(1)) if match else -1

def extract_ai_object_type(text):
    lines = text.strip().split("\n")
    last_line = lines[-1] if lines else ""
    return last_line.strip().lower()

def fuzzy_match_category(ai_object_type, df):
    ai_lower = ai_object_type.lower()
    
    # Maak lijsten van alle unieke labels en bijhorende categorieën
    label_map = {}
    for idx, row in df.iterrows():
        label_map[row['Label'].strip().lower()] = row['Categorie']
        synoniemen = str(row['Synoniemen']).split(",")
        for syn in synoniemen:
            syn_clean = syn.strip().lower()
            if syn_clean:
                label_map[syn_clean] = row['Categorie']
    
    candidates = list(label_map.keys())
    best_match = difflib.get_close_matches(ai_lower, candidates, n=1, cutoff=0.6)
    if best_match:
        match_term = best_match[0]
        return label_map[match_term], match_term
    return "Onbekend", None

def render_score_stars(score):
    if score == -1:
        return "⛔ Staat onbekend"
    stars = "⭐" * score + "☆" * (5 - score)
    if score <= 1:
        desc = "Zeer slechte staat"
    elif score == 2:
        desc = "Matige staat"
    elif score == 3:
        desc = "Redelijke staat"
    elif score == 4:
        desc = "Goede staat"
    else:
        desc = "Nieuwstaat"
    return f"{stars} ({desc})"

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
    try:
        if os.path.exists(EXCEL_LOG):
            df_existing = pd.read_excel(EXCEL_LOG)
            df_all = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_all = df_new
        with pd.ExcelWriter(EXCEL_LOG, engine='openpyxl', mode='w') as writer:
            df_all.to_excel(writer, index=False)
            writer.book.save(EXCEL_LOG)
        print(f"✅ Excel succesvol opgeslagen in {EXCEL_LOG}")
    except PermissionError:
        st.error(f"⚠️ Kan {EXCEL_LOG} niet opslaan. Sluit het bestand indien het open is in Excel en probeer opnieuw.")
    except Exception as e:
        st.error(f"⚠️ Onverwachte fout bij opslaan: {e}")

# === UI logica ===
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
    category, matched_term = fuzzy_match_category(ai_object_type, df)

    st.markdown(f"<div class='category-box'>📂 {category}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='score-box'>{render_score_stars(score)}</div>", unsafe_allow_html=True)

    st.markdown(f"**🔍 Gematcht op:** `{matched_term}` *(AI zei: {ai_object_type})*")
    st.markdown(f"**📍 Locatie:** `{st.session_state.location or 'Niet opgegeven'}`")
    st.markdown(f"**🕓 Tijd:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

    save_to_db(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)
    save_to_excel(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)

    st.success("✅ Gegevens opgeslagen in database en Excel.")

    if st.button("📸 Nieuwe foto maken"):
        st.session_state.step = "start"
        st.rerun()
