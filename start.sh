#!/bin/bash

echo "Starting MinerU VLM PDF Processor..."

# Start sglang service in the background
echo "Starting sglang VLM service on port 80..."
mineru-sglang-server \
    --host 0.0.0.0 \
    --port 80 \
    --mem-fraction-static 0.5 &

# Wait for sglang to start
echo "Waiting for sglang service to initialize..."
sleep 15

# Check if sglang is ready
while ! curl -s http://localhost:80/health > /dev/null; do
    echo "Waiting for sglang service..."
    sleep 5
done

echo "Sglang service is ready!"

# Start FastAPI service
echo "Starting PDF processing API on port 8080..."
cd /app
python3 api_server.py 