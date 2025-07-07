# Use an official Python image as base
FROM python:3.13

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
RUN apt update && apt install -y ffmpeg && apt clean

# Create a safe cache directory for yt-dlp
RUN mkdir -p /app/cache && chown -R 1000:1000 /app/cache

# Copy Python dependencies and install them
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Expose the Flask port
EXPOSE 5000

# Define the command to run the app
CMD ["python", "app.py"]
