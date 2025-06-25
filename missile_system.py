# FILE: missile_system.py
from collections import deque
from config import INITIAL_MISSILES, GRID_WIDTH, GRID_HEIGHT, MISSILE_SPEED

class Missile:
    """Represents a missile in flight."""
    def __init__(self, target_position, path):
        self.path = path
        # Start at the beginning of the path
        self.current_position = path[0].copy() if path else None 
        self.target_position = target_position
        self.status = 'IN_FLIGHT' # 'IN_FLIGHT', 'DETONATED'
        self.speed = int(MISSILE_SPEED) # e.g., 3 tiles per tick

    def update(self):
        """Moves the missile along its path according to its speed."""
        if self.status != 'IN_FLIGHT':
            return
        
        # Move multiple steps per tick based on speed
        for _ in range(self.speed):
            if not self.path:
                self.status = 'DETONATED'
                print(f"Missile reached target coordinates {self.current_position}")
                break
            
            # Move to the next point in the path
            self.current_position = self.path.pop(0)

        # If path is now empty, it means we reached the target this tick
        if not self.path:
            self.status = 'DETONATED'

class MissileSystem:
    """Manages missile inventory and launching."""
    def __init__(self, grid):
        self.missile_count = INITIAL_MISSILES
        self.grid = grid

    def fire(self, target_coord, known_tiles):
        """
        Prepares a missile for launch by calculating a safe path.
        Returns a Missile object if successful, otherwise None.
        """
        if self.missile_count <= 0:
            print("MISSILE_SYSTEM: No missiles left to fire.")
            return None

        # Launch from the center of the base
        launch_site = {'x': 5, 'y': 5}
        
        path = self._find_path_on_known_map(launch_site, target_coord, known_tiles)

        if not path:
            print(f"MISSILE_SYSTEM: No safe path found to {target_coord} based on current intelligence. Aborting launch.")
            return None

        print(f"MISSILE_SYSTEM: Firing missile at {target_coord}. Safe path with {len(path)} steps calculated.")
        self.missile_count -= 1 # Decrement on launch
        return Missile(target_coord, path)

    def _find_path_on_known_map(self, start_pos, target_pos, known_tiles):
        """BFS pathfinding that only uses tiles known by the strategist."""
        start = (start_pos['x'], start_pos['y'])
        target = (target_pos['x'], target_pos['y'])

        if start == target:
            return [start_pos]

        queue = deque([(start, [start_pos])])
        visited = {start}
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]

        while queue:
            (current_x, current_y), path = queue.popleft()

            if (current_x, current_y) == target:
                return path

            for dx, dy in directions:
                next_x, next_y = current_x + dx, current_y + dy

                if not (0 <= next_x < GRID_WIDTH and 0 <= next_y < GRID_HEIGHT):
                    continue

                if (next_x, next_y) in visited:
                    continue

                # Path must only use known, non-obstacle tiles.
                tile_info = known_tiles.get((next_x, next_y))
                if tile_info and tile_info.get('type') == 'OBSTACLE':
                    continue
                
                # If a tile is unknown, missile cannot safely fly through it.
                if (next_x, next_y) not in known_tiles and (next_x, next_y) != target:
                    continue
                
                visited.add((next_x, next_y))
                new_path = path + [{'x': next_x, 'y': next_y}]
                queue.append(((next_x, next_y), new_path))
        
        return [] # No path found