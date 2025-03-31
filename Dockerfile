# Use a slim Python base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1 # Prevents python from writing .pyc files
ENV PYTHONUNBUFFERED 1       # Ensures logs are sent straight to terminal without buffering

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by some Python packages (like lxml)
# Clean up apt cache afterwards to keep image size down
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin -c "Docker image user" appuser

# Create directories for filings and output and set ownership
# These directories will be mounted over by volumes in docker-compose
RUN mkdir -p /app/sec_filings /app/output \
    && chown -R appuser:appgroup /app/sec_filings \
    && chown -R appuser:appgroup /app/output

# Copy the rest of the application code into the working directory
COPY . .

# Change ownership of the app code to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Command to run the application
CMD ["python", "main.py"]