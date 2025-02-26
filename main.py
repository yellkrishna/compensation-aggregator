import streamlit as st
import pandas as pd
from scrape import scrape_website
from st_aggrid import AgGrid, GridOptionsBuilder
import io

st.title("compensation-aggregator")
url = st.text_input("Enter URL:")

headless_mode = st.checkbox("Run Chrome in headless mode", value=True)

if st.button("Scrape site"):
    st.markdown("**Scraping the website recursively. Please wait...**")
    results = scrape_website(url, max_depth=2, max_breadth=6, headless=headless_mode)
    
    if results.empty:
        st.warning("No job postings were found.")
    else:
        st.markdown(f"**Scraping complete! Found {len(results)} job postings.**")
        df = results.copy()
        
        # Build grid options for AgGrid display.
        # Use original columns and apply cell styling to visually truncate long text.
        gb = GridOptionsBuilder.from_dataframe(
            df[["title", "location", "salary_range", "responsibilities", "qualification", "description"]]
        )
        
        # Define a style that truncates text with ellipsis if it overflows the cell.
        truncate_style = {"whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}
        
        # Configure the columns with potentially long text.
        gb.configure_column("description", cellStyle=truncate_style, tooltipField="description")
        gb.configure_column("qualification", cellStyle=truncate_style, tooltipField="qualification")
        gb.configure_column("responsibilities", cellStyle=truncate_style, tooltipField="responsibilities")
        
        gridOptions = gb.build()
        
        AgGrid(df, gridOptions=gridOptions, allow_unsafe_jscode=True)
        
        # Convert DataFrame to Excel file in memory and add a download button.
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Job Postings')
        buffer.seek(0)
        
        st.download_button(
            "Download Excel File",
            data=buffer,
            file_name="job_postings.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
