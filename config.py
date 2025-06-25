# FILE: config.py
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
API_KEY = os.getenv("API_KEY")

# Simulation Settings
GRID_WIDTH = 100
GRID_HEIGHT = 100
NUM_DRONES = 10
NUM_STATIONARY_ENEMIES = 2
NUM_MOVING_ENEMIES = 2
NUM_HSS = 4  # Hidden Air Defense Systems
INITIAL_MISSILES = 5

# LLM Settings
LLM_MODEL = "gpt-4o"
# Set to True to skip API calls and use mock response for testing
MOCK_LLM_RESPONSE = False 

# Drone Settings
DRONE_BATTERY_MAX = 1000.0
DRONE_SCAN_RADIUS = 5
DRONE_SPEED = 1.0 # tiles per tick
COST_MOVE = 1.0
COST_SCAN = 5.0
COST_REPORT = 2.0
BASE_RECHARGE_RATE = 50.0

# Enemy & Missile Settings
MOVING_ENEMY_SPEED = 0.5 # tiles per tick (moves every 2 ticks)
MISSILE_SPEED = 3.0 # tiles per tick

# Visualization Settings (Pygame)
ENABLE_VISUALIZATION = True
CELL_SIZE = 8
FPS = 10  # Controls simulation speed

# Colors
COLOR_BG = (10, 10, 20)
COLOR_GRID = (40, 40, 50)
COLOR_EMPTY = (25, 25, 40)
COLOR_OBSTACLE = (100, 100, 100)
COLOR_BASE = (0, 150, 50, 100)
COLOR_STATIONARY_ENEMY = (255, 0, 0) # Red 'X'
COLOR_MOVING_ENEMY = (255, 165, 0) # Orange triangle
COLOR_HSS = (255, 100, 0)
COLOR_DRONE = (0, 200, 255)
COLOR_DRONE_DESTROYED = (150, 0, 0)
COLOR_SCAN_AREA = (255, 255, 0, 50)
COLOR_KNOWN_WORLD = (0, 0, 255, 30)  # Areas known by strategist
COLOR_HSS_RANGE = (255, 100, 0, 60)
COLOR_MISSILE = (255, 255, 255) # White
COLOR_MISSILE_PATH = (200, 200, 200, 100) # Light grey, transparent

# Calculated values
if ENABLE_VISUALIZATION:
    SCREEN_WIDTH = GRID_WIDTH * CELL_SIZE
    SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE