# Use Python 3.12 slim base image
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Set Chromium path environment variable for PDF & story rendering
ENV CHROMIUM_PATH=/usr/bin/chromium

# Install system dependencies
# Added: chromium (for HTML-to-PDF & viral story generation), tesseract-ocr, libgl1 & libglib (for OpenCV)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    fonts-noto-core \
    fonts-noto-color-emoji \
    fonts-liberation \
    chromium \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# Copy requirements first (for caching)
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 8080

# Run the bot
CMD ["python", "bot.py"]