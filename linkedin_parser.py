import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from pypdf import PdfReader

# 1. Load GROQ_API_KEY from .env
load_dotenv()

st.set_page_config(page_title="LinkedIn URL to JSON", page_icon="📄")
st.title("📄 LinkedIn Profile Downloader & JSON Parser")

SAVE_FOLDER = Path("linkedin_cvs")
SAVE_FOLDER.mkdir(exist_ok=True)


# 2. Define the JSON Schema
class Experience(BaseModel):
    role: str = Field(description="Job title")
    company: str = Field(description="Company name")
    duration: Optional[str] = Field(default=None, description="Time period worked")


class Education(BaseModel):
    degree: str = Field(description="Degree or certification")
    institution: str = Field(description="University or school name")
    years: Optional[str] = Field(default=None, description="Years attended")


class LinkedInProfile(BaseModel):
    name: str = Field(description="Full name of the person")
    headline: Optional[str] = Field(default=None, description="Profile headline")
    location: Optional[str] = Field(default=None, description="City or country")
    email: Optional[str] = Field(default=None, description="Email address if present")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile URL if present")
    summary: Optional[str] = Field(default=None, description="About / Summary section")
    skills: List[str] = Field(default_factory=list, description="List of top skills")
    experience: List[Experience] = Field(default_factory=list, description="Work experience history")
    education: List[Education] = Field(default_factory=list, description="Education history")


# 3. Async Playwright function to download LinkedIn PDF using Edge
async def download_linkedin_pdf(profile_url: str, save_folder: Path) -> Path:
    session_dir = str(Path("linkedin_session").resolve())

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            channel="msedge",
            headless=False,
            accept_downloads=True,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Open LinkedIn feed first to avoid HTTP 999 anti-bot block
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        # If not logged in yet, wait for manual sign-in
        if "login" in page.url or "authwall" in page.url or "checkpoint" in page.url:
            await page.wait_for_url("**/feed/**", timeout=90000)

        # Navigate to the target profile and let dynamic buttons render
        await page.goto(profile_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Listen for the PDF download (up to 60s)
        async with page.expect_download(timeout=60000) as download_info:
            try:
                # Target the circular "..." icon button in the top profile card
                dots_btn = page.locator(
                    "main section button[aria-label*='More' i]:visible"
                ).first
                await dots_btn.wait_for(state="visible", timeout=10000)
                await dots_btn.click()

                # Click "Save to PDF" in the dropdown menu
                save_pdf_btn = page.get_by_text("Save to PDF", exact=True).locator("visible=true").first
                await save_pdf_btn.wait_for(state="visible", timeout=5000)
                await save_pdf_btn.click()
            except Exception:
                # Fallback: click "..." -> "Save to PDF" manually in the open Edge window
                pass

        download = await download_info.value
        slug = profile_url.rstrip("/").split("/")[-1].split("?")[0] or "profile"
        save_path = save_folder / f"{slug}.pdf"
        await download.save_as(save_path)

        await browser.close()
        return save_path


def run_download(profile_url: str) -> Path:
    # ProactorEventLoop is required for Playwright subprocesses on Windows
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(download_linkedin_pdf(profile_url, SAVE_FOLDER))
    finally:
        loop.close()


# --- STEP 1: DOWNLOAD PDF FROM LINKEDIN URL ---
st.header("Step 1: Download LinkedIn Profile PDF")
url = st.text_input("Enter LinkedIn Profile URL", placeholder="https://www.linkedin.com/in/username/")

if st.button("Download PDF to Folder") and url:
    with st.spinner("Opening browser... (If prompted, log in or click '...' -> 'Save to PDF')"):
        try:
            saved_file = run_download(url)
            st.success(f"Saved PDF: `{saved_file.name}` inside `{SAVE_FOLDER}/`")
        except Exception as e:
            st.error(f"Download failed: {e}")

st.divider()

# --- STEP 2: PARSE ALL PDFs IN FOLDER TO JSON ---
st.header("Step 2: Parse All PDFs in Folder")
folder_input = st.text_input("Folder Path", value=str(SAVE_FOLDER.resolve()))
folder = Path(folder_input)

if folder.exists() and folder.is_dir():
    pdf_files = list(folder.glob("*.pdf"))
    st.info(f"Found **{len(pdf_files)}** PDF file(s) in `{folder.name}`.")

    if pdf_files and st.button("Parse All Profiles to JSON"):
        llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
        structured_llm = llm.with_structured_output(LinkedInProfile, method="json_mode")
        schema = json.dumps(LinkedInProfile.model_json_schema(), indent=2)

        all_profiles = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, file in enumerate(pdf_files):
            status_text.text(f"Parsing ({i + 1}/{len(pdf_files)}): {file.name}")
            try:
                reader = PdfReader(str(file))
                raw_text = "\n".join([page.extract_text() or "" for page in reader.pages])

                prompt = (
                    "Extract all LinkedIn/CV profile details from the PDF text below.\n"
                    "Return ONLY a valid JSON object that strictly follows this exact JSON schema "
                    "(use the exact field names like 'role', 'company', 'duration', 'skills', 'linkedin_url'):\n\n"
                    f"SCHEMA:\n{schema}\n\n"
                    f"PDF TEXT:\n{raw_text}"
                )
                parsed_profile = structured_llm.invoke(prompt)

                profile_dict = parsed_profile.model_dump()
                profile_dict["source_file"] = file.name
                all_profiles.append(profile_dict)
            except Exception as e:
                all_profiles.append({"source_file": file.name, "error": str(e)})

            progress_bar.progress((i + 1) / len(pdf_files))

        status_text.text("Done!")
        st.success(f"Parsed {len(all_profiles)} profile(s)!")

        # Save combined JSON directly into the folder
        output_file = folder / "parsed_profiles.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_profiles, f, indent=2)
        st.caption(f"Saved automatically to: `{output_file}`")

        st.json(all_profiles)

        st.download_button(
            label="Download All as JSON",
            data=json.dumps(all_profiles, indent=2),
            file_name="all_parsed_profiles.json",
            mime="application/json",
        )
else:
    st.warning("Folder not found. Check the folder path above.")