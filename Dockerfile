# Use an official Python image as base
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
RUN apt update && apt install -y ffmpeg curl && apt clean

# Create a safe cache directory for yt-dlp
RUN mkdir -p /app/cache && chown -R 1000:1000 /app/cache

# Copy Python dependencies and install them
COPY requirements.txt ./
RUN pip install -U --no-cache-dir -r requirements.txt

# Copy autodownloader script
#COPY autodownloader.sh /app/autodownloader.sh
#RUN chmod +x /app/autodownloader.sh

# Copy the rest of the application files
COPY . .

# Expose the Flask port
EXPOSE 5000

# Define the command to run the app
CMD ["python", "app.py"]
