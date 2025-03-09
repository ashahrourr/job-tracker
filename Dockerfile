# Use the same base image for production
FROM python:3.12
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
