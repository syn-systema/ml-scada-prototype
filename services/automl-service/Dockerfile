# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that H2O might need (like Java)
# H2O requires Java Runtime Environment (JRE)
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install curl for health checks in entrypoint
RUN apt-get update && apt-get install -y curl --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Ensure the entrypoint script is executable (redundant with host chmod but good practice)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the default H2O Flow UI port
EXPOSE 54321

# Command to run the application using the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
