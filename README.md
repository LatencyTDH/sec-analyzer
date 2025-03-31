## Running with Docker (Recommended)

This project includes Docker support for easy setup and execution in a containerized environment.

1.  **Install Docker and Docker Compose:** Follow the official installation instructions for your operating system.
2.  **Create `.env` file:** In the project's root directory, create a file named `.env` and add your SEC EDGAR email address:
    ```
    # .env
    SEC_EMAIL=your_real_email@example.com
    ```
    Replace `your_real_email@example.com` with your actual email. This file is ignored by Git (via `.gitignore`).
3.  **Build and Run:** Open a terminal in the project's root directory and run:
    ```bash
    docker compose up --build
    ```
    This command will:
    *   Build the Docker image using the `Dockerfile`.
    *   Start a container based on that image using `docker-compose.yml`.
    *   Mount Docker volumes (`sec_data`, `output_data`) to persist downloaded filings and store results.
    *   Pass your `SEC_EMAIL` from the `.env` file into the container.
    *   Execute the `main.py` script inside the container.

4.  **Accessing Results:** The output CSV file will be stored inside the `output_data` Docker volume. You can copy it out:
    *   Find the container ID (e.g., using `docker ps -a`). Let's say it's `sec_analyzer`.
    *   List files in the output directory: `docker exec sec_analyzer ls /app/output`
    *   Copy the file to your host machine: `docker cp sec_analyzer:/app/output/your_output_file.csv ./` (Replace `your_output_file.csv` with the actual filename).
    Alternatively, you can inspect the volume location (`docker volume inspect output_data`) but copying via `docker cp` is often simpler.

5.  **Stopping:** Press `Ctrl+C` in the terminal where `docker compose up` is running. To remove the container (but keep the volumes), run `docker compose down`. To remove the container *and* the volumes (deleting downloaded filings and results), run `docker compose down -v`.

## Running Natively (Without Docker)

(Keep existing native instructions here, but emphasize the `.env` file method or setting the environment variable directly)

1.  **Prerequisites:** Python 3.8+ and pip installed.
2.  **Clone:** `git clone ...`
3.  **Virtual Env:** `python -m venv venv`, `source venv/bin/activate`
4.  **Install Deps:** `pip install -r requirements.txt`
5.  **Configure Email:**
    *   **Method 1 (Recommended):** Create a `.env` file as described in the Docker section (`echo "SEC_EMAIL=your_email@example.com" > .env`). The script will pick it up if you run it from the same directory. You might need `pip install python-dotenv` and add `from dotenv import load_dotenv; load_dotenv()` at the start of `main.py` for this to work automatically when run natively *or* set the environment variable manually in your terminal: `export SEC_EMAIL="your_email@example.com"` (Linux/macOS) or `set SEC_EMAIL=your_email@example.com` (Windows CMD) or `$env:SEC_EMAIL="your_email@example.com"` (PowerShell) before running the script.
    *   **Method 2 (Old):** Directly modify the `YOUR_EMAIL_ADDRESS = os.getenv(...)` line in `main.py` to hardcode it (not recommended).
6.  **Run:** `python main.py`
7.  **Results:** Output CSV will be in the `output/` directory.