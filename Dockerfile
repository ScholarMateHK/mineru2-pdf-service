# Use the official sglang image
FROM lmsysorg/sglang:v0.4.7-cu124

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install mineru with all dependencies
RUN --mount=type=cache,id=mineru_cache,target=/root/.cache,sharing=locked \
    python3 -m pip install -U 'mineru[full]' fastapi uvicorn \
    opencv-python ultralytics doclayout-yolo rapid-table fast-langdetect \
    -i https://mirrors.aliyun.com/pypi/simple --break-system-packages

# Download models and update the configuration file (using HuggingFace for overseas servers)
RUN --mount=type=cache,id=mineru_cache,target=/root/.cache,sharing=locked \
    mineru-models-download -s huggingface -m vlm && \
    cp -r /root/.cache/huggingface /tmp/huggingface
RUN mkdir -p /root/.cache && \
    mv /tmp/huggingface /root/.cache/huggingface

# Copy application files
COPY api_server.py /app/
COPY start.sh /app/
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 80 8080

# Set environment variables
ENV MINERU_MODEL_SOURCE=local

# Set the entry point to run both services
ENTRYPOINT ["/app/start.sh"]
