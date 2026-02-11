import streamlit as st
import pandas as pd
import requests
import json
import time
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- 1. SETTINGS & UI ---
st.set_page_config(page_title="BagasseScout Pro: Ultimate Edition", layout="wide", page_icon="🌱")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 8px; height: 3em; }
    .stProgress > div > div > div > div { background-color: #2e7d32; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 BagasseScout Pro: All-in-One Lead Engine")
st.subheader("Targeting UK & European Importers, Wholesalers, and Stockists")

# --- 2. SIDEBAR API SETUP ---
with st.sidebar:
    st.header("🔑 API Configuration")
    st.markdown("[Get Serper Key](https://serper.dev) | [Get Firecrawl Key](https://firecrawl.dev) | [Get Gemini Key](https://aistudio.google.com/)")
    
    serper_key = st.text_input("Serper API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.header("🌍 Market Target")
    target_market = st.selectbox("Select Region", ["uk", "de", "fr", "nl", "be", "it", "es"], index=0)
    search_limit = st.slider("Results to Analyze", 5, 30, 10)
    st.info("💡 High numbers (20+) may hit free-tier rate limits.")

# --- 3. THE CORE ENGINE ---

def get_search_results(query, country, api_key):
    """Fetches high-intent URLs from Google via Serper."""
    url = "https://google.serper.dev/search"
    # Adds B2B intent keywords to your search automatically
    b2b_query = f"{query} wholesale distributor stockist {country.upper()}"
    payload = json.dumps({"q": b2b_query, "gl": country, "num": search_limit})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json().get('organic', [])
    except Exception as e:
        st.error(f"Search Error: {str(e)}")
        return []

def scrape_with_firecrawl(url, api_key):
    """Extracts clean text from websites using Firecrawl v1."""
    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json().get("data", {}).get("markdown", "")
        elif response.status_code == 429:
            return "RATE_LIMIT"
    except:
        return None
    return None

def analyze_with_gemini(content, url, api_key):
    """Uses AI to identify if the company is a buyer/importer."""
    genai.configure(api_key=api_key)
    model = GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Analyze the website content from {url}. 
    We are looking for BUYERS (Importers, Wholesalers, Catering Suppliers) of Bagasse (Sugarcane) tableware.

    RULES:
    1. ACCEPT (is_relevant: true) if they sell eco-packaging, catering disposables, or have a wholesale/trade section.
    2. REJECT (is_relevant: false) ONLY if they are a factory in China/India with no European contact info.
    3. Even if they are an 'Online Shop', they are a potential lead if they carry stock in Europe.

    Content: {content[:7000]}

    Return JSON ONLY:
    {{
        "company": "Name",
        "is_relevant": true,
        "type": "Wholesaler / Distributor / Brand Owner",
        "email": "Email if found, else 'Check website'",
        "phone": "Phone number if found",
        "location": "HQ City/Country",
        "reasoning": "1-sentence why they are a good lead",
        "score": 1-10
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except:
        return None

# --- 4. MAIN EXECUTION ---

user_query = st.text_input("Enter Search (Example: 'Bagasse plates' or 'Sugarcane tableware')", "Bagasse tableware")

if st.button("🚀 EXECUTE LEAD ENGINE"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("⚠️ Please provide all three API keys in the sidebar.")
    else:
        st.info(f"🔎 Hunting for importers in {target_market.upper()}...")
        
        # 1. Search
        search_results = get_search_results(user_query, target_market, serper_key)
        
        if not search_results:
            st.warning("No search results found. Check your Serper API Key.")
        else:
            final_leads = []
            progress_bar = st.progress(0)
            
            # 2. Loop through sites
            for i, result in enumerate(search_results):
                site_url = result['link']
                st.write(f"🔄 **Analyzing:** {site_url}")
                
                # Scrape
                page_text = scrape_with_firecrawl(site_url, firecrawl_key)
                
                if page_text == "RATE_LIMIT":
                    st.warning("⏸️ Firecrawl Rate Limit reached. Waiting 10s...")
                    time.sleep(10)
                    page_text = scrape_with_firecrawl(site_url, firecrawl_key)

                if page_text and len(page_text) > 200:
                    # AI Analysis
                    lead_data = analyze_with_gemini(page_text, site_url, gemini_key)
                    
                    if lead_data and lead_data.get('is_relevant'):
                        lead_data['website'] = site_url
                        final_leads.append(lead_data)
                        st.success(f"🎯 **Match Found:** {lead_data['company']} ({lead_data['type']})")
                
                progress_bar.progress((i + 1) / len(search_results))
                time.sleep(1.5) # Gentle pacing

            # 3. Display Results
            if final_leads:
                st.divider()
                st.balloons()
                st.subheader(f"✅ Extracted {len(final_leads)} Qualified Leads")
                
                df = pd.DataFrame(final_leads)
                # Cleanup and reorder
                cols = ['score', 'company', 'type', 'location', 'email', 'phone', 'website', 'reasoning']
                df = df[cols].sort_values(by='score', ascending=False)
                
                st.dataframe(df, use_container_width=True)
                
                # Export to CSV
                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Lead List (CSV)", 
                    csv_data, 
                    f"bagasse_leads_{target_market}.csv", 
                    "text/csv"
                )
            else:
                st.warning("Process complete, but no importers were qualified. Try a broader search like 'Catering supplies wholesale'.")
