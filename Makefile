# Multi-Agentic Drone Simulation - Docker Management
.PHONY: help build run run-headless dev clean logs shell test setup

# Default target
help:
	@echo "🚁 Multi-Agentic Drone Simulation - Docker Commands"
	@echo "=================================================="
	@echo ""
	@echo "Setup:"
	@echo "  setup          - Initial setup (copy env template)"
	@echo "  build          - Build Docker image"
	@echo ""
	@echo "Run:"
	@echo "  run            - Run with visualization"
	@echo "  run-headless   - Run without visualization"
	@echo "  dev            - Run in development mode"
	@echo ""
	@echo "Management:"
	@echo "  logs           - View simulation logs"
	@echo "  shell          - Open interactive shell"
	@echo "  test           - Run in test mode (mock LLM)"
	@echo "  clean          - Clean up containers and images"
	@echo ""
	@echo "Examples:"
	@echo "  make setup && make run"
	@echo "  make test"
	@echo "  make run-headless"

# Setup environment
setup:
	@echo "🔧 Setting up environment..."
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "📝 Created .env file from template"; \
		echo "⚠️  Please edit .env with your OpenAI API key!"; \
	else \
		echo "✅ .env file already exists"; \
	fi
	@mkdir -p logs data
	@chmod +x docker-run.sh
	@echo "✅ Setup complete!"

# Build Docker image
build:
	@echo "🏗️  Building Docker image..."
	@docker-compose build

# Run with visualization
run: setup
	@echo "🎮 Running simulation with visualization..."
	@./docker-run.sh

# Run headless
run-headless: setup
	@echo "🖥️  Running simulation in headless mode..."
	@./docker-run.sh --headless

# Development mode
dev: setup
	@echo "🛠️  Running in development mode..."
	@docker-compose run --rm -v $(PWD):/app drone-simulation

# View logs
logs:
	@echo "📊 Viewing simulation logs..."
	@docker-compose logs -f drone-simulation 2>/dev/null || \
	 docker-compose --profile headless logs -f drone-simulation-headless 2>/dev/null || \
	 echo "No running containers found"

# Interactive shell
shell: setup
	@echo "🐚 Opening interactive shell..."
	@docker-compose run --rm drone-simulation bash

# Test mode (mock LLM)
test: setup
	@echo "🧪 Running in test mode (mock LLM responses)..."
	@MOCK_LLM_RESPONSE=true docker-compose run --rm drone-simulation

# Clean up
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@docker-compose down --rmi all -v --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup complete!"

# Quick test without API
quick-test:
	@echo "⚡ Quick test without API calls..."
	@docker-compose run --rm -e MOCK_LLM_RESPONSE=true -e ENABLE_VISUALIZATION=false drone-simulation

# Show container status
status:
	@echo "📊 Container status:"
	@docker-compose ps

# Show resource usage
stats:
	@echo "📈 Resource usage:"
	@docker stats --no-stream multi-agentic-drone-sim 2>/dev/null || echo "No running containers"
