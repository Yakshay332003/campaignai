import streamlit as st
import requests
import json
import re
import pandas as pd
import io
import time
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# -------------------------------
# Password Protection Function
# -------------------------------
def check_password():
    def password_entered():
        if st.session_state["password"] == "your_secret_password":  # Change your password here
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Enter password to access the app:", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.error("❌ Incorrect password. Please refresh and try again.")
        st.stop()

# Run password check first
check_password()


def extract_json_from_text(text):
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text)
        return json.dumps(obj)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        else:
            raise ValueError("No JSON found in the response.")

def call_perplexity_api(prompt):
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a data extraction assistant. Always respond with a single valid JSON object. Do not include markdown, text, or explanations."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload, verify=False)

    if response.status_code == 200:
        answer = response.json()['choices'][0]['message']['content']
        clean_json = extract_json_from_text(answer)
        return json.loads(clean_json)
    else:
        raise Exception(f"API Error {response.status_code}: {response.text}")

def safe_stringify(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    elif value is None:
        return ""
    else:
        return str(value)

def flatten_company_data(companies, extra_fields_list):
    flat_data = []
    for item in companies:
        contacts = item.get("Company Contacts", [])
        contact_str = "; ".join([f"{c.get('Designation','')} - {c.get('Name','')} ({c.get('Email','')})" for c in contacts]) if isinstance(contacts, list) else str(contacts)

        row = {
            "Company Name": item.get("Company Name", ""),
            "Type": item.get("Type", ""),
            "Assets": item.get("Assets", ""),
            "City": item.get("City", ""),
            "State": item.get("State", ""),
            "Country": item.get("Country", ""),
            "Region": item.get("Region", ""),
            "Website": item.get("Website", ""),
            "Latest Update": item.get("Latest Update", ""),
            "Funding / Financials": item.get("Funding / Financials", ""),
            "Company Type": item.get("Company Type", ""),
            "CDMO Requirement": item.get("CDMO Requirement", ""),
            "CDMO Use Case": item.get("CDMO Use Case", ""),
            "Company Contacts": contact_str
        }

        for field in extra_fields_list:
            row[field] = safe_stringify(item.get(field, ""))

        flat_data.append(row)
    return flat_data

def get_base_prompt(extra_fields_list):
    base_prompt = (
        "[Company Name, Type, Assets, City, State, Country, Region, Website, Latest Update, Funding / Financials, Company Type, CDMO Requirement, CDMO Use Case, Company Contacts"
    )
    if extra_fields_list:
        base_prompt += ", " + ", ".join(extra_fields_list)

    base_prompt += "].\n\n"
    base_prompt += (
        "'CDMO Requirement' should state whether the company is likely to require CDMO services (Yes/No).\n"
        "'CDMO Use Case' should describe how the company could potentially use CDMO services (e.g., for drug development, manufacturing, scaling production, etc.).\n"
        "'Company Contacts' should provide a list of relevant contact persons in the company with their designations, names, and email IDs. Use realistic placeholders if actual data is not available.\n\n"
        "Respond strictly in JSON format without any additional explanation or markdown formatting."
    )
    return base_prompt

# Streamlit App

st.set_page_config(page_title="Company Info Extractor", page_icon="🔍", layout="centered")

st.markdown("""
    <style>
    body { background-color: #0d1117; color: #c9d1d9; }
    .main { background-color: transparent; }
    .stTextInput > div > div > input, .stTextArea > div > textarea { background-color: #161b22; color: #c9d1d9; border-radius: 8px; padding: 10px; border: 1px solid #30363d; }
    .stButton > button { background: linear-gradient(90deg, #00c6ff, #0072ff); color: white; border-radius: 10px; padding: 10px 25px; font-weight: 600; border: none; transition: all 0.3s ease-in-out; }
    .stButton > button:hover { background: linear-gradient(90deg, #0072ff, #00c6ff); transform: scale(1.05); }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
# <span style="background: linear-gradient(90deg, #00c6ff, #0072ff); -webkit-background-clip: text; color: transparent; font-size: 38px; font-weight: bold;">
Company Info Extractor
</span>
""", unsafe_allow_html=True)

mode = st.radio("Choose an Option:", [
    "📂 1) Excel Company Extraction",
    "🔍 2) Global Market Search",
    "🆕 3) Global Search & Compare with Excel"
])

extra_fields = st.text_input("Optional: Add Extra Fields (comma separated)", "Drug Pipeline, Therapeutic Area")
extra_fields_list = [f.strip() for f in extra_fields.split(",") if f.strip() != ""]

# Option 1: Excel Company Extraction
if mode == "📂 1) Excel Company Extraction":
    st.header("Upload Excel File with 'COMPANY' Column")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        if 'COMPANY' not in df.columns:
            st.error("Uploaded file must have a 'COMPANY' column.")
        else:
            company_list = df['COMPANY'].tolist()
            if st.button("🚀 Extract Info for Excel Companies"):
                all_data = []
                with st.spinner("Extracting company info..."):
                    for company in company_list:
                        try:
                            prompt = (
                                f"Provide a structured JSON for the company '{company}' with the following keys:\n"
                            )
                            prompt += get_base_prompt(extra_fields_list)

                            info = call_perplexity_api(prompt)
                            all_data.append(info)
                            time.sleep(1.5)  # Avoid API rate limit

                        except Exception as e:
                            st.warning(f"Skipping {company}: {str(e)}")

                flat_data = flatten_company_data(all_data, extra_fields_list)
                df_result = pd.DataFrame(flat_data)

                st.success("✅ Extraction Completed")
                st.dataframe(df_result)

                output = io.BytesIO()
                with pd.ExcelWriter(output) as writer:
                    df_result.to_excel(writer, index=False, sheet_name='Company Info')

                output.seek(0)

                st.download_button(
                    label="📥 Download Excel",
                    data=output,
                    file_name="company_info_excel_extraction.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Option 2: Global Market Search
elif mode == "🔍 2) Global Market Search":
    st.header("Describe the type of companies to search for")
    market_filter = st.text_area("Market Filter", "Peptide focused pharma companies working on drug development")

    if st.button("🚀 Run Global Market Search"):
        with st.spinner("Searching for companies..."):
            try:
                prompt = (
                    f"Identify global pharma or biotech companies that are working on: {market_filter.strip()}.\n\n"
                    f"For each company found, provide a structured JSON with the following keys:\n"
                )
                prompt += get_base_prompt(extra_fields_list)

                result = call_perplexity_api(prompt)

                if isinstance(result, dict) and "Companies" in result:
                    flat_data = flatten_company_data(result["Companies"], extra_fields_list)
                else:
                    flat_data = flatten_company_data(result, extra_fields_list)

                df_result = pd.DataFrame(flat_data)

                st.success("✅ Global Search Completed")
                st.dataframe(df_result)

                output = io.BytesIO()
                with pd.ExcelWriter(output) as writer:
                    df_result.to_excel(writer, index=False, sheet_name='Global Search')

                output.seek(0)

                st.download_button(
                    label="📥 Download Excel",
                    data=output,
                    file_name="global_market_search.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(str(e))

# Option 3: Global Search & Compare with Excel
elif mode == "🆕 3) Global Search & Compare with Excel":
    st.header("Upload Existing Company List (Excel with 'COMPANY' column)")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

    st.header("Describe the type of companies to search for that are not there in excel")
    market_filter = st.text_area("Market Filter", "Peptide focused pharma companies working on drug development")

    if st.button("🚀 Run Search & Find New Companies"):
        if uploaded_file is None:
            st.error("Please upload the Excel file.")
        elif not market_filter.strip():
            st.error("Please enter the market filter.")
        else:
            with st.spinner("Searching and comparing..."):
                try:
                    existing_df = pd.read_excel(uploaded_file)
                    if 'COMPANY' not in existing_df.columns:
                        st.error("Uploaded file must have 'COMPANY' column.")
                        st.stop()

                    existing_companies = set(existing_df['COMPANY'].str.strip().str.lower())

                    prompt = (
                        f"Identify global pharma or biotech companies that are working on: {market_filter.strip()}.\n\n"
                        f"For each company found, provide a structured JSON with the following keys:\n"
                    )
                    prompt += get_base_prompt(extra_fields_list)

                    result = call_perplexity_api(prompt)

                    if isinstance(result, dict) and "Companies" in result:
                        flat_data = flatten_company_data(result["Companies"], extra_fields_list)
                    else:
                        flat_data = flatten_company_data(result, extra_fields_list)

                    df_result = pd.DataFrame(flat_data)
                    df_result['Company Name Lower'] = df_result['Company Name'].str.strip().str.lower()

                    new_companies_df = df_result[~df_result['Company Name Lower'].isin(existing_companies)].copy()
                    new_companies_df.drop(columns=["Company Name Lower"], inplace=True)

                    if new_companies_df.empty:
                        st.warning("No new companies found.")
                    else:
                        st.success("✅ New companies found!")
                        st.dataframe(new_companies_df)

                        output = io.BytesIO()
                        with pd.ExcelWriter(output) as writer:
                            new_companies_df.to_excel(writer, index=False, sheet_name='New Companies')

                        output.seek(0)

                        st.download_button(
                            label="📥 Download Excel",
                            data=output,
                            file_name="new_companies_global_search.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                except Exception as e:
                    st.error(str(e))
