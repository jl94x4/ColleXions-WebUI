# Use Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application code into the container
COPY app/ /app/

# Copy requirements file
COPY requirements.txt /app/

# Install required Python packages
RUN pip install -r requirements.txt

# Install and configure supervisord to run multiple processes
RUN apt-get update && apt-get install -y supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose the Flask port
EXPOSE 2000

# Start supervisord to run both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
