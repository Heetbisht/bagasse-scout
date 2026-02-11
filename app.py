import streamlit as st
import pandas as pd
import requests
import json
import time
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- UI CONFIG ---
st.set_page_config(page_title="BagasseScout Global Master", layout="wide", page_icon="🌍")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #1b5e20; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌍 BagasseScout Global Master")
st.subheader("Multi-Country B2B Lead Engine for Bagasse & Eco-Packaging")

# --- SIDEBAR API SETUP ---
with st.sidebar:
    st.header("🔑 API Configuration")
    serper_key = st.text_input("Serper API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.header("⚙️ Automation Settings")
    selected_regions = st.multiselect(
        "Target Countries", 
        ["uk", "de", "fr", "nl", "be", "it", "es", "pl"],
        default=["uk"]
    )
    results_per_country = st.slider("Leads per Country", 5, 20, 10)
    st.info("💡 Pro Tip: Selecting 3 countries with 10 leads each will scan 30 websites total.")

# --- SMART LOGIC FUNCTIONS ---

def get_smart_query(base_product, country_code):
    """Appends high-intent B2B keywords based on the local market language."""
    footprints = {
        "uk": f'"{base_product}" wholesale UK distributor -factory -manufacturer',
        "de": f'"{base_product}" Großhandel Gastronomiebedarf -hersteller',
        "fr": f'"{base_product}" grossiste emballage alimentaire -usine',
        "nl": f'"{base_product}" groothandel suikerriet servies -fabriek',
        "it": f'"{base_product}" ingrosso stoviglie monouso -fabbrica',
        "es": f'"{base_product}" mayorista envases biodegradables -fábrica'
    }
    # Default to English B2B terms if country not in list
    return footprints.get(country_code, f'"{base_product}" wholesale distributor {country_code} -factory')

def scrape_site(url, api_key):
    """Reliable v1 Firecrawl Scraper."""
    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json().get("data", {}).get("markdown", "")
    except: return None
    return None

def analyze_with_ai(content, url, api_key):
    """The 'Ultimate' AI Brain that distinguishes Importers from Factories."""
    genai.configure(api_key=api_key)
    model = GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Analyze this website content: {url}
    Context: We are searching for European IMPORTERS or WHOLESALERS of Bagasse (Sugarcane) tableware.

    RULES:
    1. ACCEPT (is_relevant: true) if they are a distributor, catering supplier, stockist, or have a 'Trade Account' or 'Wholesale' section.
    2. REJECT (is_relevant: false) if they are a MANUFACTURING PLANT in Asia (e.g., Factory in China/Vietnam) with no local EU warehouse.
    3. Even if they sell other eco-items, if they carry bagasse plates/containers, they are a lead.

    Website Content (First 7000 chars): {content[:7000]}

    Return JSON ONLY:
    {{
        "company_name": "Name",
        "is_relevant": true,
        "type": "Importer / Wholesaler / Online Trade Shop",
        "reason": "Why is this a good buyer lead?",
        "contact_info": "Email or Phone if found",
        "location": "City/Country",
        "score": 1-10
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except: return None

# --- MAIN FLOW ---

product_input = st.text_input("Product Type", "Bagasse tableware")

if st.button("🚀 EXECUTE GLOBAL SEARCH"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Missing API Keys in sidebar.")
    elif not selected_regions:
        st.warning("Please select at least one target country.")
    else:
        all_leads = []
        
        for country in selected_regions:
            st.header(f"📍 Market: {country.upper()}")
            
            # 1. Smart Google Search
            smart_q = get_smart_query(product_input, country)
            st.write(f"Searching: *{smart_q}*")
            
            search_url = "https://google.serper.dev/search"
            search_payload = json.dumps({"q": smart_q, "gl": country, "num": results_per_country})
            search_headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
            
            try:
                search_results = requests.post(search_url, headers=search_headers, data=search_payload).json().get('organic', [])
            except:
                st.error(f"Search failed for {country}")
                continue

            # 2. Scrape and Analyze
            for i, result in enumerate(search_results):
                url = result['link']
                with st.status(f"[{country.upper()}] Analyzing {url}...", expanded=False) as status:
                    
                    text = scrape_site(url, firecrawl_key)
                    if text:
                        lead = analyze_with_ai(text, url, gemini_key)
                        if lead and lead.get('is_relevant'):
                            lead['website'] = url
                            lead['market'] = country.upper()
                            all_leads.append(lead)
                            status.update(label=f"✅ MATCH: {lead['company_name']}", state="complete")
                            st.toast(f"Match in {country.upper()}!")
                        else:
                            status.update(label="❌ Not a lead", state="complete")
                    else:
                        status.update(label="⚠️ Site unreachable", state="error")
                
                time.sleep(1.5) # Prevent rate limits

        # 3. Final Table & Download
        if all_leads:
            st.divider()
            st.success(f"🎊 Total Leads Found: {len(all_leads)}")
            df = pd.DataFrame(all_leads)
            
            # Reorder for professional look
            cols = ['market', 'score', 'company_name', 'type', 'location', 'contact_info', 'website', 'reason']
            df = df[cols].sort_values(by=['market', 'score'], ascending=[True, False])
            
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download All Global Leads (CSV)", csv, "global_bagasse_leads.csv", "text/csv")
        else:
            st.warning("No leads found across selected markets. Try broader terms like 'Catering supplies'.")
