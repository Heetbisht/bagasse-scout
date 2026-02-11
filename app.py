import streamlit as st
import pandas as pd
import requests
import json
import time
import google.generativeai as genai
from google.api_core import exceptions

# --- UI CONFIG ---
st.set_page_config(page_title="BagasseScout Pro: Patient Edition", layout="wide")
st.title("🌱 BagasseScout: High-Accuracy Lead Engine")
st.info("Note: This version has 'Patience Logic' to stay within Free Tier limits.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Setup")
    serper_key = st.text_input("Serper API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    st.divider()
    market = st.selectbox("Select Country", ["uk", "de", "fr", "nl", "be"], index=0)
    search_limit = st.slider("Leads to find", 5, 30, 10)

# --- THE ENGINE ---

def get_urls(query, country, key, limit):
    url = "https://google.serper.dev/search"
    full_query = f"{query} wholesale distributor {country.upper()}"
    payload = json.dumps({"q": full_query, "gl": country, "num": limit})
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, data=payload)
        return res.json().get('organic', [])
    except: return []

def get_content(url, key):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    try:
        res = requests.post("https://api.firecrawl.dev/v1/scrape", json=data, headers=headers, timeout=40)
        return res.json().get("data", {}).get("markdown", "")
    except: return None

def ai_analyze_with_retry(content, url, key):
    genai.configure(api_key=key)
    
    # Discovery available models
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selected_model = next((m for m in available_models if "flash" in m), available_models[0])
        model = genai.GenerativeModel(selected_model)
    except:
        return {"error": "API Key Invalid or Model Discovery failed."}

    prompt = f"Analyze website: {url}. Content: {content[:8000]}. Task: Extract if this is a European importer/wholesaler of bagasse/eco-tableware. Return JSON: {{'company':'Name','is_lead':true,'email':'Email','reason':'Why'}}"
    
    # --- RETRY LOOP FOR 429 ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            if "```json" in raw_text: raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text: raw_text = raw_text.split("```")[1].split("```")[0].strip()
            return json.loads(raw_text)
        except exceptions.ResourceExhausted:
            wait_time = 15 + (attempt * 10) # Wait 15s, then 25s
            st.warning(f"⏳ API Limit hit. Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        except Exception as e:
            return {"error": str(e)}
    
    return {"error": "Exceeded retries due to quota limits."}

# --- EXECUTION ---

search_term = st.text_input("Product Search", "Bagasse tableware wholesale")

if st.button("🚀 Start Lead Engine"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Missing API Keys!")
    else:
        results = []
        links = get_urls(search_term, market, serper_key, search_limit)
        
        if not links:
            st.warning("Google found no results.")
        else:
            progress = st.progress(0)
            status_text = st.empty()
            
            for i, item in enumerate(links):
                url = item['link']
                status_text.text(f"🔍 Analyzing ({i+1}/{len(links)}): {url}")
                
                text = get_content(url, firecrawl_key)
                if text:
                    data = ai_analyze_with_retry(text, url, gemini_key)
                    if data and "error" not in data:
                        if data.get("is_lead"):
                            data['url'] = url
                            results.append(data)
                            st.success(f"✅ Found Lead: {data['company']}")
                    elif data and "error" in data:
                        st.error(f"AI Warning: {data['error']}")
                
                progress.progress((i + 1) / len(links))
                # Mandatory pause to stay under 15 RPM
                time.sleep(4) 

            if results:
                st.divider()
                st.balloons()
                st.subheader(f"Captured {len(results)} Leads")
                df = pd.DataFrame(results)
                st.dataframe(df)
                st.download_button("Download CSV", df.to_csv(index=False), "leads.csv")
            else:
                st.info("No leads found. Try a broader search term like 'Catering suppliers'.")
