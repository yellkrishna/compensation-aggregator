import streamlit as st
import pandas as pd
from scrape import scrape_website  # Import the individual scrape function
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import time 

st.title("Compensation Aggregator")

# Upload the Excel file (first column: company names, second column: URLs)
uploaded_file = st.file_uploader("Upload Excel file containing company names and URLs", type=["xlsx", "xls"])

headless_mode = st.checkbox("Run Chrome in headless mode", value=True)

if uploaded_file is not None:
    # Read the uploaded Excel file.
    url_df = pd.read_excel(uploaded_file)
    st.markdown(f"**Found {len(url_df)} companies in the uploaded file.**")
    
    if st.button("Scrape sites"):
        st.markdown("**Scraping sites... Please wait.**")

        # Start timer
        start_time = time.time()
        
        all_dfs = []  # List to hold DataFrames from each company
        
        # Iterate over each row to get company name and URL.
        for index, row in url_df.iterrows():
            company_name = row.iloc[0]  # Company name in the first column
            url = row.iloc[1]           # URL in the second column
            st.markdown(f"Scraping jobs for **{company_name}** from URL: {url}")
            
            # Call the scraping function for this URL.
            df = scrape_website(url, max_depth=2, max_breadth=3, headless=headless_mode)
            
            if not df.empty:
                # Insert a new column at the beginning for the company name.
                df.insert(0, "company", company_name)
                all_dfs.append(df)
            else:
                st.warning(f"No job postings found for {company_name}.")

        if all_dfs:
            final_df = pd.concat(all_dfs, ignore_index=True)
            st.markdown(f"**Scraping complete! Found {len(final_df)} job postings across all companies.**")

            # Stop timer and calculate elapsed time
            elapsed_time = time.time() - start_time
            st.markdown(f"**Time taken:** {elapsed_time:.2f} seconds")
            
            # Set up AgGrid options for display.
            gb = GridOptionsBuilder.from_dataframe(
                final_df[["company", "title", "location", "salary_range", "responsibilities", "qualification", "description"]]
            )
            truncate_style = {"whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}
            gb.configure_column("description", cellStyle=truncate_style, tooltipField="description")
            gb.configure_column("qualification", cellStyle=truncate_style, tooltipField="qualification")
            gb.configure_column("responsibilities", cellStyle=truncate_style, tooltipField="responsibilities")
            gridOptions = gb.build()
            
            AgGrid(final_df, gridOptions=gridOptions, allow_unsafe_jscode=True)
            
            # Create an in-memory Excel file.
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='Job Postings')
            buffer.seek(0)
            
            st.download_button(
                "Download Excel File",
                data=buffer,
                file_name="job_postings.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No job postings found across the provided URLs.")
