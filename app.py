import streamlit as st
import pandas as pd
import requests
import json
import time
import re
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- PROFESSIONAL UI SETUP ---
st.set_page_config(page_title="BagasseScout Pro | Lead Engine", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stProgress > div > div > div > div { background-color: #2e7d32; }
    .status-box { padding: 10px; border-radius: 5px; margin: 5px 0; border: 1px solid #ccc; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 BagasseScout Pro: Ultimate Lead Engine")
st.write("Targeting European Importers & Wholesalers • **Strict No-Manufacturer Filter**")

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("🔑 API Configuration")
    SERPER_API = st.text_input("Serper API Key", type="password", help="For Google Search results")
    FIRECRAWL_API = st.text_input("Firecrawl API Key", type="password", help="To read website content")
    GEMINI_API = st.text_input("Gemini API Key", type="password", help="The AI Brain")
    
    st.divider()
    st.header("⚙️ Search Settings")
    country = st.selectbox("Market Region", ["uk", "de", "fr", "nl", "be", "it", "es", "pl"], index=0)
    search_depth = st.slider("Search Breadth (Results)", 10, 50, 20)
    
    st.info("💡 Tip: Use 'uk' for United Kingdom, 'de' for Germany, 'nl' for Netherlands.")

# --- THE "BRAIN" FUNCTIONS ---

def get_search_queries(base_term, country_code):
    """Generates the best B2B footprints based on the country."""
    queries = {
        "uk": [f'"{base_term}" wholesale UK', f'"{base_term}" distributor London', 'eco catering supplies "trade account"'],
        "de": [f'"{base_term}" Großhandel', 'nachhaltige verpackung Gastronomiebedarf'],
        "nl": [f'"{base_term}" groothandel', 'duurzame verpakkingen horeca'],
        "fr": [f'"{base_term}" grossiste', 'emballage biodégradable restauration']
    }
    # Default to UK style if country not specifically mapped
    return queries.get(country_code, [f'"{base_term}" wholesale {country_code}'])

def execute_search(query, country_code, api_key):
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": query, 
        "gl": country_code, 
        "num": 20,
        "tbs": "qdr:y" # Focus on results active in the last year
    })
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json().get('organic', [])
    except:
        return []

def scrape_content(url, api_key):
    endpoint = "https://api.firecrawl.dev/v0/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # Extract only main content to save AI tokens
    data = {"url": url, "pageOptions": {"onlyMainContent": True, "removeHtml": True}}
    try:
        res = requests.post(endpoint, json=data, timeout=15)
        return res.json().get('data', {}).get('content', "")
    except:
        return ""

def qualify_lead_ai(content, url, gemini_key):
    genai.configure(api_key=gemini_key)
    model = GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are a professional B2B Sales Scout. Analyze this website content from: {url}
    
    GOAL: Find High-Volume IMPORTERS or WHOLESALERS of disposable tableware (Bagasse, Sugarcane, Pulp).
    
    STRICT EXCLUSION:
    - If they have a 'Factory', 'Production Line', 'R&D Lab', or offer 'OEM manufacturing', set is_relevant to FALSE.
    - We do NOT want manufacturers. We want people who BUY from manufacturers.

    POSITIVE SIGNALS (Look for these):
    - 'Trade account login'
    - 'Wholesale pricing'
    - 'Next day delivery UK/Europe'
    - 'Stockist of eco-brands'
    - 'Catering supplies distributor'

    Content (First 6000 chars): {content[:6000]}

    Respond ONLY with this JSON structure:
    {{
        "company_name": "Official Name",
        "is_relevant": true/false,
        "type": "Importer/Wholesaler/Catering Supplier",
        "reason": "One sentence explaining why they are a buyer and not a maker",
        "key_person": "CEO or Purchasing Manager name if visible",
        "contact_email": "Official email address",
        "location": "HQ City & Country",
        "lead_score": 1 to 10
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Fix for potential JSON formatting issues from LLM
        clean_json = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_json)
    except:
        return None

# --- MAIN INTERFACE ---

input_query = st.text_input("Search Term (e.g. 'Bagasse Plates' or 'Sugarcane Tableware')", "Bagasse tableware")

if st.button("🚀 START LEAD EXTRACTION"):
    if not (SERPER_API and FIRECRAWL_API and GEMINI_API):
        st.error("❌ Missing API Keys. Please fill the sidebar.")
    else:
        # Step 1: Generate smart queries
        queries = get_search_queries(input_query, country)
        st.info(f"🔎 Scanning markets for '{input_query}' in {country.upper()}...")
        
        all_leads = []
        visited_urls = set()
        progress = st.progress(0)
        
        # Step 2: Search & Scrape
        for q_idx, q in enumerate(queries):
            search_results = execute_search(q, country, SERPER_API)
            
            for r_idx, result in enumerate(search_results[:search_depth]):
                url = result['link']
                if url in visited_urls: continue
                visited_urls.add(url)
                
                with st.status(f"Analyzing {url}...", expanded=False) as status:
                    # 1. Scrape
                    raw_text = scrape_content(url, FIRECRAWL_API)
                    if raw_text:
                        # 2. AI Qualification
                        lead_data = qualify_lead_ai(raw_text, url, GEMINI_API)
                        
                        if lead_data and lead_data.get('is_relevant'):
                            lead_data['website'] = url
                            all_leads.append(lead_data)
                            st.toast(f"✅ Found: {lead_data['company_name']}")
                            status.update(label=f"🎯 MATCH: {lead_data['company_name']}", state="complete")
                        else:
                            status.update(label="❌ Skipped (Manufacturer or Irrelevant)", state="complete")
                    else:
                        status.update(label="⚠️ Could not read site", state="error")
                
                # Update progress bar
                progress.progress(((q_idx * search_depth) + r_idx + 1) / (len(queries) * search_depth))

        # Step 3: Display & Download
        if all_leads:
            st.divider()
            st.success(f"🎊 Successfully found {len(all_leads)} high-quality leads!")
            df = pd.DataFrame(all_leads)
            
            # Reorder columns for the user
            cols = ['lead_score', 'company_name', 'type', 'location', 'contact_email', 'key_person', 'website', 'reason']
            df = df[cols].sort_values(by='lead_score', ascending=False)
            
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Lead Database (CSV)",
                data=csv,
                file_name=f"bagasse_importers_{country}.csv",
                mime="text/csv",
            )
        else:
            st.warning("🧐 No relevant importers found. Try a broader term like 'Catering Supplies Wholesale'.")
