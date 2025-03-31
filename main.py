# main.py
import pandas as pd
import os
import logging
import time
from datetime import datetime
import argparse # Import argparse
import sys # Import sys for exit

from sec_downloader import SECDownloader
from text_parser import TextParser
from meeting_analyzer import MeetingAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
YOUR_EMAIL_ADDRESS = os.getenv("SEC_EMAIL")
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "GS", "BLK"]
DEFAULT_START_DATE = "2023-01-01"
DEFAULT_END_DATE = datetime.now().strftime('%Y-%m-%d')
DOWNLOAD_PATH = "sec-edgar-filings" # Relative path inside container/volume
OUTPUT_DIR = "output" # Relative path inside container/volume

# --- Argument Parsing Function ---
def parse_arguments():
    parser = argparse.ArgumentParser(description="Scan SEC DEF 14A filings for annual meeting format and location.")
    # Make city and state not required initially
    parser.add_argument('--city', required=False, default=None, help="Target city name (e.g., 'New York', 'San Francisco').")
    parser.add_argument('--state', required=False, default=None, help="Target state or region (e.g., 'NY', 'California').")
    # --- Add constraint: At least one of city or state must be provided ---
    # This check happens after parsing

    parser.add_argument('--tickers', nargs='+', default=DEFAULT_TICKERS, help=f"Space-separated list of ticker symbols. Default: {' '.join(DEFAULT_TICKERS)}")
    parser.add_argument('--start-date', default=DEFAULT_START_DATE, help=f"Start date for filings (YYYY-MM-DD). Default: {DEFAULT_START_DATE}")
    parser.add_argument('--end-date', default=DEFAULT_END_DATE, help=f"End date for filings (YYYY-MM-DD). Default: today")
    parser.add_argument('--output-file', default=None, help="Optional: Specify output CSV file name. Defaults to including location and timestamp.")

    args = parser.parse_args()

    # --- Validation: Ensure at least city or state is provided ---
    if not args.city and not args.state:
        parser.error("Argument error: At least one of --city or --state must be provided.")
        # parser.error() exits automatically

    return args

# --- Main Execution ---
def main():
    args = parse_arguments() # Parse arguments (includes validation)

    # Validate Email
    if not YOUR_EMAIL_ADDRESS:
        logging.error("CRITICAL: SEC_EMAIL environment variable not set. Please configure it (e.g., in a .env file).")
        sys.exit(1) # Use sys.exit for clearer exit status
    elif "@" not in YOUR_EMAIL_ADDRESS or "." not in YOUR_EMAIL_ADDRESS.split('@')[1]:
         logging.warning(f"SEC_EMAIL ({YOUR_EMAIL_ADDRESS}) does not look like a standard email address. EDGAR might reject requests.")

    log_target = []
    if args.city:
        log_target.append(f"City: '{args.city}'")
    if args.state:
        log_target.append(f"State: '{args.state}'")
    logging.info(f"Starting SEC DEF 14A Analysis for {' and '.join(log_target)}")
    logging.info(f"Tickers: {', '.join(args.tickers)}")
    logging.info(f"Date Range: {args.start_date} to {args.end_date}")

    os.makedirs(OUTPUT_DIR, exist_ok=True) # Ensure output dir exists inside container/volume

    # Generate output file name (handles state-only cases now)
    if args.output_file:
        output_file = os.path.join(OUTPUT_DIR, args.output_file)
    else:
        city_slug = "".join(c if c.isalnum() else "_" for c in args.city.lower()) if args.city else ""
        state_slug = "_" + "".join(c if c.isalnum() else "_" for c in args.state.lower()) if args.state else ""
        location_slug = f"{city_slug}{state_slug}".strip('_') # Combine and remove leading/trailing _
        output_file = os.path.join(OUTPUT_DIR, f"meeting_analysis_{location_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    # Initialize components (Pass both city and state to Analyzer)
    downloader = SECDownloader(download_path=DOWNLOAD_PATH, email_address=YOUR_EMAIL_ADDRESS)
    parser = TextParser()
    analyzer = MeetingAnalyzer(target_city=args.city, target_state=args.state)

    results = []

    for ticker in args.tickers:
        logging.info(f"--- Processing Ticker: {ticker} ---")

        # 1. Download Filings
        try:
            num_downloaded = downloader.download_def14a(ticker, args.start_date, args.end_date)
            if num_downloaded is None:
                logging.warning(f"Skipping {ticker} due to download error.")
                continue
            elif num_downloaded == 0:
                 logging.info(f"No new DEF 14A filings found for {ticker} in the date range.")
            # Rate limit handled by decorator in downloader
            # time.sleep(1.1) # No longer needed here if downloader uses rate limit decorator

        except Exception as e:
            logging.error(f"Critical error during download process for {ticker}: {e}")
            continue # Skip to next ticker

        # 2. Find downloaded filing paths
        ticker_filing_base = os.path.join(DOWNLOAD_PATH, ticker.upper(), "DEF 14A")

        if not os.path.exists(ticker_filing_base):
             logging.warning(f"No downloaded filings directory found for {ticker} at expected path: {ticker_filing_base}. Skipping analysis for this ticker.")
             continue

        # Get accession numbers safely
        try:
            accession_numbers = [d for d in os.listdir(ticker_filing_base) if os.path.isdir(os.path.join(ticker_filing_base, d))]
        except Exception as e:
             logging.error(f"Error listing accession numbers in {ticker_filing_base}: {e}. Skipping {ticker}.")
             continue

        if not accession_numbers:
             logging.info(f"No specific filing subdirectories (accession numbers) found for {ticker} in {ticker_filing_base}")
             continue

        for acc_no in accession_numbers:
            logging.info(f"Analyzing filing: {ticker} - {acc_no}")
            filing_path = downloader.get_filing_path(ticker, acc_no)
            if not filing_path:
                logging.warning(f"Could not find primary document file for {ticker} / {acc_no}. Skipping.")
                continue

            # 3. Parse Text
            text_content = parser.extract_text_from_file(filing_path)
            if not text_content:
                logging.warning(f"Could not parse text from {filing_path}. Skipping analysis.")
                results.append({
                    'Ticker': ticker,
                    'AccessionNo': acc_no,
                    'FilingPath': os.path.basename(filing_path), # Just filename for brevity maybe
                    'MeetingFormat': 'Parse Error',
                    'IsInTargetLocation': None, # Rename key
                    'TargetCity': args.city,
                    'TargetState': args.state,
                    'Confidence': 'Low',
                    'Snippet': 'Failed to extract text.',
                    'AnalysisTimestamp': datetime.now()
                })
                continue

            # 4. Analyze Text
            analysis_result = analyzer.analyze(text_content)

            # 5. Store Result (using updated key name)
            results.append({
                'Ticker': ticker,
                'AccessionNo': acc_no,
                'FilingPath': os.path.basename(filing_path),
                'MeetingFormat': analysis_result['meeting_format'],
                'IsInTargetLocation': analysis_result['is_in_target_location'], # Use new key
                'TargetCity': args.city, # Record what was searched for
                'TargetState': args.state, # Record what was searched for
                'Confidence': analysis_result['confidence'],
                'Snippet': analysis_result['snippet'],
                'AnalysisTimestamp': datetime.now()
            })
            logging.info(f"Analysis result for {ticker}/{acc_no}: Format={analysis_result['meeting_format']}, InTarget={analysis_result['is_in_target_location']}, Confidence={analysis_result['confidence']}")

            time.sleep(0.1) # Small pause between analyses

    # 6. Save Results
    if results:
        results_df = pd.DataFrame(results)
        # Reorder columns with new key
        cols = ['Ticker', 'AccessionNo', 'MeetingFormat', 'IsInTargetLocation', 'TargetCity', 'TargetState', 'Confidence', 'Snippet', 'FilingPath', 'AnalysisTimestamp']
        # Ensure all desired columns exist before reordering
        results_df = results_df.reindex(columns=[c for c in cols if c in results_df.columns])
        results_df.to_csv(output_file, index=False, encoding='utf-8')
        logging.info(f"Analysis complete. Results saved to: {output_file}")
    else:
        logging.info("Analysis complete. No results generated (or no filings found/analyzed).")

if __name__ == "__main__":
    main()
