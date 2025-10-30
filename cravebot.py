import os
import re
import time
from narwhals import col
import streamlit as st
import requests
import random
from urllib.parse import quote
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="CraveBot", page_icon="🤖", layout="wide")

# --- LOAD CSS & BACKGROUND ---
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""
<div class="morphing-gradient-bg">
  <div class="morphing-gradient-layer"></div>
  <div class="morphing-noise-layer"></div>
</div>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def create_google_maps_link(name, address):
    """Return a Google Maps search URL for a restaurant."""
    query = quote(f"{name} {address}")
    return f"https://www.google.com/maps/search/?api=1&query={query}"

def get_image_base64(file_path):
    """Encode an image to base64 for embedding."""
    try:
        with open(file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

def get_valid_image_url(item, api_key, craving):
    """Return a valid image URL: Google photo if available, else Unsplash fallback."""
    try:
        photo_ref = item["photos"][0]["photo_reference"]
        google_url = f'https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={api_key}'
        
        # Check if Google photo URL actually works
        resp = requests.head(google_url, allow_redirects=True, timeout=5)
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
            return resp.url  # use redirected URL if valid
        
    except Exception as e:
        print(f"Image fetch error: {e}")

    # Fallback to Unsplash (always returns a valid image)
    name = item.get("name", "food")
    fallback_url = f"https://source.unsplash.com/800x600/?{quote(craving or 'restaurant')},{quote(name)}"
    return fallback_url

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_places(api_key, keyword, location):
    """Fetch nearby restaurants (no Streamlit calls)."""
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={api_key}"
    try:
        resp = requests.get(geo_url).json()
        if not resp.get("results"):
            return {"error": "invalid_location"}
        lat, lng = resp["results"][0]["geometry"]["location"].values()
    except requests.RequestException:
        return {"error": "geocode_failed"}

    url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=3500&keyword={quote(keyword)}&type=restaurant&key={api_key}"
    try:
        data = requests.get(url).json().get("results", [])
        return {"results": data}
    except requests.RequestException:
        return {"error": "places_failed"}


def search_places(api_key, keyword, location):
    """Wrapper that handles UI feedback."""
    data = fetch_places(api_key, keyword, location)
    if "error" in data:
        if data["error"] == "invalid_location":
            st.toast("Could not find that location. Try a different ZIP or area.")
        elif data["error"] == "geocode_failed":
            st.toast("Failed to connect to the Geocoding API.")
        elif data["error"] == "places_failed":
            st.toast("Failed to connect to the Places API.")
        time.sleep(2)
        return []
    return data["results"]

def display_favorites():
    """Show user's saved 'craved' restaurants in the sidebar."""
    st.markdown("<h3 class='sidebar-title'>💖 Your Crave List 👇</h3>", unsafe_allow_html=True)
    favorites = st.session_state.get("favorites", [])
    if not favorites:
        st.markdown('<div class="empty-favorites-message fade-in">Your craved items will appear here after you ❤️ one!</div>', unsafe_allow_html=True)
        return
    
    for fav in favorites:
        name, address = fav.get("name", "N/A"), fav.get("vicinity", "N/A")
        maps_link = create_google_maps_link(name, address)
        st.markdown(f"""
            <div class="favorite-item">
                <a href="{maps_link}" target="_blank">
                    <strong>{name}</strong><br>
                    <span>{address}</span>
                </a>
            </div>
        """, unsafe_allow_html=True)
    if st.button("Clear All ❤️", key="clear_favorites"):
        st.session_state.favorites = []
        st.rerun()

# --- SESSION INITIALIZATION ---
st.session_state.setdefault("results", [])
st.session_state.setdefault("index", 0)
st.session_state.setdefault("favorites", [])
st.session_state.setdefault("recommendation", None)

# --- HEADER & LOGO ---
logo_base64 = get_image_base64("logo.png")
st.markdown(f"""
<div class="hero-title-row">
  <div class="hero-title">CraveBot</div>
  <img src="data:image/png;base64,{logo_base64}" alt="CraveBot Logo" class="hero-logo-img"/>
</div>
<div class="logo-section">
  <span class="main-title">What are you craving?</span><br>
  <span class="main-subtitle">CraveBot helps you discover the perfect meal when you don't know what you want.</span>
</div>
""", unsafe_allow_html=True)

# --- SEARCH FORM ---


with st.form("search_form"):
    st.info("Leave the craving blank for a random suggestion.")
    location_input = st.text_input("Location", placeholder="Enter your location or ZIP code", label_visibility="collapsed")
    craving_input = st.text_input("Craving", placeholder="Enter your craving (optional)", label_visibility="collapsed")
    search_button = st.form_submit_button("Find Food 🍽️")

# --- MAIN LOGIC ---
if search_button:
    if not location_input.strip():
        st.toast("Please enter a location to find food.", icon="📍")
        time.sleep(1.5)
        st.rerun()
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.toast("Missing Google API key. Add it to .streamlit/secrets.toml.", icon="🚫")
        time.sleep(1.5)
        st.rerun()        
    else:
        st.markdown("<div class='loading-container'>🍔 Scanning your neighborhood for bites...</div>", unsafe_allow_html=True)
        time.sleep(1.5)
        search_term = craving_input.strip() or random.choice(["sushi", "burgers", "pasta", "thai", "mexican", "pizza", "ramen"])
        st.session_state.recommendation = craving_input or search_term
        results = search_places(api_key, search_term, location_input.strip())
        if results:
            random.shuffle(results)
            st.session_state.results = results
            st.session_state.index = 0
            st.session_state.favorites = []
        else:
            st.session_state.results = []
        st.rerun()
# --- DISPLAY RESULTS ---
main_col, sidebar_col = st.columns([2, 1])

with main_col:
    results = st.session_state.results
    if results:
        if st.session_state.recommendation:
            st.markdown(f"""
                <div class="cravebot-recommend-box">
                    <span class="cravebot-robot">🤖</span>
                    <strong>CraveBot Recommends:</strong>
                    <span class="recommend-cuisine"> {st.session_state.recommendation.title()}!</span>
                </div>
            """, unsafe_allow_html=True)

        index = st.session_state.index
        if index < len(results):
            item = results[index]
            api_key = st.secrets.get("GOOGLE_API_KEY")
            name, rating, address = item.get("name", "N/A"), item.get("rating", "N/A"), item.get("vicinity", "N/A")
            maps_link = create_google_maps_link(name, address)
            image_url = get_valid_image_url(item, api_key, craving_input or "food")

            st.markdown(f"""
                <div class="food-card">
                    <a href="{maps_link}" target="_blank"><img src="{image_url}" alt="{name}"></a>
                    <a href="{maps_link}" target="_blank"><h2>{name}</h2></a>
                    <p><b>⭐ {rating}</b> &nbsp;·&nbsp; {address}</p>
                </div>
            """, unsafe_allow_html=True)

            b_col1,b_col2, b_col3 = st.columns([3, 3, 4])
            with b_col2:
                if st.button("❤️", help="Crave it!"):
                    st.session_state.favorites.append(item)
                    st.session_state.index += 1
                    st.rerun()
            with b_col3:
                if st.button("➡️", help="Next"):
                    st.session_state.index += 1
                    st.rerun()
        else:
            st.success("🎉 You've seen all the results!")
            st.info("Check your Crave List on the right or Search again.")

with sidebar_col:
    if st.session_state.results:
        display_favorites()
