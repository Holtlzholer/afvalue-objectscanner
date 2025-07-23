import streamlit as st
import base64
import requests
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime
import difflib

AFVALUE_GREEN = "#00C853"
AFVALUE_DARK = "#263238"
AFVALUE_ACCENT = "#546E7A"
FONT_FAMILY = "'Poppins', sans-serif"

BLACKLIST_PATH = "blacklist_test.xlsx"
API_KEY = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Afvalue Demo - VG Score", layout="centered")

def apply_afvalue_style():
    st.markdown(f"""
        <style>
        html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; color: {AFVALUE_DARK}; background-color: #FAFAFA; }}
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
        .block-title {{
            font-size: 1.3em; font-weight: bold; margin-top: 1em;
        }}
        </style>
    """, unsafe_allow_html=True)

apply_afvalue_style()
st.title("♻️ Afvalue - VG-score Demo")

def analyze_image_with_openai(image_path):
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = (
        "Beantwoord de volgende drie vragen over het object op de foto, zonder verdere toelichting:\n"
        "1. Staat van het object (kies uit: goed, gebruikt, eenvoudig reparabel, moeilijk reparabel, niet)\n"
        "2. Kan het object hergebruikt worden? (kies uit: ja, herbestemming mogelijk, nee)\n"
        "3. Wat is het type object (één woord)?"
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
        "max_tokens": 200
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    result = response.json()
    return result["choices"][0]["message"]["content"]

def check_blacklist(label):
    if not os.path.exists(BLACKLIST_PATH):
        return False, None
    df_black = pd.read_excel(BLACKLIST_PATH)
    for _, row in df_black.iterrows():
        if row['Label'].lower() in label.lower():
            return True, row['Reden']
    return False, None

def compute_vg_score(label, buyer_choice, cond_score, hergebruikstype):
    blocked, reason = check_blacklist(label)
    if blocked:
        return 0, f"🚫 Niet rechtmatig: {reason}"
    zeker = 0
    zeker += 2 if buyer_choice == "Ja" else (1 if buyer_choice == "Twijfel" else 0)
    zeker += 1
    zeker += cond_score
    if hergebruikstype == "ja":
        hoogwaardig = 2
    elif hergebruikstype == "herbestemming mogelijk":
        hoogwaardig = 1
    else:
        hoogwaardig = 0
    total = min(10, zeker + hoogwaardig)
    toelichting = f"✅ Rechtmatig gebruik bevestigd. Zeker gebruik: {zeker}/8, Hoogwaardig: {hoogwaardig}/2"
    return total, toelichting

def parse_ai_response(text):
    lines = text.strip().split("\n")
    if len(lines) < 3:
        return "onbekend", "onbekend", "onbekend"
    return lines[0].strip().lower(), lines[1].strip().lower(), lines[2].strip().lower()

if "step" not in st.session_state:
    st.session_state.step = "start"
if "location" not in st.session_state:
    st.session_state.location = ""

if st.session_state.step == "start":
    st.session_state.location = st.text_input("📍 Locatie (optioneel)", value="Demo Arnhem")
    uploaded_photo = st.camera_input("📷 Maak een foto van het object of upload er een")
    if uploaded_photo:
        with open("object.jpg", "wb") as f:
            f.write(uploaded_photo.getbuffer())
        st.session_state.img_path = "object.jpg"
        st.session_state.step = "analyze"
        st.rerun()

elif st.session_state.step == "analyze":
    st.image(st.session_state.img_path, caption="AI-analyse bezig...", use_column_width=True)
    with st.spinner("De AI onderzoekt het object..."):
        ai_output = analyze_image_with_openai(st.session_state.img_path)
    cond_ai, reuse_ai, label_ai = parse_ai_response(ai_output)
    st.session_state.ai_output = ai_output
    st.session_state.cond_ai = cond_ai
    st.session_state.reuse_ai = reuse_ai
    st.session_state.label_ai = label_ai
    st.session_state.step = "result"
    st.rerun()

elif st.session_state.step == "result":
    st.image(st.session_state.img_path, caption="📷 Gekozen object", use_column_width=True)
    st.subheader("🧠 AI-output")
    st.code(st.session_state.ai_output)

    buyer_choice = st.selectbox("📥 Is er een afnemer bekend?", ["Twijfel", "Ja", "Nee"], index=0)

    cond_options = ["goed", "gebruikt", "eenvoudig reparabel", "moeilijk reparabel", "niet"]
    cond_index = cond_options.index(st.session_state.cond_ai) if st.session_state.cond_ai in cond_options else 0
    cond_choice = st.selectbox("🛠️ Staat van het object:", cond_options, index=cond_index)
    cond_overridden = cond_choice != st.session_state.cond_ai
    cond_map = {"goed": 4, "gebruikt": 3, "eenvoudig reparabel": 2, "moeilijk reparabel": 1, "niet": 0}
    if cond_overridden:
        st.warning("⚠️ Handmatig aangepast t.o.v. AI-inschatting (staat)")

    reuse_options = ["ja", "herbestemming mogelijk", "nee"]
    reuse_index = reuse_options.index(st.session_state.reuse_ai) if st.session_state.reuse_ai in reuse_options else 0
    reuse_choice = st.selectbox("♻️ Kan het object hergebruikt worden?", reuse_options, index=reuse_index)
    reuse_overridden = reuse_choice != st.session_state.reuse_ai
    if reuse_overridden:
        st.warning("⚠️ Handmatig aangepast t.o.v. AI-inschatting (hergebruik)")

    score, toelichting = compute_vg_score(st.session_state.label_ai, buyer_choice, cond_map[cond_choice], reuse_choice)

    st.subheader("🔢 VG-score (Voortgezet Gebruik)")
    st.metric(label="VG-score", value=f"{score} / 10")
    st.success(toelichting) if score > 0 else st.error(toelichting)

    if st.button("🔁 Volgende object (reset)"):
        st.session_state.step = "start"
        st.rerun()
