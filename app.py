import streamlit as st
import pandas as pd
import requests
import json
import time
from google.generativeai import GenerativeModel
import google.generativeai as genai

# --- PAGE CONFIG ---
st.set_page_config(page_title="BagasseScout | Lead Engine", layout="wide", page_icon="🌱")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #2e7d32; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 BagasseScout: Importer Search Engine")
st.subheader("Targeting UK & European Wholesalers (Excluding Factories)")

# --- SIDEBAR: API KEYS ---
with st.sidebar:
    st.header("🔑 API Setup")
    st.info("Get keys: [Serper.dev](https://serper.dev) | [Firecrawl](https://firecrawl.dev) | [Gemini](https://aistudio.google.com/)")
    SERPER_API = st.text_input("Serper API Key", type="password")
    FIRECRAWL_API = st.text_input("Firecrawl API Key", type="password")
    GEMINI_API = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.write("### Search Settings")
    target_country = st.selectbox("Target Country", ["uk", "de", "fr", "nl", "be", "it", "es"])
    max_results = st.slider("Number of sites to scan", 5, 30, 10)

# --- HELPER FUNCTIONS ---

def google_search(query, country_code, api_key):
    """Searches Google for potential importers."""
    url = "https://google.serper.dev/search"
    # Negative keywords added to query to filter out manufacturers at the search level
    refined_query = f"{query} -factory -manufacturer -maker -production -plant"
    payload = json.dumps({"q": refined_query, "gl": country_code, "num": max_results})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json().get('organic', [])
    except Exception as e:
        st.error(f"Search Error: {e}")
        return []

def scrape_site(url, api_key):
    """Uses Firecrawl to extract clean text from the website."""
    endpoint = "https://api.firecrawl.dev/v0/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"url": url, "pageOptions": {"onlyMainContent": True}}
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.json().get('data', {}).get('content', "")
    except:
        return None
    return None

def qualify_with_ai(content, url, gemini_key):
    """Uses Gemini to filter for importers and extract contact details."""
    genai.configure(api_key=gemini_key)
    model = GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Analyze this website content from {url}. 
    Goal: Identify if this company is a BUYER/IMPORTER/DISTRIBUTOR of disposable tableware.
    
    STRICT FILTER: 
    - If they mention 'our factory', 'manufacturing process', 'we produce', 'ISO factory', or 'OEM services', they are a MANUFACTURER. Mark is_relevant as false.
    - If they mention 'wholesale', 'distributor of', 'in stock', 'order catalog', or 'catering supplies', they are a BUYER. Mark is_relevant as true.

    Content: {content[:6000]}

    Return ONLY a JSON object:
    {{
        "company_name": "Name",
        "is_relevant": true/false,
        "business_model": "Importer / Wholesaler / Retailer",
        "reasoning": "1-sentence why they are not a factory",
        "top_person": "CEO or Purchasing Manager name if found, else 'Not Found'",
        "email": "Contact email if found",
        "phone": "Phone number if found",
        "location": "City/Country",
        "lead_score": 1-10
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Clean JSON formatting
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except:
        return None

# --- MAIN APP LOGIC ---

search_term = st.text_input("What are you looking for?", "Bagasse tableware wholesale")

if st.button("🚀 Run Lead Engine"):
    if not (SERPER_API and FIRECRAWL_API and GEMINI_API):
        st.warning("Please enter all API keys in the sidebar.")
    else:
        st.info(f"Searching for leads in {target_country.upper()}...")
        
        raw_results = google_search(search_term, target_country, SERPER_API)
        
        leads_found = []
        progress_bar = st.progress(0)
        
        for idx, result in enumerate(raw_results):
            url = result['link']
            # Update UI
            st.write(f"🔍 Checking: {url}")
            
            # 1. Scrape
            content = scrape_site(url, FIRECRAWL_API)
            
            if content:
                # 2. Qualify
                data = qualify_with_ai(content, url, GEMINI_API)
                
                if data and data.get('is_relevant'):
                    data['website'] = url
                    leads_found.append(data)
                    st.success(f"✅ Lead Added: {data['company_name']}")
            
            # Update Progress
            progress_bar.progress((idx + 1) / len(raw_results))
            time.sleep(1) # Ethics delay

        if leads_found:
            st.divider()
            st.subheader("🎯 Qualified Importer List")
            df = pd.DataFrame(leads_found)
            st.dataframe(df)
            
            # Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Leads CSV", csv, "bagasse_leads.csv", "text/csv")
        else:
            st.error("No relevant importers found. Try broadening your search term.")