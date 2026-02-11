import streamlit as st
import pandas as pd
import requests
import json
import time
import google.generativeai as genai

st.set_page_config(page_title="BagasseScout Pro", layout="wide")
st.title("🌱 BagasseScout: Professional Edition")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Setup")
    serper_key = st.text_input("Serper API Key", type="password")
    firecrawl_key = st.text_input("Firecrawl API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    st.divider()
    market = st.selectbox("Select Country", ["uk", "de", "fr", "nl"], index=0)
    search_limit = st.slider("Sites to check", 5, 20, 10)

# --- THE ENGINE ---

def get_urls(query, country, key, limit):
    url = "https://google.serper.dev/search"
    # Added B2B keywords directly to search
    full_query = f"{query} wholesale distributor {country.upper()}"
    payload = json.dumps({"q": full_query, "gl": country, "num": limit})
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, data=payload)
        return res.json().get('organic', [])
    except: return []

def get_content(url, key):
    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    try:
        res = requests.post(endpoint, json=data, headers=headers, timeout=30)
        if res.status_code == 200:
            return res.json().get("data", {}).get("markdown", "")
    except: return None
    return None

def ai_analyze(content, url, key):
    genai.configure(api_key=key)
    
    # Try multiple model names to solve the 404 error
    model_names = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    
    success = False
    model_to_use = None
    
    for name in model_names:
        try:
            model_to_use = genai.GenerativeModel(name)
            # Test a tiny prompt to see if model exists
            model_to_use.generate_content("test")
            success = True
            break
        except:
            continue

    if not success:
        return {"error": "Could not connect to any Gemini models. Check your API Key permissions."}

    prompt = f"""
    Extract business info from this text: {content[:7000]}
    URL: {url}
    
    Return ONLY JSON:
    {{
        "company": "Name",
        "type": "Importer/Wholesaler/Manufacturer",
        "is_lead": true,
        "email": "email",
        "phone": "phone",
        "reason": "Why is this a lead?"
    }}
    """
    try:
        response = model_to_use.generate_content(prompt)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"error": str(e)}

# --- EXECUTION ---

search_term = st.text_input("Product Search", "Bagasse tableware")

if st.button("🚀 Start Lead Engine"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Missing API Keys!")
    else:
        results = []
        links = get_urls(search_term, market, serper_key, search_limit)
        
        if not links:
            st.warning("Google found no results. Check Serper Key.")
        else:
            progress = st.progress(0)
            for i, item in enumerate(links):
                url = item['link']
                st.write(f"🔍 Analyzing: {url}")
                
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
                st.info("No qualified leads found. Try a broader search term.")
