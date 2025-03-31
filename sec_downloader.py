import os
from sec_edgar_downloader import Downloader
from ratelimit import limits, sleep_and_retry
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SEC EDGAR allows 10 requests per second. Let's be safe.
CALLS = 9
RATE_LIMIT = 1 # Second

class SECDownloader:
    """Handles downloading DEF 14A filings from SEC EDGAR."""

    def __init__(self, download_path="sec_filings", email_address="your_email@example.com"):
        """
        Initializes the downloader.

        Args:
            download_path (str): Directory to save downloaded filings.
            email_address (str): Your email address (required by EDGAR).
                                PLEASE REPLACE with your actual email.
        """
        if email_address == "your_email@example.com":
            logging.warning("Please replace 'your_email@example.com' with your actual email address in sec_downloader.py")
        self.download_path = download_path
        self.dl = Downloader(self.download_path, email_address)
        os.makedirs(self.download_path, exist_ok=True)
        logging.info(f"SEC Downloader initialized. Files will be saved to: {self.download_path}")

    # Apply rate limiting to the download method
    @sleep_and_retry
    @limits(calls=CALLS, period=RATE_LIMIT)
    def download_def14a(self, ticker, start_date, end_date):
        """
        Downloads DEF 14A filings for a given ticker within a date range.

        Args:
            ticker (str): Company ticker symbol.
            start_date (str): Start date in YYYY-MM-DD format.
            end_date (str): End date in YYYY-MM-DD format.

        Returns:
            int: Number of filings downloaded, or None if error.
        """
        try:
            logging.info(f"Attempting to download DEF 14A for {ticker} ({start_date} to {end_date})")
            num_downloaded = self.dl.get("DEF 14A", ticker, after=start_date, before=end_date)
            logging.info(f"Downloaded {num_downloaded} DEF 14A filings for {ticker}.")
            return num_downloaded
        except Exception as e:
            logging.error(f"Error downloading filings for {ticker}: {e}")
            # Consider more specific exception handling (NetworkError, etc.)
            return None

    def get_filing_path(self, ticker, accession_number_no_dashes):
        """
        Constructs the expected path to a downloaded filing file.
        Note: sec-edgar-downloader creates a specific directory structure.

        Args:
            ticker (str): Company ticker symbol.
            accession_number_no_dashes (str): Accession number without dashes.

        Returns:
            str: The full path to the filing text file, or None if not found.
        """
        # Structure: download_path/sec-edgar-filings/TICKER/DEF 14A/accession_number/full-submission.txt
        # Or sometimes the primary document is an HTML file directly
        base_path = os.path.join(self.download_path, "sec-edgar-filings", ticker.upper(), "DEF 14A", accession_number_no_dashes)

        # Prioritize the primary document if it exists (often more relevant than full-submission)
        # Heuristic: Look for .htm or .html files first
        primary_doc_html = None
        primary_doc_txt = None

        if os.path.exists(base_path):
            for filename in os.listdir(base_path):
                 # Primary documents often don't have standard names, might just be .htm/.html
                 # Exclude 'filing-details.xml' etc.
                if filename.lower().endswith(('.htm', '.html')) and 'filing-details' not in filename:
                    primary_doc_html = os.path.join(base_path, filename)
                    break # Assume the first HTML is the primary proxy doc
                elif filename.lower().endswith('.txt') and filename != 'full-submission.txt':
                     primary_doc_txt = os.path.join(base_path, filename)
                     # Don't break yet, prefer HTML if found

        if primary_doc_html:
             logging.debug(f"Found primary HTML doc: {primary_doc_html}")
             return primary_doc_html
        elif primary_doc_txt:
             logging.debug(f"Found primary TXT doc: {primary_doc_txt}")
             return primary_doc_txt

        # Fallback to full-submission.txt if no other primary doc found
        full_submission_path = os.path.join(base_path, "full-submission.txt")
        if os.path.exists(full_submission_path):
            logging.debug(f"Using full-submission.txt: {full_submission_path}")
            return full_submission_path

        logging.warning(f"Could not find a suitable filing file in path: {base_path}")
        return None
