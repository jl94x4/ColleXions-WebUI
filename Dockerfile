# Use Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the application code into the container
COPY app/ /app/
COPY requirements.txt /app/requirements.txt

# Install required Python packages
RUN pip install -r /app/requirements.txt

# Expose the Flask port
EXPOSE 2000

# Start the Flask application
CMD ["python3", "run.py"]
