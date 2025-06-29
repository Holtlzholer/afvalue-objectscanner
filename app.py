import streamlit as st
import cv2
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime
from difflib import get_close_matches

# === Responsive AFVALUE-styling ===
st.set_page_config(page_title="Objectherkenner Afvalue", layout="centered")

def apply_afvalue_style():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            max-width: 600px;
            margin: auto;
            padding: 10px;
        }

        h1, h2, h3 {
            color: #000000;
        }

        .stButton button {
            background-color: #00C853;
            color: white;
            border: none;
            padding: 0.6em 1.4em;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1em;
        }

        .stButton button:hover {
            background-color: #00a843;
        }

        .stAlert {
            background-color: #E0F2F1;
            border-left: 5px solid #00C853;
        }

        .stMarkdown, .stCaption, .stImage img {
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

# === Config ===
API_KEY = st.secrets["OPENAI_API_KEY"]
EXCEL_PATH = "categorie_mapping_nl_100_uniek.xlsx"
DB_PATH = "object_db.sqlite"
EXCEL_LOG = "resultaten_log.xlsx"

apply_afvalue_style()

st.title("♻️ Objectherkenner voor Afvalue Mobile")
st.caption("Gebruik op iPhone via Safari - AI analyse, categorisatie, score en logging.")

# === Upload in plaats van webcam capture ===
def upload_photo():
    uploaded_file = st.file_uploader("📷 Maak of upload een foto", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        img_path = "object.jpg"
        with open(img_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return img_path
    return None

# === Start scherm ===
if st.session_state.step == "start":
    st.session_state.location = st.text_input("📍 Voer de locatie in (bijv. Gemeente Enschede)")
    path = upload_photo()
    if path:
        st.session_state.img_path = path
        st.session_state.step = "confirm"
        st.rerun()

# === AI-analyse ===
def analyze_image_with_openai(image_path):
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        "Wat voor object is dit en in welke staat verkeert het? "
        "Geef een score van 0 (slecht) tot 5 (nieuwstaat). "
        "Geef vervolgens in ÉÉN WOORD de beste beschrijving van het objecttype zoals mok, stoel of emmer."
    )

    payload = {
        "model": "gpt-4o-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            }
        ],
        "max_tokens": 400
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    st.write("🔍 Status code:", response.status_code)
    st.write("🔍 Response:", response.text)

    try:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"AI-analyse mislukt: {e}")
        return "AI-analyse mislukt"

# === Extract score ===
def extract_score(text):
    match = re.search(r"\b([0-5])\b", text)
    return int(match.group(1)) if match else 0

# === Match categorie ===
def match_category_with_synonyms(ai_category, df):
    ai_category_lower = ai_category.strip().lower()
    unique_categories = df['Categorie'].str.lower().unique()
    for cat in unique_categories:
        if cat == ai_category_lower:
            return cat.capitalize()
    for idx, row in df.iterrows():
        label_lower = row['Label'].lower()
        synonyms_lower = row['Synoniemen'].lower().split(",") if isinstance(row['Synoniemen'], str) else []
        if ai_category_lower in label_lower or ai_category_lower in synonyms_lower:
            return row['Categorie']
    return "Onbekend"

# === Database logging ===
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
        )""")
    cur.execute("INSERT INTO objects VALUES (?, ?, ?, ?, ?, ?, ?)", (
        None,
        datetime.now().isoformat(),
        img_path,
        label,
        category,
        score,
        location
    ))
    conn.commit()
    conn.close()

# === Excel logging ===
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

# === Stateful UI flow ===
if "step" not in st.session_state:
    st.session_state.step = "start"

if "location" not in st.session_state:
    st.session_state.location = ""

# === Start scherm ===
if st.session_state.step == "start":
    st.session_state.location = st.text_input("📍 Voer de locatie in (bijv. Gemeente Enschede)")
    if st.button("📷 Maak foto"):
        path = capture_photo()
        if path:
            st.session_state.img_path = path
            st.session_state.step = "confirm"
            st.rerun()

# === Foto bevestigen ===
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

# === AI analyse uitvoeren ===
elif st.session_state.step == "analyze":
    st.image(st.session_state.img_path, caption="⏳ AI-analyse bezig...", use_column_width=True)
    with st.spinner("AI analyse wordt uitgevoerd..."):
        desc = analyze_image_with_openai(st.session_state.img_path)
    st.session_state.description = desc
    st.session_state.step = "result"
    st.rerun()

# === Resultaat tonen ===
elif st.session_state.step == "result":
    st.image(st.session_state.img_path, caption="📷 Gekozen foto", use_column_width=True)
    st.subheader("🧠 AI-analyse")
    st.markdown("**📋 Beschrijving:**")
    st.info(st.session_state.description)

    # Extract AI category
    ai_category_match = re.findall(r"\b[A-Z]{3,}\b", st.session_state.description)
    ai_category = ai_category_match[0] if ai_category_match else "Onbekend"

    df_categories = pd.read_excel(EXCEL_PATH)
    category = match_category_with_synonyms(ai_category, df_categories)
    score = extract_score(st.session_state.description)

    st.markdown(f"📂 **Categorie:** `{category}`")
    st.markdown(f"🏷️ **Objecttype (AI):** `{ai_category.lower()}`")
    st.markdown(f"⭐ **Score (0-5):** `{score}`")
    st.markdown(f"📍 **Locatie:** `{st.session_state.location or 'Niet opgegeven'}`")
    st.markdown(f"🕓 **Tijd:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

    save_to_db(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)
    save_to_excel(st.session_state.img_path, st.session_state.description, category, score, st.session_state.location)

    st.success("✅ Gegevens opgeslagen in database en Excel.")

    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    if st.button("📷 Nieuwe foto maken"):
        st.session_state.step = "start"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
