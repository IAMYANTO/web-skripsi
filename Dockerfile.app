
FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libmariadb-dev \
    gcc \
    g++ \
    sshpass \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates/ ./templates/
EXPOSE 5000
CMD ["python", "app.py"]
