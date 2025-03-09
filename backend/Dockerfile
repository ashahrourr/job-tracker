# 🔹 Build stage
FROM python:3.12 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# ✅ Create virtual environment
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# ✅ Install dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 🔹 Production stage (smaller image)
FROM python:3.12-slim
WORKDIR /app

# ✅ Copy virtual environment & application code
COPY --from=builder /opt/venv /opt/venv/
COPY . .

# ✅ Ensure Uvicorn is executable
RUN chmod +x /opt/venv/bin/uvicorn

# ✅ Set the virtual environment as default
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# ✅ Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
