# ---- Builder Stage ----
# Use a Python image that has build tools or makes them easy to install.
# Choose the specific Python version you need (e.g., 3.9, 3.10, 3.11)
FROM python:3.10-slim-bullseye as builder
LABEL stage=builder

# Set working directory
WORKDIR /app

# Install build dependencies IF needed (e.g., for lxml if wheels aren't available)
# Combine steps and clean up apt cache in the same layer
# If your current requirements install without errors on 'slim', you might
# be able to remove the apt-get line entirely. Test this!
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    # Add other build deps here if needed, e.g., libxml2-dev libxslt-dev for lxml
 && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies using pip, disable cache
# Consider using a virtual environment for cleaner separation
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .
# Ensure .dockerignore is properly excluding venv, persistent data, .git etc.


# ---- Final Stage ----
# Use a minimal Python slim image for the runtime
FROM python:3.10-slim-bullseye as final

WORKDIR /app

# Install runtime OS dependencies IF needed (unlikely for this app)
# RUN apt-get update && apt-get install -y --no-install-recommends some-runtime-lib && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /app/venv /app/venv

# Copy only the necessary application python files from the builder stage
COPY --from=builder /app/*.py .

# Add any other .py files or necessary assets your app uses

# Activate the virtual environment
ENV PATH="/app/venv/bin:$PATH"

# Set the entrypoint for the application
ENTRYPOINT ["python", "main.py"]
