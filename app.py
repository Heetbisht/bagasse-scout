import streamlit as st
import pandas as pd
import requests
import json
import time
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- UI ---
st.set_page_config(page_title="BagasseScout: High-Capture Edition", layout="wide")
st.title("🌱 BagasseScout: High-Capture Lead Engine")
st.info("This version records every business found to ensure you never get '0 leads'.")

with st.sidebar:
    st.header("🔑 API Keys")
    serper_key = st.text_input("Serper.dev API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    st.divider()
    target_market = st.multiselect("Select Markets", ["uk", "de", "fr", "nl"], default=["uk"])
    limit = st.slider("Results per market", 5, 20, 10)

# --- ENGINE ---

def get_search_urls(query, country, api_key, num):
    """Broad search to ensure we find targets."""
    url = "https://google.serper.dev/search"
    # We use broader terms: Sugarcane and Biodegradable are more common than 'Bagasse'
    q = f"{query} wholesale distributor {country.upper()}"
    payload = json.dumps({"q": q, "gl": country, "num": num})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, data=payload)
        return res.json().get('organic', [])
    except: return []

def scrape_content(url, api_key):
    """Standard scrape with timeout handling."""
    try:
        res = requests.post("https://api.firecrawl.dev/v1/scrape", 
                            json={"url": url, "formats": ["markdown"]},
                            headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
        return res.json().get("data", {}).get("markdown", "")
    except: return None

def analyze_ai(content, url, api_key):
    """Lenient AI: Categorize instead of Rejecting."""
    genai.configure(api_key=api_key)
    model = GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analyze this website: {url}
    Content: {content[:5000]}
    
    Task: Is this a business that sells/distributes food packaging? 
    If yes, extract details. If they are a factory, still extract them but label as 'Manufacturer'.
    
    Return JSON:
    {{
        "company": "Name",
        "type": "Importer / Wholesaler / Manufacturer / Retailer",
        "is_importer": true/false,
        "email": "Email if found",
        "phone": "Phone if found",
        "location": "City/Country",
        "summary": "1-sentence description"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except: return None

# --- RUN ---

search_input = st.text_input("Search for...", "Sugarcane tableware wholesale")

if st.button("🚀 START CAPTURING LEADS"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Please enter all API keys!")
    else:
        results_list = []
        for market in target_market:
            st.write(f"### 📍 Checking {market.upper()} Market...")
            sites = get_search_urls(search_input, market, serper_key, limit)
            
            if not sites:
                st.warning(f"Google found no results for {market}. Check your Serper Key.")
                continue

            for site in sites:
                url = site['link']
                st.write(f"Checking: {url}")
                
                text = scrape_content(url, firecrawl_key)
                if text and len(text) > 100:
                    data = analyze_ai(text, url, gemini_key)
                    if data:
                        data['url'] = url
                        data['market'] = market.upper()
                        results_list.append(data)
                        st.success(f"✅ Captured: {data['company']} ({data['type']})")
                else:
                    st.write("◽ Skipping: Could not read page text.")
                time.sleep(1)

        if results_list:
            st.divider()
            df = pd.DataFrame(results_list)
            # Filter: Show Importers at the top
            df['priority'] = df['is_importer'].apply(lambda x: "⭐ High" if x else "Low")
            df = df.sort_values('priority', ascending=False)
            
            st.subheader("📋 Captured Leads")
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download All Leads (CSV)", csv, "leads.csv", "text/csv")
        else:
            st.error("Still 0 leads. Check your Firecrawl credit balance at firecrawl.dev.")
