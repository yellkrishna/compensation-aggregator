import streamlit as st
from scrape import scrape_website

st.title("compensation-aggregator")
url = st.text_input("Enter URL:")

# Checkbox to control headless mode
headless_mode = st.checkbox("Run Chrome in headless mode", value=True)

if st.button("Scrape site"):
    st.markdown("**Scraping the website recursively. Please wait...**")
    # Pass the user's choice for headless mode
    results = scrape_website(url, max_depth=1, max_breadth=6, headless=headless_mode)
    
    st.markdown(f"**Scraping complete! Found {len(results)} job postings.**")
    for i, job in enumerate(results, start=1):
        st.markdown(f"### Job {i}")
        # Render the markdown content of the job correctly
        st.markdown(job, unsafe_allow_html=True)
