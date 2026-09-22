FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install cron and required system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper.py .
COPY uploader.py .
COPY main.py .
COPY app.py .
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create directories for state files, articles, and logs
RUN mkdir -p /app/articles /app/state /app/logs

# Set timezone to UTC
ENV TZ=UTC

# Expose port for web server
EXPOSE 8000

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
