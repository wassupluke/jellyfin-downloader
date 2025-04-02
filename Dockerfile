# Use an official Python image as base
FROM python:3.13

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .
RUN chmod 777 /media/devmon

# Expose the Flask port
EXPOSE 5000

# Define the command to run the app
CMD ["python", "app.py"]
