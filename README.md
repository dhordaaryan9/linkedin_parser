# LinkedIn Profile Downloader & JSON Parser

A Streamlit application that automates downloading LinkedIn profiles as PDFs using Playwright and batch-parses them into structured JSON using Groq LLM and Pydantic.

## 1. Prerequisites
- Python 3.10+
- Microsoft Edge installed (used by Playwright on Windows)
- A [Groq API Key](https://console.groq.com/)

## 2. Installation

Create a `requirements.txt` file with the following packages:
```text
streamlit
python-dotenv
langchain-groq
playwright
pydantic
pypdf
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

## 3. Environment Setup (`.env`)

Create a file named `.env` in the root project folder and add your Groq API key:
```env
GROQ_API_KEY=your_groq_api_key_here
```

## 4. How to Run

Run the Streamlit app from your project folder:
```bash
streamlit run linkedin_app.py --server.fileWatcherType none
```
*(The `--server.fileWatcherType none` flag prevents unnecessary terminal warnings from Streamlit's file watcher.)*

## 5. First-Time Login Instructions

1. Paste any LinkedIn profile URL in **Step 1** and click **Download PDF to Folder**.
2. A Microsoft Edge window will open automatically to LinkedIn.
3. **Sign in using your LinkedIn email and password.**
   - **Do NOT click "Continue with Google"** — Google blocks sign-ins from automated browsers.
   - Complete any CAPTCHA or verification code if prompted.
4. Once logged in, the browser will navigate to the profile and download the PDF into the `linkedin_cvs/` folder (named after the profile's URL slug).
   - **Fallback:** If LinkedIn's layout prevents the auto-click, simply click the **`...` (More)** button → **Save to PDF** in the open Edge window. The app will still catch the download and save it automatically.
5. Your login session is saved locally in the `linkedin_session/` folder, so you won't need to log in again on future runs.

## 6. Parsing Profiles to JSON

1. In **Step 2**, verify the folder path (defaults to `linkedin_cvs/`).
2. Click **Parse All Profiles to JSON**.
3. The structured JSON output will be displayed on screen, saved automatically to `linkedin_cvs/parsed_profiles.json`, and available via the **Download All as JSON** button.
