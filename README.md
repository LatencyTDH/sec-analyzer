# SEC DEF 14A Meeting Analyzer

This project downloads and analyzes SEC DEF 14A (proxy statement) filings to determine:
1.  If the annual shareholder meeting is scheduled to be held **in-person**.
2.  If the in-person meeting location is in a **user-specified target city** (and optionally state/region).

The analysis focuses on achieving high precision and recall through careful text processing and dynamic pattern matching using regular expressions.

## Features

*   Automated downloading of DEF 14A filings from SEC EDGAR.
*   Handles HTML and TXT filing formats.
*   Extracts relevant text content using `BeautifulSoup`.
*   Uses sophisticated Regular Expressions to identify meeting format (In-Person, Virtual, Hybrid).
*   **Accepts command-line arguments for the target city and state/region.**
*   Dynamically checks for the specified location within the meeting context.
*   Provides confidence levels for the analysis (High, Medium, Low).
*   Outputs results to a CSV file, including snippets for verification.
*   Includes rate limiting for SEC EDGAR.
*   Docker support for easy execution.

## Setup

1.  **Clone the repository:** `git clone ...`
2.  **Install Docker and Docker Compose:** (If using Docker) Follow official instructions.
3.  **Create `.env` file:** In the project root, create `.env` with your SEC email:
    ```
    # .env
    SEC_EMAIL=your_real_email@example.com
    ```
4.  **(Optional) Native Setup:**
    *   Create virtual environment: `python -m venv venv`, `source venv/bin/activate`
    *   Install dependencies: `pip install -r requirements.txt`

## Running the Analysis

### Using Docker (Recommended)

1.  **Build the image (only needed once or after code changes):**
    ```bash
    docker compose build
    ```
2.  **Run the analysis:** Use `docker compose run` to pass arguments to the script. The service name is `analyzer` (as defined in `docker-compose.yml`). Arguments are passed *after* the service name.
    ```bash
    # Example: Analyze for meetings in Chicago, IL for default tickers/dates
    docker compose run --rm analyzer --city "Chicago" --state "IL"

    # Example: Analyze for meetings in Austin, TX for specific tickers & dates
    docker compose run --rm analyzer --city "Austin" --state "TX" --tickers GOOGL TSLA --start-date "2023-06-01"

    # Example: City only (less precise)
    docker compose run --rm analyzer --city "Boston"
    ```
    *   `--rm`: Automatically removes the container after it finishes.
    *   `analyzer`: The name of the service in `docker-compose.yml`.
    *   `--city "City Name"`: **Required.** The target city. Use quotes if the name has spaces.
    *   `--state "State/Region"`: *Optional but recommended.* The target state or region (e.g., "CA", "New York", "Illinois").
    *   `--tickers TICKER1 TICKER2`: Optional. Override default tickers.
    *   `--start-date YYYY-MM-DD`, `--end-date YYYY-MM-DD`: Optional. Override date range.
    *   `--output-file filename.csv`: Optional. Specify the output CSV filename.

3.  **Accessing Results:** The output CSV is saved in the `output_data` volume. Copy it out as described previously (e.g., `docker cp <container_id>:/app/output/your_file.csv ./`). Use `docker ps -a` to find the container ID if you didn't use `--rm`.

### Running Natively (Without Docker)

1.  **Ensure Setup:** Complete the native setup steps (virtual env, `pip install`).
2.  **Set Environment Variable:** Make sure the `SEC_EMAIL` is available (either via the `.env` file and `python-dotenv`, or by exporting it in your terminal: `export SEC_EMAIL="your_email@example.com"`).
3.  **Run the script with arguments:**
    ```bash
    # Example: Analyze for meetings in Palo Alto, CA
    python main.py --city "Palo Alto" --state "CA"

    # Example: Analyze for Redmond, WA for specific tickers
    python main.py --city "Redmond" --state "WA" --tickers MSFT AMZN

    # Example: Specifying output file
    python main.py --city "New York" --state "NY" --output-file ny_meetings_q1_2024.csv --start-date 2024-01-01 --end-date 2024-03-31
    ```
    Refer to the Docker examples above for the available arguments (`--city`, `--state`, `--tickers`, `--start-date`, `--end-date`, `--output-file`).

4.  **Results:** The output CSV file will be in the `output/` directory.

## Accuracy Considerations

*   **Location Specificity:** Providing the `--state` significantly improves accuracy by disambiguating common city names (e.g., Springfield).
*   **Address Formatting:** The `physical_location_context_regex` tries to capture common address formats but might miss unconventional ones. Reviewing snippets is important.
*   **Regex Tuning:** Further tuning in `meeting_analyzer.py` might be needed for specific edge cases or less common city/state representations in filings.