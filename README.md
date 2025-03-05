# Compensation Aggregator

A robust web application for scraping and aggregating job postings from multiple company websites.

## Features

- **Web Scraping**: Automatically extracts job postings from company websites
- **Data Aggregation**: Combines job data from multiple sources into a unified format
- **Interactive UI**: Streamlit-based interface with filtering and visualization
- **Error Handling**: Robust error recovery and retry mechanisms
- **Fallback Systems**: Multiple extraction methods to ensure reliability
- **Data Export**: Download results as Excel or CSV

## Requirements

- Python 3.8+
- Chrome browser (for Selenium WebDriver)
- OpenAI API key (for enhanced extraction capabilities)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/compensation-aggregator.git
   cd compensation-aggregator
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Download ChromeDriver:
   - Download the appropriate version for your Chrome browser from [ChromeDriver website](https://sites.google.com/chromium.org/driver/)
   - Place the executable in the project root directory

4. Create a `.env` file in the project root with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

1. Start the application:
   ```
   streamlit run main.py
   ```

2. Upload an Excel file with company names and URLs:
   - First column: Company names
   - Second column: URLs to job listing pages

3. Configure scraping parameters in the sidebar:
   - Adjust crawl depth and breadth
   - Set retry attempts
   - Configure timeout settings

4. Click "Scrape sites" to begin the extraction process

5. View and download results:
   - Interactive data grid
   - Statistics visualization
   - Excel/CSV export

## Error Handling

The application includes comprehensive error handling:

- Automatic retries with exponential backoff
- Fallback extraction methods
- Detailed logging
- Graceful degradation when services are unavailable

## Logs

Logs are stored in:
- `app.log` - Main application log
- `logs/` directory - Additional log files

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
