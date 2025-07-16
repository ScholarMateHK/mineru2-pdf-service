#!/bin/bash

echo "Starting MinerU VLM PDF Processor..."

# Function to start sglang service
start_sglang() {
    echo "Starting sglang VLM service on port 80..."
    mineru-sglang-server \
        --host 0.0.0.0 \
        --port 80 \
        --mem-fraction-static 0.6 \
        --max-running-requests 8 \
        --schedule-conservativeness 1.5 \
        --watchdog-timeout 600 &
    SGLANG_PID=$!
    echo "SGLang started with PID: $SGLANG_PID"
}

# Function to check if sglang is healthy
check_sglang_health() {
    curl -s http://localhost:80/health > /dev/null 2>&1
    return $?
}

# Function to monitor and restart sglang if needed
monitor_sglang() {
    while true; do
        sleep 30  # Check every 30 seconds
        if ! check_sglang_health; then
            echo "SGLang service is unhealthy, restarting..."
            pkill -f "mineru-sglang-server" || true
            sleep 5
            start_sglang
            sleep 15
            # Wait for service to be ready
            while ! check_sglang_health; do
                echo "Waiting for restarted sglang service..."
                sleep 5
            done
            echo "SGLang service restarted successfully!"
        fi
    done
}

# Start sglang service
start_sglang

# Wait for sglang to start
echo "Waiting for sglang service to initialize..."
sleep 15

# Check if sglang is ready
while ! check_sglang_health; do
    echo "Waiting for sglang service..."
    sleep 5
done

echo "Sglang service is ready!"

# Start monitoring in background
monitor_sglang &
MONITOR_PID=$!
echo "SGLang monitor started with PID: $MONITOR_PID"

# Start FastAPI service
echo "Starting PDF processing API on port 8080..."
cd /app
python3 api_server.py