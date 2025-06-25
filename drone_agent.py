# FILE: drone_agent.py
import openai
import json
import random
from collections import deque
from config import *

class DroneAgent:
    """Individual unit that moves on the map and collects sensor data."""
    def __init__(self, drone_id, grid):
        self.id = drone_id
        self.grid = grid
        self.position = {'x': random.randint(1, 9), 'y': random.randint(1, 9)}
        self.battery = DRONE_BATTERY_MAX
        self.status = 'ACTIVE'  # 'ACTIVE', 'RECHARGING', 'DESTROYED'
        self.current_command = {"command_type": "STANDBY"}
        self.scan_results = []
        self.scan_mode = 'PASSIVE'  # 'ACTIVE' or 'PASSIVE'
        self.path = []
        self.known_tiles = {}
        self.threat_zones = []
        self.client = openai.OpenAI(api_key=API_KEY)
        self.last_llm_consultation_tick = 0

    def set_command(self, command):
        self.current_command = command
        if 'scan_mode' in command:
            self.scan_mode = command['scan_mode']
        if 'known_tiles' in command:
            self.known_tiles = command['known_tiles']
        if 'threat_zones' in command:
            self.threat_zones = command['threat_zones']

    def update(self, current_tick=0):
        """Main update method called every tick."""
        if self.status != 'ACTIVE':
            return
        
        self.execute_command()
        
        if self.battery <= 0:
            print(f"WARNING: {self.id} battery depleted and destroyed!")
            self.status = 'DESTROYED'

    def execute_command(self):
        """Processes commands from the center."""
        cmd_type = self.current_command.get('command_type')

        if cmd_type == 'MOVE_DRONE':
            target_pos = self.current_command.get('target_position')
            if target_pos:
                self.move(target_pos)
        elif cmd_type == 'SCAN_AREA':
            self.scan()
        elif cmd_type == 'STANDBY':
            tile = self.grid.get_tile(self.position['x'], self.position['y'])
            if tile.type == 'BASE' and self.battery < DRONE_BATTERY_MAX:
                self.recharge()

    def move(self, target_position):
        """Moves towards target using HSS-aware pathfinding."""
        target_x, target_y = target_position['x'], target_position['y']
        
        if self.position['x'] == target_x and self.position['y'] == target_y:
            self.path = []
            if self.scan_mode == 'ACTIVE':
                self.scan()
            else:
                self.current_command = {"command_type": "STANDBY"}
            return

        if not self.path or not self._is_path_valid():
            self.path = self._bfs_pathfind_avoid_hss(target_x, target_y)
            if not self.path:
                print(f"{self.id} no path found to target ({target_x},{target_y}), waiting.")
                self.current_command = {"command_type": "STANDBY"}
                return

        if self.path:
            next_pos = self.path.pop(0)
            tile = self.grid.get_tile(next_pos['x'], next_pos['y'])
            if tile and tile.type != 'OBSTACLE':
                self.position = next_pos
                self.battery -= COST_MOVE
                if self.scan_mode == 'ACTIVE' and random.random() < 0.3:
                    self.scan()
            else:
                print(f"{self.id} hit unknown obstacle at ({next_pos['x']},{next_pos['y']}), recalculating.")
                self.known_tiles[(next_pos['x'], next_pos['y'])] = {'type': 'OBSTACLE', 'position': next_pos}
                self.path = []

    def _is_path_valid(self):
        """Checks if current path is still valid."""
        for pos in self.path:
            if self._is_known_obstacle(pos['x'], pos['y']):
                return False
        return True

    def _bfs_pathfind_avoid_hss(self, target_x, target_y):
        """BFS pathfinding that avoids known HSS danger zones."""
        start = (self.position['x'], self.position['y'])
        target = (target_x, target_y)
        queue = deque([(start, [])])
        visited = {start}
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        
        while queue:
            (current_x, current_y), path = queue.popleft()
            if (current_x, current_y) == target:
                return [{'x': x, 'y': y} for x, y in path]
            
            for dx, dy in directions:
                next_x, next_y = current_x + dx, current_y + dy
                if not (0 <= next_x < GRID_WIDTH and 0 <= next_y < GRID_HEIGHT) or (next_x, next_y) in visited:
                    continue
                if self._is_known_obstacle(next_x, next_y) or self._is_in_hss_danger_zone(next_x, next_y):
                    continue
                visited.add((next_x, next_y))
                queue.append(((next_x, next_y), path + [(next_x, next_y)]))
        return []

    def _is_known_obstacle(self, x, y):
        """Checks known obstacles (known tiles only)."""
        tile_data = self.known_tiles.get((x, y))
        return tile_data and tile_data.get('type') == 'OBSTACLE'

    def _is_in_hss_danger_zone(self, x, y):
        """Check if position is within any known HSS danger zone."""
        for zone in self.threat_zones:
            if 'hss_location' in zone:
                hss_x, hss_y, hss_radius = zone['hss_location']['x'], zone['hss_location']['y'], zone['radius']
                if (x - hss_x)**2 + (y - hss_y)**2 <= hss_radius**2:
                    return True
        return False

    def scan(self):
        """Scans for static tiles in the environment."""
        self.scan_results = self.grid.get_visible_tiles(
            self.position['x'], self.position['y'], DRONE_SCAN_RADIUS
        )
        self.battery -= COST_SCAN
        print(f"{self.id} scanned area around ({self.position['x']},{self.position['y']}).")
        self.current_command = {"command_type": "STANDBY"}

    def recharge(self):
        self.battery = min(DRONE_BATTERY_MAX, self.battery + BASE_RECHARGE_RATE)

    def report_to_center(self, moving_enemies=[]):
        """Prepares status, tile scan results, and visible moving enemies."""
        if self.status == 'DESTROYED':
            return None

        report = {
            "drone_id": self.id,
            "status": self.status,
            "position": self.position,
            "battery": round(self.battery, 2),
            "scan_results": [],
            "spotted_enemies": []
        }
        
        for tile in self.scan_results:
            tile_type = 'EMPTY' if tile.type == 'HSS' else tile.type
            tile_data = {"type": tile_type, "position": {"x": tile.x, "y": tile.y}}
            if tile.type == 'STATIONARY_ENEMY':
                tile_data["properties"] = tile.properties
            report["scan_results"].append(tile_data)
            self.known_tiles[(tile.x, tile.y)] = tile_data
        
        for enemy in moving_enemies:
            if enemy.status == 'ACTIVE':
                dist_sq = (self.position['x'] - enemy.position['x'])**2 + (self.position['y'] - enemy.position['y'])**2
                if dist_sq <= DRONE_SCAN_RADIUS**2:
                    report["spotted_enemies"].append({
                        "id": enemy.id,
                        "position": enemy.position
                    })

        self.battery -= COST_REPORT
        self.scan_results = []  # Clear tile scan results after reporting
        return report