FROM python:3.11-slim

# System dependencies + Node.js for ZK proofs
RUN apt-get update && apt-get install -y \
    curl build-essential git libgmp-dev \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .
RUN pip install -e .

# Install snarkjs locally
RUN cd zk && npm install snarkjs

# Data directory
RUN mkdir -p /app/.dronesync_data

# Run as non-root
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["python3", "main.py"]
