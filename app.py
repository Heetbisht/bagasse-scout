import streamlit as st
import pandas as pd
import requests
import json
import time
import google.generativeai as genai

st.set_page_config(page_title="BagasseScout: Self-Healing Edition", layout="wide")
st.title("🌱 BagasseScout: Smart Model Discovery")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Setup")
    serper_key = st.text_input("Serper API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    st.divider()
    market = st.selectbox("Select Country", ["uk", "de", "fr", "nl"], index=0)

# --- THE ENGINE ---

def get_urls(query, country, key):
    url = "https://google.serper.dev/search"
    full_query = f"{query} wholesale distributor {country.upper()}"
    payload = json.dumps({"q": full_query, "gl": country, "num": 10})
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, data=payload)
        return res.json().get('organic', [])
    except: return []

def get_content(url, key):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    try:
        res = requests.post("https://api.firecrawl.dev/v1/scrape", json=data, headers=headers, timeout=30)
        return res.json().get("data", {}).get("markdown", "")
    except: return None

def ai_analyze(content, url, key):
    genai.configure(api_key=key)
    
    # --- AUTO-DISCOVERY LOGIC ---
    try:
        # Ask the API which models are available for THIS key
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not available_models:
            return {"error": "No generative models found for this API key."}
        
        # Pick the best available (Flash is preferred, then Pro)
        selected_model = next((m for m in available_models if "flash" in m), available_models[0])
        model = genai.GenerativeModel(selected_model)
    except Exception as e:
        return {"error": f"Model Discovery Failed: {str(e)}"}

    prompt = f"""
    Website: {url}
    Content: {content[:7000]}
    Task: Is this a European wholesaler/importer of bagasse/eco-tableware? 
    Return ONLY JSON:
    {{
        "company": "Name",
        "is_lead": true/false,
        "type": "Importer/Wholesaler/Manufacturer",
        "email": "Email if found",
        "reason": "Short reason"
    }}
    """
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        # Clean JSON markdown if present
        if "```json" in raw_text: raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text: raw_text = raw_text.split("```")[1].split("```")[0].strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"error": f"AI Parsing Error: {str(e)}"}

# --- EXECUTION ---

search_term = st.text_input("Product Search", "Bagasse tableware")

if st.button("🚀 Start Lead Engine"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Missing API Keys!")
    else:
        results = []
        links = get_urls(search_term, market, serper_key)
        
        if not links:
            st.warning("Google found no results. Check Serper Key.")
        else:
            progress = st.progress(0)
            for i, item in enumerate(links):
                url = item['link']
                st.write(f"🔎 Analyzing: {url}")
                
                text = get_content(url, firecrawl_key)
                if text:
                    data = ai_analyze(text, url, gemini_key)
                    if data and "error" not in data:
                        if data.get("is_lead"):
                            data['url'] = url
                            results.append(data)
                            st.success(f"✅ Found: {data['company']}")
                    elif data and "error" in data:
                        st.error(f"AI Error: {data['error']}")
                
                progress.progress((i + 1) / len(links))
                time.sleep(1)

            if results:
                st.divider()
                st.balloons()
                df = pd.DataFrame(results)
                st.dataframe(df)
                st.download_button("Download CSV", df.to_csv(index=False), "leads.csv")
            else:
                st.info("No leads found. Broaden your search term.")
