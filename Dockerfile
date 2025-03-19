FROM python:3.13-slim

# Install Rust
RUN apt-get update && apt-get install -y curl build-essential pkg-config
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set up app directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Command to run the application
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}