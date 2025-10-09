# FILE: drone_agent.py
import openai
import json
import random
from collections import deque
from config import *

class DroneAgent:
    """
    Individual unit that moves on the map, collects sensor data, and executes long-term missions.
    It has its own pathfinding and can dynamically replan if it encounters obstacles.
    """
    def __init__(self, drone_id, grid):
        self.id = drone_id
        self.grid = grid
        self.position = {'x': random.randint(1, 9), 'y': random.randint(1, 9)}
        self.battery = DRONE_BATTERY_MAX
        self.status = 'ACTIVE'  # 'ACTIVE', 'RECHARGING', 'DESTROYED'
        
        # Mission and Path Management
        self.current_command = {"command_type": "STANDBY"}
        self.target_position = None  # The ultimate destination given by the strategist
        self.path = []               # The sequence of steps to reach the target

        # Intelligence and Reporting
        self.scan_results = []
        self.scan_mode = 'PASSIVE'  # 'ACTIVE' or 'PASSIVE'
        self.known_tiles = {}       # Drone's personal map of known obstacles/tiles
        self.threat_zones = []      # Known HSS danger zones from strategist

        self.client = openai.OpenAI(api_key=API_KEY)


    def set_command(self, command):
        """Receives a new command from the simulation engine."""
        new_cmd_type = command.get('command_type')
        
        # If the new command is a MOVE command, update the drone's mission goal.
        if new_cmd_type == 'MOVE_DRONE':
            new_target = command.get('target_position')
            # If the target has changed, this constitutes a new mission.
            # Clear the old path to force recalculation.
            if new_target and new_target != self.target_position:
                self.target_position = new_target
                self.path = []
                print(f"{self.id} received new mission: move to {self.target_position}")
        
        # Always update the main command
        self.current_command = command

        # Update scan mode if specified
        if 'scan_mode' in command:
            if self.scan_mode != command['scan_mode']:
                self.scan_mode = command['scan_mode']
                print(f"{self.id} scan mode set to {self.scan_mode}")

        # Update intelligence from the strategist
        if 'known_tiles' in command:
            self.known_tiles.update(command['known_tiles'])
        if 'threat_zones' in command:
            self.threat_zones = command['threat_zones']


    def update(self, current_tick=0):
        """Main update method called every simulation tick."""
        if self.status != 'ACTIVE':
            return
        
        # Process the current mission (move, scan, or standby)
        self.process_mission()
        
        # Check for battery failure
        if self.battery <= 0:
            print(f"CRITICAL: {self.id} battery depleted and destroyed at {self.position}!")
            self.status = 'DESTROYED'


    def process_mission(self):
        """Executes the logic for the drone's current command."""
        cmd_type = self.current_command.get('command_type')

        if cmd_type == 'MOVE_DRONE' and self.target_position:
            self.move()
        elif cmd_type == 'SCAN_AREA':
            self.scan()
        elif cmd_type == 'STANDBY':
            # If at base, recharge. Otherwise, just wait.
            tile = self.grid.get_tile(self.position['x'], self.position['y'])
            if tile and tile.type == 'BASE' and self.battery < DRONE_BATTERY_MAX:
                self.recharge()


    def move(self):
        """
        Continuously moves the drone towards its target_position, one step per tick.
        Handles path calculation and dynamic replanning.
        """
        # Mission Completion Check: If no target, or if we have arrived at the target.
        if not self.target_position or self.position == self.target_position:
            if self.target_position and self.position == self.target_position:
                print(f"SUCCESS: {self.id} reached target {self.target_position}. Mission complete.")
                if self.scan_mode == 'ACTIVE':
                    self.scan()  # Perform a final scan upon arrival.
            
            # Reset mission state and wait for new orders.
            self.target_position = None
            self.path = []
            self.current_command = {'command_type': 'STANDBY'}
            return

        # Path Calculation: If path is empty or invalid, calculate a new one.
        if not self.path or not self._is_path_valid():
            self.path = self._bfs_pathfind_avoid_hss(self.target_position['x'], self.target_position['y'])
            
            # If no path can be found, abort the mission.
            if not self.path:
                print(f"FAILURE: {self.id} could not find a path to {self.target_position}. Aborting mission.")
                self.target_position = None
                self.current_command = {'command_type': 'STANDBY'}
                return
            # print(f"INFO: {self.id} calculated new path to {self.target_position} with {len(self.path)} steps.")

        # Path Execution: If a valid path exists, take the next step.
        if self.path:
            next_pos = self.path.pop(0)
            
            # Dynamic Replanning: Check for unexpected obstacles.
            # This uses the drone's personal 'known_tiles' map.
            if self._is_known_obstacle(next_pos['x'], next_pos['y']):
                print(f"INFO: {self.id} detected obstacle on path at {next_pos}. Recalculating next tick.")
                self.path = [] # Invalidate the path to trigger recalculation on the next tick.
                return

            # Move to the next position.
            self.position = next_pos
            self.battery -= COST_MOVE
            
            # Perform scan if in active mode.
            if self.scan_mode == 'ACTIVE' and random.random() < 0.5: # 50% chance to scan each step
                self.scan()


    def _is_path_valid(self):
        """Checks if the current path is still valid by looking for new obstacles."""
        for pos in self.path:
            if self._is_known_obstacle(pos['x'], pos['y']):
                return False
        return True


    def _bfs_pathfind_avoid_hss(self, target_x, target_y):
        """BFS pathfinding that avoids known HSS danger zones and known obstacles."""
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
                
                # Check grid boundaries
                if not (0 <= next_x < GRID_WIDTH and 0 <= next_y < GRID_HEIGHT):
                    continue
                # Check if already visited
                if (next_x, next_y) in visited:
                    continue
                # Check for known obstacles or HSS zones
                if self._is_known_obstacle(next_x, next_y) or self._is_in_hss_danger_zone(next_x, next_y):
                    continue
                
                visited.add((next_x, next_y))
                queue.append(((next_x, next_y), path + [(next_x, next_y)]))
        return [] # Return empty list if no path is found


    def _is_known_obstacle(self, x, y):
        """Checks drone's personal map for obstacles."""
        tile_data = self.known_tiles.get((x, y))
        return tile_data and tile_data.get('type') == 'OBSTACLE'


    def _is_in_hss_danger_zone(self, x, y):
        """Checks if a position is within any known HSS danger zone."""
        for zone in self.threat_zones:
            if 'hss_location' in zone:
                hss_x, hss_y, hss_radius = zone['hss_location']['x'], zone['hss_location']['y'], zone['radius']
                if (x - hss_x)**2 + (y - hss_y)**2 <= hss_radius**2:
                    return True
        return False


    def scan(self):
        """
        Scans the environment, adds results to scan_results, and updates personal known_tiles.
        The scan_results will be cleared after reporting to the strategist.
        """
        self.battery -= COST_SCAN
        # Get visible tiles from the grid simulation
        visible_tiles = self.grid.get_visible_tiles(self.position['x'], self.position['y'], DRONE_SCAN_RADIUS)
        
        # Process and store scan results for the next report
        for tile in visible_tiles:
            tile_type = 'EMPTY' if tile.type == 'HSS' else tile.type
            tile_data = {"type": tile_type, "position": {"x": tile.x, "y": tile.y}}
            if tile.type == 'STATIONARY_ENEMY':
                tile_data["properties"] = tile.properties
            
            # Add to scan_results to be sent in the report
            self.scan_results.append(tile_data)
            
            # Update the drone's personal knowledge base immediately
            if tile.type == 'OBSTACLE':
                self.known_tiles[(tile.x, tile.y)] = tile_data


    def recharge(self):
        """Recharges the drone's battery when at base."""
        self.battery = min(DRONE_BATTERY_MAX, self.battery + BASE_RECHARGE_RATE)


    def report_to_center(self, moving_enemies=[]):
        """Prepares a report for the central strategist."""
        if self.status == 'DESTROYED':
            return None

        # Base report structure
        report = {
            "drone_id": self.id,
            "status": self.status,
            "position": self.position,
            "battery": round(self.battery, 2),
            "scan_results": self.scan_results, # Send the collected scan results
            "spotted_enemies": []
        }
        
        # Spot nearby moving enemies
        for enemy in moving_enemies:
            if enemy.status == 'ACTIVE':
                dist_sq = (self.position['x'] - enemy.position['x'])**2 + (self.position['y'] - enemy.position['y'])**2
                if dist_sq <= DRONE_SCAN_RADIUS**2:
                    report["spotted_enemies"].append({
                        "id": enemy.id,
                        "position": enemy.position
                    })

        self.battery -= COST_REPORT
        # CRITICAL: Clear scan results after they have been reported.
        self.scan_results = []
        return report