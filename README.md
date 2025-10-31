# 🚁 Strategist Drone Simulation

A sophisticated multi-agent simulation where LLM-powered drones explore a grid map, avoid hidden air defense systems, and destroy targets using intelligent pathfinding and risk assessment.


## 🧠 Key Features

### **LLM-Powered Agents**
- **Central Strategist**: GPT-4o controls overall strategy
- **Individual Drones**: Each drone has its own GPT-4o-mini for pathfinding decisions
- **Dynamic Decision Making**: Agents adapt to threats and discoveries

### **Intelligent Pathfinding**
- **3 Strategies**: DIRECT, AVOID_THREATS, CAUTIOUS
- **Threat Avoidance**: Known danger zones influence path planning
- **Fallback Mechanisms**: Safe path → risky path if needed

### **Fog of War System**
- **Progressive Discovery**: Map revealed through drone scanning
- **Hidden Threats**: HSS systems are invisible until triggered
- **Knowledge Sharing**: Central system distributes intelligence

### **Risk Management**
- **Threat Zones**: Areas where drones were destroyed
- **Battery Management**: Low battery forces return to base
- **Sacrifice Strategies**: Risk vs reward calculations

## 🚀 Quick Start

### 🐳 **Docker (Recommended)**
```bash
# 1. Setup environment
cp env.example .env
# Edit .env with your OpenAI API key

# 2. Run with visualization
./docker-run.sh

# 3. Or run headless
./docker-run.sh --headless
```

### 🐍 **Local Python Installation**

#### 1. **Installation**
```bash
pip install -r requirements.txt
```

#### 2. **Configuration**
Create a `.env` file:
```bash
API_KEY=your_openai_api_key_here
```

#### 3. **Run Simulation**
```bash
python main.py
```

#### 4. **Testing Mode**
To run without API calls, set in `.env`:
```bash
MOCK_LLM_RESPONSE=true
```

## 🐳 Docker Deployment

For a fully containerized experience with all dependencies handled automatically:

### **Features**
- ✅ Complete environment isolation
- ✅ X11 forwarding for visualization
- ✅ Persistent logs and data
- ✅ Easy configuration via environment variables
- ✅ Headless mode for servers

### **Quick Commands**
```bash
# Build and run with GUI
docker-compose up --build

# Run headless (no visualization)
docker-compose --profile headless up

# Interactive development
docker-compose run --rm drone-simulation bash
```

📖 **See [DOCKER.md](DOCKER.md) for complete Docker setup guide**

## ⚙️ Configuration

All settings can be configured via environment variables (`.env` file) or by editing `config.py`:

### **Simulation Parameters**
```python
GRID_WIDTH = 100          # Map width
GRID_HEIGHT = 100         # Map height
NUM_DRONES = 10           # Number of drones
NUM_TARGETS = 3           # Targets to destroy
NUM_HSS = 4               # Hidden air defense systems
```

### **LLM Settings**
```python
LLM_MODEL = "gpt-4o"      # Main strategist model
MOCK_LLM_RESPONSE = False # Use real API calls
```

### **Visualization**
```python
ENABLE_VISUALIZATION = True
FPS = 10                  # Simulation speed
```

## 🎮 Controls

- **Close Window**: End simulation
- **Watch**: Drones move autonomously
- **Console**: Strategy decisions and events logged

## 📊 Game Mechanics

### **Mission Objective**
Destroy all 3 hidden targets using 5 missiles while minimizing drone losses.

### **Threats**
- **HSS Systems**: Invisible air defense with circular kill zones (5-8 radius)
- **Obstacles**: Block movement and line-of-sight
- **Battery Depletion**: Drones must return to base to recharge

### **Intelligence Gathering**
- **Scanning**: Reveals 5x5 area around drone
- **Line-of-Sight**: Obstacles block vision
- **Reporting**: Discoveries shared with central command

### **Strategic Elements**
- **Exploration vs Safety**: Risk unknown areas for intelligence
- **Resource Management**: Battery and missile conservation
- **Adaptive Tactics**: Learn from drone losses

## 🔧 Modules

### **`drone_agent.py`**
Individual drone with LLM-powered navigation:
- Intelligent pathfinding with threat avoidance
- Battery and resource management
- Scanning and reporting capabilities

### **`central_strategist.py`**
Master AI controlling overall strategy:
- World model maintenance
- High-level mission planning
- Resource allocation decisions

### **`grid.py`**
Map and environment management:
- Procedural map generation
- Line-of-sight calculations
- Tile state management

### **`simulation_engine.py`**
Core simulation loop:
- Tick-based updates
- Command distribution
- Game state management

### **`visualizer.py`**
Real-time visualization:
- Pygame-based rendering
- Fog of war display
- Threat zone indicators

## 🎯 Strategy Tips

1. **Early Exploration**: Spread drones to cover maximum area
2. **Active Scanning**: Use ACTIVE mode for exploration drones
3. **Threat Learning**: Mark and avoid areas where drones were lost
4. **Battery Management**: Return to base before critical levels
5. **Risk Assessment**: Balance safety vs discovery speed

## 🛠️ Development

### **Adding New Features**
Each module is independent - modify individual components without affecting others.

### **Extending Drone Behavior**
Edit `drone_agent.py` to add new capabilities or decision-making logic.

### **Custom Strategies**
Modify prompts in `central_strategist.py` and `drone_agent.py` for different AI behaviors.

### **Map Variants**
Adjust `grid.py` for different map layouts or obstacle patterns.

## 📈 Performance

- **API Optimization**: Drone LLMs consult every 10 ticks
- **Efficient Pathfinding**: BFS with early termination
- **Selective Reporting**: Reduce unnecessary communication

## 🐛 Troubleshooting

### **API Errors**
- Check `.env` file has valid `API_KEY`
- Verify OpenAI account has credits
- Use `MOCK_LLM_RESPONSE = True` for testing

### **Performance Issues**
- Reduce `FPS` in `config.py`
- Decrease `NUM_DRONES` for simpler simulation
- Disable visualization: `ENABLE_VISUALIZATION = False`

### **Import Errors**
- Install requirements: `pip install -r requirements.txt`
- Check Python version (3.8+ recommended)

## 📝 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
Feel free to modify and extend!

---

**🎮 Have fun watching your AI drones navigate, survive, and complete their mission!** 