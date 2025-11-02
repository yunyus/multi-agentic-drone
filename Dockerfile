# Multi-Agentic Drone Simulation Dockerfile
FROM python:3.11-slim

# Install system dependencies for pygame and X11
RUN apt-get update && apt-get install -y \
    # For pygame and graphics
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libfreetype6-dev \
    libportmidi-dev \
    libjpeg-dev \
    python3-dev \
    # For X11 forwarding (visualization)
    x11-apps \
    xauth \
    # General utilities
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for pygame and graphics
ENV SDL_VIDEODRIVER=x11
ENV DISPLAY=:0
ENV XDG_RUNTIME_DIR=/tmp/runtime
ENV HOME=/home/appuser
# Completely disable audio to avoid ALSA/PulseAudio issues
ENV SDL_AUDIODRIVER=dummy
ENV PULSE_RUNTIME_PATH=""
ENV SDL_MIXER_FREQUENCY=22050
ENV SDL_MIXER_SIZE=-16
ENV SDL_MIXER_CHANNELS=2
ENV SDL_MIXER_CHUNKSIZE=1024

# Create app user and directories with proper permissions
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /home/appuser/.cache /home/appuser/.config /tmp/pulse /tmp/runtime && \
    chmod 755 /tmp/pulse /tmp/runtime && \
    chown -R appuser:appuser /app /home/appuser

# Create app directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for logs and simulation data
RUN mkdir -p /app/logs /app/data

# Set permissions (don't switch user - will be handled by docker-compose)
RUN chmod +x /app/main.py

# Default command
CMD ["python", "main.py"]
