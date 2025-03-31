import pandas as pd
import os
import logging
import time
from datetime import datetime

from sec_downloader import SECDownloader
from text_parser import TextParser
from meeting_analyzer import MeetingAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Read SEC Email from environment variable (set in .env file for docker-compose)
YOUR_EMAIL_ADDRESS = os.getenv("SEC_EMAIL")
if not YOUR_EMAIL_ADDRESS:
    logging.error("CRITICAL: SEC_EMAIL environment variable not set.")
    # You might want to exit here or raise an error if running outside Docker without it set
    # For simplicity, we'll let the Downloader potentially fail later if it's None,
    # but the docker-compose setup ensures it's set when run via 'docker compose up'.
    # Fallback for running directly without setting ENV var (not recommended):
    # YOUR_EMAIL_ADDRESS = "fallback_email@example.com" # Or raise an exception

# List of tickers to analyze
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "GS", "BLK"] # Example list

# Date range for filings (adjust as needed)
START_DATE = "2023-01-01"
END_DATE = datetime.now().strftime('%Y-%m-%d') # Today

DOWNLOAD_PATH = "sec_filings"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"meeting_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# --- Main Execution ---
def main():
    logging.info("Starting SEC DEF 14A Analysis...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    downloader = SECDownloader(download_path=DOWNLOAD_PATH, email_address=YOUR_EMAIL_ADDRESS)
    parser = TextParser()
    analyzer = MeetingAnalyzer()

    results = []

    for ticker in TICKERS:
        logging.info(f"--- Processing Ticker: {ticker} ---")

        # 1. Download Filings (or ensure they exist)
        try:
            # Check number of filings already downloaded for this run to avoid re-downloading excessively
            # Note: sec-edgar-downloader inherently checks if files exist
            logging.info(f"Checking/Downloading DEF 14A for {ticker}...")
            num_downloaded = downloader.download_def14a(ticker, START_DATE, END_DATE)
            if num_downloaded is None:
                logging.warning(f"Skipping {ticker} due to download error.")
                continue
            elif num_downloaded == 0:
                 logging.info(f"No new DEF 14A filings found for {ticker} in the date range.")
                 # Optional: Still check existing downloaded files if needed
                 # For now, we just proceed assuming the library handled existence checks

            # Give EDGAR a little break between tickers, even with rate limiting per request
            time.sleep(1.1)

        except Exception as e:
            logging.error(f"Critical error during download process for {ticker}: {e}")
            continue # Skip to the next ticker

        # 2. Find downloaded filing paths for the current ticker
        # This requires knowing the structure sec-edgar-downloader uses
        ticker_filing_base = os.path.join(DOWNLOAD_PATH, "sec-edgar-filings", ticker.upper(), "DEF 14A")

        if not os.path.exists(ticker_filing_base):
             logging.warning(f"No downloaded filings directory found for {ticker} at {ticker_filing_base}. Skipping analysis for this ticker.")
             continue

        accession_numbers = [d for d in os.listdir(ticker_filing_base) if os.path.isdir(os.path.join(ticker_filing_base, d))]

        if not accession_numbers:
             logging.info(f"No specific filing subdirectories found for {ticker} in {ticker_filing_base}")
             continue

        for acc_no in accession_numbers:
            logging.info(f"Analyzing filing: {ticker} - {acc_no}")
            filing_path = downloader.get_filing_path(ticker, acc_no)

            if not filing_path:
                logging.warning(f"Could not find primary document for {ticker} / {acc_no}. Skipping.")
                continue

            # 3. Parse Text
            text_content = parser.extract_text_from_file(filing_path)
            if not text_content:
                logging.warning(f"Could not parse text from {filing_path}. Skipping analysis.")
                results.append({
                    'Ticker': ticker,
                    'AccessionNo': acc_no,
                    'FilingPath': filing_path,
                    'MeetingFormat': 'Parse Error',
                    'IsInNYC': None,
                    'Confidence': 'Low',
                    'Snippet': 'Failed to extract text.',
                     'AnalysisTimestamp': datetime.now()
                })
                continue

            # 4. Analyze Text
            analysis_result = analyzer.analyze(text_content)

            # 5. Store Result
            results.append({
                'Ticker': ticker,
                'AccessionNo': acc_no,
                'FilingPath': filing_path, # Good for reference
                'MeetingFormat': analysis_result['meeting_format'],
                'IsInNYC': analysis_result['is_in_nyc'],
                'Confidence': analysis_result['confidence'],
                'Snippet': analysis_result['snippet'], # Crucial for verification!
                'AnalysisTimestamp': datetime.now()
            })
            logging.info(f"Analysis result for {ticker}/{acc_no}: Format={analysis_result['meeting_format']}, NYC={analysis_result['is_in_nyc']}, Confidence={analysis_result['confidence']}")

            # Optional small delay between analyzing files
            time.sleep(0.1)


    # 6. Save Results
    if results:
        results_df = pd.DataFrame(results)
        results_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        logging.info(f"Analysis complete. Results saved to: {OUTPUT_FILE}")
    else:
        logging.info("Analysis complete. No results generated.")

if __name__ == "__main__":
    if not YOUR_EMAIL_ADDRESS:
        logging.error("CRITICAL: SEC_EMAIL environment variable is not set. Please configure it (e.g., in a .env file).")
        # Optionally exit:
        # import sys
        # sys.exit(1)
    else:
        # Optional: Add a check for basic email format if desired
        if "@" not in YOUR_EMAIL_ADDRESS or "." not in YOUR_EMAIL_ADDRESS.split('@')[1]:
             logging.warning(f"SEC_EMAIL ({YOUR_EMAIL_ADDRESS}) does not look like a standard email address. EDGAR might reject requests.")
        main()
