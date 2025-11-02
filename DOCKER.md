# 🐳 Docker Setup Guide

This guide explains how to run the Multi-Agentic Drone Simulation in a Docker container with full support for visualization and all features.

## 🚀 Quick Start

### 1. **Prerequisites**
- Docker and Docker Compose installed
- X11 server running (for visualization on Linux)
- OpenAI API key

### 2. **Setup Environment**
```bash
# Copy environment template
cp env.example .env

# Edit .env file with your OpenAI API key
nano .env
```

### 3. **Run with Visualization**
```bash
# Make script executable
chmod +x docker-run.sh

# Run with GUI
./docker-run.sh
```

### 4. **Run Headless (No GUI)**
```bash
# Run without visualization
./docker-run.sh --headless
```

## 🔧 Configuration Options

### **Environment Variables**
All simulation parameters can be configured via environment variables in the `.env` file:

```bash
# API Configuration
API_KEY=your_openai_api_key_here
MOCK_LLM_RESPONSE=false

# Simulation Settings
GRID_WIDTH=50
GRID_HEIGHT=50
NUM_DRONES=10
NUM_STATIONARY_ENEMIES=2
NUM_MOVING_ENEMIES=2
NUM_HSS=4
INITIAL_MISSILES=5

# Performance
FPS=10
LLM_CALL_FREQUENCY=10

# Visualization
ENABLE_VISUALIZATION=true
CELL_SIZE=16
```

### **Docker Services**

#### **Main Service (with visualization)**
```bash
docker-compose up drone-simulation
```
- Supports pygame GUI
- Requires X11 forwarding
- Full feature set

#### **Headless Service**
```bash
docker-compose --profile headless up drone-simulation-headless
```
- No GUI components
- Runs in background
- Perfect for servers/CI

## 🖥️ Platform-Specific Setup

### **Linux**
```bash
# Enable X11 forwarding
xhost +local:docker

# Run simulation
./docker-run.sh
```

### **macOS**
```bash
# Install XQuartz
brew install --cask xquartz

# Start XQuartz and enable network connections
open -a XQuartz
# In XQuartz preferences: Security → "Allow connections from network clients"

# Set DISPLAY variable
export DISPLAY=host.docker.internal:0

# Run simulation
./docker-run.sh
```

### **Windows (WSL2)**
```bash
# Install VcXsrv or X410
# Configure X server to allow connections

# Set DISPLAY in WSL
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0

# Run simulation
./docker-run.sh
```

## 📁 Volume Mounts

The Docker setup includes several volume mounts:

```yaml
volumes:
  - /tmp/.X11-unix:/tmp/.X11-unix:rw  # X11 socket
  - ./.env:/app/.env:ro               # Environment config
  - ./logs:/app/logs                  # Simulation logs
  - ./data:/app/data                  # Output data
  - ./:/app:ro                        # Source code (development)
```

## 🛠️ Development Mode

For development with live code reloading:

```bash
# Build and run with source mounted
docker-compose up --build drone-simulation

# Or run interactively
docker-compose run --rm drone-simulation bash
```

## 🐛 Troubleshooting

### **Visualization Issues**

**Problem**: Black screen or no window
```bash
# Check X11 permissions
xhost +local:docker
echo $DISPLAY

# Test X11 forwarding
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw alpine sh -c "apk add --no-cache xeyes && xeyes"
```

**Problem**: Permission denied
```bash
# Set correct user permissions
export UID=$(id -u)
export GID=$(id -g)
docker-compose up drone-simulation
```

### **API Issues**

**Problem**: OpenAI API errors
```bash
# Check API key
grep API_KEY .env

# Test with mock mode
echo "MOCK_LLM_RESPONSE=true" >> .env
docker-compose up drone-simulation
```

### **Performance Issues**

**Problem**: Slow simulation
```bash
# Reduce FPS
echo "FPS=5" >> .env

# Reduce grid size
echo "GRID_WIDTH=30" >> .env
echo "GRID_HEIGHT=30" >> .env

# Fewer drones
echo "NUM_DRONES=5" >> .env
```

## 📊 Monitoring

### **View Logs**
```bash
# Real-time logs
docker-compose logs -f drone-simulation

# Simulation logs
tail -f logs/simulation_log.json
```

### **Container Stats**
```bash
# Resource usage
docker stats multi-agentic-drone-sim

# Container info
docker inspect multi-agentic-drone-sim
```

## 🔄 Updates and Maintenance

### **Update Container**
```bash
# Rebuild with latest changes
docker-compose build --no-cache

# Pull latest base images
docker-compose pull
```

### **Clean Up**
```bash
# Remove containers
docker-compose down

# Remove images
docker-compose down --rmi all

# Clean volumes
docker-compose down -v
```

## 🚀 Production Deployment

For production deployment without GUI:

```bash
# Use headless profile
docker-compose --profile headless up -d drone-simulation-headless

# With resource limits
docker-compose --profile headless up -d --scale drone-simulation-headless=1
```

### **Docker Swarm**
```bash
# Deploy to swarm
docker stack deploy -c docker-compose.yml drone-sim
```

### **Kubernetes**
```bash
# Generate Kubernetes manifests
docker-compose config > k8s-manifest.yaml
# Edit and apply to cluster
```

## 📈 Performance Optimization

### **Resource Limits**
Add to docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
    reservations:
      cpus: '1.0'
      memory: 512M
```

### **Multi-Stage Builds**
For smaller production images, consider multi-stage Dockerfile builds.

## 🔐 Security Considerations

- API keys are mounted as read-only volumes
- Container runs with non-root user
- Network access limited to necessary ports
- No privileged mode required

---

**Need help?** Check the main README.md or open an issue on GitHub!
