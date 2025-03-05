import streamlit as st
import pandas as pd
from scrape import scrape_website  # Import the individual scrape function
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import time
import logging
import traceback
import os
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Set page configuration
st.set_page_config(
    page_title="Compensation Aggregator",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Compensation Aggregator")
st.markdown("Upload an Excel file with company names and URLs to scrape job postings.")

# Sidebar for configuration options
with st.sidebar:
    st.header("Configuration")
    headless_mode = st.checkbox("Run Chrome in headless mode", value=True)
    max_depth = st.slider("Maximum crawl depth", min_value=1, max_value=10, value=4)
    max_breadth = st.slider("Maximum links per page", min_value=5, max_value=30, value=17)
    retry_count = st.slider("Retry attempts for failed scrapes", min_value=1, max_value=5, value=2)
    
    # Advanced options collapsible section
    with st.expander("Advanced Options"):
        timeout_seconds = st.slider("Page load timeout (seconds)", min_value=10, max_value=300, value=60)
        show_logs = st.checkbox("Show logs in UI", value=False)

# Upload the Excel file (first column: company names, second column: URLs)
uploaded_file = st.file_uploader("Upload Excel file containing company names and URLs", type=["xlsx", "xls"])

# Display log viewer if enabled
if show_logs and os.path.exists("app.log"):
    with st.expander("Application Logs"):
        try:
            with open("app.log", "r") as log_file:
                st.code(log_file.read(), language="text")
        except Exception as e:
            st.error(f"Error reading log file: {str(e)}")

def validate_excel_format(df: pd.DataFrame) -> bool:
    """Validate that the uploaded Excel file has the correct format."""
    if df.empty:
        return False
    
    # Check if we have at least two columns
    if df.shape[1] < 2:
        return False
    
    # Check if first column contains company names (non-empty strings)
    if df.iloc[:, 0].isna().any() or not all(isinstance(x, str) for x in df.iloc[:, 0].dropna()):
        return False
    
    # Check if second column contains URLs (non-empty strings)
    if df.iloc[:, 1].isna().any() or not all(isinstance(x, str) for x in df.iloc[:, 1].dropna()):
        return False
    
    return True

def safe_scrape_website(company_name: str, url: str, max_depth: int, max_breadth: int, 
                        headless: bool, retry_count: int, timeout: int) -> Optional[pd.DataFrame]:
    """Safely scrape a website with retry logic and error handling."""
    progress_text = st.empty()
    progress_text.markdown(f"Scraping jobs for **{company_name}** from URL: {url}")
    
    for attempt in range(retry_count):
        try:
            logger.info(f"Scraping {company_name} from {url} (Attempt {attempt+1}/{retry_count})")
            df = scrape_website(
                url, 
                max_depth=max_depth, 
                max_breadth=max_breadth, 
                headless=headless,
                timeout=timeout
            )
            
            if not df.empty:
                logger.info(f"Successfully scraped {len(df)} job postings from {company_name}")
                # Insert a new column at the beginning for the company name
                df.insert(0, "company", company_name)
                return df
            else:
                logger.warning(f"No job postings found for {company_name} on attempt {attempt+1}")
                if attempt < retry_count - 1:
                    progress_text.markdown(f"No results found for **{company_name}**, retrying... ({attempt+1}/{retry_count})")
                    time.sleep(2)  # Wait before retrying
        except Exception as e:
            logger.error(f"Error scraping {company_name}: {str(e)}")
            logger.debug(traceback.format_exc())
            if attempt < retry_count - 1:
                progress_text.markdown(f"Error scraping **{company_name}**, retrying... ({attempt+1}/{retry_count})")
                time.sleep(2)  # Wait before retrying
    
    progress_text.markdown(f"Failed to scrape **{company_name}** after {retry_count} attempts")
    return None

if uploaded_file is not None:
    try:
        # Read the uploaded Excel file
        url_df = pd.read_excel(uploaded_file)
        
        # Validate the Excel format
        if not validate_excel_format(url_df):
            st.error("Invalid Excel format. Please ensure the file has at least two columns: company names and URLs.")
        else:
            st.markdown(f"**Found {len(url_df)} companies in the uploaded file.**")
            
            if st.button("Scrape sites"):
                # Create a progress bar
                progress_bar = st.progress(0)
                status_container = st.container()
                
                with status_container:
                    st.markdown("**Scraping sites... Please wait.**")
                
                # Start timer
                start_time = time.time()
                
                all_dfs = []  # List to hold DataFrames from each company
                failed_companies = []  # Track failed scrapes
                
                # Iterate over each row to get company name and URL
                for index, row in url_df.iterrows():
                    try:
                        company_name = row.iloc[0]  # Company name in the first column
                        url = row.iloc[1]           # URL in the second column
                        
                        # Update progress
                        progress_percent = (index + 1) / len(url_df)
                        progress_bar.progress(progress_percent)
                        
                        # Call the scraping function for this URL with retry logic
                        df = safe_scrape_website(
                            company_name, 
                            url, 
                            max_depth=max_depth, 
                            max_breadth=max_breadth, 
                            headless=headless_mode,
                            retry_count=retry_count,
                            timeout=timeout_seconds
                        )
                        
                        if df is not None and not df.empty:
                            all_dfs.append(df)
                        else:
                            failed_companies.append(company_name)
                            with status_container:
                                st.warning(f"No job postings found for {company_name}.")
                    except Exception as e:
                        logger.error(f"Unexpected error processing {row.iloc[0]}: {str(e)}")
                        logger.debug(traceback.format_exc())
                        failed_companies.append(row.iloc[0])
                        with status_container:
                            st.error(f"Error processing {row.iloc[0]}: {str(e)}")
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        logger.error(f"Excel file error: {str(e)}")
        logger.debug(traceback.format_exc())

    # Process results - this block should NOT be indented under the except block
    if 'all_dfs' in locals() and all_dfs:
        try:
            final_df = pd.concat(all_dfs, ignore_index=True)
            
            # Complete the progress bar
            if 'progress_bar' in locals():
                progress_bar.progress(1.0)
            
            with status_container:
                st.success(f"**Scraping complete! Found {len(final_df)} job postings across {len(all_dfs)} companies.**")
                
                # Report on failed companies
                if failed_companies:
                    st.warning(f"Failed to scrape {len(failed_companies)} companies: {', '.join(failed_companies)}")
                
                # Stop timer and calculate elapsed time
                elapsed_time = time.time() - start_time
                st.markdown(f"**Time taken:** {elapsed_time:.2f} seconds")
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["Data Grid", "Statistics"])
            
            with tab1:
                # Set up AgGrid options for display
                try:
                    gb = GridOptionsBuilder.from_dataframe(
                        final_df[["company", "title", "location", "salary_range", "responsibilities", "qualification", "description"]]
                    )
                    truncate_style = {"whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}
                    gb.configure_column("description", cellStyle=truncate_style, tooltipField="description")
                    gb.configure_column("qualification", cellStyle=truncate_style, tooltipField="qualification")
                    gb.configure_column("responsibilities", cellStyle=truncate_style, tooltipField="responsibilities")
                    gridOptions = gb.build()
                    
                    AgGrid(final_df, gridOptions=gridOptions, allow_unsafe_jscode=True)
                except Exception as e:
                    st.error(f"Error displaying data grid: {str(e)}")
                    st.dataframe(final_df)  # Fallback to standard dataframe
            
            with tab2:
                # Display some statistics about the data
                st.subheader("Job Posting Statistics")
                
                # Company distribution
                st.write("Job postings by company:")
                company_counts = final_df["company"].value_counts()
                st.bar_chart(company_counts)
                
                # Location distribution (top 10)
                if "location" in final_df.columns:
                    st.write("Top 10 locations:")
                    location_counts = final_df["location"].value_counts().head(10)
                    st.bar_chart(location_counts)
            
            # Create an in-memory Excel file
            try:
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
            except Exception as e:
                st.error(f"Error creating Excel file: {str(e)}")
                logger.error(f"Excel creation error: {str(e)}")
                
                # Fallback to CSV
                csv_buffer = io.StringIO()
                final_df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                
                st.download_button(
                    "Download CSV File (Excel generation failed)",
                    data=csv_buffer.getvalue(),
                    file_name="job_postings.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"Error processing results: {str(e)}")
            logger.error(f"Results processing error: {str(e)}")
            logger.debug(traceback.format_exc())
    elif 'all_dfs' in locals():
        with status_container:
            st.warning("No job postings found across the provided URLs.")
            logger.warning("No job postings found across any companies")
