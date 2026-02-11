import streamlit as st
import pandas as pd
import requests
import json
import time
import google.generativeai as genai

st.set_page_config(page_title="Lead Debugger", layout="wide")
st.title("🕵️‍♂️ Lead Engine: Debugger Mode")
st.write("This version shows exactly what is happening behind the scenes.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 API Keys")
    serper_key = st.text_input("Serper.dev Key", type="password")
    firecrawl_key = st.text_input("Firecrawl Key", type="password")
    gemini_key = st.text_input("Gemini Key", type="password")
    st.divider()
    market = st.selectbox("Market", ["uk", "de", "fr", "nl"], index=0)

# --- THE PROCESSORS ---

def get_urls(query, country, key):
    st.write(f"🔎 Searching Google for: `{query}` in `{country}`")
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": country, "num": 5})
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, data=payload)
        results = res.json().get('organic', [])
        st.write(f"✅ Google found {len(results)} links.")
        return results
    except Exception as e:
        st.error(f"Search Failed: {e}")
        return []

def get_content(url, key):
    st.write(f"🌐 Scraping: {url}...")
    # Using the most stable Firecrawl endpoint
    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"url": url, "formats": ["markdown"]}
    try:
        res = requests.post(endpoint, json=data, headers=headers, timeout=30)
        if res.status_code == 200:
            content = res.json().get("data", {}).get("markdown", "")
            if content:
                st.write(f"📄 Scraped {len(content)} characters of text.")
                return content
            else:
                st.warning("⚠️ Firecrawl returned empty text for this site.")
        else:
            st.error(f"❌ Firecrawl Error {res.status_code}: {res.text}")
    except Exception as e:
        st.error(f"Scrape Failed: {e}")
    return None

def ai_analyze(content, url, key):
    st.write("🤖 AI is analyzing content...")
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Extract business info from this text: {content[:5000]}
    URL: {url}
    
    Return ONLY JSON:
    {{
        "company": "Name",
        "type": "Importer/Distributor/Manufacturer/Other",
        "is_lead": true,
        "email": "email",
        "phone": "phone"
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Robust JSON cleaning
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(raw_text)
        return data
    except Exception as e:
        st.error(f"AI Analysis Failed: {e}")
        st.write(f"Raw AI response was: {response.text[:200]}")
        return None

# --- RUN BUTTON ---
search_input = st.text_input("Business Category", "Catering supplies wholesale")

if st.button("Start Debugging"):
    if not (serper_key and firecrawl_key and gemini_key):
        st.error("Fill in all keys!")
    else:
        results_data = []
        links = get_urls(search_input, market, serper_key)
        
        for item in links:
            url = item['link']
            text = get_content(url, firecrawl_key)
            
            if text:
                analysis = ai_analyze(text, url, gemini_key)
                if analysis:
                    analysis['url'] = url
                    results_data.append(analysis)
                    st.success(f"✔️ Found: {analysis['company']}")
            
            st.divider()
            time.sleep(1)

        if results_data:
            st.balloons()
            st.dataframe(pd.DataFrame(results_data))
        else:
            st.error("No leads captured. Check the logs above to see which step failed.")
