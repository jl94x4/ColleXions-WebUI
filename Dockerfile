# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Define container paths (can be overridden at runtime if needed)
    APP_DIR=/app \
    CONFIG_DIR=/app/config \
    LOG_DIR=/app/logs \
    DATA_DIR=/app/data

# Set the working directory in the container
WORKDIR $APP_DIR

# Create directories for config, logs, and data within the container
# These will be the mount points for volumes
RUN mkdir -p $CONFIG_DIR $LOG_DIR $DATA_DIR

# Install system dependencies if any (psutil might need gcc/python-dev sometimes, but slim usually works)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .
# Ensure the script is executable (might not be needed depending on base image)
RUN chmod +x ColleXions.py run.py

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define the command to run the application using Waitress
# This assumes 'app' is the Flask object inside 'run.py'
CMD ["waitress-serve", "--host=0.0.0.0", "--port=2500", "run:app"]