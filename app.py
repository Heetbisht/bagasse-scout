import streamlit as st
import pandas as pd
import requests
import json
import time
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- UI CONFIG ---
st.set_page_config(page_title="BagasseScout Pro v2", layout="wide", page_icon="🚀")

st.title("🚀 BagasseScout Pro (v2 Engine)")
st.write("Using Firecrawl v2 + Gemini 1.5 Flash for high-accuracy lead scraping.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Setup")
    SERPER_API = st.text_input("Serper.dev API Key", type="password")
    FIRECRAWL_API = st.text_input("Firecrawl API Key", type="password")
    GEMINI_API = st.text_input("Gemini API Key", type="password")
    st.divider()
    target_country = st.selectbox("Market", ["uk", "de", "fr", "nl", "be"], index=0)
    max_leads = st.slider("Max Leads to Process", 5, 20, 10)
    st.warning("⚠️ Free Firecrawl accounts: Use a max of 5-10 leads per run to avoid rate limits.")

# --- THE ENGINE ---

def scrape_v2(url, api_key):
    """Uses Firecrawl v2 API with better error reporting."""
    # Use v2 endpoint which is faster and more reliable
    endpoint = "https://api.firecrawl.dev/v2/scrape"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # v2 uses 'formats' list instead of old pageOptions
    data = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "timeout": 30000 
    }
    
    try:
        response = requests.post(endpoint, json=data, headers=headers)
        
        if response.status_code == 429:
            return "ERROR: Rate limit hit. Please wait 60 seconds."
        elif response.status_code == 401:
            return "ERROR: Invalid Firecrawl API Key."
        elif response.status_code == 402:
            return "ERROR: Out of Firecrawl Credits."
        
        result = response.json()
        if result.get("success"):
            return result.get("data", {}).get("markdown", "")
        else:
            return f"ERROR: {result.get('error', 'Unknown Error')}"
    except Exception as e:
        return f"ERROR: Connection failed ({str(e)})"

def analyze_lead(content, url, gemini_key):
    """AI logic remains focused on identifying buyers vs manufacturers."""
    genai.configure(api_key=gemini_key)
    model = GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Analyze this website content from {url}.
    Objective: Find WHOLESALERS/IMPORTERS of bagasse (sugarcane) tableware.
    
    REJECT (is_relevant: false) if:
    - They are a factory/manufacturer (look for: 'our plant', 'OEM', 'production facility').
    
    ACCEPT (is_relevant: true) if:
    - They are a 'distributor', 'wholesaler', 'catering supplier', or have a 'wholesale login'.

    Content: {content[:5000]}

    Return JSON:
    {{
        "company": "Name",
        "is_relevant": true/false,
        "type": "Importer/Wholesaler",
        "email": "Email if found",
        "score": 1-10
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except:
        return None

# --- APP FLOW ---

query = st.text_input("Enter Search (e.g., 'Eco packaging wholesale UK')", "Bagasse tableware distributor UK")

if st.button("Start Extraction"):
    if not (SERPER_API and FIRECRAWL_API and GEMINI_API):
        st.error("Missing API Keys!")
    else:
        # 1. Search Google
        search_url = "https://google.serper.dev/search"
        search_data = json.dumps({"q": query, "gl": target_country, "num": max_leads})
        search_headers = {'X-API-KEY': SERPER_API, 'Content-Type': 'application/json'}
        
        st.info("Searching Google...")
        sites = requests.post(search_url, headers=search_headers, data=search_data).json().get('organic', [])
        
        found_leads = []
        for i, site in enumerate(sites):
            url = site['link']
            st.write(f"🔍 Processing ({i+1}/{len(sites)}): {url}")
            
            # 2. Scrape with v2
            content = scrape_v2(url, FIRECRAWL_API)
            
            if "ERROR" in content:
                st.error(f"❌ {url}: {content}")
                if "Rate limit" in content:
                    st.warning("Pausing for 10 seconds...")
                    time.sleep(10) # Wait a bit if rate limited
                continue
            
            # 3. AI Analyze
            res = analyze_lead(content, url, GEMINI_API)
            if res and res.get('is_relevant'):
                res['website'] = url
                found_leads.append(res)
                st.success(f"✅ Found Lead: {res['company']}")
            
            # Anti-Rate Limit Delay (crucial for free accounts)
            time.sleep(2) 

        if found_leads:
            df = pd.DataFrame(found_leads)
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False), "leads.csv")
        else:
            st.warning("No leads found. Try a broader search term.")
